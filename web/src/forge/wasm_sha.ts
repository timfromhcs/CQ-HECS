// Loader for the SHA-256 exports of the bundled WebAssembly core.
//
// The page must be able to say "the WASM tier is available" only after this
// module has actually computed a known answer, so `selfTest()` is what the backend
// probe calls — the loader does not trust that instantiating the module means it
// works (a wrong export name, a stale binary or a broken build all instantiate
// fine and then produce garbage).
//
// The module is the same `public/cqhecs_core.wasm` the state-vector emulator uses:
// one artefact, two capabilities, one hash in the release record.

export interface WasmSha {
  /** A scalar SHA-256 implementation is present and passed its self-test. */
  scalar: boolean;
  /** No SIMD variant is built on purpose; see the module's source comment. */
  simd: boolean;
  /** Re-runs the known-answer test; `simd` is accepted for the probe's signature. */
  selfTest: (simd: boolean) => boolean;
  /** SHA-256 of the given bytes, or null when the module is unusable. */
  sha256: (message: Uint8Array) => Uint8Array | null;
  sha256d: (message: Uint8Array) => Uint8Array | null;
  /** Why the module is unusable, if it is. */
  loadError?: string;
}

interface ShaExports {
  memory: WebAssembly.Memory;
  buf_alloc(bytes: number): number;
  sha256(data: number, len: number, out: number): number;
  sha256d(data: number, len: number, out: number): number;
}

const KAT_INPUT = "616263";
const KAT_DIGEST = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

const toHex = (bytes: Uint8Array): string => Array.from(bytes, (x) => x.toString(16).padStart(2, "0")).join("");

/** Fetches and instantiates the core; never throws. */
export async function loadWasmSha(url = "/cqhecs_core.wasm"): Promise<WasmSha | undefined> {
  let exports: ShaExports;
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      return undefined;
    }
    const { instance } = await WebAssembly.instantiateStreaming(response.clone(), {}).catch(async () => {
      // Some servers serve the .wasm with the wrong MIME type; instantiate from bytes.
      const bytes = await response.arrayBuffer();
      return WebAssembly.instantiate(bytes, {});
    });
    exports = instance.exports as unknown as ShaExports;
  } catch {
    return undefined;
  }

  if (typeof exports.sha256 !== "function" || typeof exports.buf_alloc !== "function") {
    return { scalar: false, simd: false, selfTest: () => false, sha256: () => null, sha256d: () => null, loadError: "the module has no sha256 export" };
  }

  const call = (message: Uint8Array, fn: (inPtr: number, outPtr: number) => number): Uint8Array | null => {
    const inPtr = exports.buf_alloc(Math.max(message.length, 1));
    const outPtr = exports.buf_alloc(32);
    if (!inPtr || !outPtr) {
      return null;
    }
    new Uint8Array(exports.memory.buffer).set(message, inPtr);
    if (fn(inPtr, outPtr) !== 0) {
      return null;
    }
    return new Uint8Array(exports.memory.buffer.slice(outPtr, outPtr + 32));
  };

  const sha256 = (message: Uint8Array) => call(message, (i, o) => exports.sha256(i, message.length, o));
  const sha256d = (message: Uint8Array) => call(message, (i, o) => exports.sha256d(i, message.length, o));

  const selfTest = (): boolean => {
    const digest = sha256(new TextEncoder().encode("abc"));
    return digest !== null && toHex(digest) === KAT_DIGEST;
  };

  const scalar = selfTest();
  return {
    scalar,
    simd: false,
    selfTest,
    sha256,
    sha256d,
    loadError: scalar ? undefined : `self-test failed for ${KAT_INPUT}`,
  };
}

/** Exposed for tests: the expected digest of the self-test input. */
export const SELF_TEST_DIGEST = KAT_DIGEST;
