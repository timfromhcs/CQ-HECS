// T6-02: Quantum Gravity Lab logic. The browser model and QASM are checked against values the
// Python reference (cqhecs.quantum_gravity) wrote into the snapshot; i18n parity and the
// "no credentials, no network" property of the UI source are gates, not comments.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ORACLE: { theta: number; concurrence: number; negativity: number; entropy_bits: number; chsh_max: number; qasm: string; qasm_sha256: string }[] =
  JSON.parse(readFileSync(new URL("./fixtures/qg_oracle.json", import.meta.url), "utf8")).points;

import { sha256Hex } from "../src/digest";
import { QG_KEYS, qgMissingKeys } from "../src/qg_i18n";
import {
  OBSERVABLES, SNAPSHOT, bmvQasm, formatG17, measuredScan, modelCurve, parseBounded, qasmStats, runBmv,
  scanCsv, submitRefusal, validatePlan,
} from "../src/qg_logic";

const near = (a: number, b: number, tol = 1e-12) => assert.ok(Math.abs(a - b) <= tol, `${a} vs ${b}`);

test("every QG key exists in English, German and French", () => {
  assert.deepEqual(qgMissingKeys(), []);
});

test("every key used by qg.ts is defined", () => {
  const src = readFileSync(new URL("../src/qg.ts", import.meta.url), "utf8");
  const used = new Set<string>();
  for (const m of src.matchAll(/qt\("([\w.]+)"/g)) used.add(m[1]);
  for (const m of src.matchAll(/qt\(`([\w.]+)\$\{/g)) void m; // dynamic prefixes are checked below
  for (const k of used) assert.ok(QG_KEYS.includes(k), `missing key ${k}`);
  for (const tb of ["overview", "theories", "model", "circuit", "design", "backends", "analysis", "evidence"]) assert.ok(QG_KEYS.includes(`tab.${tb}`));
  for (const f of ["hypothesis", "thetas", "points", "shots", "seed", "fit", "observable", "stop"]) assert.ok(QG_KEYS.includes(`ex.f.${f}`));
  for (const k of ["bk.gpuYes", "bk.gpuNoApi", "bk.gpuNoAdapter", "bk.gpuErr"]) assert.ok(QG_KEYS.includes(k));
});

test("the lab source holds no credentials and makes no network request", () => {
  for (const f of ["qg.ts", "qg_logic.ts"]) {
    const src = readFileSync(new URL(`../src/${f}`, import.meta.url), "utf8");
    assert.ok(!/\bfetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|OPENQUANTUM|client_secret|Authorization|localStorage/i.test(src), `${f} must stay offline and credential-free`);
  }
});

test("browser model agrees with the Python reference for every snapshot oracle point", () => {
  assert.ok(ORACLE.length >= 9);
  for (const o of ORACLE) {
    const r = runBmv({ theta: o.theta, phaseA: 0, phaseB: 0 });
    near(r.concurrence, o.concurrence);
    near(r.negativity, o.negativity);
    near(r.entropyBits, o.entropy_bits, 1e-9);
    near(r.chshMax, o.chsh_max);
    near(Object.values(r.probabilities).reduce((a, b) => a + b, 0), 1);
  }
});

test("local phases do not change the entangling observables; the invariant is -2 theta", () => {
  const base = runBmv({ theta: 0.7, phaseA: 0, phaseB: 0 });
  const withPhases = runBmv({ theta: 0.7, phaseA: 1.3, phaseB: -2.1 });
  near(base.concurrence, withPhases.concurrence);
  near(base.entropyBits, withPhases.entropyBits, 1e-9);
  near(Math.cos(withPhases.entanglingPhase), Math.cos(-1.4));
  near(Math.sin(withPhases.entanglingPhase), Math.sin(-1.4));
});

test("QASM bytes and SHA-256 equal the Python reference", async () => {
  for (const o of ORACLE) {
    const q = bmvQasm({ theta: o.theta, phaseA: 0, phaseB: 0 });
    assert.equal(q, o.qasm);
    assert.equal(await sha256Hex(q), o.qasm_sha256);
  }
});

test("formatG17 reproduces Python's %.17g", () => {
  const cases: [number, string][] = [
    [0, "0"], [1e-5, "1.0000000000000001e-05"], [1e-4, "0.0001"], [0.00012345, "0.00012344999999999999"],
    [123456.789, "123456.789"], [1e16, "10000000000000000"], [1e17, "1e+17"], [3, "3"], [-2.5, "-2.5"],
    [0.30000000000000004, "0.30000000000000004"], [1.5e-7, "1.4999999999999999e-07"], [99.99999, "99.999989999999997"],
  ];
  for (const [x, s] of cases) assert.equal(formatG17(x), s, String(x));
});

test("qasmStats counts the generated circuit", () => {
  const s = qasmStats(bmvQasm({ theta: 1, phaseA: 0, phaseB: 0 }));
  assert.equal(s.width, 2);
  assert.equal(s.gates, 7);
  assert.deepEqual(s.counts, { h: 2, cx: 2, rz: 3 });
  assert.equal(s.depth, 5);
});

test("parseBounded accepts numbers and pi forms and rejects everything else", () => {
  near(parseBounded("pi/4")!, Math.PI / 4);
  near(parseBounded("3pi/8")!, 3 * Math.PI / 8);
  near(parseBounded("-pi/2")!, -Math.PI / 2);
  near(parseBounded("0,5")!, 0.5);
  near(parseBounded("1e-3")!, 0.001);
  near(parseBounded("2*pi")!, 2 * Math.PI);
  for (const bad of ["", "abc", "101", "-100.01", "NaN", "Infinity", "pi/0", "1e999", "1/2"]) assert.equal(parseBounded(bad), null, bad);
  assert.equal(parseBounded("100"), 100);
});

const good = { hypothesis: "Measured YZ follows sin theta", thetas: "0 pi/8 pi/4", shots: "1000", seed: "7", fitFraction: "0.5", observable: "YZ", stopRule: "stop on null drift" };

test("experiment plan validates, carries no credit estimate and a typed refusal", () => {
  const r = validatePlan(good);
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.equal(r.plan.credit_estimate, null);
  assert.equal(r.plan.design_only, true);
  assert.equal(r.plan.submission.status, "UNAVAILABLE");
  assert.equal(r.plan.submission.spend_credits, 0);
  assert.equal(r.plan.thetas.length, 3);
});

test("experiment plan rejects every invalid field", () => {
  const cases: [Partial<typeof good>, string][] = [
    [{ hypothesis: "short" }, "hypothesis"], [{ thetas: "0 foo" }, "thetas"], [{ thetas: "" }, "thetas"],
    [{ thetas: Array(33).fill("0.1").join(" ") }, "points"], [{ shots: "0" }, "shots"], [{ shots: "100001" }, "shots"],
    [{ shots: "1.5" }, "shots"], [{ seed: "-1" }, "seed"], [{ seed: "2147483648" }, "seed"], [{ fitFraction: "1" }, "fit"],
    [{ fitFraction: "" }, "fit"], [{ observable: "QQ" }, "observable"], [{ stopRule: "no" }, "stop"],
  ];
  for (const [patch, field] of cases) {
    const r = validatePlan({ ...good, ...patch });
    assert.ok(!r.ok, field);
    if (!r.ok) assert.ok(r.errors.includes(field), `${field}: ${r.errors}`);
  }
  assert.ok(OBSERVABLES.length >= 3);
});

test("submission is always a typed refusal, never a success", () => {
  const r = submitRefusal();
  assert.equal(r.status, "UNAVAILABLE");
  assert.equal(r.code, "WEB_NO_PROVIDER_SUBMISSION");
  assert.equal(r.spend_credits, 0);
  assert.equal(r.network, "none");
  assert.equal(r.credentials_in_browser, false);
});

test("recorded scan data are finite and the CSV reproduces every displayed row", () => {
  const pts = measuredScan();
  assert.equal(pts.length, SNAPSHOT.bmv_scan.length);
  for (const p of pts) { assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y)); assert.ok(p.err === null || p.err > 0); }
  const csv = scanCsv(pts).trim().split("\n");
  assert.equal(csv.length, pts.length + 1);
  const curve = modelCurve();
  near(curve[0].y, 0);
  near(curve[curve.length - 1].y, 1);
});

test("snapshot records a sha256 for every evidence file and excludes raw data", () => {
  assert.ok(SNAPSHOT.files.length >= 8);
  for (const f of SNAPSHOT.files) {
    assert.match(f.sha256, /^[0-9a-f]{64}$/);
    assert.ok(!/\/raw\/|JOB_LEDGER/.test(f.path), f.path);
  }
});
