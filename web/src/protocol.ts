// Messages between the UI thread and the engine worker.

import type { Op } from "./circuit";

export type EngineKind = "wasm" | "webgpu";

export interface Noise {
  /** Depolarizing probability after each 1-qubit gate. */
  p1: number;
  /** Depolarizing probability after each multi-qubit gate (per involved qubit). */
  p2: number;
  /** Classical bit-flip probability on each measured bit. */
  readout: number;
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
  | { type: "probe"; numQubits: number }
  | RunRequest
  | { type: "stop" };

export type WorkerResponse =
  | { type: "init"; info: EngineInfo }
  | { type: "probe"; numQubits: number; ok: boolean }
  | { type: "progress"; id: number; fraction: number; label: string }
  | { type: "result"; result: RunResult }
  | { type: "error"; id: number; message: string };
