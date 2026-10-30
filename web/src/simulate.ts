// Run a compiled circuit on the exact WASM core: shot sampling, noise
// trajectories, mid-circuit measurement and the result summary.

import { isTerminalOnly, matrix, type Op } from "./circuit";
import { bitsOf, rng, type Core } from "./core";
import type { Noise, RunResult } from "./protocol";

const PAULI = [matrix("x"), matrix("y"), matrix("z")];
const EXACT_LIMIT = 22; // above this the 2^n probability table is not built
/** Amplitude updates allowed for noise trajectories (keeps runs in seconds). */
const TRAJECTORY_BUDGET = 4e8;

/**
 * Trajectories for a noisy run: one per shot (statistically exact) when that is
 * cheap, otherwise as many as the budget allows, never fewer than 256.
 */
export function trajectoryCount(shots: number, gateOps: number, numQubits: number): number {
  const perTrajectory = Math.max(1, gateOps + 1) * 2 ** numQubits;
  return Math.min(shots, Math.max(256, Math.floor(TRAJECTORY_BUDGET / perTrajectory)));
}

export interface RunInput {
  numQubits: number;
  numClbits: number;
  ops: Op[];
  shots: number;
  seed: number;
  noise: Noise;
}

type Progress = (fraction: number, label: string) => void;

/** Map each measured qubit to its classical bit; with no measure, measure all qubits. */
export function measurementMap(input: RunInput): { pairs: [number, number][]; width: number } {
  const pairs: [number, number][] = [];
  for (const op of input.ops) if (op.kind === "measure") pairs.push([op.qubit, op.clbit]);
  if (pairs.length === 0) {
    for (let q = 0; q < input.numQubits; q++) pairs.push([q, q]);
    return { pairs, width: input.numQubits };
  }
  const width = Math.max(input.numClbits, ...pairs.map(([, c]) => c + 1));
  return { pairs, width };
}

function gateNoise(noise: Noise) {
  return noise.p1 > 0 || noise.p2 > 0 || (noise.xflip ?? []).some((v) => v > 0);
}

/** Readout error for qubit q: [P(read 1 | 0), P(read 0 | 1)]. */
export function readoutPair(noise: Noise, q: number): [number, number] {
  const p01 = noise.p01?.[q] ?? noise.readout;
  const p10 = noise.p10?.[q] ?? noise.readout;
  return [p01, p10];
}

function applyWithNoise(core: Core, op: Extract<Op, { kind: "u" }>, noise: Noise, r: () => number) {
  core.apply(op.target, op.ctrl, op.m);
  const controls: number[] = [];
  for (let q = 0; q < 31; q++) if (op.ctrl & (1 << q)) controls.push(q);
  if (op.arity === 1) {
    // Single-qubit depolarizing: with probability p the state is replaced by I/2,
    // i.e. one of I, X, Y, Z uniformly.
    if (noise.p1 > 0 && r() < noise.p1) {
      const k = Math.floor(r() * 4);
      if (k > 0) core.apply(op.target, 0, PAULI[k - 1]);
    }
    const flip = op.gate === "x" ? noise.xflip?.[op.target] ?? 0 : 0;
    if (flip > 0 && r() < flip) core.apply(op.target, 0, PAULI[0]);
  } else if (op.arity === 2) {
    // Two-qubit depolarizing (1-p) rho + p I/4: with probability p apply a uniformly
    // random two-qubit Pauli (16 including identity), exactly as the Python channel.
    if (noise.p2 > 0 && r() < noise.p2) {
      const k = Math.floor(r() * 16);
      const a = k >> 2, b = k & 3;
      if (a > 0) core.apply(controls[0], 0, PAULI[a - 1]);
      if (b > 0) core.apply(op.target, 0, PAULI[b - 1]);
    }
  } else if (noise.p2 > 0) {
    for (const q of [...controls, op.target]) {
      if (r() < noise.p2) {
        const k = Math.floor(r() * 4);
        if (k > 0) core.apply(q, 0, PAULI[k - 1]);
      }
    }
  }
}

export function run(core: Core, input: RunInput, progress: Progress = () => {}): Omit<RunResult, "id" | "engine"> {
  const started = performance.now();
  const n = input.numQubits;
  const { pairs, width } = measurementMap(input);
  const r = rng(input.seed);
  const counts: Record<string, number> = {};
  const add = (bits: string, k = 1) => { counts[bits] = (counts[bits] ?? 0) + k; };
  const hasReadout = input.noise.readout > 0 || (input.noise.p01 ?? []).some((v) => v > 0) || (input.noise.p10 ?? []).some((v) => v > 0);
  /** Apply the measured qubit's readout error to one classical bit value. */
  const misread = (bit: number, qubit: number) => {
    if (!hasReadout) return bit;
    const [p01, p10] = readoutPair(input.noise, qubit);
    return r() < (bit ? p10 : p01) ? bit ^ 1 : bit;
  };
  const terminal = isTerminalOnly(input.ops);
  const unitary = input.ops.filter((o) => o.kind === "u") as Extract<Op, { kind: "u" }>[];

  if (!core.init(n)) throw new Error(`Speicher für ${n} Qubits konnte nicht reserviert werden`);

  // 1) The noiseless final state: exact probabilities, amplitudes, Bloch vectors.
  progress(0, "Zustandsvektor");
  const chunk = Math.max(1, Math.floor(unitary.length / 20));
  unitary.forEach((op, k) => {
    core.apply(op.target, op.ctrl, op.m);
    if (k % chunk === 0) progress((0.6 * k) / unitary.length, "Gatter anwenden");
  });
  const norm = core.norm();
  const exact: RunResult["exact"] = [];
  const amplitudes: RunResult["amplitudes"] = [];
  if (n <= EXACT_LIMIT) {
    const probs = core.probabilities();
    const order = Array.from(probs.keys()).filter((i) => probs[i] > 1e-12);
    order.sort((a, b) => probs[b] - probs[a]);
    for (const i of order.slice(0, 64)) exact.push({ bits: bitsOf(i, n), p: probs[i] });
  }
  if (n <= 6) {
    const amp = core.amplitudes();
    for (let i = 0; i < 2 ** n; i++) amplitudes.push({ bits: bitsOf(i, n), re: amp[2 * i], im: amp[2 * i + 1] });
  }
  const bloch = Array.from({ length: Math.min(n, 16) }, (_, q) => core.bloch(q));

  // 2) Shots.
  let mode: RunResult["mode"] = "sampled";
  let trajectories = 1;
  const toClassical = (index: number) => {
    let v = 0;
    for (const [q, c] of pairs) {
      if (misread((index >>> q) & 1, q)) v |= 1 << c; else v &= ~(1 << c);
    }
    return v;
  };
  if (terminal && !gateNoise(input.noise)) {
    progress(0.7, "Shots ziehen");
    const samples = core.sample(input.shots, input.seed);
    const tally = new Map<number, number>();
    for (const s of samples) {
      const v = toClassical(s);
      tally.set(v, (tally.get(v) ?? 0) + 1);
    }
    for (const [v, k] of tally) add(bitsOf(v, width), k);
  } else {
    // Monte-Carlo trajectories: every trajectory replays the circuit with its own
    // random Pauli errors and mid-circuit outcomes; the shot mixture is unbiased.
    mode = "trajectories";
    const perShot = !terminal;
    trajectories = perShot ? input.shots : trajectoryCount(input.shots, unitary.length, n);
    const base = Math.floor(input.shots / trajectories);
    let extra = input.shots - base * trajectories;
    for (let t = 0; t < trajectories; t++) {
      const shotsHere = base + (extra-- > 0 ? 1 : 0);
      core.reset();
      let classical = 0;
      for (const op of input.ops) {
        if (op.kind === "u") applyWithNoise(core, op, input.noise, r);
        else if (op.kind === "reset") {
          if (core.measure(op.qubit, r()) === 1) core.apply(op.qubit, 0, PAULI[0]);
        } else if (perShot) {
          const bit = misread(core.measure(op.qubit, r()), op.qubit);
          classical = bit ? classical | (1 << op.clbit) : classical & ~(1 << op.clbit);
        }
      }
      if (perShot) {
        // Qubits never measured are reported through the default map only when
        // the circuit has no measurement at all, which is the terminal case.
        add(bitsOf(classical, width), shotsHere);
      } else {
        for (const s of core.sample(shotsHere, input.seed + t + 1)) add(bitsOf(toClassical(s), width));
      }
      if (t % Math.max(1, Math.floor(trajectories / 50)) === 0) {
        progress(0.7 + (0.3 * t) / trajectories, `Trajektorie ${t + 1}/${trajectories}`);
      }
    }
  }
  progress(1, "fertig");
  return {
    numQubits: n,
    shots: input.shots,
    counts,
    exact,
    amplitudes,
    bloch,
    norm,
    elapsedMs: performance.now() - started,
    mode,
    trajectories,
  };
}
