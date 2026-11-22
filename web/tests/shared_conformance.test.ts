// Shared conformance corpus (T6-05 / W13), browser side in Node.
//
// The same file `tests/fixtures/shared_conformance.json` is checked by
// `tests/test_web_shared_conformance.py` (Qiskit oracle + the Python four-path reference).
// Here the browser's own parser, compiler and WebAssembly f64 core are the subject, plus the
// browser's measurement mapping (`simulate.run`). WebGPU cannot run in Node: the f32 section
// below is an EMULATION of the WGSL kernel arithmetic (Math.fround) and is labelled as such. It
// bounds the f32 deviation the declared tolerance has to absorb; it is not a WebGPU result.
// The real-adapter run lives in `e2e/conformance.spec.ts` and is NOT_RUN without an adapter.
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

import { Core } from "../src/core";
import { compile, parseQasm, type Op } from "../src/circuit";
import { measurementMap, run } from "../src/simulate";

interface Case {
  name: string;
  family: string;
  qasm: string;
  num_qubits: number;
  num_clbits: number;
  measurement_map: [number, number][];
  probabilities_sparse: Record<string, number>;
  classical_distribution: Record<string, number>;
  deterministic_counts: boolean;
  amplitudes?: [number, number][];
  webgpu: { in_declared_range: boolean };
}
interface Corpus {
  schema: string;
  tolerance_f64: number;
  webgpu: { precision: string; declared_max_qubits: number; tolerance: { max_abs_probability_diff: number; total_variation: number } };
  cases: Case[];
  refusals: { name: string; qasm: string; expected: string }[];
}

const corpus: Corpus = JSON.parse(readFileSync(new URL("./fixtures/shared_conformance.json", import.meta.url), "utf8"));
const wasmBytes = readFileSync(new URL("../public/cqhecs_core.wasm", import.meta.url));
const NO_NOISE = { p1: 0, p2: 0, readout: 0 };

function dense(c: Case): number[] {
  const out = new Array(2 ** c.num_qubits).fill(0);
  for (const [k, v] of Object.entries(c.probabilities_sparse)) out[Number(k)] = v;
  return out;
}

/** Largest deviation of `amp` from `reference` after removing one global phase. */
function amplitudeDeviation(amp: ArrayLike<number>, reference: [number, number][]): number {
  let k = 0;
  for (let i = 1; i < reference.length; i++) if (Math.hypot(...reference[i]) > Math.hypot(...reference[k])) k = i;
  const [rr, ri] = reference[k];
  const [ar, ai] = [amp[2 * k], amp[2 * k + 1]];
  const mag = Math.hypot(rr, ri) * Math.hypot(ar, ai);
  const pr = (rr * ar + ri * ai) / mag; // phase = ref * conj(actual) / |.|
  const pi = (ri * ar - rr * ai) / mag;
  let worst = 0;
  for (let i = 0; i < reference.length; i++) {
    const x = amp[2 * i], y = amp[2 * i + 1];
    worst = Math.max(worst, Math.hypot(x * pr - y * pi - reference[i][0], x * pi + y * pr - reference[i][1]));
  }
  return worst;
}

async function f64Core(qasm: string) {
  const circuit = parseQasm(qasm);
  const core = await Core.load(wasmBytes);
  assert.ok(core.init(circuit.numQubits));
  core.applyOps(compile(circuit));
  return { core, circuit };
}

test("the corpus declares its semantics and a WebGPU range", () => {
  assert.equal(corpus.schema, "hcs.conformance.shared.v1");
  assert.equal(corpus.webgpu.precision, "f32");
  assert.ok(corpus.webgpu.declared_max_qubits >= 10);
  assert.ok(corpus.cases.length >= 20);
});

for (const c of corpus.cases) {
  test(`wasm f64 / ${c.name}: probabilities, norm, global-phase amplitudes`, async () => {
    const { core, circuit } = await f64Core(c.qasm);
    assert.equal(circuit.numQubits, c.num_qubits);
    const probs = core.probabilities();
    const expected = dense(c);
    for (let i = 0; i < expected.length; i++) {
      assert.ok(Math.abs(probs[i] - expected[i]) <= corpus.tolerance_f64, `${c.name}: P(${i}) ${probs[i]} vs ${expected[i]}`);
    }
    assert.ok(Math.abs(core.norm() - 1) <= corpus.tolerance_f64, `norm ${core.norm()}`);
    if (c.amplitudes) {
      assert.ok(amplitudeDeviation(core.amplitudes(), c.amplitudes) <= 1e-11, `${c.name}: amplitudes differ beyond a global phase`);
    }
    core.free();
  });

  test(`wasm f64 / ${c.name}: measurement map and classical counts`, async () => {
    const circuit = parseQasm(c.qasm);
    const input = { numQubits: circuit.numQubits, numClbits: circuit.numClbits, ops: compile(circuit), shots: 4000, seed: 3, noise: NO_NOISE };
    const { pairs, width } = measurementMap(input);
    assert.deepEqual(pairs, c.measurement_map, "measurement map");
    assert.equal(width, c.num_clbits, "classical width");
    const core = await Core.load(wasmBytes);
    const result = run(core, input);
    core.free();
    assert.equal(Object.values(result.counts).reduce((a, b) => a + b, 0), input.shots);
    if (c.deterministic_counts) {
      assert.deepEqual(result.counts, { [Object.keys(c.classical_distribution)[0]]: input.shots });
    } else if (Object.keys(c.classical_distribution).length <= 64) {
      let tv = 0;
      const keys = new Set([...Object.keys(result.counts), ...Object.keys(c.classical_distribution)]);
      for (const k of keys) tv += Math.abs((result.counts[k] ?? 0) / input.shots - (c.classical_distribution[k] ?? 0));
      assert.ok(tv / 2 <= 0.06 + 0.004 * keys.size, `${c.name}: TV ${tv / 2} against the corpus distribution`);
    }
    for (const key of Object.keys(result.counts)) assert.equal(key.length, c.num_clbits, "keys are c[n-1]..c[0]");
  });
}

test("every refusal case is refused by the browser parser or compiler, never run", () => {
  assert.ok(corpus.refusals.length >= 4);
  for (const r of corpus.refusals) {
    assert.throws(() => compile(parseQasm(r.qasm)), undefined, `${r.name} must be refused`);
  }
});

test("break test: reading the corpus big-endian is detected", async () => {
  const c = corpus.cases.find((x) => x.name === "endianness-x-q0")!;
  const { core } = await f64Core(c.qasm);
  const probs = core.probabilities();
  assert.equal(probs[1], 1);
  assert.equal(probs[4], 0, "q0 must not be the high bit");
  core.free();
});

test("break test: a conjugated S gate is rejected through the pinned amplitudes", async () => {
  const c = corpus.cases.find((x) => x.name === "s-interference")!;
  const conjugated = c.qasm.replace("s q[0];", "sdg q[0];");
  assert.notEqual(conjugated, c.qasm);
  assert.ok(c.amplitudes, "n <= 4 cases carry amplitudes");
  const { core } = await f64Core(conjugated);
  // H S H and H Sdg H have the same probabilities (1/2, 1/2); only the amplitudes tell them apart.
  assert.ok(Math.abs(core.probabilities()[0] - 0.5) < 1e-12);
  assert.ok(amplitudeDeviation(core.amplitudes(), c.amplitudes) > 1e-3, "the corpus must tell S from Sdg");
  core.free();
});

// ---------------------------------------------------------------- f32 emulation (NOT WebGPU)

function emulateF32(n: number, ops: Op[]): Float32Array {
  const f = Math.fround;
  const amp = new Float32Array(2 * 2 ** n);
  amp[0] = 1;
  const cm = (ar: number, ai: number, br: number, bi: number): [number, number] => [f(f(ar * br) - f(ai * bi)), f(f(ar * bi) + f(ai * br))];
  for (const op of ops) {
    if (op.kind !== "u") continue;
    const m = Array.from(op.m, f);
    const tbit = 1 << op.target;
    for (let idx = 0; idx < 2 ** (n - 1); idx++) {
      const lo = idx & (tbit - 1);
      const i = ((idx - lo) << 1) | lo;
      if ((i & op.ctrl) !== op.ctrl) continue;
      const j = i | tbit;
      const xr = amp[2 * i], xi = amp[2 * i + 1], yr = amp[2 * j], yi = amp[2 * j + 1];
      const [a0r, a0i] = cm(m[0], m[1], xr, xi), [a1r, a1i] = cm(m[2], m[3], yr, yi);
      const [b0r, b0i] = cm(m[4], m[5], xr, xi), [b1r, b1i] = cm(m[6], m[7], yr, yi);
      amp[2 * i] = f(a0r + a1r); amp[2 * i + 1] = f(a0i + a1i);
      amp[2 * j] = f(b0r + b1r); amp[2 * j + 1] = f(b0i + b1i);
    }
  }
  return amp;
}

test("f32 EMULATION of the WGSL kernel stays inside the declared WebGPU tolerance (not a WebGPU run)", () => {
  const report: Record<string, { max_abs: number; tv: number }> = {};
  for (const c of corpus.cases) {
    if (!c.webgpu.in_declared_range) continue;
    const amp = emulateF32(c.num_qubits, compile(parseQasm(c.qasm)));
    const expected = dense(c);
    let maxAbs = 0, tv = 0, norm = 0;
    for (let i = 0; i < expected.length; i++) {
      const p = amp[2 * i] ** 2 + amp[2 * i + 1] ** 2;
      norm += p;
      maxAbs = Math.max(maxAbs, Math.abs(p - expected[i]));
      tv += Math.abs(p - expected[i]);
    }
    report[c.name] = { max_abs: maxAbs, tv: tv / 2 };
    assert.ok(maxAbs <= corpus.webgpu.tolerance.max_abs_probability_diff, `${c.name}: f32 emulation max |dP| ${maxAbs}`);
    assert.ok(tv / 2 <= corpus.webgpu.tolerance.total_variation, `${c.name}: f32 emulation TV ${tv / 2}`);
    assert.ok(Math.abs(norm - 1) <= 1e-5, `${c.name}: f32 norm ${norm}`);
  }
  mkdirSync(new URL("../test-results/", import.meta.url), { recursive: true });
  writeFileSync(
    new URL("../test-results/shared_conformance_f32_emulation.json", import.meta.url),
    JSON.stringify({ kind: "f32-emulation-not-webgpu", tolerance: corpus.webgpu.tolerance, cases: report }, null, 2),
  );
});
