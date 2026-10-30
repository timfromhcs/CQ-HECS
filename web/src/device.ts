// Device capability check and the safe-run policy.
//
// The exact limit is a memory statement: an n-qubit f64 state vector needs
// 16 * 2^n bytes and must fit in the WebAssembly heap (wasm32: 4 GiB address
// space, so at most 2^27 amplitudes) and in a conservative share of the device
// RAM. The limit is then confirmed by actually allocating it in the worker.

import type { EngineInfo } from "./protocol";

export interface DeviceReport {
  os: string;
  browser: string;
  arch: string;
  mobile: boolean;
  cores: number;
  /** navigator.deviceMemory in GiB (Chromium only, rounded and capped at 8). */
  ramGiB: number | null;
  ramSource: string;
  gpuName: string;
  gpuVendor: string;
  gpuBackend: string;
  webgpu: boolean;
  webgl2: boolean;
  crossOriginIsolated: boolean;
}

export interface Limits {
  /** Largest n whose exact f64 state fits the policy budget. */
  exactQubits: number;
  /** Confirmed by a real allocation in the worker. */
  exactVerified: boolean;
  gpuQubits: number;
  budgetBytes: number;
  /** Kernel speed used for runtime estimates (amplitude updates per second). */
  rate: number;
}

const WASM_MAX_QUBITS = 27; // 2^27 * 16 B = 2 GiB of the 4 GiB wasm32 heap
const MAX_RUN_SECONDS = 90;

function detectOs(ua: string, platform: string): string {
  const p = `${platform} ${ua}`;
  if (/Windows/i.test(p)) return "Windows";
  if (/Android/i.test(p)) return "Android";
  if (/iPhone|iPad|iOS/i.test(p)) return "iOS / iPadOS";
  if (/Mac/i.test(p)) return "macOS";
  if (/CrOS/i.test(p)) return "ChromeOS";
  if (/Linux/i.test(p)) return "Linux";
  return platform || "unbekannt";
}

function detectBrowser(ua: string): string {
  const m =
    ua.match(/(Edg)\/([\d]+)/) ?? ua.match(/(OPR)\/([\d]+)/) ?? ua.match(/(Firefox)\/([\d]+)/) ??
    ua.match(/(Chrome)\/([\d]+)/) ?? ua.match(/Version\/([\d]+).*(Safari)/);
  if (!m) return "unbekannt";
  const names: Record<string, string> = { Edg: "Edge", OPR: "Opera" };
  return m[2] === "Safari" ? `Safari ${m[1]}` : `${names[m[1]] ?? m[1]} ${m[2]}`;
}

function likelyBackend(os: string): string {
  switch (os) {
    case "Windows": return "Direct3D 12 (Vulkan nur nativ, nicht im Browser)";
    case "macOS": case "iOS / iPadOS": return "Metal";
    case "Android": case "Linux": case "ChromeOS": return "Vulkan";
    default: return "unbekannt";
  }
}

function webglRenderer(): { name: string; vendor: string; ok: boolean } {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2");
    if (!gl) return { name: "", vendor: "", ok: false };
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const name = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    const vendor = ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return { name: String(name), vendor: String(vendor), ok: true };
  } catch {
    return { name: "", vendor: "", ok: false };
  }
}

export async function detectDevice(): Promise<DeviceReport> {
  const nav = navigator as Navigator & {
    deviceMemory?: number;
    userAgentData?: {
      mobile: boolean;
      platform: string;
      getHighEntropyValues(h: string[]): Promise<Record<string, string>>;
    };
  };
  const ua = navigator.userAgent;
  let platform = nav.userAgentData?.platform ?? "";
  let arch = "";
  let platformVersion = "";
  try {
    const hints = await nav.userAgentData?.getHighEntropyValues(["architecture", "bitness", "platformVersion"]);
    if (hints) {
      arch = [hints.architecture, hints.bitness && `${hints.bitness}-bit`].filter(Boolean).join(" ");
      platformVersion = hints.platformVersion ?? "";
    }
  } catch { /* hints are optional */ }
  let os = detectOs(ua, platform);
  if (os === "Windows" && platformVersion) os = Number(platformVersion.split(".")[0]) >= 13 ? "Windows 11" : "Windows 10";
  const gl = webglRenderer();
  let gpuName = gl.name, gpuVendor = gl.vendor;
  let webgpu = false;
  if (navigator.gpu) {
    try {
      const adapter = await navigator.gpu.requestAdapter({ powerPreference: "high-performance" });
      if (adapter) {
        webgpu = true;
        const info = adapter.info;
        if (info?.description) gpuName = info.description;
        else if (!gpuName && info) gpuName = [info.vendor, info.architecture].filter(Boolean).join(" ");
        if (info?.vendor) gpuVendor = info.vendor;
      }
    } catch { /* WebGPU blocked or unsupported */ }
  }
  return {
    os,
    browser: detectBrowser(ua),
    arch: arch || "unbekannt",
    mobile: nav.userAgentData?.mobile ?? /Mobi|Android|iPhone/i.test(ua),
    cores: navigator.hardwareConcurrency || 1,
    ramGiB: nav.deviceMemory ?? null,
    ramSource: nav.deviceMemory ? "navigator.deviceMemory (gerundet, max. 8)" : "vom Browser nicht gemeldet",
    gpuName: gpuName || "unbekannt",
    gpuVendor: gpuVendor || "",
    gpuBackend: webgpu ? likelyBackend(os.replace(/ \d+$/, "")) : "kein WebGPU",
    webgpu,
    webgl2: gl.ok,
    crossOriginIsolated: self.crossOriginIsolated ?? false,
  };
}

/** Policy: at most a quarter of reported RAM (or 1 GiB / 512 MiB on mobile if unknown). */
export function computeLimits(dev: DeviceReport, engine: EngineInfo): Limits {
  const GiB = 1024 ** 3;
  const ram = dev.ramGiB ?? (dev.mobile ? 2 : 4);
  const budgetBytes = Math.min(ram * GiB * 0.25, 2 * GiB);
  const exactQubits = engine.wasm.ok
    ? Math.max(1, Math.min(WASM_MAX_QUBITS, Math.floor(Math.log2(budgetBytes / 16))))
    : 0;
  const gpuQubits = engine.gpu.ok ? Math.min(engine.gpu.maxQubits, Math.floor(Math.log2(budgetBytes / 8))) : 0;
  return { exactQubits, exactVerified: false, gpuQubits, budgetBytes, rate: engine.wasmRate || 5e7 };
}

export interface Estimate {
  bytes: number;
  seconds: number;
  safe: boolean;
  reason: string;
}

/** Estimate memory and time of a run and decide whether it is a safe run. */
export function estimate(n: number, gateOps: number, shots: number, trajectories: number, limits: Limits, gpu: boolean): Estimate {
  const bytes = (gpu ? 8 : 16) * 2 ** n;
  const replays = Math.max(1, trajectories);
  const gpuSpeedup = gpu ? 8 : 1; // conservative; only used for the guard
  const seconds = ((gateOps + 2) * replays * 2 ** n) / (limits.rate * gpuSpeedup) + shots * 2e-7;
  const max = gpu ? limits.gpuQubits : limits.exactQubits;
  if (n > max) {
    return { bytes, seconds, safe: false, reason: `${n} Qubits überschreiten das sichere Limit von ${max} auf diesem Gerät` };
  }
  if (seconds > MAX_RUN_SECONDS) {
    return { bytes, seconds, safe: false, reason: `geschätzte Laufzeit ${seconds.toFixed(0)} s > ${MAX_RUN_SECONDS} s` };
  }
  return { bytes, seconds, safe: true, reason: "" };
}

export function formatBytes(bytes: number): string {
  const units = ["B", "KiB", "MiB", "GiB"];
  let v = bytes, u = 0;
  while (v >= 1024 && u < units.length - 1) { v /= 1024; u++; }
  return `${v.toFixed(v < 10 && u > 0 ? 1 : 0)} ${units[u]}`;
}
