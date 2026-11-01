// HCS SHA Forge page. Demo-first: no network request is made until the user clicks "Connect".

import * as sha from "./sha";
import { detectWasmSimd, probeBackends, type ProbeResult } from "./backends";
import { cpuBatch, createGpuSha, MAX_BATCH, webgpuSelfTest, type GpuSha } from "./gpu_sha";
import { DEMO_HEADER, DEMO_LABEL, demoTelemetry } from "./demo";
import { LANGS, pickLang, t, type Lang } from "./i18n";

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;
const enc = new TextEncoder();
let lang: Lang = pickLang(navigator.languages ?? [navigator.language], new URLSearchParams(location.search).get("lang") ?? safeGet("hcs-forge-lang"));

function safeGet(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } }
function safeSet(k: string, v: string): void { try { localStorage.setItem(k, v); } catch { /* storage may be blocked */ } }

function el<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string, cls?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

interface Session {
  trace?: unknown; probe?: ProbeResult; benchmark?: { workload: string; unit: string; value: number; blocks: number; engine: string }[];
  bridge?: { reachable: boolean; capabilities?: unknown };
}
const session: Session = {};
let gpuRef: GpuSha | null = null;

// ------------------------------------------------------------------ i18n & tabs
function applyI18n(): void {
  document.documentElement.lang = lang;
  document.querySelectorAll<HTMLElement>("[data-i18n]").forEach((n) => { n.textContent = t(lang, n.dataset.i18n!); });
  $<HTMLSelectElement>("lang").value = lang;
  renderBoundary();
  renderMinerStatic();
}

function showTab(name: string): void {
  document.querySelectorAll<HTMLElement>("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== name; });
  document.querySelectorAll<HTMLButtonElement>("#tabs [role=tab]").forEach((b) => {
    const on = b.dataset.tab === name;
    b.setAttribute("aria-selected", String(on));
    b.tabIndex = on ? 0 : -1;
  });
  if (location.hash.slice(1) !== name) history.replaceState(null, "", `#${name}`);
}

function initTabs(): void {
  const tabs = Array.from(document.querySelectorAll<HTMLButtonElement>("#tabs [role=tab]"));
  tabs.forEach((b, i) => {
    b.addEventListener("click", () => showTab(b.dataset.tab!));
    b.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      const next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      next.focus();
      showTab(next.dataset.tab!);
    });
  });
  const wanted = location.hash.slice(1);
  showTab(tabs.some((b) => b.dataset.tab === wanted) ? wanted : "overview");
}

// ------------------------------------------------------------------ overview
function renderBoundary(): void {
  const tb = $("boundary");
  tb.replaceChildren();
  for (const k of ["asic", "sw", "demo"]) {
    const tr = el("tr");
    tr.append(el("td", t(lang, `ov.row.${k}`)), el("td", t(lang, `ov.row.${k}.w`)), el("td", t(lang, `ov.row.${k}.n`)));
    tb.append(tr);
  }
}

function setEnv(kind: "demo" | "local" | "hardware" | "recovery"): void {
  const b = $("env-badge");
  b.className = `badge ${kind}`;
  b.textContent = kind.toUpperCase();
}

// ------------------------------------------------------------------ analyzer
let currentBlocks: sha.BlockTrace[] = [];

function parseInput(mode: string, raw: string): Uint8Array {
  if (mode === "text") return enc.encode(raw);
  let bytes: Uint8Array;
  try { bytes = sha.fromHex(raw); } catch { throw new Error(t(lang, "an.err.hex")); }
  if (mode === "header" && bytes.length !== 80) throw new Error(t(lang, "an.err.header"));
  return bytes;
}

function dd(dl: HTMLElement, k: string, v: string): void { dl.append(el("dt", k), el("dd", v)); }

function renderRound(i: number): void {
  const blk = currentBlocks[Number($<HTMLSelectElement>("an-block").value)];
  if (!blk) return;
  const r = blk.rounds[i];
  if (!r) return;
  $("an-round-label").textContent = `${i} / ${blk.rounds.length - 1}`;
  const n = (s: string) => parseInt(s, 16) >>> 0;
  const e = n(r.in.e), f = n(r.in.f), g = n(r.in.g), a = n(r.in.a), b = n(r.in.b), c = n(r.in.c);
  const rot = (x: number, k: number) => ((x >>> k) | (x << (32 - k))) >>> 0;
  const S1 = (rot(e, 6) ^ rot(e, 11) ^ rot(e, 25)) >>> 0, S0 = (rot(a, 2) ^ rot(a, 13) ^ rot(a, 22)) >>> 0;
  const ch = ((e & f) ^ (~e & g)) >>> 0, mj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
  const d = $("an-detail");
  d.replaceChildren();
  const lines = [
    `t=${r.t}  K=${r.K}  W=${r.W}`,
    `Σ1(e)=${sha.hex8(S1)}  Ch(e,f,g)=${sha.hex8(ch)}  T1=h+Σ1+Ch+K+W=${r.T1}`,
    `Σ0(a)=${sha.hex8(S0)}  Maj(a,b,c)=${sha.hex8(mj)}  T2=Σ0+Maj=${r.T2}`,
    `a'=T1+T2=${r.out.a}  e'=d+T1=${r.out.e}`,
  ];
  lines.forEach((l) => d.append(el("div", l)));
  document.querySelectorAll("#an-table tbody tr").forEach((tr, idx) => tr.classList.toggle("sel", idx === i));
}

function renderBlock(): void {
  const blk = currentBlocks[Number($<HTMLSelectElement>("an-block").value)];
  const tbl = $("an-table");
  tbl.replaceChildren();
  if (!blk) return;
  const regs = sha.REGS;
  const head = el("thead"), hr = el("tr");
  ["t", "K", "W", ...regs.map((r) => `${r}'`), "T1", "T2"].forEach((h) => hr.append(el("th", h)));
  head.append(hr);
  const body = el("tbody");
  blk.rounds.forEach((r, i) => {
    const tr = el("tr");
    [String(r.t), r.K, r.W, ...regs.map((x) => r.out[x]), r.T1, r.T2].forEach((c) => tr.append(el("td", c)));
    tr.addEventListener("click", () => { $<HTMLInputElement>("an-slider").value = String(i); renderRound(i); });
    body.append(tr);
  });
  tbl.append(head, body);
  const slider = $<HTMLInputElement>("an-slider");
  slider.max = String(Math.max(0, blk.rounds.length - 1));
  slider.value = "0";
  renderRound(0);
}

async function runAnalyzer(ev: Event): Promise<void> {
  ev.preventDefault();
  const err = $("an-error"), out = $("an-out");
  err.hidden = true;
  try {
    const mode = $<HTMLSelectElement>("an-mode").value;
    const rounds = Number($<HTMLInputElement>("an-rounds").value);
    if (!Number.isInteger(rounds) || rounds < 1 || rounds > 64) throw new Error(t(lang, "an.err.rounds"));
    const data = parseInput(mode, $<HTMLTextAreaElement>("an-input").value);
    const summary = $("an-summary");
    summary.replaceChildren();
    let digest: string, padHex: string, traceObj: unknown;
    if (mode === "header") {
      if (rounds !== 64) throw new Error(t(lang, "an.err.header") + " (64 rounds)");
      const tr = sha.traceSha256d(data);
      currentBlocks = [...tr.first_pass.blocks, ...tr.second_pass.blocks];
      digest = tr.double_hash;
      padHex = tr.first_pass.padding.padded_hex;
      traceObj = tr;
      dd(summary, "midstate", tr.first_pass.midstate!);
      dd(summary, "SHA-256", tr.first_pass.digest);
      dd(summary, "SHA-256d", tr.double_hash);
      dd(summary, "display (byte-reversed)", tr.display_hash);
      if (tr.header === sha.GENESIS_HEADER_HEX) dd(summary, "genesis check", tr.display_hash === sha.GENESIS_BLOCK_HASH ? "OK" : "MISMATCH");
    } else {
      const p = sha.pad(data);
      const blocks: sha.BlockTrace[] = [];
      let st: Uint32Array = Uint32Array.from(sha.IV);
      for (let i = 0; i < p.length; i += 64) {
        const tb = sha.traceBlock(st, p.slice(i, i + 64), rounds);
        blocks.push(tb);
        st = Uint32Array.from({ length: 8 }, (_, k) => parseInt(tb.output_state.slice(k * 8, k * 8 + 8), 16));
      }
      currentBlocks = blocks;
      digest = blocks[blocks.length - 1].output_state;
      padHex = sha.toHex(p);
      traceObj = { schema: "hcs.sha.message_trace.v1", source: "SOFTWARE_REPLAY", rounds_per_block: rounds, blocks, digest };
      dd(summary, "digest", digest);
      if (rounds !== 64) dd(summary, "note", t(lang, "an.reduced"));
      else {
        const wc = globalThis.crypto?.subtle ? sha.toHex(new Uint8Array(await crypto.subtle.digest("SHA-256", data as unknown as BufferSource))) : null;
        dd(summary, "Web Crypto", wc === null ? t(lang, "an.webcrypto.na") : wc === digest ? t(lang, "an.webcrypto.ok") : t(lang, "an.webcrypto.bad"));
      }
    }
    $("an-pad").textContent = padHex.replace(/(.{128})/g, "$1\n");
    const sel = $<HTMLSelectElement>("an-block");
    sel.replaceChildren(...currentBlocks.map((_, i) => { const o = el("option", `#${i + 1}`); o.value = String(i); return o; }));
    renderBlock();
    session.trace = traceObj;
    $<HTMLButtonElement>("an-export").disabled = false;
    out.hidden = false;
  } catch (e) {
    err.textContent = e instanceof Error ? e.message : String(e);
    err.hidden = false;
    out.hidden = true;
  }
}

function download(name: string, obj: unknown): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" }));
  const a = el("a");
  a.href = url; a.download = name;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ------------------------------------------------------------------ miner lab (demo + optional local bridge)
function renderMinerStatic(): void {
  $("mi-id").textContent = t(lang, "mi.demo.id");
  if (!session.bridge?.reachable) $("mi-state").textContent = t(lang, "mi.demo.state");
  $("mi-src").textContent = t(lang, "mi.src.demo");
  drawTelemetry();
}

function drawTelemetry(): void {
  const demo = demoTelemetry();
  const svg = $("mi-chart") as unknown as SVGSVGElement;
  svg.querySelectorAll("*:not(title):not(desc)").forEach((n) => n.remove());
  $("mi-chart-t").textContent = `${DEMO_LABEL}: hashrate`;
  $("mi-chart-d").textContent = t(lang, "mi.gap");
  const vals = demo.samples.map((s) => s.hashrate_ghs);
  const nums = vals.filter((v): v is number => v !== null);
  const lo = Math.min(...nums) - 2, hi = Math.max(...nums) + 2;
  const x = (i: number) => 30 + (i / (vals.length - 1)) * 560;
  const y = (v: number) => 140 - ((v - lo) / (hi - lo)) * 120;
  const ns = "http://www.w3.org/2000/svg";
  let seg: string[] = [];
  const flush = () => {
    if (seg.length > 1) { const p = document.createElementNS(ns, "polyline"); p.setAttribute("points", seg.join(" ")); p.setAttribute("fill", "none"); p.setAttribute("stroke", "var(--accent)"); p.setAttribute("stroke-width", "2"); svg.append(p); }
    seg = [];
  };
  vals.forEach((v, i) => { if (v === null) flush(); else seg.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`); });
  flush();
  const lab = document.createElementNS(ns, "text");
  lab.setAttribute("x", "34"); lab.setAttribute("y", "16"); lab.setAttribute("fill", "var(--warn)"); lab.setAttribute("font-size", "12");
  lab.textContent = `${DEMO_LABEL} · GH/s ${lo.toFixed(0)}–${hi.toFixed(0)}`;
  svg.append(lab);
  $("mi-cap").textContent = `${DEMO_LABEL}. ${t(lang, "mi.gap")}`;
  const tbl = $("mi-table");
  tbl.replaceChildren();
  const head = el("tr");
  ["t (s)", "GH/s", "°C", "W"].forEach((h) => head.append(el("th", h)));
  const thead = el("thead");
  thead.append(head);
  tbl.append(thead);
  const body = el("tbody");
  demo.samples.forEach((s) => {
    const tr = el("tr");
    [s.t_s, s.hashrate_ghs, s.temperature_c, s.power_w].forEach((v) => tr.append(el("td", v === null ? "—" : String(v))));
    body.append(tr);
  });
  tbl.append(body);
}

function loopbackOnly(raw: string): URL | null {
  try {
    const u = new URL(raw);
    const ok = u.protocol === "http:" && (u.hostname === "127.0.0.1" || u.hostname === "localhost" || u.hostname === "[::1]");
    return ok && !u.username && !u.password ? u : null;
  } catch { return null; }
}

async function connectBridge(): Promise<void> {
  const msg = $("mi-msg");
  const u = loopbackOnly($<HTMLInputElement>("mi-url").value.trim());
  if (!u) { msg.textContent = t(lang, "mi.err.url"); return; }
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 4000);
  try {
    // Only after this click does the browser ask for local network access.
    const base = u.origin;
    const health = await fetch(`${base}/health`, { signal: ctl.signal, cache: "no-store" });
    const caps = await (await fetch(`${base}/capabilities`, { signal: ctl.signal, cache: "no-store" })).json();
    if (!health.ok || caps.mode !== "READ_ONLY") throw new Error("unexpected bridge response");
    session.bridge = { reachable: true, capabilities: caps };
    setEnv("local");
    $("mi-state").textContent = "CONNECTED_READ_ONLY";
    msg.textContent = t(lang, "mi.ok");
  } catch {
    session.bridge = { reachable: false };
    msg.textContent = t(lang, "mi.err.net");
  } finally { clearTimeout(timer); }
}

// ------------------------------------------------------------------ benchmarks
async function acquireGpu(): Promise<{ selfTest: () => Promise<{ ok: boolean; reason?: string }> } | null> {
  const adapter = await navigator.gpu.requestAdapter();
  if (!adapter) return null;
  const device = await adapter.requestDevice();
  gpuRef = await createGpuSha(device);
  const g = gpuRef;
  g.lost.then(() => { gpuRef = null; });
  return { selfTest: () => webgpuSelfTest(g) };
}

function randomBlocks(n: number): Uint32Array {
  const out = new Uint32Array(n * 16);
  let s = 0x1234abcd;
  for (let i = 0; i < out.length; i++) { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; out[i] = s; }
  return out;
}

async function runBench(): Promise<void> {
  const msg = $("be-msg");
  msg.textContent = t(lang, "be.running");
  const probe = await probeBackends({
    hasNavigatorGpu: "gpu" in navigator,
    acquireGpu: "gpu" in navigator ? acquireGpu : undefined,
    wasmSimd: detectWasmSimd(),
    browserCpuSelfTest: () => sha.toHex(sha.sha256(enc.encode("abc"))) === "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    bridge: session.bridge?.reachable ? { reachable: true, nativeBackend: false, deviceAllowlisted: false, supportsJobType: false } : undefined,
  });
  session.probe = probe;
  const tb = $("be-decisions").querySelector("tbody")!;
  tb.replaceChildren();
  for (const d of probe.decisions) {
    const tr = el("tr");
    tr.append(el("td", d.id), el("td", `${d.ok ? "✔" : "✖"} ${t(lang, d.ok ? "be.ok" : "be.no")}`), el("td", d.reason));
    tb.append(tr);
  }
  $("be-decisions").hidden = false;
  const sel = $("be-selected");
  sel.textContent = `${t(lang, "be.selected")}: ${probe.selected}`;
  sel.hidden = false;

  const rows: NonNullable<Session["benchmark"]> = [];
  const unit = "SHA-256 compressions/s (1 block, standard IV, 64 rounds)";
  const nCpu = 20000, cpuBlocks = randomBlocks(nCpu);
  let t0 = performance.now();
  cpuBatch(cpuBlocks);
  rows.push({ workload: "BROWSER_CPU", unit, value: Math.round(nCpu / ((performance.now() - t0) / 1000)), blocks: nCpu, engine: "BROWSER_CPU" });
  if (gpuRef && probe.decisions.find((d) => d.id === "WEBGPU")?.ok) {
    try {
      const nGpu = MAX_BATCH, gb = randomBlocks(nGpu);
      await gpuRef.compressBatch(gb.subarray(0, 16 * 64)); // warm-up
      t0 = performance.now();
      const res = await gpuRef.compressBatch(gb);
      const secs = (performance.now() - t0) / 1000;
      const ref = cpuBatch(gb.subarray(0, 16 * 64));
      const same = ref.every((v, i) => v === res[i]);
      rows.push({ workload: "WEBGPU (incl. transfer)" + (same ? "" : " — MISMATCH vs CPU"), unit, value: Math.round(nGpu / secs), blocks: nGpu, engine: "WEBGPU" });
    } catch (e) {
      rows.push({ workload: `WEBGPU failed: ${String(e)}`, unit, value: 0, blocks: 0, engine: "WEBGPU" });
    }
  }
  session.benchmark = rows;
  const rb = $("be-results").querySelector("tbody")!;
  rb.replaceChildren();
  for (const r of rows) { const tr = el("tr"); tr.append(el("td", `${r.workload} (${r.blocks} blocks)`), el("td", r.unit), el("td", r.value.toLocaleString())); rb.append(tr); }
  $("be-results").hidden = false;
  msg.textContent = "";
}

// ------------------------------------------------------------------ evidence
function sessionDoc(): unknown {
  return {
    schema: "hcs.sha.forge.session.v1", generated: new Date().toISOString(), environment: $("env-badge").textContent,
    app: { version: typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "unknown", source: typeof __SOURCE_SHA__ === "string" ? __SOURCE_SHA__ : "unknown" },
    demo_label: DEMO_LABEL, probe: session.probe ?? null, benchmark: session.benchmark ?? null, bridge: session.bridge ?? null, trace_present: !!session.trace,
  };
}

// ------------------------------------------------------------------ boot
function boot(): void {
  const langSel = $<HTMLSelectElement>("lang");
  langSel.addEventListener("change", () => { lang = langSel.value as Lang; safeSet("hcs-forge-lang", lang); applyI18n(); });
  if (!LANGS.includes(lang)) lang = "en";
  initTabs();
  applyI18n();
  setEnv("demo");
  $("state-card").textContent = `${t(lang, "mi.demo.state")}`;
  $("an-form").addEventListener("submit", (e) => { void runAnalyzer(e); });
  $("an-genesis").addEventListener("click", () => {
    $<HTMLSelectElement>("an-mode").value = "header";
    $<HTMLTextAreaElement>("an-input").value = DEMO_HEADER.hex;
    $<HTMLInputElement>("an-rounds").value = "64";
  });
  $("an-block").addEventListener("change", renderBlock);
  $("an-slider").addEventListener("input", (e) => renderRound(Number((e.target as HTMLInputElement).value)));
  $("an-export").addEventListener("click", () => download("sha-trace.json", session.trace));
  $("mi-connect").addEventListener("click", () => { void connectBridge(); });
  $("be-run").addEventListener("click", () => { void runBench(); });
  $("ev-export").addEventListener("click", () => download("sha-forge-session.json", sessionDoc()));
  $("tabs").addEventListener("click", () => { $("ev-pre").textContent = JSON.stringify(sessionDoc(), null, 2); });
  $("ev-pre").textContent = JSON.stringify(sessionDoc(), null, 2);
  void runAnalyzer(new Event("submit"));
}

declare const __APP_VERSION__: string;
declare const __SOURCE_SHA__: string;
boot();
