// One provenance card, same contract as the Python side (`cqhecs/provenance.py`).
//
// The schema lives in `docs/provenance/hcs.run.v2.schema.json` and is the shared source of
// truth: the Python CLI writes cards that validate against it, and this module writes the
// browser's card in the same shape. The digest is always over the payload stored in the
// card, so a reader can check a card without any other file.
import { sha256Hex } from "./digest";
import { enginePrecision, isNoisy, type NoiseLike } from "./noise_predicate";

export const SCHEMA = "hcs.run.v2";

export interface CardInput {
  /** CQ-HECS version from scripts/version.py (injected at build time by Vite). */
  version: string;
  /** Commit the bundle was built from, or "unknown" outside a checkout. */
  revision: string;
  qasm: string;
  shots: number;
  engineRequested: string;
  noise: unknown;
  seed: number;
}

/** The fields of `RunResult` this module needs; kept narrow so it stays testable. */
export interface CardResult {
  engine: string;
  mode: string;
  elapsedMs: number;
  counts?: Record<string, number>;
  exact?: { bits: string; p: number }[];
  amplitudes?: { bits: string; re: number; im: number }[];
  bloch?: [number, number, number][];
  norm?: number;
  trajectories?: number;
  /** WebGPU only: total-variation distance to the exact f64 core, when it was cross-checked. */
  crossCheckTv?: number;
}

export function modeOf(noise: unknown): "SAMPLED" | "NOISY_CLASSICAL" {
  // One definition of "this noise changes the run" (D5). The simulator, the planner and the
  // run card must not disagree, so this delegates to the shared predicate rather than reading
  // only p1/p2/readout and silently mislabelling a per-qubit-readout or X-flip run as SAMPLED.
  return isNoisy(noise as NoiseLike | null | undefined) ? "NOISY_CLASSICAL" : "SAMPLED";
}

/** Why each error kind is null (W4-10): a null means "not quantified", not "zero". */
function errorScope(input: CardInput, result: CardResult): Record<string, string> {
  const precision =
    result.engine === "webgpu"
      ? "float32 (~1e-7 per amplitude)"
      : result.engine === "wasm"
        ? "float64 (~1e-16 per operation)"
        : "unknown precision";
  return {
    approximation: "no deliberate truncation in the browser engines; no numerical-rank floor is applied",
    numerical: `${precision}; not separately quantified in the browser`,
    sampling:
      input.shots > 0
        ? `${input.shots} shots; finite-shot sampling, no total-variation bound is computed in the browser`
        : "not sampled",
  };
}

export async function buildRunCard(
  input: CardInput,
  result: CardResult,
  limits: string[],
  createdAt: Date = new Date(),
): Promise<Record<string, unknown>> {
  if (!input.qasm) throw new Error("a run card needs the QASM text it describes");
  if (limits.length === 0) throw new Error("a run card needs at least one stated limit");
  const digest = await sha256Hex(input.qasm);
  return {
    schema: SCHEMA,
    created_at: createdAt.toISOString().replace(/\.\d{3}Z$/, "Z"),
    software: {
      name: "cqhecs-web",
      version: input.version,
      source_revision: input.revision,
    },
    input: {
      kind: "circuit",
      payload: input.qasm,
      digest_algorithm: "SHA-256",
      digest,
      shots: input.shots,
      engine_requested: input.engineRequested,
      noise: input.noise,
    },
    engine: {
      kind: result.engine,
      precision: enginePrecision(result.engine),
      mode: modeOf(input.noise),
      // The cross-check belongs to the WebGPU f32 path only. It is present as a number when
      // the exact core was available, and explicitly null (never omitted) when it was not.
      ...(result.engine === "webgpu" ? { cross_check_tv: result.crossCheckTv ?? null } : {}),
    },
    seed: input.seed,
    result: {
      status: "OK",
      elapsed_ms: result.elapsedMs,
      error: { approximation: null, numerical: null, sampling: null },
      error_scope: errorScope(input, result),
      counts: result.counts ?? {},
      exact: result.exact ?? [],
      amplitudes: result.amplitudes ?? [],
      bloch: result.bloch ?? [],
      norm: result.norm ?? null,
      trajectories: result.trajectories ?? 0,
    },
    limits,
  };
}
