// SHA-256 per FIPS 180-4 in plain TypeScript with exact u32 arithmetic.
// This is the browser CPU reference path (BROWSER_CPU). Trace values are fixed-width hex
// strings, identical in layout to the Python `hcs.sha.trace.v1` format.

export const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

export const IV = new Uint32Array([
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
]);

export const REGS = ["a", "b", "c", "d", "e", "f", "g", "h"] as const;
export type Reg = (typeof REGS)[number];
export type RegMap = Record<Reg, string>;

const rotr = (x: number, n: number): number => ((x >>> n) | (x << (32 - n))) >>> 0;
const ch = (x: number, y: number, z: number): number => ((x & y) ^ (~x & z)) >>> 0;
const maj = (x: number, y: number, z: number): number => ((x & y) ^ (x & z) ^ (y & z)) >>> 0;
const S0 = (x: number): number => (rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22)) >>> 0;
const S1 = (x: number): number => (rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25)) >>> 0;
const s0 = (x: number): number => (rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3)) >>> 0;
const s1 = (x: number): number => (rotr(x, 17) ^ rotr(x, 19) ^ (x >>> 10)) >>> 0;

export const hex8 = (x: number): string => (x >>> 0).toString(16).padStart(8, "0");

export function pad(message: Uint8Array): Uint8Array {
  const bitLen = BigInt(message.length) * 8n;
  const total = Math.ceil((message.length + 9) / 64) * 64;
  const out = new Uint8Array(total);
  out.set(message);
  out[message.length] = 0x80;
  new DataView(out.buffer).setBigUint64(total - 8, bitLen, false);
  return out;
}

export function blockWords(block: Uint8Array): Uint32Array {
  if (block.length !== 64) throw new Error(`a SHA-256 block is 64 bytes, got ${block.length}`);
  const dv = new DataView(block.buffer, block.byteOffset, 64);
  const w = new Uint32Array(16);
  for (let i = 0; i < 16; i++) w[i] = dv.getUint32(i * 4, false);
  return w;
}

export function schedule(words: Uint32Array): Uint32Array {
  const w = new Uint32Array(64);
  w.set(words);
  for (let t = 16; t < 64; t++) w[t] = (s1(w[t - 2]) + w[t - 7] + s0(w[t - 15]) + w[t - 16]) >>> 0;
  return w;
}

type State = [number, number, number, number, number, number, number, number];

function step(st: State, k: number, w: number): { next: State; t1: number; t2: number } {
  const [a, b, c, d, e, f, g, h] = st;
  const t1 = (h + S1(e) + ch(e, f, g) + k + w) >>> 0;
  const t2 = (S0(a) + maj(a, b, c)) >>> 0;
  return { next: [(t1 + t2) >>> 0, a, b, c, (d + t1) >>> 0, e, f, g], t1, t2 };
}

export function compress(state: ArrayLike<number>, words: Uint32Array, rounds = 64, feedForward = true): Uint32Array {
  if (rounds < 0 || rounds > 64) throw new Error("rounds must be between 0 and 64");
  const w = schedule(words);
  let st = Array.from(state) as State;
  for (let t = 0; t < rounds; t++) st = step(st, K[t], w[t]).next;
  return new Uint32Array(feedForward ? st.map((x, i) => (x + state[i]) >>> 0) : st);
}

export function sha256(message: Uint8Array, iv: ArrayLike<number> = IV): Uint8Array {
  let st: Uint32Array = Uint32Array.from(iv);
  const p = pad(message);
  for (let i = 0; i < p.length; i += 64) st = compress(st, blockWords(p.subarray(i, i + 64)));
  const out = new Uint8Array(32);
  const dv = new DataView(out.buffer);
  st.forEach((x, i) => dv.setUint32(i * 4, x, false));
  return out;
}

export const sha256d = (data: Uint8Array): Uint8Array => sha256(sha256(data));

export const toHex = (b: Uint8Array): string => Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
export function fromHex(s: string): Uint8Array {
  const clean = s.trim().replace(/\s+/g, "");
  if (clean.length % 2 !== 0 || /[^0-9a-fA-F]/.test(clean)) throw new Error("invalid hex");
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(clean.substr(i * 2, 2), 16);
  return out;
}

// ---------------------------------------------------------------- traces

export interface RoundRecord {
  t: number; K: string; W: string; in: RegMap; T1: string; T2: string; out: RegMap;
}
export interface BlockTrace {
  schema: "hcs.sha.trace.v1"; source: "SOFTWARE_REPLAY"; block: string; input_state: string;
  schedule: string[]; rounds_executed: number; feed_forward: boolean; rounds: RoundRecord[]; output_state: string;
}

const regs = (st: ArrayLike<number>): RegMap =>
  Object.fromEntries(REGS.map((r, i) => [r, hex8(st[i])])) as RegMap;
const stateHex = (st: ArrayLike<number>): string => Array.from(st as ArrayLike<number>, hex8).join("");
const parseState = (s: string): Uint32Array => {
  if (s.length !== 64) throw new Error("state hex must be 64 characters");
  return Uint32Array.from({ length: 8 }, (_, i) => parseInt(s.slice(i * 8, i * 8 + 8), 16));
};

export function traceBlock(state: ArrayLike<number>, block: Uint8Array, rounds = 64, feedForward = true): BlockTrace {
  if (rounds < 0 || rounds > 64) throw new Error("rounds must be between 0 and 64");
  const w = schedule(blockWords(block));
  let st = Array.from(state) as State;
  const recs: RoundRecord[] = [];
  for (let t = 0; t < rounds; t++) {
    const { next, t1, t2 } = step(st, K[t], w[t]);
    recs.push({ t, K: hex8(K[t]), W: hex8(w[t]), in: regs(st), T1: hex8(t1), T2: hex8(t2), out: regs(next) });
    st = next;
  }
  const final = feedForward ? st.map((x, i) => (x + state[i]) >>> 0) : st;
  return {
    schema: "hcs.sha.trace.v1", source: "SOFTWARE_REPLAY", block: toHex(block), input_state: stateHex(state),
    schedule: Array.from(w, hex8), rounds_executed: rounds, feed_forward: feedForward, rounds: recs,
    output_state: stateHex(final),
  };
}

/** Re-derive a trace from its inputs and compare every recorded value. */
export function replay(trace: BlockTrace): string {
  const fresh = traceBlock(parseState(trace.input_state), fromHex(trace.block), trace.rounds_executed, trace.feed_forward);
  if (trace.rounds.length !== fresh.rounds.length) throw new Error("round count differs");
  for (let i = 0; i < fresh.rounds.length; i++) {
    if (JSON.stringify(trace.rounds[i]) !== JSON.stringify(fresh.rounds[i])) throw new Error(`round ${i} differs from the reference`);
  }
  if (JSON.stringify(trace.schedule) !== JSON.stringify(fresh.schedule)) throw new Error("message schedule differs");
  if (trace.output_state !== fresh.output_state) throw new Error("output state differs");
  return fresh.output_state;
}

export interface MessageTrace {
  schema: "hcs.sha.message_trace.v1"; source: "SOFTWARE_REPLAY"; message_length: number;
  padding: { padded_length: number; bit_length: number; zero_bytes: number; padded_hex: string };
  blocks: BlockTrace[]; digest: string; midstate?: string;
}

export function traceMessage(message: Uint8Array, iv: ArrayLike<number> = IV): MessageTrace {
  const p = pad(message);
  let st: Uint32Array = Uint32Array.from(iv);
  const blocks: BlockTrace[] = [];
  for (let i = 0; i < p.length; i += 64) {
    const tb = traceBlock(st, p.slice(i, i + 64));
    blocks.push(tb);
    st = parseState(tb.output_state);
  }
  return {
    schema: "hcs.sha.message_trace.v1", source: "SOFTWARE_REPLAY", message_length: message.length,
    padding: { padded_length: p.length, bit_length: message.length * 8, zero_bytes: p.length - message.length - 9, padded_hex: toHex(p) },
    blocks, digest: stateHex(st),
  };
}

export interface Sha256dTrace {
  schema: "hcs.sha.sha256d_trace.v1"; source: "SOFTWARE_REPLAY"; header: string;
  first_pass: MessageTrace; second_pass: MessageTrace; double_hash: string; display_hash: string;
}

export function traceSha256d(header: Uint8Array): Sha256dTrace {
  if (header.length !== 80) throw new Error("a Bitcoin block header is exactly 80 bytes");
  const first = traceMessage(header);
  first.midstate = first.blocks[0].output_state;
  const second = traceMessage(fromHex(first.digest));
  const dbl = second.digest;
  return {
    schema: "hcs.sha.sha256d_trace.v1", source: "SOFTWARE_REPLAY", header: toHex(header),
    first_pass: first, second_pass: second, double_hash: dbl,
    display_hash: toHex(fromHex(dbl).reverse()),
  };
}

export function replayCandidate(prefix76: Uint8Array, nonce: number, leadingZeroBits: number) {
  if (prefix76.length !== 76) throw new Error("header prefix must be 76 bytes");
  if (!Number.isInteger(nonce) || nonce < 0 || nonce > 0xffffffff) throw new Error("nonce must be a 32-bit unsigned integer");
  const header = new Uint8Array(80);
  header.set(prefix76);
  new DataView(header.buffer).setUint32(76, nonce, true);
  const display = sha256d(header).reverse();
  let lz = 0;
  for (const b of display) {
    if (b === 0) { lz += 8; continue; }
    lz += Math.clz32(b) - 24;
    break;
  }
  return { source: "SOFTWARE_REPLAY" as const, nonce, hash: toHex(display), leading_zero_bits: lz, required_leading_zero_bits: leadingZeroBits, verified: lz >= leadingZeroBits };
}

export const GENESIS_HEADER_HEX =
  "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c";
export const GENESIS_BLOCK_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f";
