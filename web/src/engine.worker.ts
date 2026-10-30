/// <reference lib="webworker" />
// Engine worker: owns the WASM core and the WebGPU device so the UI never blocks.
// Cancelling a run terminates this worker; the UI starts a fresh one.

import { matrix } from "./circuit";
import { Core, bitsOf } from "./core";
import { GpuEngine } from "./gpu";
import type { EngineInfo, RunRequest, RunResult, WorkerRequest, WorkerResponse } from "./protocol";
import { measurementMap, readoutPair, run } from "./simulate";
import { parseDimacs, solve, sweep } from "./sat";

declare const self: DedicatedWorkerGlobalScope;

let core: Core | null = null;
let gpu: GpuEngine | null = null;
let gpuError = "";

const post = (msg: WorkerResponse) => self.postMessage(msg);

function simdSupported(): boolean {
  // (module (func (result v128) i32.const 0 i8x16.splat i8x16.popcnt))
  const bytes = new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11]);
  return WebAssembly.validate(bytes);
}

function benchmark(c: Core): number {
  const n = 18;
  if (!c.init(n)) return 0;
  const h = matrix("h");
  const reps = 24;
  const t0 = performance.now();
  for (let k = 0; k < reps; k++) c.apply(k % n, 0, h);
  const dt = (performance.now() - t0) / 1000;
  c.free();
  return (reps * 2 ** n) / Math.max(dt, 1e-6);
}

async function init(): Promise<EngineInfo> {
  const info: EngineInfo = {
    wasm: { ok: false, simd: simdSupported(), bytes: 0 },
    wasmRate: 0,
    gpu: { ok: false, maxQubits: 0, maxBytes: 0 },
  };
  try {
    const response = await fetch(new URL("/cqhecs_core.wasm", self.location.origin));
    core = await Core.load(await response.arrayBuffer());
    info.wasm.ok = true;
    info.wasm.bytes = core.bytes;
    info.wasmRate = benchmark(core);
  } catch (e) {
    info.wasm.error = String((e as Error).message ?? e);
  }
  try {
    gpu = await GpuEngine.create();
    info.gpu = { ok: true, maxQubits: gpu.maxQubits(), maxBytes: gpu.maxBytes };
  } catch (e) {
    gpuError = String((e as Error).message ?? e);
    info.gpu.error = gpuError;
  }
  return info;
}

async function runGpu(req: RunRequest): Promise<RunResult> {
  if (!gpu) throw new Error(gpuError || "WebGPU nicht verfügbar");
  const started = performance.now();
  const n = req.numQubits;
  const amp = await gpu.run(n, req.ops, () => false);
  const dim = 2 ** n;
  const probs = new Float64Array(dim);
  let norm = 0;
  for (let i = 0; i < dim; i++) {
    probs[i] = amp[2 * i] * amp[2 * i] + amp[2 * i + 1] * amp[2 * i + 1];
    norm += probs[i];
  }
  // Inverse-CDF sampling on the CPU from the GPU distribution.
  const { pairs, width } = measurementMap(req);
  let seed = req.seed >>> 0;
  const uniform = () => {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let t = Math.imul(seed ^ (seed >>> 15), seed | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const draws = Array.from({ length: req.shots }, () => uniform() * norm).sort((a, b) => a - b);
  const counts: Record<string, number> = {};
  let k = 0, acc = 0;
  for (const u of draws) {
    while (k + 1 < dim && acc + probs[k] <= u) acc += probs[k++];
    let v = 0;
    for (const [q, c] of pairs) {
      let bit = (k >>> q) & 1;
      const [p01, p10] = readoutPair(req.noise, q);
      if (uniform() < (bit ? p10 : p01)) bit ^= 1;
      if (bit) v |= 1 << c;
    }
    const bits = bitsOf(v, width);
    counts[bits] = (counts[bits] ?? 0) + 1;
  }
  const order = Array.from(probs.keys()).filter((i) => probs[i] > 1e-9).sort((a, b) => probs[b] - probs[a]);
  const exact = order.slice(0, 64).map((i) => ({ bits: bitsOf(i, n), p: probs[i] / norm }));
  const amplitudes = n <= 6 ? Array.from({ length: dim }, (_, i) => ({ bits: bitsOf(i, n), re: amp[2 * i], im: amp[2 * i + 1] })) : [];

  const elapsedMs = performance.now() - started;
  // Cross-check against the exact f64 core whenever it is cheap; not timed.
  let crossCheckTv: number | undefined;
  if (core && n <= 20 && core.init(n)) {
    core.applyOps(req.ops);
    const ref = core.probabilities();
    let tv = 0;
    for (let i = 0; i < dim; i++) tv += Math.abs(ref[i] - probs[i] / norm);
    crossCheckTv = tv / 2;
    core.free();
  }
  return {
    id: req.id, engine: "webgpu", numQubits: n, shots: req.shots, counts, exact, amplitudes,
    bloch: [], norm, elapsedMs, mode: "sampled", trajectories: 1, crossCheckTv,
  };
}

self.onmessage = async (event: MessageEvent<WorkerRequest>) => {
  const msg = event.data;
  if (msg.type === "init") {
    post({ type: "init", info: await init() });
  } else if (msg.type === "sat") {
    try {
      const f = parseDimacs(msg.dimacs);
      post({ type: "sat", id: msg.id, result: solve(f, msg.timeoutMs), numVars: f.numVars, numClauses: f.clauses.length });
    } catch (e) {
      post({ type: "error", id: msg.id, message: String((e as Error).message ?? e) });
    }
  } else if (msg.type === "sweep") {
    post({ type: "sweep", id: msg.id, points: sweep(msg.numVars, msg.ratios, msg.trials, msg.timeoutMs) });
  } else if (msg.type === "probe") {
    const ok = !!core && core.init(msg.numQubits);
    core?.free();
    post({ type: "probe", numQubits: msg.numQubits, ok });
  } else if (msg.type === "run") {
    try {
      let result: RunResult;
      if (msg.engine === "webgpu") {
        result = await runGpu(msg);
      } else {
        if (!core) throw new Error("WASM-Kern nicht geladen");
        result = { id: msg.id, engine: "wasm", ...run(core, msg, (fraction, label) => post({ type: "progress", id: msg.id, fraction, label })) };
        core.free();
      }
      post({ type: "result", result });
    } catch (e) {
      core?.free();
      post({ type: "error", id: msg.id, message: String((e as Error).message ?? e) });
    }
  }
};
