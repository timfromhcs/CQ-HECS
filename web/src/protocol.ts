// Messages between the UI thread and the engine worker.

import type { Op } from "./circuit";

export type EngineKind = "wasm" | "webgpu";

/**
 * Noise model. Channels follow the CQ-HECS Python definitions (M-FIT-2):
 * - p1: single-qubit depolarizing after every 1-qubit gate,
 * - p2: two-qubit depolarizing E(rho) = (1-p) rho + p I/4 after every 2-qubit gate
 *   (gates with 3+ qubits: single-qubit depolarizing p2 on each involved qubit),
 * - readout: per-qubit asymmetric p01 (read 1 on |0>) and p10 (read 0 on |1>),
 * - xflip: bit-flip after each X gate on qubits with a measured X anomaly.
 */
export interface Noise {
  p1: number;
  p2: number;
  /** Symmetric readout error, used when p01/p10 are not given. */
  readout: number;
  p01?: number[];
  p10?: number[];
  xflip?: number[];
  /** Measured profile id, for display only. */
  profile?: string;
}

export interface RunRequest {
  type: "run";
  id: number;
  numQubits: number;
  numClbits: number;
  ops: Op[];
  shots: number;
  seed: number;
  engine: EngineKind;
  noise: Noise;
}

export interface EngineInfo {
  wasm: { ok: boolean; simd: boolean; bytes: number; error?: string };
  /** Amplitude updates per second of the WASM kernel, measured at 18 qubits. */
  wasmRate: number;
  gpu: { ok: boolean; maxQubits: number; maxBytes: number; error?: string };
}

export interface RunResult {
  id: number;
  engine: EngineKind;
  numQubits: number;
  shots: number;
  counts: Record<string, number>;
  /** Exact probabilities of the most likely basis states (noiseless state, n <= 22). */
  exact: { bits: string; p: number }[];
  /** Up to 64 amplitudes for small circuits (n <= 6). */
  amplitudes: { bits: string; re: number; im: number }[];
  bloch: [number, number, number][];
  norm: number;
  elapsedMs: number;
  mode: "sampled" | "trajectories";
  trajectories: number;
  /** For WebGPU runs (n <= 20): total-variation distance to the exact WASM f64 result; not part of elapsedMs. */
  crossCheckTv?: number;
}

export type WorkerRequest =
  | { type: "init" }
  | { type: "sat"; id: number; dimacs: string; timeoutMs: number }
  | { type: "sweep"; id: number; numVars: number; ratios: number[]; trials: number; timeoutMs: number }
  | { type: "probe"; numQubits: number }
  | RunRequest
  | { type: "stop" };

export type WorkerResponse =
  | { type: "init"; info: EngineInfo }
  | { type: "probe"; numQubits: number; ok: boolean }
  | { type: "progress"; id: number; fraction: number; label: string }
  | { type: "result"; result: RunResult }
  | { type: "error"; id: number; message: string }
  | { type: "sat"; id: number; result: import("./sat").SatResult; numVars: number; numClauses: number }
  | { type: "sweep"; id: number; points: import("./sat").SweepPoint[] };
