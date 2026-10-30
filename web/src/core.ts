// Thin typed wrapper around the Rust/WebAssembly f64 core. Used by the worker
// and by the Node test suite, so both exercise the same code path.

import type { Mat2, Op } from "./circuit";

interface Exports {
  memory: WebAssembly.Memory;
  sv_init(n: number): number;
  sv_free(): void;
  sv_ptr(): number;
  sv_reset(): void;
  buf_alloc(bytes: number): number;
  buf_free(ptr: number, bytes: number): void;
  apply_u(t: number, c: number, ...m: number[]): void;
  sv_norm(): number;
  probs_into(ptr: number): void;
  bloch_into(q: number, ptr: number): void;
  sample_into(shots: number, seed: number, scratch: number, out: number): void;
  measure_qubit(q: number, r: number): number;
}

export class Core {
  private constructor(private x: Exports, public readonly bytes: number) {}
  numQubits = 0;

  static async load(source: BufferSource): Promise<Core> {
    const { instance } = await WebAssembly.instantiate(source, {});
    return new Core(instance.exports as unknown as Exports, source.byteLength);
  }

  /** Allocate |0…0>. Returns false when the memory cannot be reserved. */
  init(n: number): boolean {
    let ok = false;
    try {
      ok = this.x.sv_init(n) === 0;
    } catch {
      ok = false; // memory.grow refused by the engine
    }
    this.numQubits = ok ? n : 0;
    return ok;
  }

  free() { this.x.sv_free(); this.numQubits = 0; }
  reset() { this.x.sv_reset(); }
  norm() { return this.x.sv_norm(); }

  apply(target: number, ctrl: number, m: Mat2) {
    this.x.apply_u(target, ctrl, m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7]);
  }

  applyOps(ops: Op[]) {
    for (const op of ops) if (op.kind === "u") this.apply(op.target, op.ctrl, op.m);
  }

  /** View on the live state; re-create after any allocation (memory may grow). */
  amplitudes(): Float64Array {
    return new Float64Array(this.x.memory.buffer, this.x.sv_ptr(), 2 * 2 ** this.numQubits);
  }

  probabilities(): Float64Array {
    const dim = 2 ** this.numQubits;
    const ptr = this.x.buf_alloc(8 * dim);
    if (!ptr) throw new Error("kein Speicher für Wahrscheinlichkeiten");
    try {
      this.x.probs_into(ptr);
      return new Float64Array(this.x.memory.buffer, ptr, dim).slice();
    } finally {
      this.x.buf_free(ptr, 8 * dim);
    }
  }

  bloch(q: number): [number, number, number] {
    const ptr = this.x.buf_alloc(24);
    try {
      this.x.bloch_into(q, ptr);
      const v = new Float64Array(this.x.memory.buffer, ptr, 3);
      return [v[0], v[1], v[2]];
    } finally {
      this.x.buf_free(ptr, 24);
    }
  }

  /** Draw basis indices with a reproducible seed. */
  sample(shots: number, seed: number): Uint32Array {
    const scratch = this.x.buf_alloc(8 * shots);
    const out = this.x.buf_alloc(4 * shots);
    if (!scratch || !out) throw new Error("kein Speicher für Shots");
    try {
      this.x.sample_into(shots, seed, scratch, out);
      return new Uint32Array(this.x.memory.buffer, out, shots).slice();
    } finally {
      this.x.buf_free(scratch, 8 * shots);
      this.x.buf_free(out, 4 * shots);
    }
  }

  measure(q: number, r: number): number {
    return this.x.measure_qubit(q, r);
  }
}

/** Small seeded PRNG (mulberry32) for noise and mid-circuit measurements. */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function bitsOf(value: number, width: number): string {
  let s = "";
  for (let b = width - 1; b >= 0; b--) s += (value >>> b) & 1 ? "1" : "0";
  return s;
}
