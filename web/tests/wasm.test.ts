// The bundled WebAssembly core must compute the same SHA-256 as the TypeScript
// reference and as the FIPS 180-4 vectors.
//
// This is the point of a third implementation: Python, TypeScript, Rust/wasm and
// the firmware's C are written independently, so a transcription error in any one
// of them produces a mismatch instead of four copies agreeing by construction.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { sha256d as tsSha256d, sha256 as tsSha256, toHex, fromHex } from "../src/forge/sha";

interface ShaExports {
  memory: WebAssembly.Memory;
  buf_alloc(bytes: number): number;
  sha256(data: number, len: number, out: number): number;
  sha256d(data: number, len: number, out: number): number;
}

const bytes = readFileSync(new URL("../public/cqhecs_core.wasm", import.meta.url));
const instance = new WebAssembly.Instance(new WebAssembly.Module(bytes), {});
const core = instance.exports as unknown as ShaExports;

// Buffers come from the module's own allocator. Hardcoded offsets were the first
// attempt and failed with "memory access out of bounds": the module's initial
// memory is much smaller than the gap they assumed.
function withBuffers(message: Uint8Array, call: (inPtr: number, outPtr: number) => number): Uint8Array {
  const inPtr = core.buf_alloc(Math.max(message.length, 1));
  const outPtr = core.buf_alloc(32);
  assert.notEqual(inPtr, 0, "the module could not allocate an input buffer");
  assert.notEqual(outPtr, 0, "the module could not allocate an output buffer");
  new Uint8Array(core.memory.buffer).set(message, inPtr);
  assert.equal(call(inPtr, outPtr), 0, "the export reported a null pointer");
  return new Uint8Array(core.memory.buffer.slice(outPtr, outPtr + 32));
}

function wasmSha256(message: Uint8Array): Uint8Array {
  return withBuffers(message, (inPtr, outPtr) => core.sha256(inPtr, message.length, outPtr));
}

function wasmSha256d(message: Uint8Array): Uint8Array {
  return withBuffers(message, (inPtr, outPtr) => core.sha256d(inPtr, message.length, outPtr));
}

const KAT: Array<[string, string]> = [
  ["", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
  ["616263", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"],
  [
    toHex(new TextEncoder().encode("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")),
    "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
  ],
];

test("the wasm module exports both SHA entry points", () => {
  assert.equal(typeof core.sha256, "function");
  assert.equal(typeof core.sha256d, "function");
});

test("FIPS 180-4 known answers through the wasm module", () => {
  for (const [messageHex, digestHex] of KAT) {
    assert.equal(toHex(wasmSha256(fromHex(messageHex))), digestHex, `SHA-256(${messageHex.slice(0, 16)}...)`);
  }
});

test("one million 'a' through the wasm module", () => {
  const million = new Uint8Array(1_000_000).fill(0x61);
  assert.equal(toHex(wasmSha256(million)), "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
});

test("sha256d matches the published double hash of the genesis header", () => {
  const header = fromHex(
    "01000000" +
      "0000000000000000000000000000000000000000000000000000000000000000" +
      "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a" +
      "29ab5f49" +
      "ffff001d" +
      "1dac2b7c",
  );
  const display = Array.from(wasmSha256d(header)).reverse();
  assert.equal(toHex(new Uint8Array(display)), "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f");
  assert.equal(toHex(wasmSha256d(fromHex("616263"))), toHex(tsSha256d(fromHex("616263"))));
});

test("wasm and TypeScript agree on random messages and every padding boundary", () => {
  // Boundaries where the tail grows from one block to two, plus a spread of
  // arbitrary lengths; a padding bug shows up here and nowhere else.
  const lengths = [0, 1, 54, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 129, 255, 256, 1000, 4096];
  for (const len of lengths) {
    const message = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      message[i] = (i * 37 + 11) & 0xff;
    }
    assert.equal(toHex(wasmSha256(message)), toHex(tsSha256(message)), `length ${len}`);
  }

  // Deterministic pseudo-random inputs (no Math.random: the test must be repeatable).
  let seed = 0x9e3779b9;
  const next = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed;
  };
  for (let round = 0; round < 25; round++) {
    const len = next() % 300;
    const message = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      message[i] = next() & 0xff;
    }
    assert.equal(toHex(wasmSha256(message)), toHex(tsSha256(message)), `random length ${len}`);
    assert.equal(toHex(wasmSha256d(message)), toHex(tsSha256d(message)), `double hash, length ${len}`);
  }
});

test("a null pointer is reported, not a trap", () => {
  assert.equal(core.sha256(0, 0, 2048), -1);
});
