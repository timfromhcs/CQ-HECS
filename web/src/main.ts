import "./styles.css";
import { Builder, compile, isTerminalOnly, parseQasm, toQasm, type Circuit } from "./circuit";
import { Composer } from "./composer";
import { computeLimits, detectDevice, estimate, formatBytes, type DeviceReport, type Limits } from "./device";
import { renderBloch, renderHistogram, renderState, renderTable } from "./charts";
import { PRESETS } from "./presets";
import type { EngineInfo, EngineKind, RunResult, WorkerRequest, WorkerResponse } from "./protocol";
import type { CodeEditor } from "./editor";

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector(sel) as T;

let device: DeviceReport;
let engineInfo: EngineInfo;
let limits: Limits;
let worker: Worker;
let runId = 0;
let lastResult: RunResult | null = null;
let view: "lab" | "code" | "device" | "about" = "lab";
let codeLang: "qasm" | "js" = "qasm";
let editor: CodeEditor | null = null;
const drafts: Record<"qasm" | "js", string> = {
  qasm: `OPENQASM 2.0;\ninclude "qelib1.inc";\n// GHZ mit 4 Qubits\nqreg q[4];\ncreg c[4];\nh q[0];\ncx q[0], q[1];\ncx q[1], q[2];\ncx q[2], q[3];\nmeasure q -> c;\n`,
  js: `// Grover-Suche auf 6 Qubits nach |111111⟩\nconst n = 6, qc = circuit(n), all = [...Array(n).keys()];\nall.forEach(q => qc.h(q));\nconst steps = Math.floor(PI / 4 * Math.sqrt(2 ** n));\nfor (let k = 0; k < steps; k++) {\n  qc.mcz(...all);\n  all.forEach(q => qc.h(q).x(q));\n  qc.mcz(...all);\n  all.forEach(q => qc.x(q).h(q));\n}\nreturn qc.measureAll();\n`,
};

// ------------------------------------------------------------------ worker

function startWorker(): Worker {
  const w = new Worker(new URL("./engine.worker.ts", import.meta.url), { type: "module" });
  return w;
}

function ask<T extends WorkerResponse["type"]>(w: Worker, msg: WorkerRequest, type: T): Promise<Extract<WorkerResponse, { type: T }>> {
  return new Promise((resolve) => {
    const handler = (e: MessageEvent<WorkerResponse>) => {
      if (e.data.type === type) {
        w.removeEventListener("message", handler);
        resolve(e.data as Extract<WorkerResponse, { type: T }>);
      }
    };
    w.addEventListener("message", handler);
    w.postMessage(msg);
  });
}

// ------------------------------------------------------------------ boot

type StepState = "run" | "ok" | "warn";
function step(label: string) {
  const li = document.createElement("li");
  li.className = "run";
  li.innerHTML = `<span class="dot"></span><span>${label}</span><span class="val"></span>`;
  $("#boot-steps").appendChild(li);
  return (state: StepState, value: string) => {
    li.className = state;
    (li.querySelector(".val") as HTMLElement).textContent = value;
  };
}

async function boot() {
  const s1 = step("Betriebssystem & Browser");
  const s2 = step("CPU & Arbeitsspeicher");
  const s3 = step("Grafikkarte & WebGPU");
  device = await detectDevice();
  s1("ok", `${device.os} · ${device.browser}`);
  s2(device.ramGiB ? "ok" : "warn", `${device.cores} Threads · ${device.ramGiB ? `≥${device.ramGiB} GiB` : "RAM unbekannt"}`);
  s3(device.webgpu ? "ok" : "warn", device.webgpu ? device.gpuName.slice(0, 34) : "kein WebGPU → nur WASM");

  const s4 = step("WebAssembly-Kern laden & messen");
  worker = startWorker();
  engineInfo = (await ask(worker, { type: "init" }, "init")).info;
  if (!engineInfo.wasm.ok) {
    s4("warn", "fehlgeschlagen");
    $("#boot-steps").insertAdjacentHTML("afterend", `<p class="warnbox">WebAssembly konnte nicht geladen werden: ${engineInfo.wasm.error ?? ""}</p>`);
    return;
  }
  s4("ok", `${(engineInfo.wasmRate / 1e6).toFixed(0)} M Amp/s${engineInfo.wasm.simd ? " · SIMD" : ""}`);

  limits = computeLimits(device, engineInfo);
  const s5 = step("Exaktes Limit per Speicher-Probe bestätigen");
  await verifyLimit();
  s5(limits.exactVerified ? "ok" : "warn", `${limits.exactQubits} Qubits · ${formatBytes(16 * 2 ** limits.exactQubits)}`);

  await new Promise((r) => setTimeout(r, 450));
  $("#boot").hidden = true;
  $("#app").hidden = false;
  setupUi();
}

async function verifyLimit() {
  let n = limits.exactQubits;
  while (n > 1) {
    const res = await ask(worker, { type: "probe", numQubits: n }, "probe");
    if (res.ok) break;
    n--;
  }
  limits.exactQubits = n;
  limits.exactVerified = true;
}

// ------------------------------------------------------------------ UI

let composer: Composer;

function setupUi() {
  // Header chip + device page.
  const chip = $("#limit-chip");
  chip.textContent = `exakt bis ${limits.exactQubits} Qubits`;
  chip.className = "chip ok";
  renderDevicePage();

  // Tabs.
  document.querySelectorAll<HTMLButtonElement>(".tabs button").forEach((b) =>
    b.addEventListener("click", () => setView(b.dataset.view as typeof view)));

  // Theme.
  const stored = (() => { try { return localStorage.getItem("theme"); } catch { return null; } })();
  if (stored) document.documentElement.dataset.theme = stored;
  $("#theme").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch { /* private mode */ }
    if (lastResult) showResult(lastResult);
  });

  // Engine options.
  const engineSel = $<HTMLSelectElement>("#engine");
  if (!engineInfo.gpu.ok) {
    engineSel.querySelector<HTMLOptionElement>('option[value="webgpu"]')!.disabled = true;
    engineSel.querySelector<HTMLOptionElement>('option[value="webgpu"]')!.textContent = "WebGPU · nicht verfügbar";
  }
  engineSel.addEventListener("change", updateEstimate);

  // Composer.
  composer = new Composer($("#composer"), $("#palette"));
  composer.onChange = updateEstimate;
  const qInput = $<HTMLInputElement>("#qubits");
  qInput.max = String(limits.exactQubits);
  const setQ = (n: number) => {
    n = Math.max(1, Math.min(limits.exactQubits, Math.round(n) || 1));
    qInput.value = String(n);
    composer.setQubits(n);
    updateEstimate();
  };
  qInput.addEventListener("change", () => setQ(Number(qInput.value)));
  $("#q-dec").addEventListener("click", () => setQ(Number(qInput.value) - 1));
  $("#q-inc").addEventListener("click", () => setQ(Number(qInput.value) + 1));
  $("#clear").addEventListener("click", () => { composer.clear(); $("#preset-blurb").textContent = ""; $<HTMLSelectElement>("#preset").value = ""; });

  const presetSel = $<HTMLSelectElement>("#preset");
  for (const p of PRESETS) presetSel.add(new Option(p.title, p.id));
  presetSel.addEventListener("change", () => {
    const p = PRESETS.find((x) => x.id === presetSel.value);
    if (!p) return;
    const n = Math.max(p.minQubits, Math.min(Number(qInput.value), limits.exactQubits));
    const c = p.build(p.id === "bell" ? 2 : p.id === "teleport" ? 3 : n);
    composer.load(c);
    qInput.value = String(c.numQubits);
    $("#preset-blurb").textContent = p.blurb;
    updateEstimate();
  });

  // Noise sliders.
  const noiseOn = $<HTMLInputElement>("#noise-on");
  noiseOn.addEventListener("change", () => { $("#noise-panel").hidden = !noiseOn.checked; updateEstimate(); });
  for (const id of ["p1", "p2", "ro"]) {
    const input = $<HTMLInputElement>(`#${id}`);
    const out = $(`#${id}o`);
    const sync = () => { out.textContent = `${(Number(input.value) * 100).toFixed(2)} %`; updateEstimate(); };
    input.addEventListener("input", sync);
    sync();
  }
  $<HTMLInputElement>("#shots").addEventListener("input", updateEstimate);

  // Results tabs.
  document.querySelectorAll<HTMLButtonElement>(".results-head .seg button").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelectorAll<HTMLButtonElement>(".results-head .seg button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
      for (const k of ["hist", "table", "bloch", "state"]) $(`#res-${k}`).hidden = k !== b.dataset.res;
      if (lastResult && b.dataset.res === "bloch") renderBloch($("#res-bloch"), lastResult);
    }));

  // Run controls.
  $("#run").addEventListener("click", runCurrent);
  $("#stop").addEventListener("click", stopRun);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); runCurrent(); }
  });

  // Code view.
  document.querySelectorAll<HTMLButtonElement>(".code-head .seg button").forEach((b) =>
    b.addEventListener("click", () => switchLang(b.dataset.lang as "qasm" | "js")));
  $("#to-lab").addEventListener("click", () => {
    try {
      const c = circuitFromCode();
      if (c.numQubits > 24) throw new Error("Für das Labor bitte höchstens 24 Qubits");
      composer.load(c);
      $<HTMLInputElement>("#qubits").value = String(c.numQubits);
      setView("lab");
      updateEstimate();
    } catch (e) { showCodeError(e); }
  });
  $("#share").addEventListener("click", shareLink);
  $("#download").addEventListener("click", () => {
    try {
      const blob = new Blob([toQasm(currentCircuit())], { type: "text/plain" });
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "circuit.qasm" });
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { showCodeError(e); }
  });
  $("#reprobe").addEventListener("click", async () => {
    limits = computeLimits(device, engineInfo);
    await verifyLimit();
    renderDevicePage();
    chip.textContent = `exakt bis ${limits.exactQubits} Qubits`;
  });

  // Start state: shared link or Bell.
  if (!loadFromHash()) {
    presetSel.value = "bell";
    presetSel.dispatchEvent(new Event("change"));
  }
  updateEstimate();
}

function setView(v: typeof view) {
  view = v;
  document.querySelectorAll<HTMLButtonElement>(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.view === v)));
  document.querySelectorAll<HTMLElement>(".view").forEach((s) => (s.hidden = s.dataset.view !== v));
  const runnable = v === "lab" || v === "code";
  $(".run-panel").hidden = !runnable;
  $(".results").hidden = !runnable;
  if (v === "code") ensureEditor();
  updateEstimate();
}

async function ensureEditor() {
  if (editor) return;
  const host = $("#editor");
  const { createEditor } = await import("./editor");
  host.replaceChildren();
  editor = createEditor(host, drafts[codeLang], codeLang, runCurrent);
}

function switchLang(lang: "qasm" | "js") {
  if (editor) drafts[codeLang] = editor.get();
  codeLang = lang;
  document.querySelectorAll<HTMLButtonElement>(".code-head .seg button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.lang === lang)));
  editor?.set(drafts[lang], lang);
  updateEstimate();
}

function circuitFromCode(): Circuit {
  const text = editor ? editor.get() : drafts[codeLang];
  if (codeLang === "qasm") return parseQasm(text);
  const fn = new Function("circuit", "PI", `"use strict";\n${text}`);
  const result = fn((n: number) => new Builder(n), Math.PI);
  if (!(result instanceof Builder)) throw new Error("Das Skript muss eine Schaltung zurückgeben: return qc;");
  return result;
}

function currentCircuit(): Circuit {
  return view === "code" ? circuitFromCode() : composer.circuit();
}

function showCodeError(e: unknown) {
  const box = $("#code-error");
  box.textContent = String((e as Error).message ?? e);
  box.hidden = false;
  if (view !== "code") alert(box.textContent);
}

function noiseSettings() {
  const on = $<HTMLInputElement>("#noise-on").checked;
  return {
    p1: on ? Number($<HTMLInputElement>("#p1").value) : 0,
    p2: on ? Number($<HTMLInputElement>("#p2").value) : 0,
    readout: on ? Number($<HTMLInputElement>("#ro").value) : 0,
  };
}

function plan() {
  const c = currentCircuit();
  const ops = compile(c);
  const engine = $<HTMLSelectElement>("#engine").value as EngineKind;
  const shots = Math.max(1, Math.min(1_000_000, Math.round(Number($<HTMLInputElement>("#shots").value)) || 1));
  const noise = noiseSettings();
  const terminal = isTerminalOnly(ops);
  const noisy = noise.p1 > 0 || noise.p2 > 0;
  if (engine === "webgpu" && (!terminal || noisy)) {
    throw new Error("WebGPU rechnet nur Schaltungen ohne Mitte-Messung/Reset und ohne Gatter-Rauschen. Bitte WebAssembly wählen.");
  }
  const trajectories = !terminal ? shots : noisy ? Math.min(shots, 256) : 1;
  const gateOps = ops.filter((o) => o.kind === "u").length;
  const est = estimate(c.numQubits, gateOps, shots, trajectories, limits, engine === "webgpu");
  return { c, ops, engine, shots, noise, est };
}

function updateEstimate() {
  const box = $("#estimate");
  const runBtn = $<HTMLButtonElement>("#run");
  if (!limits) return;
  try {
    $("#code-error").hidden = true;
    const p = plan();
    const t = p.est.seconds < 0.01 ? "<10 ms" : p.est.seconds < 1 ? `${Math.round(p.est.seconds * 1000)} ms` : `${p.est.seconds.toFixed(1)} s`;
    box.textContent = p.est.safe
      ? `${p.c.numQubits} Qubits · ${formatBytes(p.est.bytes)} · ≈${t}`
      : `⚠ ${p.est.reason}`;
    box.classList.toggle("bad", !p.est.safe);
    runBtn.disabled = !p.est.safe;
  } catch (e) {
    box.textContent = view === "code" ? "" : `⚠ ${(e as Error).message}`;
    box.classList.toggle("bad", view !== "code");
    runBtn.disabled = view !== "code";
  }
}

function setRunning(on: boolean) {
  $<HTMLButtonElement>("#run").disabled = on;
  $("#stop").hidden = !on;
  $("#progress").hidden = !on;
}

function stopRun() {
  worker.terminate();
  runId++;
  setRunning(false);
  worker = startWorker();
  ask(worker, { type: "init" }, "init").then((m) => { engineInfo = m.info; });
  $("#stats").innerHTML = `<span class="chip">abgebrochen</span>`;
}

async function runCurrent() {
  if ($<HTMLButtonElement>("#run").disabled && $("#stop").hidden === false) return;
  let p: ReturnType<typeof plan>;
  try {
    p = plan();
  } catch (e) {
    showCodeError(e);
    return;
  }
  if (!p.est.safe) { $("#estimate").textContent = `⚠ abgelehnt: ${p.est.reason}`; return; }
  const id = ++runId;
  setRunning(true);
  const bar = $("#progress .bar"), label = $("#progress .label");
  bar.style.width = "0";
  label.textContent = "starte …";
  const onMsg = (e: MessageEvent<WorkerResponse>) => {
    const m = e.data;
    if (m.type === "progress" && m.id === id) {
      bar.style.width = `${(m.fraction * 100).toFixed(1)}%`;
      label.textContent = m.label;
    } else if ((m.type === "result" && m.result.id === id) || (m.type === "error" && m.id === id)) {
      worker.removeEventListener("message", onMsg);
      setRunning(false);
      updateEstimate();
      if (m.type === "result") showResult(m.result);
      else showCodeError(new Error(m.message));
    }
  };
  worker.addEventListener("message", onMsg);
  worker.postMessage({
    type: "run", id, numQubits: p.c.numQubits, numClbits: p.c.numClbits, ops: p.ops,
    shots: p.shots, seed: (Math.random() * 2 ** 31) | 0, engine: p.engine, noise: p.noise,
  } satisfies WorkerRequest);
}

function showResult(r: RunResult) {
  lastResult = r;
  const chips = [
    r.engine === "wasm" ? "WASM f64 exakt" : "WebGPU f32",
    `${r.numQubits} Qubits`,
    `${r.shots} Shots`,
    `${r.elapsedMs < 1000 ? r.elapsedMs.toFixed(1) + " ms" : (r.elapsedMs / 1000).toFixed(2) + " s"}`,
    `‖ψ‖²−1 = ${(r.norm - 1).toExponential(1)}`,
  ];
  if (r.mode === "trajectories") chips.push(`${r.trajectories} Trajektorien`);
  if (r.crossCheckTv !== undefined) chips.push(`TV zu f64: ${r.crossCheckTv.toExponential(1)}`);
  $("#stats").innerHTML = chips.map((c) => `<span class="chip">${c}</span>`).join("");
  renderHistogram($("#res-hist"), r);
  renderTable($("#res-table"), r);
  renderState($("#res-state"), r);
  if (!$("#res-bloch").hidden) renderBloch($("#res-bloch"), r);
  else $("#res-bloch").replaceChildren();
}

function renderDevicePage() {
  const kv = (pairs: [string, string][]) => pairs.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  $("#device-list").innerHTML = kv([
    ["Betriebssystem", device.os],
    ["Browser", device.browser],
    ["Architektur", device.arch],
    ["CPU-Threads", String(device.cores)],
    ["Arbeitsspeicher", device.ramGiB ? `≥ ${device.ramGiB} GiB · ${device.ramSource}` : device.ramSource],
    ["GPU", `${device.gpuName}${device.gpuVendor ? ` (${device.gpuVendor})` : ""}`],
    ["WebGPU", device.webgpu ? `ja · Backend wahrscheinlich ${device.gpuBackend}` : "nein"],
    ["WebGL 2", device.webgl2 ? "ja" : "nein"],
    ["WASM SIMD128", engineInfo.wasm.simd ? "ja" : "nein"],
    ["WASM-Kern", `${(engineInfo.wasm.bytes / 1024).toFixed(0)} KiB · ${(engineInfo.wasmRate / 1e6).toFixed(0)} Mio. Amplituden-Updates/s`],
  ]);
  $("#limit-list").innerHTML = kv([
    ["Speicherbudget", formatBytes(limits.budgetBytes)],
    ["Exakt (WASM f64)", `${limits.exactQubits} Qubits · ${formatBytes(16 * 2 ** limits.exactQubits)} · ${limits.exactVerified ? "durch Reservierung bestätigt" : "berechnet"}`],
    ["Schnell (WebGPU f32)", engineInfo.gpu.ok ? `${limits.gpuQubits} Qubits · Puffer max. ${formatBytes(engineInfo.gpu.maxBytes)}` : `nicht verfügbar${engineInfo.gpu.error ? ` (${engineInfo.gpu.error})` : ""}`],
    ["Laufzeit-Grenze", "90 s geschätzt"],
  ]);
}

// ------------------------------------------------------------------ sharing

function b64url(s: string) {
  return btoa(String.fromCharCode(...new TextEncoder().encode(s))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function unb64url(s: string) {
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/"));
  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
}

async function shareLink() {
  try {
    const qasm = toQasm(currentCircuit());
    const url = `${location.origin}${location.pathname}#qasm=${b64url(qasm)}`;
    history.replaceState(null, "", url);
    await navigator.clipboard?.writeText(url);
    $("#share").textContent = "Link kopiert ✓";
    setTimeout(() => ($("#share").textContent = "Link teilen"), 1800);
  } catch (e) { showCodeError(e); }
}

function loadFromHash(): boolean {
  const m = location.hash.match(/qasm=([\w-]+)/);
  if (!m) return false;
  try {
    const qasm = unb64url(m[1]);
    const c = parseQasm(qasm);
    drafts.qasm = qasm;
    if (c.numQubits <= 24) {
      composer.load(c);
      $<HTMLInputElement>("#qubits").value = String(c.numQubits);
    } else {
      setView("code");
    }
    return true;
  } catch {
    return false;
  }
}

boot().catch((e) => {
  $("#boot-steps").insertAdjacentHTML("afterend", `<p class="warnbox">Start fehlgeschlagen: ${String((e as Error).message ?? e)}</p>`);
});
