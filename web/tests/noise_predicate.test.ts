// D5 (Wave 3, W3-12): one noise predicate shared by the simulator, the planner and the
// run card, a stable refusal code for WebGPU, and an explicit engine precision.
//
// Before this change `modeOf` (provenance.ts) looked only at p1, p2 and the symmetric
// `readout`, while the simulator also applies per-qubit p01/p10 readout and X bit flips.
// A measured profile with only readout error therefore ran with noise but its run card
// said mode SAMPLED.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  REFUSAL_WEBGPU_UNSUPPORTED,
  RefusalError,
  enginePrecision,
  hasGateNoise,
  hasReadoutNoise,
  isNoisy,
  webgpuRefusal,
} from "../src/noise_predicate";
import { buildRunCard, modeOf } from "../src/provenance";
import { profileNoise, type DeviceProfile } from "../src/profiles";

const IDEAL = { p1: 0, p2: 0, readout: 0 };

test("gate noise covers p1, p2 and per-qubit X bit flips", () => {
  assert.equal(hasGateNoise(IDEAL), false);
  assert.equal(hasGateNoise({ ...IDEAL, p1: 0.001 }), true);
  assert.equal(hasGateNoise({ ...IDEAL, p2: 0.01 }), true);
  assert.equal(hasGateNoise({ ...IDEAL, xflip: [0, 0.02] }), true);
  assert.equal(hasGateNoise({ ...IDEAL, xflip: [0, 0] }), false);
  assert.equal(hasGateNoise({}), false);
  assert.equal(hasGateNoise(null), false);
});

test("readout noise covers the symmetric value and per-qubit p01 and p10", () => {
  assert.equal(hasReadoutNoise(IDEAL), false);
  assert.equal(hasReadoutNoise({ ...IDEAL, readout: 0.01 }), true);
  assert.equal(hasReadoutNoise({ ...IDEAL, p01: [0, 0.02] }), true);
  assert.equal(hasReadoutNoise({ ...IDEAL, p10: [0.03] }), true);
  assert.equal(hasReadoutNoise({ ...IDEAL, p01: [0, 0], p10: [0] }), false);
});

test("a non-finite or negative channel value is not noise", () => {
  assert.equal(isNoisy({ p1: Number.NaN, p2: -0.1, readout: Number.NaN }), false);
});

test("modeOf agrees with the simulator for every noise channel (D5 regression)", () => {
  // These three all failed before the shared predicate: noise is applied, the card said SAMPLED.
  assert.equal(modeOf({ ...IDEAL, p01: [0.02, 0.02] }), "NOISY_CLASSICAL");
  assert.equal(modeOf({ ...IDEAL, p10: [0.03] }), "NOISY_CLASSICAL");
  assert.equal(modeOf({ ...IDEAL, xflip: [0.05] }), "NOISY_CLASSICAL");
  assert.equal(modeOf(IDEAL), "SAMPLED");
  assert.equal(modeOf(undefined), "SAMPLED");
});

const READOUT_ONLY_PROFILE: DeviceProfile = {
  id: "readout-only",
  label: "Readout only",
  cx_depolarizing: 0,
  p01: [0.01, 0.02],
  p10: [0.03, 0.04],
  x_bitflip: [0, 0],
  measured_qubits: 2,
} as unknown as DeviceProfile;

test("a readout-only measured profile produces a NOISY_CLASSICAL run card", async () => {
  const noise = profileNoise(READOUT_ONLY_PROFILE, 2);
  assert.equal(hasGateNoise(noise), false);
  assert.equal(hasReadoutNoise(noise), true);
  const card = await buildRunCard(
    { version: "5.0.0", revision: "abc", qasm: "qreg q[2];", shots: 10, engineRequested: "wasm", noise, seed: 1 },
    { engine: "wasm", mode: "sampled", elapsedMs: 1, counts: {} },
    ["limit"],
  );
  assert.equal((card.engine as { mode: string }).mode, "NOISY_CLASSICAL");
});

test("engine precision is explicit per engine and never guessed", () => {
  assert.equal(enginePrecision("wasm"), "f64");
  assert.equal(enginePrecision("webgpu"), "f32");
  // Anything else used to be reported as f32. It is unknown, and the schema has "n/a".
  assert.equal(enginePrecision("quantum-annealer"), "n/a");
  assert.equal(enginePrecision(""), "n/a");
});

test("an unknown engine does not get an f32 precision on the run card", async () => {
  const card = await buildRunCard(
    { version: "5.0.0", revision: "abc", qasm: "qreg q[1];", shots: 1, engineRequested: "x", noise: IDEAL, seed: 1 },
    { engine: "something-else", mode: "sampled", elapsedMs: 1, counts: {} },
    ["limit"],
  );
  assert.equal((card.engine as { precision: string }).precision, "n/a");
});

test("a WebGPU run card carries the cross-check TV, or an explicit null", async () => {
  const base = { version: "5.0.0", revision: "abc", qasm: "qreg q[1];", shots: 1, engineRequested: "webgpu", noise: IDEAL, seed: 1 };
  const withTv = await buildRunCard(base, { engine: "webgpu", mode: "sampled", elapsedMs: 1, counts: {}, crossCheckTv: 2.5e-8 }, ["limit"]);
  assert.equal((withTv.engine as { cross_check_tv: unknown }).cross_check_tv, 2.5e-8);
  const without = await buildRunCard(base, { engine: "webgpu", mode: "sampled", elapsedMs: 1, counts: {} }, ["limit"]);
  assert.equal((without.engine as { cross_check_tv: unknown }).cross_check_tv, null);
  // The cross-check belongs to WebGPU only; the WASM f64 card has no such field.
  const wasm = await buildRunCard(base, { engine: "wasm", mode: "sampled", elapsedMs: 1, counts: {} }, ["limit"]);
  assert.equal("cross_check_tv" in (wasm.engine as object), false);
});

test("WebGPU refusal has a stable code and machine-readable reasons", () => {
  assert.equal(REFUSAL_WEBGPU_UNSUPPORTED, "WEBGPU_UNSUPPORTED_CIRCUIT");
  assert.equal(webgpuRefusal(true, IDEAL, "msg"), null);
  // Readout noise is applied after sampling, so WebGPU accepts it.
  assert.equal(webgpuRefusal(true, { ...IDEAL, p01: [0.1] }, "msg"), null);

  const midCircuit = webgpuRefusal(false, IDEAL, "localized text");
  assert.ok(midCircuit instanceof RefusalError);
  assert.equal(midCircuit.code, REFUSAL_WEBGPU_UNSUPPORTED);
  assert.deepEqual(midCircuit.reasons, ["mid_circuit_measurement"]);
  assert.equal(midCircuit.message, "localized text");

  const noisy = webgpuRefusal(true, { ...IDEAL, xflip: [0.1] }, "m");
  assert.ok(noisy);
  assert.deepEqual(noisy.reasons, ["gate_noise"]);

  const both = webgpuRefusal(false, { ...IDEAL, p2: 0.1 }, "m");
  assert.ok(both);
  assert.deepEqual(both.reasons, ["mid_circuit_measurement", "gate_noise"]);
});

test("the stable code does not depend on the message language", () => {
  const de = webgpuRefusal(false, IDEAL, "WebGPU rechnet nur ...");
  const fr = webgpuRefusal(false, IDEAL, "WebGPU n'exécute que ...");
  assert.ok(de && fr);
  assert.equal(de.code, fr.code);
  assert.notEqual(de.message, fr.message);
});
