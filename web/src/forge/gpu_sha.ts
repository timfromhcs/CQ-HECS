// WebGPU batch SHA-256 compression (one 64-byte block per invocation, standard IV).
// Integer-only u32 arithmetic; no f32 anywhere. Every batch is only trusted after
// `webgpuSelfTest()` matched the CPU reference.

import { IV, K, blockWords, compress, pad } from "./sha";

export const MAX_BATCH = 1 << 16; // bounded dispatch: 65 536 blocks = 4 MiB input

const WGSL = /* wgsl */ `
@group(0) @binding(0) var<storage, read> input : array<u32>;
@group(0) @binding(1) var<storage, read_write> output : array<u32>;
@group(0) @binding(2) var<storage, read> kconst : array<u32, 64>;
@group(0) @binding(3) var<uniform> params : vec4<u32>; // x = block count, y = rounds

fn rotr(x: u32, n: u32) -> u32 { return (x >> n) | (x << (32u - n)); }

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid : vec3<u32>) {
  let idx = gid.x;
  if (idx >= params.x) { return; }
  var w : array<u32, 64>;
  for (var i = 0u; i < 16u; i = i + 1u) { w[i] = input[idx * 16u + i]; }
  for (var t = 16u; t < 64u; t = t + 1u) {
    let a = w[t - 15u]; let b = w[t - 2u];
    let s0 = rotr(a, 7u) ^ rotr(a, 18u) ^ (a >> 3u);
    let s1 = rotr(b, 17u) ^ rotr(b, 19u) ^ (b >> 10u);
    w[t] = s1 + w[t - 7u] + s0 + w[t - 16u];
  }
  var h = array<u32, 8>(0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au, 0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u);
  var a = h[0]; var b = h[1]; var c = h[2]; var d = h[3];
  var e = h[4]; var f = h[5]; var g = h[6]; var hh = h[7];
  for (var t = 0u; t < params.y; t = t + 1u) {
    let S1 = rotr(e, 6u) ^ rotr(e, 11u) ^ rotr(e, 25u);
    let ch = (e & f) ^ (~e & g);
    let t1 = hh + S1 + ch + kconst[t] + w[t];
    let S0 = rotr(a, 2u) ^ rotr(a, 13u) ^ rotr(a, 22u);
    let mj = (a & b) ^ (a & c) ^ (b & c);
    let t2 = S0 + mj;
    hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
  }
  let outv = array<u32, 8>(a + h[0], b + h[1], c + h[2], d + h[3], e + h[4], f + h[5], g + h[6], hh + h[7]);
  for (var i = 0u; i < 8u; i = i + 1u) { output[idx * 8u + i] = outv[i]; }
}
`;

export interface GpuSha {
  compressBatch(blocks: Uint32Array, rounds?: number): Promise<Uint32Array>;
  lost: Promise<string>;
}

export async function createGpuSha(device: GPUDevice): Promise<GpuSha> {
  const module = device.createShaderModule({ code: WGSL });
  const info = await module.getCompilationInfo();
  const errors = info.messages.filter((m) => m.type === "error");
  if (errors.length) throw new Error("WGSL compilation failed: " + errors.map((e) => e.message).join("; "));
  const pipeline = await device.createComputePipelineAsync({ layout: "auto", compute: { module, entryPoint: "main" } });
  const kBuf = device.createBuffer({ size: 256, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
  device.queue.writeBuffer(kBuf, 0, K as unknown as BufferSource);
  const lost = device.lost.then((i) => `device lost: ${i.reason} ${i.message}`);

  return {
    lost,
    async compressBatch(blocks, rounds = 64) {
      if (blocks.length % 16 !== 0) throw new Error("blocks must be a multiple of 16 words");
      const n = blocks.length / 16;
      if (n === 0 || n > MAX_BATCH) throw new Error(`batch size must be 1..${MAX_BATCH}`);
      if (rounds < 0 || rounds > 64) throw new Error("rounds must be between 0 and 64");
      const inBuf = device.createBuffer({ size: blocks.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
      const outSize = n * 32;
      const outBuf = device.createBuffer({ size: outSize, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC });
      const readBuf = device.createBuffer({ size: outSize, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
      const pBuf = device.createBuffer({ size: 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
      device.queue.writeBuffer(inBuf, 0, blocks as unknown as BufferSource);
      device.queue.writeBuffer(pBuf, 0, new Uint32Array([n, rounds, 0, 0]));
      const bind = device.createBindGroup({
        layout: pipeline.getBindGroupLayout(0),
        entries: [
          { binding: 0, resource: { buffer: inBuf } }, { binding: 1, resource: { buffer: outBuf } },
          { binding: 2, resource: { buffer: kBuf } }, { binding: 3, resource: { buffer: pBuf } },
        ],
      });
      const enc = device.createCommandEncoder();
      const pass = enc.beginComputePass();
      pass.setPipeline(pipeline);
      pass.setBindGroup(0, bind);
      pass.dispatchWorkgroups(Math.ceil(n / 64));
      pass.end();
      enc.copyBufferToBuffer(outBuf, 0, readBuf, 0, outSize);
      device.queue.submit([enc.finish()]);
      await readBuf.mapAsync(GPUMapMode.READ);
      const result = new Uint32Array(readBuf.getMappedRange().slice(0));
      readBuf.unmap();
      for (const b of [inBuf, outBuf, readBuf, pBuf]) b.destroy();
      return result;
    },
  };
}

/** Deterministic blocks used for the self-test (padding of fixed messages + pseudo-random words). */
export function selfTestBlocks(): Uint32Array {
  const msgs = [new Uint8Array(0), new TextEncoder().encode("abc"), new TextEncoder().encode("a".repeat(55))];
  const out = new Uint32Array(16 * (msgs.length + 5));
  msgs.forEach((m, i) => out.set(blockWords(pad(m).subarray(0, 64)), i * 16));
  let s = 0x9e3779b9;
  for (let i = msgs.length * 16; i < out.length; i++) {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    out[i] = s;
  }
  return out;
}

export function cpuBatch(blocks: Uint32Array, rounds = 64): Uint32Array {
  const out = new Uint32Array((blocks.length / 16) * 8);
  for (let i = 0; i < blocks.length / 16; i++) out.set(compress(IV, blocks.subarray(i * 16, i * 16 + 16), rounds), i * 8);
  return out;
}

export async function webgpuSelfTest(gpu: GpuSha): Promise<{ ok: boolean; reason?: string }> {
  try {
    const blocks = selfTestBlocks();
    for (const rounds of [64, 20]) {
      const got = await gpu.compressBatch(blocks, rounds);
      const want = cpuBatch(blocks, rounds);
      for (let i = 0; i < want.length; i++) if (got[i] !== want[i]) return { ok: false, reason: `mismatch at word ${i} (rounds=${rounds})` };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, reason: String(e) };
  }
}
