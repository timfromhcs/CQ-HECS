// WebGPU -> WASM fallback policy (W4-09).
//
// The WebGPU engine is an optional f32 accelerator. When it fails at run time (the device is
// lost, an allocation fails, validation fails) the run is repeated on the exact WASM f64 core
// and the result says so. A silent engine swap is not allowed: the result carries a
// `Fallback` record that the UI, the provenance list and the exported run card all show.
// A deliberate cancellation is not a failure and never triggers a fallback.

export type FallbackKind = "device-lost" | "gpu-error";

export interface Fallback {
  from: "webgpu";
  to: "wasm";
  kind: FallbackKind;
  /** Raw reason from the browser or the engine; shown as data, never interpreted. */
  reason: string;
}

/** The GPU device was lost (driver reset, tab backgrounded, adapter removed). */
export class GpuLossError extends Error {
  constructor(public readonly lossReason: string, message?: string) {
    super(message ?? `WebGPU device lost: ${lossReason}`);
    this.name = "GpuLossError";
  }
}

/** The run was cancelled on purpose; the caller must not fall back. */
export const CANCELLED_MESSAGE = "abgebrochen";

export function classifyGpuFailure(e: unknown): Fallback | null {
  if (e instanceof GpuLossError) {
    return { from: "webgpu", to: "wasm", kind: "device-lost", reason: e.lossReason };
  }
  const message = String((e as Error | undefined)?.message ?? e);
  if (message === CANCELLED_MESSAGE) return null;
  return { from: "webgpu", to: "wasm", kind: "gpu-error", reason: message };
}

export interface Fallen<R> {
  result: R;
  fallback?: Fallback;
}

/**
 * Run `primary` (WebGPU). If it fails for a non-cancel reason, run `secondary` (WASM) and
 * attach the fallback record. If the fallback also fails, the error names both causes so the
 * user sees that neither engine could run the circuit; no partial result is produced.
 */
export async function runWithFallback<R>(
  primary: () => Promise<R>,
  secondary: () => Promise<R>,
  onFallback?: (f: Fallback) => void,
): Promise<Fallen<R>> {
  try {
    return { result: await primary() };
  } catch (e) {
    const fb = classifyGpuFailure(e);
    if (!fb) throw e;
    onFallback?.(fb);
    try {
      return { result: await secondary(), fallback: fb };
    } catch (e2) {
      throw new Error(`WebGPU failed (${fb.kind}: ${fb.reason}); WASM fallback also failed: ${String((e2 as Error).message ?? e2)}`);
    }
  }
}

/** One line for the run card's `limits` list, so an exported card records the swap. */
export function fallbackLimit(fb: Fallback): string {
  return `Requested WebGPU f32 but the run used WASM f64: ${fb.kind} (${fb.reason}). The result is the exact f64 core's.`;
}
