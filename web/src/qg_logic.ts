// Quantum Gravity Lab: pure logic (no DOM). Everything here is testable under node.
//
// Scope: a finite two-qubit effective-phase toy model (BMV-type). It is NOT a measurement of
// gravity, and theta is a model parameter, not a physical mass or separation.
import snapshot from "./qg_snapshot.json";

export const THETA_RANGE = 100; // same bound as the Studio API (|value| <= 100)

export type Snapshot = typeof snapshot;
export const SNAPSHOT: Snapshot = snapshot;

export interface BmvParams { theta: number; phaseA: number; phaseB: number }

export interface BmvResult {
  surface: "WEB_WASM_F64_JS"; // browser JS double precision; not the Python reference
  precision: "f64";
  probabilities: Record<string, number>;
  concurrence: number;
  negativity: number;
  entropyBits: number;
  chshMax: number;
  entanglingPhase: number;
}

/** Parse a number the user typed ("0.5", "-1e-3", "pi/4", "3pi/8"); null if not finite or out of range. */
export function parseBounded(text: string, low = -THETA_RANGE, high = THETA_RANGE): number | null {
  const s = text.trim().toLowerCase().replace(",", ".").replace(/\s+/g, "");
  if (s === "") return null;
  let value: number;
  if (/^-?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/.test(s)) {
    value = Number(s);
  } else {
    const f = /^(-?)((?:\d+\.?\d*|\.\d+)?)\*?pi(?:\/((?:\d+\.?\d*|\.\d+)))?$/.exec(s);
    if (!f) return null;
    const k = f[2] === "" ? 1 : Number(f[2]);
    const d = f[3] === undefined ? 1 : Number(f[3]);
    if (!(d > 0)) return null;
    value = (f[1] === "-" ? -1 : 1) * k * Math.PI / d;
  }
  if (!Number.isFinite(value) || value < low || value > high) return null;
  return value;
}

/** Exact two-qubit state of Rz(b) Rz(a) exp(-i theta/2 ZZ) |+>|+>, amplitudes [re, im] for 00,01,10,11. */
export function bmvState(p: BmvParams): [number, number][] {
  const out: [number, number][] = [];
  for (let idx = 0; idx < 4; idx++) {
    const sx = (idx >> 1) & 1 ? -1 : 1; // q0 is the most significant bit
    const sy = idx & 1 ? -1 : 1;
    const phase = -0.5 * (p.theta * sx * sy + p.phaseA * sx + p.phaseB * sy);
    out.push([0.5 * Math.cos(phase), 0.5 * Math.sin(phase)]);
  }
  return out;
}

const mul = (a: [number, number], b: [number, number]): [number, number] => [a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]];
const conj = (a: [number, number]): [number, number] => [a[0], -a[1]];
const xlog2x = (x: number) => (x <= 1e-300 ? 0 : x * Math.log2(x));

export function runBmv(p: BmvParams): BmvResult {
  const c = bmvState(p);
  const probs: Record<string, number> = {};
  c.forEach((a, i) => { probs[i.toString(2).padStart(2, "0")] = a[0] * a[0] + a[1] * a[1]; });
  const prodA = mul(c[0], c[3]);
  const prodB = mul(c[1], c[2]);
  const concurrence = 2 * Math.hypot(prodA[0] - prodB[0], prodA[1] - prodB[1]);
  // reduced state of q0: rho01 = sum_y c[0y] conj(c[1y])
  const r01a = mul(c[0], conj(c[2]));
  const r01b = mul(c[1], conj(c[3]));
  const off = Math.hypot(r01a[0] + r01b[0], r01a[1] + r01b[1]);
  const lam1 = 0.5 + off;
  const lam2 = 0.5 - off;
  const inv = mul(prodA, conj(prodB)); // c00 c11 conj(c01 c10)
  return {
    surface: "WEB_WASM_F64_JS",
    precision: "f64",
    probabilities: probs,
    concurrence,
    negativity: concurrence / 2,
    entropyBits: -(xlog2x(lam1) + xlog2x(lam2)),
    chshMax: 2 * Math.sqrt(1 + concurrence * concurrence),
    entanglingPhase: Math.atan2(inv[1], inv[0]),
  };
}

/** Python-style `format(x, ".17g")`, so the QASM bytes (and their digest) match the Python reference. */
export function formatG17(x: number): string {
  if (x === 0) return Object.is(x, -0) ? "-0" : "0";
  const [mant, ex] = x.toExponential(16).split("e");
  const e = Number(ex);
  if (e < -4 || e >= 17) {
    const m = mant.replace(/0+$/, "").replace(/\.$/, "");
    return `${m}e${e < 0 ? "-" : "+"}${String(Math.abs(e)).padStart(2, "0")}`;
  }
  const s = x.toPrecision(17); // fixed notation for -4 <= e < 17
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
}

export function bmvQasm(p: BmvParams): string {
  return [
    "OPENQASM 2.0;",
    'include "qelib1.inc";',
    "qreg q[2];",
    "creg c[2];",
    "h q[0];",
    "h q[1];",
    "cx q[0],q[1];",
    `rz(${formatG17(p.theta)}) q[1];`,
    "cx q[0],q[1];",
    `rz(${formatG17(p.phaseA)}) q[0];`,
    `rz(${formatG17(p.phaseB)}) q[1];`,
    "measure q -> c;",
  ].join("\n") + "\n";
}

export interface CircuitStats { width: number; gates: number; depth: number; counts: Record<string, number> }

/** Gate counts and depth of the generated QASM (each gate line counted; measurement excluded from depth bookkeeping separately). */
export function qasmStats(qasm: string): CircuitStats {
  const level = [0, 0];
  const counts: Record<string, number> = {};
  let gates = 0;
  for (const raw of qasm.split("\n")) {
    const m = /^(\w+)(?:\([^)]*\))?\s+q\[(\d)\](?:,q\[(\d)\])?;$/.exec(raw.trim());
    if (!m || m[1] === "measure" || m[1] === "qreg" || m[1] === "creg") continue;
    counts[m[1]] = (counts[m[1]] ?? 0) + 1;
    gates++;
    const qs = [Number(m[2]), ...(m[3] !== undefined ? [Number(m[3])] : [])];
    const d = Math.max(...qs.map((q) => level[q])) + 1;
    qs.forEach((q) => { level[q] = d; });
  }
  return { width: 2, gates, depth: Math.max(level[0], level[1]), counts };
}

// ---------------------------------------------------------------- experiment design

export interface PlanInput {
  hypothesis: string;
  thetas: string;
  shots: string;
  seed: string;
  fitFraction: string;
  observable: string;
  stopRule: string;
}

export interface PlanOk {
  ok: true;
  plan: {
    schema: "cqhecs.web.qg_experiment_design.v1";
    hypothesis: string;
    thetas: number[];
    null_control_theta: 0;
    shots: number;
    seed: number;
    fit_fraction: number;
    observable: string;
    stop_rule: string;
    credit_estimate: null;
    credit_estimate_reason: string;
    submission: SubmissionRefusal;
    design_only: true;
  };
}
export interface PlanErr { ok: false; errors: string[] }

export const OBSERVABLES = ["YZ", "ZY", "XX", "concurrence_witness"] as const;
export const MAX_SHOTS = 100000;
export const MAX_POINTS = 32;

export interface SubmissionRefusal {
  status: "UNAVAILABLE";
  code: "WEB_NO_PROVIDER_SUBMISSION";
  reason: string;
  spend_credits: 0;
  network: "none";
  credentials_in_browser: false;
}

/** The web app never submits a job and never holds provider credentials. A typed refusal, always. */
export function submitRefusal(): SubmissionRefusal {
  return {
    status: "UNAVAILABLE",
    code: "WEB_NO_PROVIDER_SUBMISSION",
    reason: "The browser app has no provider credentials and does not submit jobs or quotes. Quotes and submissions run only in the local CLI/MCP with an authorised, frozen campaign.",
    spend_credits: 0,
    network: "none",
    credentials_in_browser: false,
  };
}

export function validatePlan(i: PlanInput): PlanOk | PlanErr {
  const errors: string[] = [];
  const hypothesis = i.hypothesis.trim();
  if (hypothesis.length < 8) errors.push("hypothesis");
  const thetas: number[] = [];
  for (const part of i.thetas.split(/[;\s]+/).filter(Boolean)) {
    const v = parseBounded(part);
    if (v === null) { errors.push("thetas"); break; }
    thetas.push(v);
  }
  if (thetas.length === 0 && !errors.includes("thetas")) errors.push("thetas");
  if (thetas.length > MAX_POINTS) errors.push("points");
  const shots = Number(i.shots);
  if (!Number.isInteger(shots) || shots < 1 || shots > MAX_SHOTS) errors.push("shots");
  const seed = Number(i.seed);
  if (!Number.isInteger(seed) || seed < 0 || seed > 2 ** 31 - 1) errors.push("seed");
  const fit = Number(i.fitFraction);
  if (!(fit >= 0 && fit < 1) || i.fitFraction.trim() === "") errors.push("fit");
  if (!(OBSERVABLES as readonly string[]).includes(i.observable)) errors.push("observable");
  const stop = i.stopRule.trim();
  if (stop.length < 4) errors.push("stop");
  if (errors.length) return { ok: false, errors };
  return {
    ok: true,
    plan: {
      schema: "cqhecs.web.qg_experiment_design.v1",
      hypothesis,
      thetas,
      null_control_theta: 0,
      shots,
      seed,
      fit_fraction: fit,
      observable: i.observable,
      stop_rule: stop,
      credit_estimate: null,
      credit_estimate_reason: "No quote exists. A credit estimate comes only from an exact provider quote for the frozen QASM; the web app never requests one.",
      submission: submitRefusal(),
      design_only: true,
    },
  };
}

// ---------------------------------------------------------------- analysis data

export interface ChartPoint { x: number; y: number; err: number | null; series: string }

/** Measured two-qubit correlators from the recorded QPU phase scan (read-only snapshot). */
export function measuredScan(s: Snapshot = SNAPSHOT): ChartPoint[] {
  return s.bmv_scan.map((p) => ({ x: p.theta, y: p.correlator, err: p.std_err, series: p.basis }));
}

/** Model prediction |sin(theta)| over [0, pi/2] (the analytic oracle of the toy model). */
export function modelCurve(n = 33): ChartPoint[] {
  return Array.from({ length: n }, (_, i) => {
    const x = (Math.PI / 2) * (i / (n - 1));
    return { x, y: Math.abs(Math.sin(x)), err: null, series: "model" };
  });
}

export function shortHash(h: string): string { return `${h.slice(0, 12)}…${h.slice(-6)}`; }

/** CSV for the displayed analysis table, so the export reproduces the shown values. */
export function scanCsv(points: ChartPoint[]): string {
  const rows = ["series,theta_rad,correlator,std_err,source"];
  for (const p of points) rows.push(`${p.series},${p.x.toPrecision(17)},${p.y},${p.err ?? ""},QPU measured (${SNAPSHOT.backend})`);
  return rows.join("\n") + "\n";
}
