// Run-card import: round trip through the exporter, and every refusal path.
import { test } from "node:test";
import assert from "node:assert/strict";

import { buildRunCard } from "../src/provenance";
import { MAX_CARD_BYTES, parseRunCard } from "../src/runcard_import";

const QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n';

async function card(overrides: (c: any) => void = () => {}): Promise<string> {
  const c = await buildRunCard(
    { version: "t", revision: "r", qasm: QASM, shots: 256, engineRequested: "wasm", noise: { p1: 0, p2: 0, readout: 0 }, seed: 99 },
    { engine: "wasm", mode: "sampled", elapsedMs: 1, counts: { "00": 128, "11": 128 }, norm: 1 },
    ["limit"],
  );
  overrides(c);
  return JSON.stringify(c);
}

test("round trip: an exported card imports with its circuit, shots and seed", async () => {
  const r = await parseRunCard(await card());
  assert.ok(r.ok);
  if (r.ok) {
    assert.equal(r.qasm, QASM);
    assert.equal(r.shots, 256);
    assert.equal(r.seed, 99);
    assert.equal(r.engine, "wasm");
    assert.equal(r.hasResult, true);
    assert.match(r.digest, /^[0-9a-f]{64}$/);
  }
});

const refusals: [string, (c: any) => void, string][] = [
  ["edited payload", (c) => { c.input.payload += "// tampered\n"; }, "digest_mismatch"],
  ["edited digest", (c) => { c.input.digest = "0".repeat(64); }, "digest_mismatch"],
  ["missing digest", (c) => { delete c.input.digest; }, "digest_mismatch"],
  ["wrong schema", (c) => { c.schema = "hcs.run.v1"; }, "wrong_schema"],
  ["not a circuit", (c) => { c.input.kind = "cnf"; }, "not_a_circuit"],
  ["empty payload", (c) => { c.input.payload = ""; }, "not_a_circuit"],
  ["zero shots", (c) => { c.input.shots = 0; }, "bad_shots"],
  ["fractional shots", (c) => { c.input.shots = 1.5; }, "bad_shots"],
  ["huge shots", (c) => { c.input.shots = 10_000_000; }, "bad_shots"],
  ["negative seed", (c) => { c.seed = -1; }, "bad_seed"],
  ["unknown engine", (c) => { c.input.engine_requested = "tpu"; }, "bad_engine"],
];
for (const [name, mutate, code] of refusals) {
  test(`refused: ${name}`, async () => {
    const r = await parseRunCard(await card(mutate));
    assert.equal(r.ok, false);
    if (!r.ok) assert.equal(r.code, code);
  });
}

test("refused: a payload this page's parser rejects, even with a correct digest", async () => {
  const bad = "OPENQASM 2.0;\nqreg q[1];\nfrobnicate q[0];\n";
  const { sha256Hex } = await import("../src/digest");
  const digest = await sha256Hex(bad);
  const r = await parseRunCard(await card((c) => { c.input.payload = bad; c.input.digest = digest; }));
  assert.equal(r.ok, false);
  if (!r.ok) assert.equal(r.code, "qasm_invalid");
});

test("refused: not JSON, a JSON array, null, and an oversized file", async () => {
  for (const text of ["", "{", "[]", "null", "42"]) {
    const r = await parseRunCard(text);
    assert.equal(r.ok, false, JSON.stringify(text));
    if (!r.ok) assert.equal(r.code, "not_json");
  }
  const big = await parseRunCard(" ".repeat(MAX_CARD_BYTES + 1));
  assert.equal(big.ok, false);
  if (!big.ok) assert.equal(big.code, "too_large");
});

test("hostile text in the card is returned as data, never interpreted", async () => {
  const r = await parseRunCard(await card((c) => { c.software.version = "<img src=x onerror=alert(1)>"; }));
  assert.ok(r.ok);
  if (r.ok) assert.equal(r.version, "<img src=x onerror=alert(1)>");
});
