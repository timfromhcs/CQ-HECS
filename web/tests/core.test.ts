// Correctness of the WASM f64 core and the circuit layer.
// Bundled with esbuild and run by `node --test` (see tests/run.mjs).

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Builder, compile, matrix, parseQasm, toQasm, type Circuit } from "../src/circuit";
import { Core } from "../src/core";
import { PRESETS } from "../src/presets";
import { run } from "../src/simulate";

const wasm = readFileSync(new URL("../public/cqhecs_core.wasm", import.meta.url));
const fixtures = JSON.parse(readFileSync(new URL("./fixtures/qiskit_statevectors.json", import.meta.url), "utf-8"));
const NO_NOISE = { p1: 0, p2: 0, readout: 0 };

async function stateOf(c: Circuit): Promise<Float64Array> {
  const core = await Core.load(wasm);
  assert.ok(core.init(c.numQubits));
  core.applyOps(compile(c));
  return core.amplitudes().slice();
}

// Independent reference: apply each gate's full 2^k matrix on its own qubits.
// It shares only the 2x2 matrix definitions with the engine, not compile().
function reference(c: Circuit): Float64Array {
  const n = c.numQubits, dim = 2 ** n;
  let re = new Float64Array(dim), im = new Float64Array(dim);
  re[0] = 1;
  for (const g of c.gates) {
    if (g.name === "measure" || g.name === "barrier") continue;
    const qs = g.qubits;
    const k = qs.length, size = 2 ** k;
    // Build the k-qubit matrix U (row-major, complex) in the local basis where
    // local bit j corresponds to qs[j].
    const Ur = new Float64Array(size * size), Ui = new Float64Array(size * size);
    for (let col = 0; col < size; col++) {
      let row = col;
      const bit = (j: number) => (col >> j) & 1;
      if (g.name === "swap") row = (bit(0) << 1) | bit(1);
      else if (g.name === "cswap") row = bit(0) ? (bit(1) << 2) | (bit(2) << 1) | 1 : col;
      else {
        // Controls are qs[0..k-2], the target is qs[k-1] (mcz is symmetric anyway).
        const allOn = Array.from({ length: k - 1 }, (_, j) => bit(j)).every(Boolean);
        if (!allOn) {
          Ur[col * size + col] = 1;
          continue;
        }
        const base = k === 1 ? g.name : g.name === "mcx" ? "x" : g.name === "mcz" ? "z" : g.name === "ccx" ? "x" : g.name;
        const m = matrix(base, g.params);
        const t = bit(k - 1);
        for (const out of [0, 1]) {
          const idx = out * 2 + t; // m[out][t]
          const r2 = (col & ~(1 << (k - 1))) | (out << (k - 1));
          Ur[r2 * size + col] += m[2 * idx];
          Ui[r2 * size + col] += m[2 * idx + 1];
        }
        continue;
      }
      Ur[row * size + col] = 1;
    }
    const nr = new Float64Array(dim), ni = new Float64Array(dim);
    for (let i = 0; i < dim; i++) {
      if (re[i] === 0 && im[i] === 0) continue;
      let local = 0;
      qs.forEach((q, j) => { local |= ((i >> q) & 1) << j; });
      for (let row = 0; row < size; row++) {
        const ur = Ur[row * size + local], ui = Ui[row * size + local];
        if (ur === 0 && ui === 0) continue;
        let target = i;
        qs.forEach((q, j) => { target = (target & ~(1 << q)) | (((row >> j) & 1) << q); });
        nr[target] += ur * re[i] - ui * im[i];
        ni[target] += ur * im[i] + ui * re[i];
      }
    }
    re = nr; im = ni;
  }
  const out = new Float64Array(2 * dim);
  for (let i = 0; i < dim; i++) { out[2 * i] = re[i]; out[2 * i + 1] = im[i]; }
  return out;
}

function maxDiff(a: ArrayLike<number>, b: ArrayLike<number>) {
  let d = 0;
  for (let i = 0; i < a.length; i++) d = Math.max(d, Math.abs(a[i] - b[i]));
  return d;
}

test("matches Qiskit Statevector on 40 random circuits (1-8 qubits), no global-phase slack", async () => {
  for (const [k, cs] of fixtures.cases.entries()) {
    const c = parseQasm(cs.qasm);
    const got = await stateOf(c);
    const want = new Float64Array(2 * cs.re.length);
    cs.re.forEach((v: number, i: number) => { want[2 * i] = v; want[2 * i + 1] = cs.im[i]; });
    assert.ok(maxDiff(got, want) < 1e-12, `case ${k}: max |Δ| = ${maxDiff(got, want)}`);
  }
});

test("matches an independent full-matrix reference, incl. mcx/mcz/cswap", async () => {
  let seed = 7;
  const r = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  for (let trial = 0; trial < 60; trial++) {
    const n = 3 + (trial % 5);
    const b = new Builder(n);
    for (let d = 0; d < 25; d++) {
      const pick = () => Math.floor(r() * n);
      const three = () => { const s = new Set<number>(); while (s.size < 3) s.add(pick()); return [...s]; };
      const x = r();
      if (x < 0.3) b.u(r() * 3, r() * 6 - 3, r() * 6 - 3, pick());
      else if (x < 0.5) { const [a, c] = three(); b.cx(a, c); }
      else if (x < 0.6) { const [a, c] = three(); b.crz(r() * 6, a, c); }
      else if (x < 0.7) { const [a, c] = three(); b.swap(a, c); }
      else if (x < 0.8) { const [a, c, t] = three(); b.cswap(a, c, t); }
      else if (x < 0.9) b.mcx(...three());
      else b.mcz(...three());
    }
    const got = await stateOf(b);
    const want = reference(b);
    assert.ok(maxDiff(got, want) < 1e-12, `trial ${trial}: ${maxDiff(got, want)}`);
  }
});

test("unitarity: norm stays 1 to 1e-12 on a 16-qubit random circuit", async () => {
  const c = PRESETS.find((p) => p.id === "random")!.build(16);
  const core = await Core.load(wasm);
  assert.ok(core.init(16));
  core.applyOps(compile(c));
  assert.ok(Math.abs(core.norm() - 1) < 1e-12);
});

test("QASM export round-trips to the identical state", async () => {
  for (const cs of fixtures.cases.slice(0, 15)) {
    const c = parseQasm(cs.qasm);
    const again = parseQasm(toQasm(c));
    assert.ok(maxDiff(await stateOf(c), await stateOf(again)) < 1e-13);
  }
});

test("presets: Bell, GHZ, Grover and teleportation behave as expected", async () => {
  const core = await Core.load(wasm);
  const bell = run(core, { ...PRESETS[0].build(2), ops: compile(PRESETS[0].build(2)), shots: 20000, seed: 1, noise: NO_NOISE });
  assert.deepEqual(Object.keys(bell.counts).sort(), ["00", "11"]);
  assert.ok(Math.abs(bell.counts["00"] / 20000 - 0.5) < 0.02);
  for (const n of [4, 5, 6]) {
    const g = PRESETS.find((p) => p.id === "grover")!.build(n);
    const res = run(core, { ...g, ops: compile(g), shots: 100, seed: 2, noise: NO_NOISE });
    const k = Math.floor((Math.PI / 4) * Math.sqrt(2 ** n));
    const theta = Math.asin(Math.sqrt(1 / 2 ** n));
    const expected = Math.sin((2 * k + 1) * theta) ** 2;
    assert.ok(Math.abs(res.exact[0].p - expected) < 1e-12, `grover n=${n}`);
    assert.equal(res.exact[0].bits, "1".repeat(n));
  }
  const tp = PRESETS.find((p) => p.id === "teleport")!.build(3);
  const t = run(core, { ...tp, ops: compile(tp), shots: 500, seed: 3, noise: NO_NOISE });
  assert.deepEqual(t.counts, { "0": 500 });
  const ghz = PRESETS.find((p) => p.id === "ghz")!.build(10);
  const gr = run(core, { ...ghz, ops: compile(ghz), shots: 1000, seed: 4, noise: NO_NOISE });
  assert.deepEqual(Object.keys(gr.counts).sort(), ["0000000000", "1111111111"]);
});

test("mid-circuit measurement collapses and feeds later gates", async () => {
  const core = await Core.load(wasm);
  const c = parseQasm(`OPENQASM 2.0; include "qelib1.inc"; qreg q[2]; creg c[2];
    h q[0]; measure q[0] -> c[0]; cx q[0], q[1]; h q[0]; measure q[1] -> c[1];`);
  const res = run(core, { ...c, ops: compile(c), shots: 400, seed: 5, noise: NO_NOISE });
  assert.equal(res.mode, "trajectories");
  for (const bits of Object.keys(res.counts)) assert.equal(bits[0], bits[1], `c1 must equal c0, got ${bits}`);
});

test("reset returns a qubit to |0> and readout noise flips bits", async () => {
  const core = await Core.load(wasm);
  const c = new Builder(1).x(0).reset(0).measure(0);
  const res = run(core, { ...c, ops: compile(c), shots: 200, seed: 6, noise: NO_NOISE });
  assert.deepEqual(res.counts, { "0": 200 });
  const flip = new Builder(1).measure(0);
  const noisy = run(core, { ...flip, ops: compile(flip), shots: 20000, seed: 7, noise: { p1: 0, p2: 0, readout: 0.1 } });
  assert.ok(Math.abs(noisy.counts["1"] / 20000 - 0.1) < 0.01);
});

test("sampling is reproducible for a seed and statistically sound", async () => {
  const core = await Core.load(wasm);
  const c = new Builder(3).h(0).h(1).h(2).measureAll();
  const a = run(core, { ...c, ops: compile(c), shots: 80000, seed: 11, noise: NO_NOISE });
  const b = run(core, { ...c, ops: compile(c), shots: 80000, seed: 11, noise: NO_NOISE });
  assert.deepEqual(a.counts, b.counts);
  let chi2 = 0;
  for (const v of Object.values(a.counts)) chi2 += (v - 10000) ** 2 / 10000;
  assert.ok(chi2 < 24.3, `chi2=${chi2}`); // p = 0.001 for 7 dof
});

test("the core refuses widths outside 1..30 instead of truncating", async () => {
  const core = await Core.load(wasm);
  assert.equal(core.init(0), false);
  assert.equal(core.init(31), false);
});

test("parser rejects malformed input", () => {
  assert.throws(() => parseQasm("qreg q[2]; foo q[0];"), /unsupported gate/);
  assert.throws(() => parseQasm("qreg q[2]; cx q[0];"), /expects 2/);
  assert.throws(() => parseQasm("qreg q[2]; rx(alert(1)) q[0];"), /cannot parse|invalid parameter/);
  assert.throws(() => parseQasm("qreg q[2]; rx(this.x) q[0];"), /invalid parameter/);
  assert.throws(() => compile({ numQubits: 2, numClbits: 0, gates: [{ name: "cx", qubits: [0, 0] }] }), /repeated/);
});

test("device-profile noise reproduces the exact Python M-FIT-2 distributions", async () => {
  const { profileNoise } = await import("../src/profiles");
  const doc = JSON.parse(readFileSync(new URL("../public/device_profiles.json", import.meta.url), "utf-8"));
  const noisy = JSON.parse(readFileSync(new URL("./fixtures/device_noise.json", import.meta.url), "utf-8"));
  const core = await Core.load(wasm);
  let worst = 0;
  for (const [k, cs] of noisy.cases.entries()) {
    const profile = doc.profiles.find((p: { id: string }) => p.id === cs.profile);
    const c = parseQasm(cs.qasm);
    const shots = 60000;
    const res = run(core, { ...c, ops: compile(c), shots, seed: 1000 + k, noise: profileNoise(profile, c.numQubits) });
    let tv = 0;
    cs.probabilities.forEach((p: number, i: number) => {
      const bits = i.toString(2).padStart(cs.num_qubits, "0");
      tv += Math.abs((res.counts[bits] ?? 0) / shots - p);
    });
    tv /= 2;
    worst = Math.max(worst, tv);
    // 60k shots over <= 32 outcomes: the finite-shot TV is ~0.01; 0.02 leaves room
    // for sampling noise but catches any wrong channel (those give TV >= 0.05).
    assert.ok(tv < 0.02, `${cs.profile} ${cs.job}: TV ${tv.toFixed(4)}`);
  }
  assert.ok(worst > 0, "sanity: sampling noise is present");
});

test("trajectory count is one per shot for small circuits and bounded for large ones", async () => {
  const { trajectoryCount } = await import("../src/simulate");
  assert.equal(trajectoryCount(1000, 30, 5), 1000);
  assert.equal(trajectoryCount(100000, 500, 20), 256);
});

test("SAT solver: sound verdicts, brute-force agreement, budgets", async () => {
  const { solve, parseDimacs, random3Sat, pigeonhole, satisfies } = await import("../src/sat");
  for (let seed = 0; seed < 300; seed++) {
    const f = random3Sat(8, 20 + (seed % 25), seed);
    let any = false;
    for (let bits = 0; bits < 256 && !any; bits++) {
      const m = [false, ...Array.from({ length: 8 }, (_, i) => ((bits >> i) & 1) === 1)];
      any = satisfies(f, m);
    }
    const r = solve(f, 5000);
    assert.equal(r.status, any ? "SAT" : "UNSAT", `seed ${seed}`);
    if (r.status === "SAT") assert.ok(r.verified && satisfies(f, r.model!));
  }
  assert.equal(solve(pigeonhole(5)).status, "UNSAT");
  assert.equal(solve(pigeonhole(9), 1).status, "UNKNOWN"); // never a fake UNSAT
  assert.equal(solve(parseDimacs("p cnf 2 2\n1 0\n-1 2 0\n")).status, "SAT");
  assert.throws(() => parseDimacs("p cnf 1 1\n2 0\n"), /exceeds/);
});

test("i18n: every UI key and guide section exists in EN, DE and FR", async () => {
  const { missingKeys } = await import("../src/i18n");
  assert.deepEqual(missingKeys(), []);
  const { GUIDE, GUIDE_UI } = await import("../src/guide");
  for (const s of GUIDE) for (const l of ["en", "de", "fr"] as const) {
    assert.ok(s.title[l] && s.body[l].length > 200, `${s.id}:${l}`);
  }
  assert.deepEqual(Object.keys(GUIDE_UI).sort(), ["de", "en", "fr"]);
  for (const p of PRESETS) for (const l of ["en", "de", "fr"] as const) assert.ok(p.title[l] && p.blurb[l], `${p.id}:${l}`);
});
