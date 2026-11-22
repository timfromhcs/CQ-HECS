// W4-09 / T6-06: WebGPU failure handling, fallback labelling, low-memory policy and the
// allocation-failure path. Node has no WebGPU, so GPU behaviour is driven through a fake device
// that exposes exactly the surface `gpu.ts` uses.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { CANCELLED_MESSAGE, GpuLossError, classifyGpuFailure, fallbackLimit, runWithFallback } from "../src/fallback";
import { GpuEngine } from "../src/gpu";
import { Core } from "../src/core";
import { computeLimits, estimate, type DeviceReport } from "../src/device";
import type { EngineInfo } from "../src/protocol";
import { moveCursor } from "../src/composer_nav";

// ---------------------------------------------------------------- classification

test("a device loss and a GPU error fall back; a cancellation never does", () => {
  assert.equal(classifyGpuFailure(new GpuLossError("destroyed"))?.kind, "device-lost");
  assert.equal(classifyGpuFailure(new Error("WebGPU-Fehler: out of memory"))?.kind, "gpu-error");
  assert.equal(classifyGpuFailure(new Error(CANCELLED_MESSAGE)), null);
});

test("runWithFallback labels the fallback and keeps the WASM result", async () => {
  const seen: string[] = [];
  const out = await runWithFallback(
    async () => { throw new GpuLossError("unknown: driver reset"); },
    async () => "wasm-result",
    (f) => seen.push(f.kind),
  );
  assert.equal(out.result, "wasm-result");
  assert.deepEqual(out.fallback, { from: "webgpu", to: "wasm", kind: "device-lost", reason: "unknown: driver reset" });
  assert.deepEqual(seen, ["device-lost"]);
  assert.match(fallbackLimit(out.fallback!), /WASM f64: device-lost/);
});

test("a successful GPU run has no fallback record", async () => {
  const out = await runWithFallback(async () => "gpu", async () => assert.fail("must not run"));
  assert.equal(out.result, "gpu");
  assert.equal(out.fallback, undefined);
});

test("a cancellation propagates and does not start the fallback", async () => {
  await assert.rejects(
    runWithFallback(async () => { throw new Error(CANCELLED_MESSAGE); }, async () => assert.fail("must not run")),
    /abgebrochen/,
  );
});

test("when the fallback also fails, both causes are reported and no result is produced", async () => {
  await assert.rejects(
    runWithFallback(async () => { throw new GpuLossError("destroyed"); }, async () => { throw new Error("memory"); }),
    /device-lost: destroyed.*fallback also failed: memory/,
  );
});

// ---------------------------------------------------------------- fake WebGPU device

type Hooks = { loseDuringRun?: boolean; oomOnSubmit?: boolean };

function installFakeGpu(hooks: Hooks) {
  let lose!: (info: { reason: string; message: string }) => void;
  const lost = new Promise<{ reason: string; message: string }>((r) => { lose = r; });
  let scopes = 0;
  const device = {
    lost,
    pushErrorScope() { scopes++; },
    async popErrorScope() { scopes--; return hooks.oomOnSubmit && scopes === 1 ? { message: "out of memory" } : null; },
    createShaderModule: () => ({}),
    createComputePipeline: () => ({ getBindGroupLayout: () => ({}) }),
    createBuffer: () => ({ destroy() {}, mapAsync: async () => {}, getMappedRange: () => new ArrayBuffer(16), unmap() {} }),
    createBindGroup: () => ({}),
    createCommandEncoder: () => ({
      beginComputePass: () => ({ setPipeline() {}, setBindGroup() {}, dispatchWorkgroups() {}, end() {} }),
      copyBufferToBuffer() {}, finish: () => ({}),
    }),
    queue: {
      writeBuffer() {},
      submit() { if (hooks.loseDuringRun) lose({ reason: "unknown", message: "driver reset" }); },
      // After a loss the real promise never settles; the engine must not wait for it.
      onSubmittedWorkDone: () => (hooks.loseDuringRun ? new Promise<void>(() => {}) : Promise.resolve()),
    },
  };
  const adapter = {
    limits: { maxStorageBufferBindingSize: 1 << 30, maxBufferSize: 1 << 30 },
    requestDevice: async () => device,
  };
  const g = globalThis as Record<string, unknown>;
  const savedNav = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", { value: { gpu: { requestAdapter: async () => adapter } }, configurable: true });
  g.GPUBufferUsage = { STORAGE: 1, COPY_SRC: 2, COPY_DST: 4, UNIFORM: 8, MAP_READ: 16 };
  g.GPUMapMode = { READ: 1 };
  return () => {
    if (savedNav) Object.defineProperty(globalThis, "navigator", savedNav);
    delete g.GPUBufferUsage;
    delete g.GPUMapMode;
  };
}

const H = [{ kind: "u" as const, target: 0, ctrl: 0, m: [0.7071, 0, 0.7071, 0, 0.7071, 0, -0.7071, 0] }];

test("device loss mid-run raises GpuLossError instead of hanging, and the engine stays lost", async () => {
  const restore = installFakeGpu({ loseDuringRun: true });
  try {
    const engine = await GpuEngine.create();
    await assert.rejects(engine.run(1, H as never, () => false), (e: unknown) => e instanceof GpuLossError && /driver reset/.test(e.message));
    assert.equal(engine.isLost, true);
    // A lost engine refuses at once rather than touching the dead device again.
    await assert.rejects(engine.run(1, H as never, () => false), GpuLossError);
  } finally { restore(); }
});

test("a GPU out-of-memory is a typed error the worker can fall back on", async () => {
  const restore = installFakeGpu({ oomOnSubmit: true });
  try {
    const engine = await GpuEngine.create();
    const err = await engine.run(1, H as never, () => false).catch((e) => e);
    assert.match(String(err.message), /out of memory/);
    assert.equal(classifyGpuFailure(err)?.kind, "gpu-error");
    assert.equal(engine.isLost, false);
  } finally { restore(); }
});

test("a healthy fake device runs without a loss", async () => {
  const restore = installFakeGpu({});
  try {
    const engine = await GpuEngine.create();
    const amp = await engine.run(1, H as never, () => false);
    assert.ok(amp instanceof Float32Array);
    assert.equal(engine.isLost, false);
  } finally { restore(); }
});

test("WebGPU unavailable: create() refuses with a reason instead of pretending", async () => {
  const savedNav = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", { value: {}, configurable: true });
  try {
    await assert.rejects(GpuEngine.create(), /WebGPU/);
  } finally { if (savedNav) Object.defineProperty(globalThis, "navigator", savedNav); }
});

// ---------------------------------------------------------------- low memory policy

const baseDevice: DeviceReport = {
  os: "Android", browser: "Chrome 1", arch: "", mobile: true, cores: 4, ramGiB: null, ramSource: "",
  gpuName: "", gpuVendor: "", gpuBackend: "", webgpu: false, webgl2: false, crossOriginIsolated: false,
};
const engineOk: EngineInfo = { wasm: { ok: true, simd: true, bytes: 1 }, wasmRate: 1e8, gpu: { ok: true, maxQubits: 27, maxBytes: 2 ** 30 } };

test("low memory: a quarter of the reported RAM bounds the width, 0.25 GiB gives 22 qubits", () => {
  const limits = computeLimits({ ...baseDevice, ramGiB: 0.25 }, engineOk);
  assert.equal(limits.exactQubits, 22);
  assert.equal(estimate(23, 10, 100, 1, limits, false).safe, false);
  assert.equal(estimate(22, 10, 100, 1, limits, false).safe, true);
});

test("memory API absent: mobile assumes 2 GiB, desktop 4 GiB (never unlimited)", () => {
  assert.equal(computeLimits({ ...baseDevice, ramGiB: null, mobile: true }, engineOk).exactQubits, 25);
  assert.equal(computeLimits({ ...baseDevice, ramGiB: null, mobile: false }, engineOk).exactQubits, 26);
});

test("no WASM core or no WebGPU: the width limit is 0 and every run is refused", () => {
  const noWasm = computeLimits(baseDevice, { ...engineOk, wasm: { ok: false, simd: false, bytes: 0 } });
  assert.equal(noWasm.exactQubits, 0);
  assert.equal(estimate(1, 1, 1, 1, noWasm, false).safe, false);
  const noGpu = computeLimits(baseDevice, { ...engineOk, gpu: { ok: false, maxQubits: 0, maxBytes: 0 } });
  assert.equal(noGpu.gpuQubits, 0);
  assert.equal(estimate(1, 1, 1, 1, noGpu, true).safe, false);
});

// ---------------------------------------------------------------- allocation failure

const wasm = readFileSync(new URL("../public/cqhecs_core.wasm", import.meta.url));

test("a failed allocation returns false and leaves the core usable", async () => {
  const core = await Core.load(wasm);
  // 2^30 amplitudes x 16 B = 16 GiB: cannot fit a wasm32 heap, so init must refuse, not trap.
  assert.equal(core.init(30), false);
  assert.equal(core.init(3), true);
  core.free();
});

// ---------------------------------------------------------------- composer keyboard cursor

test("the composer cursor never leaves the grid", () => {
  let c = { col: 0, q: 0 };
  c = moveCursor(c, "ArrowUp", 3, 8);
  c = moveCursor(c, "ArrowLeft", 3, 8);
  assert.deepEqual(c, { col: 0, q: 0 });
  for (let i = 0; i < 20; i++) c = moveCursor(c, "ArrowDown", 3, 8);
  for (let i = 0; i < 30; i++) c = moveCursor(c, "ArrowRight", 3, 8);
  assert.deepEqual(c, { col: 7, q: 2 });
  assert.deepEqual(moveCursor(c, "Home", 3, 8), { col: 0, q: 2 });
  assert.deepEqual(moveCursor(c, "PageUp", 3, 8), { col: 7, q: 0 });
  assert.deepEqual(moveCursor(c, "End", 3, 1000), { col: 63, q: 2 });
  assert.deepEqual(moveCursor({ col: 5, q: 9 }, "ArrowLeft", 1, 2), { col: 1, q: 0 });
});
