// HCS SHA Forge web logic: SHA reference, traces (cross-checked with Python), backends, demo.

import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import * as sha from "../src/forge/sha";
import { probeBackends, type ProbeEnv } from "../src/forge/backends";
import { cpuBatch, selfTestBlocks } from "../src/forge/gpu_sha";
import { DEMO_LABEL, demoBenchmark, demoTelemetry } from "../src/forge/demo";

const fixtures = JSON.parse(readFileSync(new URL("./fixtures/sha_traces.json", import.meta.url), "utf-8"));
const enc = new TextEncoder();

test("known answers and node:crypto cross-check across length boundaries", () => {
  assert.equal(sha.toHex(sha.sha256(new Uint8Array(0))), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  assert.equal(sha.toHex(sha.sha256(enc.encode("abc"))), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  for (const n of [0, 1, 54, 55, 56, 57, 63, 64, 65, 119, 120, 128, 1000]) {
    const m = Uint8Array.from({ length: n }, (_, i) => (i * 7 + 3) & 255);
    assert.equal(sha.toHex(sha.sha256(m)), createHash("sha256").update(m).digest("hex"), `n=${n}`);
  }
});

test("Web Crypto agrees with the reference digest", async () => {
  const m = enc.encode("round analyzer");
  const d = new Uint8Array(await webcrypto.subtle.digest("SHA-256", m));
  assert.equal(sha.toHex(d), sha.toHex(sha.sha256(m)));
});

test("sha256d of the genesis header", () => {
  const h = sha.fromHex(sha.GENESIS_HEADER_HEX);
  assert.equal(h.length, 80);
  assert.equal(sha.toHex(sha.sha256d(h).reverse()), sha.GENESIS_BLOCK_HASH);
});

test("traces equal the Python reference trace round by round", () => {
  const abc = sha.traceBlock(sha.IV, sha.pad(enc.encode("abc")));
  assert.deepEqual(abc, fixtures.abc_block);
  assert.deepEqual(sha.traceBlock(sha.IV, sha.pad(enc.encode("abc")), 20), fixtures.abc_20);
  assert.deepEqual(sha.traceSha256d(sha.fromHex(sha.GENESIS_HEADER_HEX)), fixtures.genesis);
  assert.deepEqual(sha.traceMessage(enc.encode("a".repeat(100))), fixtures.msg100);
});

test("replay accepts the genuine trace and rejects tampering", () => {
  const tr = sha.traceBlock(sha.IV, sha.pad(enc.encode("abc")));
  assert.equal(sha.replay(JSON.parse(JSON.stringify(tr))), tr.output_state);
  tr.rounds[17].W = "00000000";
  assert.throws(() => sha.replay(tr));
});

test("negative controls: wrong IV, missing feed-forward and endian swap change the digest", () => {
  const block = sha.pad(enc.encode("abc"));
  const good = sha.traceBlock(sha.IV, block).output_state;
  const badIv = Uint32Array.from(sha.IV);
  badIv[0] ^= 1;
  assert.notEqual(sha.traceBlock(badIv, block).output_state, good);
  assert.notEqual(sha.traceBlock(sha.IV, block, 64, false).output_state, good);
  assert.notEqual(sha.traceBlock(sha.IV, block, 63).output_state, good);
  const swapped = block.slice();
  for (let i = 0; i < 64; i += 4) swapped.subarray(i, i + 4).reverse();
  assert.notEqual(sha.traceBlock(sha.IV, swapped).output_state, good);
});

test("candidate replay verifies the true nonce and rejects a flipped one", () => {
  const h = sha.fromHex(sha.GENESIS_HEADER_HEX);
  const nonce = new DataView(h.buffer).getUint32(76, true);
  assert.equal(sha.replayCandidate(h.slice(0, 76), nonce, 32).verified, true);
  assert.equal(sha.replayCandidate(h.slice(0, 76), nonce ^ 1, 32).verified, false);
  assert.throws(() => sha.replayCandidate(h.slice(0, 75), nonce, 1));
  assert.throws(() => sha.replayCandidate(h.slice(0, 76), 2 ** 32, 1));
});

test("CPU batch oracle equals per-block reference (WebGPU self-test oracle)", () => {
  const blocks = selfTestBlocks();
  const got = cpuBatch(blocks);
  const abc = sha.compress(sha.IV, blocks.subarray(16, 32));
  assert.deepEqual(Array.from(got.subarray(8, 16)), Array.from(abc));
});

// ------------------------------------------------------------ backend fallback chain

const base = (over: Partial<ProbeEnv> = {}): ProbeEnv => ({
  hasNavigatorGpu: false, wasmSimd: false, browserCpuSelfTest: () => true, ...over,
});
const okGpu = { acquireGpu: async () => ({ selfTest: async () => ({ ok: true }) }), hasNavigatorGpu: true };

test("WebGPU wins when its self-test passes", async () => {
  const r = await probeBackends(base(okGpu));
  assert.equal(r.selected, "WEBGPU");
});

test("every rejected backend carries a reason", async () => {
  const r = await probeBackends(base());
  assert.equal(r.selected, "BROWSER_CPU");
  for (const d of r.decisions.filter((x) => !x.ok)) assert.ok(d.reason.length > 5, d.id);
  assert.match(r.decisions.find((d) => d.id === "WEBGPU")!.reason, /navigator\.gpu/);
});

test("failed WebGPU self-test, device loss and thrown errors all fall back visibly", async () => {
  for (const acquireGpu of [
    async () => ({ selfTest: async () => ({ ok: false, reason: "mismatch at word 3" }) }),
    async () => null,
    async () => { throw new Error("device lost"); },
  ]) {
    const r = await probeBackends(base({ hasNavigatorGpu: true, acquireGpu }));
    assert.equal(r.selected, "BROWSER_CPU");
    assert.equal(r.decisions.find((d) => d.id === "WEBGPU")!.ok, false);
  }
});

test("WASM SIMD falls back to scalar, then to the browser CPU", async () => {
  const wasmSha = { scalar: true, simd: true, selfTest: (simd: boolean) => !simd };
  const r = await probeBackends(base({ wasmSimd: true, wasmSha }));
  assert.equal(r.selected, "WASM_SCALAR");
  assert.equal((await probeBackends(base({ wasmSimd: false, wasmSha }))).selected, "WASM_SCALAR");
  const none = await probeBackends(base({ wasmSimd: true, wasmSha: { scalar: false, simd: false, selfTest: () => true } }));
  assert.equal(none.selected, "BROWSER_CPU");
});

test("all engines failing selects the labelled demo, never fabricated data", async () => {
  const r = await probeBackends(base({ browserCpuSelfTest: () => false }));
  assert.equal(r.selected, "DEMO_SIMULATED");
});

test("ASIC is never a software fallback and needs the allowlisted unit plus a job type", async () => {
  const bridge = { reachable: true, nativeBackend: false, deviceAllowlisted: true, supportsJobType: true };
  const r = await probeBackends(base({ bridge }));
  assert.equal(r.selected, "BROWSER_CPU");
  assert.equal(r.decisions.find((d) => d.id === "ASIC_BM1366")!.ok, true);
  for (const b of [{ ...bridge, deviceAllowlisted: false }, { ...bridge, supportsJobType: false }, { ...bridge, reachable: false }]) {
    assert.equal((await probeBackends(base({ bridge: b }))).decisions.find((d) => d.id === "ASIC_BM1366")!.ok, false);
  }
});

// ------------------------------------------------------------ demo determinism

test("demo telemetry is deterministic, labelled and keeps gaps as null", () => {
  const a = demoTelemetry(), b = demoTelemetry();
  assert.deepEqual(a, b);
  assert.equal(a.label, DEMO_LABEL);
  assert.equal(a.source, "SIMULATED");
  assert.equal(a.samples.filter((s) => s.hashrate_ghs === null).length, 3);
  assert.notDeepEqual(demoTelemetry(1).samples, a.samples);
});

test("demo benchmark rows are flagged not comparable", () => {
  const b = demoBenchmark();
  assert.equal(b.label, DEMO_LABEL);
  assert.ok(b.rows.every((r) => r.comparable === false));
});
