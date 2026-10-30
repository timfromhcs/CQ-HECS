// WebGPU state-vector engine (f32). WGSL has no f64, so this path is fast but
// single precision (~1e-7 per amplitude); the exact path is the WASM f64 core.
// The browser maps WebGPU to Vulkan, Direct3D 12 or Metal underneath.

import type { Op } from "./circuit";

const SHADER = /* wgsl */ `
struct Params {
  tq: u32,
  ctrl: u32,
  half: u32,
  stride: u32,
  m0: vec4<f32>,
  m1: vec4<f32>,
};
@group(0) @binding(0) var<storage, read_write> amp: array<vec2<f32>>;
@group(0) @binding(1) var<uniform> P: Params;

fn cmul(a: vec2<f32>, b: vec2<f32>) -> vec2<f32> {
  return vec2<f32>(a.x * b.x - a.y * b.y, a.x * b.y + a.y * b.x);
}

@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let idx = gid.y * P.stride + gid.x;
  if (idx >= P.half) { return; }
  let tbit = 1u << P.tq;
  let lo = idx & (tbit - 1u);
  let i = ((idx - lo) << 1u) | lo;
  if ((i & P.ctrl) != P.ctrl) { return; }
  let j = i | tbit;
  let x = amp[i];
  let y = amp[j];
  amp[i] = cmul(P.m0.xy, x) + cmul(P.m0.zw, y);
  amp[j] = cmul(P.m1.xy, x) + cmul(P.m1.zw, y);
}
`;

const PARAM_STRIDE = 256; // minUniformBufferOffsetAlignment upper bound
const BATCH = 512; // ops per command buffer

export class GpuEngine {
  private constructor(
    private device: GPUDevice,
    private pipeline: GPUComputePipeline,
    public readonly maxBytes: number,
  ) {}

  static async create(): Promise<GpuEngine> {
    if (!("gpu" in navigator) || !navigator.gpu) throw new Error("WebGPU nicht verfügbar");
    const adapter = await navigator.gpu.requestAdapter({ powerPreference: "high-performance" });
    if (!adapter) throw new Error("kein WebGPU-Adapter");
    const maxBytes = Math.min(adapter.limits.maxStorageBufferBindingSize, adapter.limits.maxBufferSize);
    const device = await adapter.requestDevice({
      requiredLimits: {
        maxStorageBufferBindingSize: adapter.limits.maxStorageBufferBindingSize,
        maxBufferSize: adapter.limits.maxBufferSize,
      },
    });
    // WebGPU reports shader and validation failures asynchronously and would
    // otherwise leave the state untouched; surface them as an exception.
    device.pushErrorScope("validation");
    const module = device.createShaderModule({ code: SHADER });
    const pipeline = device.createComputePipeline({ layout: "auto", compute: { module, entryPoint: "main" } });
    const error = await device.popErrorScope();
    if (error) throw new Error(`WebGPU-Shader ungültig: ${error.message}`);
    return new GpuEngine(device, pipeline, maxBytes);
  }

  maxQubits(): number {
    return Math.floor(Math.log2(this.maxBytes / 8));
  }

  /** Run the unitary ops of a circuit from |0…0>; returns the f32 amplitudes. */
  async run(n: number, ops: Op[], shouldStop: () => boolean): Promise<Float32Array> {
    const bytes = 8 * 2 ** n;
    if (bytes > this.maxBytes) throw new Error(`GPU-Puffer zu klein für ${n} Qubits`);
    const device = this.device;
    const state = device.createBuffer({
      size: bytes,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST,
    });
    device.queue.writeBuffer(state, 0, new Float32Array([1, 0]));
    const unitary = ops.filter((o) => o.kind === "u") as Extract<Op, { kind: "u" }>[];
    const half = 2 ** (n - 1);
    const groups = Math.ceil(half / 256);
    const gx = Math.min(groups, 65535);
    const gy = Math.ceil(groups / gx);
    const params = device.createBuffer({
      size: PARAM_STRIDE * Math.max(1, Math.min(BATCH, unitary.length)),
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });
    const layout = this.pipeline.getBindGroupLayout(0);
    try {
      for (let start = 0; start < unitary.length; start += BATCH) {
        if (shouldStop()) throw new Error("abgebrochen");
        const chunk = unitary.slice(start, start + BATCH);
        const data = new ArrayBuffer(PARAM_STRIDE * chunk.length);
        chunk.forEach((op, k) => {
          const u = new Uint32Array(data, k * PARAM_STRIDE, 4);
          u.set([op.target, op.ctrl, half, gx * 256]);
          new Float32Array(data, k * PARAM_STRIDE + 16, 8).set(op.m);
        });
        device.queue.writeBuffer(params, 0, data);
        const encoder = device.createCommandEncoder();
        chunk.forEach((_, k) => {
          const bind = device.createBindGroup({
            layout,
            entries: [
              { binding: 0, resource: { buffer: state } },
              { binding: 1, resource: { buffer: params, offset: k * PARAM_STRIDE, size: 48 } },
            ],
          });
          const pass = encoder.beginComputePass();
          pass.setPipeline(this.pipeline);
          pass.setBindGroup(0, bind);
          pass.dispatchWorkgroups(gx, gy);
          pass.end();
        });
        device.pushErrorScope("validation");
        device.pushErrorScope("out-of-memory");
        device.queue.submit([encoder.finish()]);
        const oom = await device.popErrorScope();
        const invalid = await device.popErrorScope();
        if (oom || invalid) throw new Error(`WebGPU-Fehler: ${(oom ?? invalid)!.message}`);
        await device.queue.onSubmittedWorkDone();
      }
      const read = device.createBuffer({ size: bytes, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST });
      const encoder = device.createCommandEncoder();
      encoder.copyBufferToBuffer(state, 0, read, 0, bytes);
      device.queue.submit([encoder.finish()]);
      await read.mapAsync(GPUMapMode.READ);
      const out = new Float32Array(read.getMappedRange().slice(0));
      read.unmap();
      read.destroy();
      return out;
    } finally {
      state.destroy();
      params.destroy();
    }
  }
}
