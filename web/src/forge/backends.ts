// Backend capability probe with an explicit, testable fallback chain.
// Selection answers "which engine runs SHA software workloads"; ASIC_BM1366 is a
// different workload (SHA-256d mining jobs) and is never chosen as a software fallback.

export type BackendId =
  | "WEBGPU" | "WASM_SIMD" | "WASM_SCALAR" | "BROWSER_CPU" | "LOCAL_NATIVE" | "ASIC_BM1366" | "DEMO_SIMULATED";

export interface Decision { id: BackendId; ok: boolean; reason: string }

export interface BridgeInfo {
  reachable: boolean;
  nativeBackend: boolean;        // bridge advertises an installed native backend with a matching contract
  deviceAllowlisted: boolean;    // bridge confirmed the exact allowlisted unit
  supportsJobType: boolean;      // device exposes a named supported job type
}

export interface ProbeEnv {
  hasNavigatorGpu: boolean;
  acquireGpu?: () => Promise<{ selfTest: () => Promise<{ ok: boolean; reason?: string }> } | null>;
  wasmSimd: boolean;
  wasmSha?: { scalar: boolean; simd: boolean; selfTest: (simd: boolean) => boolean };
  browserCpuSelfTest: () => boolean;
  bridge?: BridgeInfo;
}

export interface ProbeResult { selected: BackendId; decisions: Decision[] }

export async function probeBackends(env: ProbeEnv): Promise<ProbeResult> {
  const d: Decision[] = [];

  // WEBGPU
  if (!env.hasNavigatorGpu) d.push({ id: "WEBGPU", ok: false, reason: "navigator.gpu is not available in this browser" });
  else if (!env.acquireGpu) d.push({ id: "WEBGPU", ok: false, reason: "no adapter acquisition available" });
  else {
    try {
      const gpu = await env.acquireGpu();
      if (!gpu) d.push({ id: "WEBGPU", ok: false, reason: "no WebGPU adapter or device could be acquired" });
      else {
        const t = await gpu.selfTest();
        d.push(t.ok ? { id: "WEBGPU", ok: true, reason: "device acquired; self-test matched the CPU reference" }
                    : { id: "WEBGPU", ok: false, reason: `self-test failed: ${t.reason ?? "unknown"}` });
      }
    } catch (e) {
      d.push({ id: "WEBGPU", ok: false, reason: `WebGPU failed: ${String(e)}` });
    }
  }

  // WASM tiers
  const sha = env.wasmSha;
  if (!sha) {
    d.push({ id: "WASM_SIMD", ok: false, reason: "no SHA-256 WebAssembly module is bundled in this build" });
    d.push({ id: "WASM_SCALAR", ok: false, reason: "no SHA-256 WebAssembly module is bundled in this build" });
  } else {
    if (!env.wasmSimd) d.push({ id: "WASM_SIMD", ok: false, reason: "WebAssembly SIMD is not supported by this browser" });
    else if (!sha.simd) d.push({ id: "WASM_SIMD", ok: false, reason: "the bundled module has no SIMD variant" });
    else d.push(sha.selfTest(true) ? { id: "WASM_SIMD", ok: true, reason: "SIMD module self-test matched the CPU reference" }
                                    : { id: "WASM_SIMD", ok: false, reason: "SIMD module self-test failed" });
    if (!sha.scalar) d.push({ id: "WASM_SCALAR", ok: false, reason: "the bundled module has no scalar variant" });
    else d.push(sha.selfTest(false) ? { id: "WASM_SCALAR", ok: true, reason: "scalar module self-test matched the CPU reference" }
                                     : { id: "WASM_SCALAR", ok: false, reason: "scalar module self-test failed" });
  }

  // BROWSER_CPU
  d.push(env.browserCpuSelfTest()
    ? { id: "BROWSER_CPU", ok: true, reason: "TypeScript reference matched the known-answer vectors" }
    : { id: "BROWSER_CPU", ok: false, reason: "TypeScript reference failed its known-answer test" });

  // Bridge-dependent backends
  const br = env.bridge;
  d.push({ id: "LOCAL_NATIVE", ok: !!br?.reachable && br.nativeBackend,
    reason: !br?.reachable ? "no local bridge connected" : br.nativeBackend ? "bridge advertises a native backend" : "bridge reports no installed native backend" });
  d.push({ id: "ASIC_BM1366", ok: !!br?.reachable && br.deviceAllowlisted && br.supportsJobType,
    reason: !br?.reachable ? "no local bridge connected"
      : !br.deviceAllowlisted ? "the allowlisted unit is not confirmed"
      : !br.supportsJobType ? "no supported ASIC job type is exposed (SHA-256d mining jobs only, no round access)"
      : "allowlisted unit confirmed; SHA-256d mining-style jobs only" });

  const order: BackendId[] = ["WEBGPU", "WASM_SIMD", "WASM_SCALAR", "BROWSER_CPU"];
  const pick = order.find((id) => d.find((x) => x.id === id)?.ok);
  d.push({ id: "DEMO_SIMULATED", ok: true, reason: "deterministic simulated fixtures; never hardware" });
  return { selected: pick ?? "DEMO_SIMULATED", decisions: d };
}

/** Feature-test WebAssembly SIMD with a minimal module (v128.const + i8x16 op). */
export function detectWasmSimd(): boolean {
  try {
    return typeof WebAssembly === "object" && WebAssembly.validate(
      new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11]));
  } catch { return false; }
}
