// One provenance card, same contract as the Python side (`cqhecs/provenance.py`).
//
// The schema lives in `docs/provenance/hcs.run.v2.schema.json` and is the shared source of
// truth: the Python CLI writes cards that validate against it, and this module writes the
// browser's card in the same shape. The digest is always over the payload stored in the
// card, so a reader can check a card without any other file.
import { sha256Hex } from "./digest";

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
}

export function modeOf(noise: unknown): "SAMPLED" | "NOISY_CLASSICAL" {
  const channels = (noise ?? {}) as { p1?: number; p2?: number; readout?: number };
  const noisy = Number(channels.p1 ?? 0) > 0 || Number(channels.p2 ?? 0) > 0 || Number(channels.readout ?? 0) > 0;
  if (noisy) return "NOISY_CLASSICAL";
  return "SAMPLED";
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
      precision: result.engine === "wasm" ? "f64" : "f32",
      mode: modeOf(input.noise),
    },
    seed: input.seed,
    result: {
      status: "OK",
      elapsed_ms: result.elapsedMs,
      error: { approximation: null, numerical: null, sampling: null },
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
