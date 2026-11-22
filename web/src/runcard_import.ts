// Run-card import (W13). The export side is `provenance.ts`; this is its inverse.
//
// Importing a card does NOT trust it. What is taken from it is only what can be checked
// without the exporting machine: the QASM text (its SHA-256 must equal the card's digest and it
// must parse with this page's own parser), the shot count, the seed, the requested engine. The
// result numbers inside the card are never displayed as if this page had computed them: the
// user re-runs the circuit and compares. A card that fails any check is refused with a code.
import { parseQasm } from "./circuit";
import { sha256Hex } from "./digest";
import { SCHEMA } from "./provenance";

export const MAX_CARD_BYTES = 2 * 1024 * 1024;
export const MAX_SHOTS = 1_000_000;

export type ImportCode =
  | "too_large"
  | "not_json"
  | "wrong_schema"
  | "not_a_circuit"
  | "digest_mismatch"
  | "qasm_invalid"
  | "bad_shots"
  | "bad_seed"
  | "bad_engine";

export type ImportResult =
  | { ok: true; qasm: string; shots: number; seed: number; engine: "wasm" | "webgpu"; digest: string; hasResult: boolean; version: string }
  | { ok: false; code: ImportCode; message: string };

const fail = (code: ImportCode, message: string): ImportResult => ({ ok: false, code, message });

export async function parseRunCard(text: string): Promise<ImportResult> {
  if (new TextEncoder().encode(text).length > MAX_CARD_BYTES) return fail("too_large", `the card is larger than ${MAX_CARD_BYTES} bytes`);
  let card: any;
  try { card = JSON.parse(text); } catch { return fail("not_json", "the file is not valid JSON"); }
  if (!card || typeof card !== "object" || Array.isArray(card)) return fail("not_json", "the JSON is not an object");
  if (card.schema !== SCHEMA) return fail("wrong_schema", `expected schema ${SCHEMA}, found ${String(card.schema).slice(0, 40)}`);
  const input = card.input;
  if (!input || input.kind !== "circuit" || typeof input.payload !== "string" || input.payload.length === 0) {
    return fail("not_a_circuit", "the card does not carry a circuit payload");
  }
  if (input.digest_algorithm !== "SHA-256" || typeof input.digest !== "string") return fail("digest_mismatch", "the card has no SHA-256 digest");
  const actual = await sha256Hex(input.payload);
  if (actual !== input.digest.toLowerCase()) return fail("digest_mismatch", "the digest does not match the payload; the card was edited or damaged");
  try { parseQasm(input.payload); } catch (e) { return fail("qasm_invalid", `the payload is not accepted by this page's parser: ${(e as Error).message}`); }
  const shots = input.shots;
  if (!Number.isInteger(shots) || shots < 1 || shots > MAX_SHOTS) return fail("bad_shots", `shots must be an integer from 1 to ${MAX_SHOTS}`);
  const seed = card.seed;
  if (!Number.isInteger(seed) || seed < 0 || seed > 2 ** 31) return fail("bad_seed", "seed must be a non-negative integer");
  const engine = input.engine_requested ?? "wasm";
  if (engine !== "wasm" && engine !== "webgpu") return fail("bad_engine", "engine_requested must be wasm or webgpu");
  return {
    ok: true,
    qasm: input.payload,
    shots,
    seed,
    engine,
    digest: actual,
    hasResult: !!card.result && typeof card.result === "object",
    version: String(card.software?.version ?? "unknown").slice(0, 32),
  };
}
