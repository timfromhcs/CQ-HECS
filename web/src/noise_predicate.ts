// One definition of "this noise model changes the run", shared by the simulator, the run
// planner, the provenance panel and the run card.
//
// Before this module three places each decided on their own. The simulator looked at p1,
// p2 and the X bit flips (gate noise) and at readout, p01 and p10 (readout noise). The run
// card (`modeOf`) and the provenance panel looked only at p1, p2 and the symmetric readout.
// A measured profile that carries only per-qubit readout error ran with noise, yet its card
// said SAMPLED and its panel said "Noise: none". That is a wrong label on a result, so the
// predicate lives here and nothing else decides it.
//
// This file imports nothing from the UI or the engine, so the Node tests can load it.

/** The fields of `Noise` (protocol.ts) the predicates read. Every field is optional on purpose. */
export interface NoiseLike {
  p1?: number;
  p2?: number;
  readout?: number;
  p01?: number[];
  p10?: number[];
  xflip?: number[];
}

/** A value counts as noise only when it is a finite number above zero. */
function positive(v: unknown): boolean {
  return typeof v === "number" && Number.isFinite(v) && v > 0;
}

function anyPositive(xs: unknown): boolean {
  return Array.isArray(xs) && xs.some(positive);
}

/** Noise applied after gates: it forces trajectories and rules out the WebGPU engine. */
export function hasGateNoise(noise: NoiseLike | null | undefined): boolean {
  if (!noise) return false;
  return positive(noise.p1) || positive(noise.p2) || anyPositive(noise.xflip);
}

/** Noise applied to measured bits only: symmetric `readout`, or per-qubit p01 and p10. */
export function hasReadoutNoise(noise: NoiseLike | null | undefined): boolean {
  if (!noise) return false;
  return positive(noise.readout) || anyPositive(noise.p01) || anyPositive(noise.p10);
}

/** True when any channel changes the run. This is what selects NOISY_CLASSICAL. */
export function isNoisy(noise: NoiseLike | null | undefined): boolean {
  return hasGateNoise(noise) || hasReadoutNoise(noise);
}

export type Precision = "f64" | "f32" | "n/a";

/**
 * The arithmetic precision of an engine, by name. Only the two engines this app ships are
 * known. Any other name is "n/a" (a value the run-card schema allows), not a guess: the card
 * used to report f32 for everything that was not "wasm".
 */
export function enginePrecision(engine: string): Precision {
  if (engine === "wasm") return "f64";
  if (engine === "webgpu") return "f32";
  return "n/a";
}

/** Stable, language-independent refusal code. The `message` is localized; the code is not. */
export const REFUSAL_WEBGPU_UNSUPPORTED = "WEBGPU_UNSUPPORTED_CIRCUIT";

export type WebGpuRefusalReason = "mid_circuit_measurement" | "gate_noise";

/** An error that carries a machine-readable code next to its human message. */
export class RefusalError extends Error {
  readonly code: string;
  readonly reasons: WebGpuRefusalReason[];
  constructor(code: string, reasons: WebGpuRefusalReason[], message: string) {
    super(message);
    this.name = "RefusalError";
    this.code = code;
    this.reasons = reasons;
  }
}

/**
 * Why the WebGPU engine cannot run this circuit, or null when it can. The WebGPU path is a
 * single f32 state vector with terminal measurement, so a mid-circuit measurement or reset
 * (`terminal` false) and any gate noise are refused. Readout noise is applied to the sampled
 * bits afterwards, so it is accepted. `message` is the caller's localized text.
 */
export function webgpuRefusal(terminal: boolean, noise: NoiseLike | null | undefined, message: string): RefusalError | null {
  const reasons: WebGpuRefusalReason[] = [];
  if (!terminal) reasons.push("mid_circuit_measurement");
  if (hasGateNoise(noise)) reasons.push("gate_noise");
  if (reasons.length === 0) return null;
  return new RefusalError(REFUSAL_WEBGPU_UNSUPPORTED, reasons, message);
}
