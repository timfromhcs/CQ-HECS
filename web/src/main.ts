import "./styles.css";
import { Builder, compile, isTerminalOnly, parseQasm, toQasm, type Circuit } from "./circuit";
import { Composer } from "./composer";
import { computeLimits, detectDevice, estimate, formatBytes, type DeviceReport, type Limits } from "./device";
import { renderBloch, renderHistogram, renderState, renderTable } from "./charts";
import { PRESETS } from "./presets";
import { GUIDE, GUIDE_UI } from "./guide";
import { LANGS, applyI18n, detectLang, getLang, onLangChange, setLang, t, type Lang } from "./i18n";
import { loadProfiles, profileNoise, type DeviceProfile } from "./profiles";
import { pigeonhole, random3Sat, toDimacs, type SweepPoint } from "./sat";
import type { EngineInfo, EngineKind, Noise, RunResult, WorkerRequest, WorkerResponse } from "./protocol";
import type { CodeEditor } from "./editor";
import { trajectoryCount } from "./simulate";

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector(sel) as T;
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

type Route = "home" | "guide" | "lab" | "code" | "sat" | "compare" | "device";

let device: DeviceReport | null = null;
let engineInfo: EngineInfo | null = null;
let limits: Limits | null = null;
let profiles: DeviceProfile[] = [];
let worker: Worker;
let reqId = 0;
let lastResult: RunResult | null = null;
let route: Route = "home";
let codeLang: "qasm" | "js" = "qasm";
let editor: CodeEditor | null = null;
let composer: Composer;
let bootState: "running" | "ready" | "failed" = "running";
const drafts: Record<"qasm" | "js", string> = {
  qasm: `OPENQASM 2.0;\ninclude "qelib1.inc";\n// GHZ, 4 qubits\nqreg q[4];\ncreg c[4];\nh q[0];\ncx q[0], q[1];\ncx q[1], q[2];\ncx q[2], q[3];\nmeasure q -> c;\n`,
  js: `// Grover search on 6 qubits for |111111⟩\nconst n = 6, qc = circuit(n), all = [...Array(n).keys()];\nall.forEach(q => qc.h(q));\nconst steps = Math.floor(PI / 4 * Math.sqrt(2 ** n));\nfor (let k = 0; k < steps; k++) {\n  qc.mcz(...all);\n  all.forEach(q => qc.h(q).x(q));\n  qc.mcz(...all);\n  all.forEach(q => qc.x(q).h(q));\n}\nreturn qc.measureAll();\n`,
};

// ------------------------------------------------------------------ worker

function startWorker(): Worker {
  return new Worker(new URL("./engine.worker.ts", import.meta.url), { type: "module" });
}

function ask<T extends WorkerResponse["type"]>(msg: WorkerRequest, type: T, id?: number): Promise<Extract<WorkerResponse, { type: T }> | { type: "error"; message: string }> {
  return new Promise((resolve) => {
    const handler = (e: MessageEvent<WorkerResponse>) => {
      const m = e.data;
      const sameId = id === undefined || !("id" in m) || (m as { id?: number }).id === id;
      if ((m.type === type || (m.type === "error" && id !== undefined)) && sameId) {
        worker.removeEventListener("message", handler);
        resolve(m as Extract<WorkerResponse, { type: T }>);
      }
    };
    worker.addEventListener("message", handler);
    worker.postMessage(msg);
  });
}

// ------------------------------------------------------------------ boot (non-blocking)

type StepState = "run" | "ok" | "warn";
function step(key: string) {
  const li = document.createElement("li");
  li.className = "run";
  li.innerHTML = `<span class="dot"></span><span data-i18n="${key}">${esc(t(key))}</span><span class="val"></span>`;
  $("#boot-steps").appendChild(li);
  return (state: StepState, value: string) => {
    li.className = state;
    (li.querySelector(".val") as HTMLElement).textContent = value;
  };
}

async function boot() {
  const s1 = step("boot.os"), s2 = step("boot.mem"), s3 = step("boot.gpu");
  device = await detectDevice();
  s1("ok", `${device.os} · ${device.browser}`);
  s2(device.ramGiB ? "ok" : "warn", `${device.cores} · ${device.ramGiB ? `≥${device.ramGiB} GiB` : t("boot.ramUnknown")}`);
  s3(device.webgpu ? "ok" : "warn", device.webgpu ? device.gpuName.slice(0, 40) : t("boot.noWebgpu"));

  const s4 = step("boot.wasm");
  const init = await ask({ type: "init" }, "init");
  if (init.type !== "init" || !init.info.wasm.ok) {
    s4("warn", t("boot.failed"));
    bootState = "failed";
    $("#hero-limit").textContent = t("err.wasm", { e: init.type === "init" ? init.info.wasm.error ?? "" : init.message });
    return;
  }
  engineInfo = init.info;
  s4("ok", `${(engineInfo.wasmRate / 1e6).toFixed(0)} M/s${engineInfo.wasm.simd ? " · SIMD" : ""}`);
  limits = computeLimits(device, engineInfo);
  const s5 = step("boot.probe");
  await verifyLimit();
  s5("ok", `${limits.exactQubits} · ${formatBytes(16 * 2 ** limits.exactQubits)}`);
  bootState = "ready";
  onReady();
}

async function verifyLimit() {
  if (!limits) return;
  let n = limits.exactQubits;
  while (n > 1) {
    const res = await ask({ type: "probe", numQubits: n }, "probe");
    if (res.type === "probe" && res.ok) break;
    n--;
  }
  limits.exactQubits = n;
  limits.exactVerified = true;
}

function onReady() {
  renderHeroDevice();
  renderDevicePage();
  setupEngineOptions();
  $<HTMLInputElement>("#qubits").max = String(limits!.exactQubits);
  updateEstimate();
}

function renderHeroDevice() {
  const chip = $("#limit-chip");
  if (!limits || !device || !engineInfo) {
    chip.textContent = t("chip.checking");
    return;
  }
  chip.textContent = t("chip.limit", { n: limits.exactQubits });
  chip.className = "chip ok";
  $("#hero-device").textContent = t("hero.deviceReady", { os: device.os, cores: device.cores, gpu: device.gpuName.slice(0, 48) });
  $("#hero-limit").textContent = t("hero.deviceLimit", {
    n: limits.exactQubits, mem: formatBytes(16 * 2 ** limits.exactQubits), rate: (engineInfo.wasmRate / 1e6).toFixed(0),
  });
}

// ------------------------------------------------------------------ routing

const ROUTES: Route[] = ["home", "guide", "lab", "code", "sat", "compare", "device"];

function currentRoute(): Route {
  const r = location.hash.replace(/^#\/?/, "").split(/[?&]/)[0] as Route;
  return ROUTES.includes(r) ? r : "home";
}

function show(r: Route) {
  route = r;
  document.querySelectorAll<HTMLAnchorElement>(".tabs a").forEach((a) => a.setAttribute("aria-current", String(a.dataset.route === r)));
  document.querySelectorAll<HTMLElement>(".page").forEach((p) => {
    p.hidden = !p.dataset.page!.split(" ").includes(r);
  });
  const bench = document.querySelector<HTMLElement>(".workbench")!;
  bench.querySelector<HTMLElement>(".view-lab")!.hidden = r !== "lab";
  bench.querySelector<HTMLElement>(".view-code")!.hidden = r !== "code";
  if (r === "code") ensureEditor();
  if (r === "compare") $("#cmp-circuit").textContent = describeCircuit();
  window.scrollTo({ top: 0 });
  updateEstimate();
}

function go(r: Route) {
  if (location.hash !== `#/${r === "home" ? "" : r}`) location.hash = `#/${r === "home" ? "" : r}`;
  else show(r);
}

// ------------------------------------------------------------------ language + theme

function setupChrome() {
  const sel = $<HTMLSelectElement>("#lang");
  for (const l of LANGS) sel.add(new Option(l.label, l.id));
  const fromUrl = new URLSearchParams(location.search).get("lang");
  const initial = (fromUrl === "en" || fromUrl === "de" || fromUrl === "fr") ? fromUrl : detectLang();
  sel.value = initial;
  sel.addEventListener("change", () => setLang(sel.value as Lang));
  onLangChange(relocalize);
  setLang(initial);

  try {
    const stored = localStorage.getItem("theme");
    if (stored === "light" || stored === "dark") document.documentElement.dataset.theme = stored;
  } catch { /* storage blocked */ }
  $("#theme").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch { /* storage blocked */ }
    if (lastResult) showResult(lastResult);
  });
}

function relocalize() {
  $("#foot-love").innerHTML = t("foot.love", { heart: '<span class="heart" aria-label="love">♥</span>', a: "<b>timfromhcs</b>", b: "<b>hcsmedia</b>" });
  renderGuide();
  fillPresetSelect();
  fillNoiseSelect();
  renderHeroDevice();
  if (limits) renderDevicePage();
  renderProfiles();
  if (lastResult) showResult(lastResult);
  updateEstimate();
}

// ------------------------------------------------------------------ guide

function renderGuide() {
  const ui = GUIDE_UI[getLang()];
  $("#guide-title").textContent = ui.title;
  $("#guide-intro").textContent = ui.intro;
  $("#guide-toc-title").textContent = ui.toc;
  $("#guide-toc").innerHTML = GUIDE.map((s) => `<li><a href="#/guide" data-jump="${s.id}">${esc(s.title[getLang()])}</a></li>`).join("");
  $("#guide-sections").innerHTML = GUIDE.map((s) => `
    <section class="card guide-section" id="g-${s.id}">
      <span class="badge b-${s.level}">${esc(ui.levels[s.level])}</span>
      <h2>${esc(s.title[getLang()])}</h2>
      ${s.body[getLang()]}
      ${s.action ? `<button class="btn primary small-btn" data-try="${s.id}">${esc(ui.tryIt)} →</button>` : ""}
    </section>`).join("");
}

function setupGuide() {
  $("#guide-toc").addEventListener("click", (e) => {
    const id = (e.target as HTMLElement).dataset.jump;
    if (!id) return;
    e.preventDefault();
    document.getElementById(`g-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("#guide-sections").addEventListener("click", (e) => {
    const id = (e.target as HTMLElement).dataset.try;
    const section = GUIDE.find((s) => s.id === id);
    if (!section?.action) return;
    const a = section.action;
    if (a.view) { go(a.view as Route); return; }
    if (a.preset) loadPreset(a.preset, a.qubits);
    $<HTMLSelectElement>("#noise").value = a.noise ? `profile:${a.noise}` : "none";
    onNoiseChange();
    go("lab");
  });
}

// ------------------------------------------------------------------ lab

function fillPresetSelect() {
  const sel = $<HTMLSelectElement>("#preset");
  const current = sel.value;
  sel.replaceChildren(new Option(t("lab.empty"), ""));
  for (const p of PRESETS) sel.add(new Option(p.title[getLang()], p.id));
  sel.value = current;
  const p = PRESETS.find((x) => x.id === current);
  $("#preset-blurb").textContent = p ? p.blurb[getLang()] : "";
}

function maxLabQubits() {
  return limits?.exactQubits ?? 20;
}

function loadPreset(id: string, qubits?: number) {
  const p = PRESETS.find((x) => x.id === id);
  if (!p) return;
  const q = $<HTMLInputElement>("#qubits");
  const n = Math.max(p.minQubits, Math.min(qubits ?? Number(q.value), maxLabQubits()));
  const c = p.build(id === "bell" ? 2 : id === "teleport" ? 3 : n);
  composer.load(c);
  q.value = String(c.numQubits);
  $<HTMLSelectElement>("#preset").value = id;
  $("#preset-blurb").textContent = p.blurb[getLang()];
  updateEstimate();
}

function setupLab() {
  composer = new Composer($("#composer"), $("#palette"));
  composer.onChange = updateEstimate;
  const qInput = $<HTMLInputElement>("#qubits");
  const setQ = (n: number) => {
    n = Math.max(1, Math.min(maxLabQubits(), Math.round(n) || 1));
    qInput.value = String(n);
    composer.setQubits(n);
    updateEstimate();
  };
  qInput.addEventListener("change", () => setQ(Number(qInput.value)));
  $("#q-dec").addEventListener("click", () => setQ(Number(qInput.value) - 1));
  $("#q-inc").addEventListener("click", () => setQ(Number(qInput.value) + 1));
  $("#clear").addEventListener("click", () => {
    composer.clear();
    $("#preset-blurb").textContent = "";
    $<HTMLSelectElement>("#preset").value = "";
  });
  $<HTMLSelectElement>("#preset").addEventListener("change", (e) => loadPreset((e.target as HTMLSelectElement).value));
}

// ------------------------------------------------------------------ noise

function fillNoiseSelect() {
  const sel = $<HTMLSelectElement>("#noise");
  const current = sel.value || "none";
  sel.replaceChildren(new Option(t("run.noise.none"), "none"));
  const group = document.createElement("optgroup");
  group.label = t("dev.profiles");
  for (const p of profiles) group.appendChild(new Option(`${p.label} · ${t("run.noise.measured")}`, `profile:${p.id}`));
  if (profiles.length) sel.appendChild(group);
  sel.add(new Option(t("run.noise.custom"), "custom"));
  sel.value = [...sel.options].some((o) => o.value === current) ? current : "none";
  onNoiseChange();
}

function selectedProfile(): DeviceProfile | undefined {
  const v = $<HTMLSelectElement>("#noise").value;
  return v.startsWith("profile:") ? profiles.find((p) => p.id === v.slice(8)) : undefined;
}

function onNoiseChange() {
  const v = $<HTMLSelectElement>("#noise").value;
  $("#noise-panel").hidden = v !== "custom";
  const info = $("#noise-info");
  const p = selectedProfile();
  if (!p) { info.hidden = true; updateEstimate(); return; }
  const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;
  let text = t("run.profileInfo", {
    label: p.label, cx: p.cx_depolarizing.toFixed(4), p01: mean(p.p01).toFixed(4), p10: mean(p.p10).toFixed(4),
    verdict: p.validation.h_v3_8, shots: p.shots_per_circuit,
  });
  const n = currentQubits();
  if (n > p.measured_qubits) text += " " + t("run.extrap", { from: p.measured_qubits, to: n - 1 });
  info.textContent = text;
  info.hidden = false;
  updateEstimate();
}

function noiseFor(n: number): Noise {
  const v = $<HTMLSelectElement>("#noise").value;
  const p = selectedProfile();
  if (p) return profileNoise(p, n);
  if (v === "custom") {
    const ro = Number($<HTMLInputElement>("#ro").value);
    return { p1: Number($<HTMLInputElement>("#p1").value), p2: Number($<HTMLInputElement>("#p2").value), readout: ro };
  }
  return { p1: 0, p2: 0, readout: 0 };
}

function setupNoise() {
  $<HTMLSelectElement>("#noise").addEventListener("change", onNoiseChange);
  for (const id of ["p1", "p2", "ro"]) {
    const input = $<HTMLInputElement>(`#${id}`), out = $(`#${id}o`);
    const sync = () => { out.textContent = `${(Number(input.value) * 100).toFixed(2)} %`; updateEstimate(); };
    input.addEventListener("input", sync);
    sync();
  }
}

// ------------------------------------------------------------------ code

async function ensureEditor() {
  if (editor) return;
  const host = $("#editor");
  const { createEditor } = await import("./editor");
  host.replaceChildren();
  let pending = 0;
  // Re-estimate (limits, memory, runtime) as the user types, debounced.
  editor = createEditor(host, drafts[codeLang], codeLang, runCurrent, () => {
    clearTimeout(pending);
    pending = window.setTimeout(updateEstimate, 250);
  });
  updateEstimate();
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
  if (!(result instanceof Builder)) throw new Error("return qc;");
  return result;
}

function currentCircuit(): Circuit {
  return route === "code" ? circuitFromCode() : composer.circuit();
}

function currentQubits(): number {
  try { return currentCircuit().numQubits; } catch { return Number($<HTMLInputElement>("#qubits").value) || 1; }
}

function describeCircuit(): string {
  try {
    const c = composer.circuit();
    const p = PRESETS.find((x) => x.id === $<HTMLSelectElement>("#preset").value);
    return `${p ? p.title[getLang()] : "Circuit"} · ${c.numQubits} qubits · ${c.gates.length} gates`;
  } catch { return ""; }
}

function showCodeError(e: unknown) {
  const box = $("#code-error");
  box.textContent = String((e as Error).message ?? e);
  box.hidden = route !== "code";
  if (route !== "code") $("#estimate").textContent = `⚠ ${box.textContent}`;
}

function setupCode() {
  document.querySelectorAll<HTMLButtonElement>(".code-head .seg button").forEach((b) =>
    b.addEventListener("click", () => switchLang(b.dataset.lang as "qasm" | "js")));
  $("#to-lab").addEventListener("click", () => {
    try {
      const c = circuitFromCode();
      if (c.numQubits > 24) throw new Error("≤ 24 qubits");
      composer.load(c);
      $<HTMLInputElement>("#qubits").value = String(c.numQubits);
      go("lab");
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
}

// ------------------------------------------------------------------ run

function plan() {
  if (!limits) throw new Error(t("chip.checking"));
  const c = currentCircuit();
  const ops = compile(c);
  const engine = $<HTMLSelectElement>("#engine").value as EngineKind;
  const shots = Math.max(1, Math.min(1_000_000, Math.round(Number($<HTMLInputElement>("#shots").value)) || 1));
  const noise = noiseFor(c.numQubits);
  const terminal = isTerminalOnly(ops);
  const gateNoisy = noise.p1 > 0 || noise.p2 > 0 || (noise.xflip ?? []).some((v) => v > 0);
  if (engine === "webgpu" && (!terminal || gateNoisy)) throw new Error(t("run.gpuNoise"));
  const gateOps = ops.filter((o) => o.kind === "u").length;
  const trajectories = !terminal ? shots : gateNoisy ? trajectoryCount(shots, gateOps, c.numQubits) : 1;
  const est = estimate(c.numQubits, gateOps, shots, trajectories, limits, engine === "webgpu");
  return { c, ops, engine, shots, noise, est };
}

function fmtTime(s: number) {
  return s < 0.01 ? "<10 ms" : s < 1 ? `${Math.round(s * 1000)} ms` : `${s.toFixed(1)} s`;
}

function estimateReason(p: ReturnType<typeof plan>): string {
  const max = p.engine === "webgpu" ? limits!.gpuQubits : limits!.exactQubits;
  if (p.c.numQubits > max) return t("est.limit", { n: p.c.numQubits, max });
  return t("est.time", { t: p.est.seconds.toFixed(0) });
}

function updateEstimate() {
  const box = $("#estimate"), runBtn = $<HTMLButtonElement>("#run");
  if (bootState !== "ready") { box.textContent = t("chip.checking"); runBtn.disabled = true; return; }
  try {
    $("#code-error").hidden = true;
    const p = plan();
    box.textContent = p.est.safe
      ? t("est.ok", { n: p.c.numQubits, mem: formatBytes(p.est.bytes), t: fmtTime(p.est.seconds) })
      : `⚠ ${estimateReason(p)}`;
    box.classList.toggle("bad", !p.est.safe);
    runBtn.disabled = !p.est.safe;
  } catch (e) {
    box.textContent = route === "code" ? "" : `⚠ ${(e as Error).message}`;
    box.classList.toggle("bad", route !== "code");
    runBtn.disabled = route !== "code";
  }
}

function setRunning(on: boolean) {
  $<HTMLButtonElement>("#run").disabled = on;
  $("#stop").hidden = !on;
  $("#progress").hidden = !on;
}

function stopRun() {
  worker.terminate();
  reqId++;
  setRunning(false);
  worker = startWorker();
  ask({ type: "init" }, "init");
  $("#stats").innerHTML = `<span class="chip">${esc(t("run.cancelled"))}</span>`;
}

function runOnce(c: Circuit, ops: ReturnType<typeof compile>, shots: number, engine: EngineKind, noise: Noise, onProgress?: (f: number, label: string) => void): Promise<RunResult> {
  const id = ++reqId;
  return new Promise((resolve, reject) => {
    const onMsg = (e: MessageEvent<WorkerResponse>) => {
      const m = e.data;
      if (m.type === "progress" && m.id === id) onProgress?.(m.fraction, m.label);
      else if ((m.type === "result" && m.result.id === id) || (m.type === "error" && m.id === id)) {
        worker.removeEventListener("message", onMsg);
        if (m.type === "result") resolve(m.result); else reject(new Error(m.message));
      }
    };
    worker.addEventListener("message", onMsg);
    worker.postMessage({
      type: "run", id, numQubits: c.numQubits, numClbits: c.numClbits, ops, shots,
      seed: (Math.random() * 2 ** 31) | 0, engine, noise,
    } satisfies WorkerRequest);
  });
}

async function runCurrent() {
  if (!$("#stop").hidden) return;
  let p: ReturnType<typeof plan>;
  try { p = plan(); } catch (e) { showCodeError(e); return; }
  if (!p.est.safe) { $("#estimate").textContent = `⚠ ${t("run.refused", { reason: estimateReason(p) })}`; return; }
  setRunning(true);
  try {
    lastRunInput = { qasm: toQasm(p.c), shots: p.shots, engine: p.engine, noise: p.noise };
  } catch {
    lastRunInput = { qasm: "", shots: p.shots, engine: p.engine, noise: p.noise };
  }
  const bar = $("#progress .bar"), label = $("#progress .label");
  bar.style.width = "0";
  label.textContent = t("run.starting");
  try {
    const r = await runOnce(p.c, p.ops, p.shots, p.engine, p.noise, (f, l) => {
      bar.style.width = `${(f * 100).toFixed(1)}%`;
      label.textContent = l;
    });
    (r as RunResult & { profile?: string; extrapolated?: number }).profile = p.noise.profile;
    (r as RunResult & { extrapolated?: number }).extrapolated = (p.noise as Noise & { extrapolated?: number }).extrapolated ?? 0;
    showResult(r);
  } catch (e) {
    showCodeError(e);
  } finally {
    setRunning(false);
    updateEstimate();
  }
}

function showResult(r: RunResult) {
  lastResult = r;
  const extra = r as RunResult & { profile?: string; extrapolated?: number };
  const chips = [
    r.engine === "wasm" ? "WASM f64" : "WebGPU f32",
    `${r.numQubits} q`,
    `${r.shots} shots`,
    r.elapsedMs < 1000 ? `${r.elapsedMs.toFixed(1)} ms` : `${(r.elapsedMs / 1000).toFixed(2)} s`,
    `‖ψ‖²−1 = ${(r.norm - 1).toExponential(1)}`,
  ];
  if (extra.profile) chips.push(profiles.find((p) => p.id === extra.profile)?.label ?? extra.profile);
  if (extra.extrapolated) chips.push(t("res.extrap", { n: extra.extrapolated }));
  if (r.mode === "trajectories") chips.push(t("res.traj", { n: r.trajectories }));
  if (r.crossCheckTv !== undefined) chips.push(t("res.tv", { v: r.crossCheckTv.toExponential(1) }));
  $("#stats").innerHTML = chips.map((c) => `<span class="chip">${esc(c)}</span>`).join("");
  renderProvenance(r);
  renderHistogram($("#res-hist"), r);
  renderTable($("#res-table"), r);
  renderState($("#res-state"), r);
  if (!$("#res-bloch").hidden) renderBloch($("#res-bloch"), r);
  else $("#res-bloch").replaceChildren();
}

let lastRunInput: { qasm: string; shots: number; engine: EngineKind; noise: Noise } | null = null;

function renderProvenance(r: RunResult) {
  const extra = r as RunResult & { profile?: string };
  const profile = extra.profile ? profiles.find((p) => p.id === extra.profile) : undefined;
  const noise = lastRunInput?.noise;
  const noiseLine = profile
    ? t("prov.noise.profile", { id: profile.label, path: profile.evidence })
    : noise && (noise.p1 > 0 || noise.p2 > 0 || noise.readout > 0) ? t("prov.noise.custom") : t("prov.noise.none");
  const items = [
    t(r.engine === "wasm" ? "prov.engine.wasm" : "prov.engine.webgpu"),
    noiseLine,
    t("prov.sampling"),
    t("prov.not"),
    t("prov.build", { version: __APP_VERSION__, sha: __SOURCE_SHA__.slice(0, 12) }),
  ];
  $("#prov-list").innerHTML = items.map((x) => `<li>${esc(x)}</li>`).join("");
  $("#res-details").hidden = false;
}

function exportResult() {
  if (!lastResult) return;
  const document_ = {
    schema: "cqhecs.web.run/1.0",
    app_version: __APP_VERSION__,
    source_revision: __SOURCE_SHA__,
    created_at: new Date().toISOString(),
    input: lastRunInput,
    engine: { kind: lastResult.engine, precision: lastResult.engine === "wasm" ? "f64" : "f32" },
    result: lastResult,
    limitations: [t("prov.not")],
  };
  const blob = new Blob([JSON.stringify(document_, null, 2)], { type: "application/json" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `cqhecs-run-${Date.now()}.json` });
  a.click();
  URL.revokeObjectURL(a.href);
}

function setupRun() {
  $("#res-export").addEventListener("click", exportResult);
  $("#run").addEventListener("click", runCurrent);
  $("#stop").addEventListener("click", stopRun);
  $<HTMLInputElement>("#shots").addEventListener("input", updateEstimate);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && (route === "lab" || route === "code")) { e.preventDefault(); runCurrent(); }
  });
  document.querySelectorAll<HTMLButtonElement>(".results-head .seg button").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelectorAll<HTMLButtonElement>(".results-head .seg button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
      for (const k of ["hist", "table", "bloch", "state"]) $(`#res-${k}`).hidden = k !== b.dataset.res;
      if (lastResult && b.dataset.res === "bloch") renderBloch($("#res-bloch"), lastResult);
    }));
}

function setupEngineOptions() {
  // Offer WebGPU only if both the page's own adapter check and the worker found it.
  if (!engineInfo?.gpu.ok || !device?.webgpu) {
    const opt = $<HTMLSelectElement>("#engine").querySelector<HTMLOptionElement>('option[value="webgpu"]')!;
    opt.disabled = true;
    opt.dataset.i18n = "run.gpuNo";
    opt.textContent = t("run.gpuNo");
  }
  $<HTMLSelectElement>("#engine").addEventListener("change", updateEstimate);
}

// ------------------------------------------------------------------ SAT

function setupSat() {
  const input = $<HTMLTextAreaElement>("#sat-input");
  $("#sat-random").addEventListener("click", () => {
    const n = Math.max(3, Math.min(200, Number($<HTMLInputElement>("#sat-vars").value) || 40));
    const ratio = Number($<HTMLInputElement>("#sat-ratio").value) || 4.26;
    input.value = toDimacs(random3Sat(n, Math.round(ratio * n), (Math.random() * 2 ** 31) | 0));
  });
  $("#sat-php").addEventListener("click", () => { input.value = toDimacs(pigeonhole(6)); });
  $("#sat-solve").addEventListener("click", async () => {
    const out = $("#sat-result");
    out.innerHTML = `<p class="muted">…</p>`;
    const id = ++reqId;
    const m = await ask({ type: "sat", id, dimacs: input.value, timeoutMs: Number($<HTMLInputElement>("#sat-timeout").value) || 5000 }, "sat", id);
    if (m.type !== "sat") { out.innerHTML = `<p class="error">${esc(m.message)}</p>`; return; }
    const r = m.result;
    const cls = r.status === "SAT" ? "ok" : r.status === "UNSAT" ? "bad" : "warn";
    const model = r.model ? r.model.slice(1).map((v, i) => (v ? i + 1 : -(i + 1))).join(" ") : "";
    out.innerHTML = `<p><span class="status ${cls}">${r.status}</span> <span class="muted small">${m.numVars} vars · ${m.numClauses} clauses</span></p>
      <p class="cert ${r.certification === "UNCERTIFIED" ? "warn" : ""}">${esc(t(`sat.cert.${r.certification}`, { n: r.certificateSteps }))}</p>
      <p class="small">${esc(t("sat.stats", { d: r.decisions, p: r.propagations, c: r.conflicts, t: r.elapsedMs.toFixed(1) }))}</p>
      <p class="muted small">${esc(r.note)}</p>
      ${model ? `<details><summary>${esc(t("sat.model"))}</summary><pre class="model">${esc(model)}</pre></details>` : ""}`;
  });
  $("#sat-count").addEventListener("click", async () => {
    const out = $("#sat-result");
    out.innerHTML = `<p class="muted">…</p>`;
    const id = ++reqId;
    const m = await ask({ type: "count", id, dimacs: input.value, timeoutMs: Number($<HTMLInputElement>("#sat-timeout").value) || 5000 }, "count", id);
    if (m.type !== "count") { out.innerHTML = `<p class="error">${esc(m.message)}</p>`; return; }
    const r = m.result;
    out.innerHTML = r.status === "COUNTED"
      ? `<p><span class="status ok">#SAT</span> <span class="muted small">${m.numVars} vars · ${m.numClauses} clauses</span></p>
         <p class="count-value">${esc(t("sat.countResult", { n: r.count ?? "" }))}</p>
         <p class="muted small">${r.nodes} nodes · ${r.cacheHits} cache hits · ${r.elapsedMs.toFixed(1)} ms · ${esc(r.note)}</p>`
      : `<p><span class="status warn">UNKNOWN</span></p><p class="cert warn">${esc(t("sat.countUnknown"))}</p>`;
  });
  $("#sat-sweep").addEventListener("click", async () => {
    const chart = $("#sat-chart");
    chart.innerHTML = `<p class="muted">…</p>`;
    const ratios = [2, 3, 3.5, 4, 4.26, 4.5, 5, 6, 7];
    const id = ++reqId;
    const m = await ask({ type: "sweep", id, numVars: 50, ratios, trials: 12, timeoutMs: 2000 }, "sweep", id);
    if (m.type === "sweep") renderSweep(chart, m.points);
  });
}

function renderSweep(host: HTMLElement, pts: SweepPoint[]) {
  const w = 480, h = 240, pad = 36;
  const maxD = Math.max(1, ...pts.map((p) => p.medianDecisions));
  const x = (r: number) => pad + ((r - 2) / 5) * (w - pad - 10);
  const yD = (d: number) => h - pad - (d / maxD) * (h - pad - 12);
  const yS = (s: number) => h - pad - s * (h - pad - 12);
  const line = (f: (p: SweepPoint) => number) => pts.map((p, i) => `${i ? "L" : "M"}${x(p.ratio).toFixed(1)} ${f(p).toFixed(1)}`).join("");
  host.innerHTML = `<svg viewBox="0 0 ${w} ${h}" class="sweep" role="img" aria-label="${esc(t("sat.sweep"))}">
    <line x1="${pad}" y1="${h - pad}" x2="${w - 10}" y2="${h - pad}" class="grid"/>
    <line x1="${x(4.26)}" y1="10" x2="${x(4.26)}" y2="${h - pad}" class="mark"/>
    <path d="${line((p) => yD(p.medianDecisions))}" class="l1"/>
    <path d="${line((p) => yS(p.satFraction))}" class="l2"/>
    ${pts.map((p) => `<circle cx="${x(p.ratio)}" cy="${yD(p.medianDecisions)}" r="3.5" class="p1"><title>ratio ${p.ratio}: ${p.medianDecisions} decisions, ${(p.satFraction * 100).toFixed(0)} % SAT, ${p.unknown} unknown</title></circle>`).join("")}
    ${[2, 3, 4, 5, 6, 7].map((r) => `<text x="${x(r)}" y="${h - pad + 16}" class="axis" text-anchor="middle">${r}</text>`).join("")}
    <text x="${pad}" y="12" class="axis">max ${maxD} decisions</text>
  </svg>
  <div class="legend"><span><i style="background:var(--accent)"></i>median decisions</span><span><i style="background:var(--warn)"></i>P(SAT)</span><span>4.26</span></div>`;
}

// ------------------------------------------------------------------ device comparison

async function compareDevices() {
  const out = $("#cmp-result");
  if (!limits) return;
  let c: Circuit;
  try { c = composer.circuit(); } catch (e) { out.textContent = String(e); return; }
  if (c.numQubits > 14) { out.innerHTML = `<p class="warnbox">${esc(t("cmp.limit"))}</p>`; return; }
  const ops = compile(c);
  const shots = 20000;
  out.innerHTML = `<p class="muted">…</p>`;
  const ideal = await runOnce(c, ops, shots, "wasm", { p1: 0, p2: 0, readout: 0 });
  const idealP = new Map(ideal.exact.map((e) => [e.bits, e.p]));
  const sameLayout = Object.keys(ideal.counts)[0]?.length === c.numQubits;
  const rows: { label: string; vendor: string; tv: number; top: string; topP: number }[] = [];
  for (const p of profiles) {
    const r = await runOnce(c, ops, shots, "wasm", profileNoise(p, c.numQubits));
    const keys = new Set([...Object.keys(r.counts), ...(sameLayout ? idealP.keys() : Object.keys(ideal.counts))]);
    let tv = 0;
    for (const k of keys) {
      const ref = sameLayout ? idealP.get(k) ?? 0 : (ideal.counts[k] ?? 0) / shots;
      tv += Math.abs((r.counts[k] ?? 0) / shots - ref);
    }
    const [top, n] = Object.entries(r.counts).sort((a, b) => b[1] - a[1])[0];
    rows.push({ label: p.label, vendor: p.vendor, tv: tv / 2, top, topP: n / shots });
  }
  rows.sort((a, b) => a.tv - b.tv);
  const maxTv = Math.max(0.05, ...rows.map((r) => r.tv));
  out.innerHTML = `<div class="table-wrap"><table class="cmp"><thead><tr><th>${esc(t("cmp.device"))}</th><th class="num">${esc(t("cmp.tv"))}</th><th></th><th>${esc(t("cmp.top"))}</th></tr></thead><tbody>
    ${rows.map((r) => `<tr><td><b>${esc(r.label)}</b> <span class="muted small">${esc(r.vendor)}</span></td><td class="num">${r.tv.toFixed(4)}</td>
      <td class="barcell"><span style="width:${((r.tv / maxTv) * 100).toFixed(1)}%"></span></td><td><code>${r.top}</code> ${(r.topP * 100).toFixed(1)} %</td></tr>`).join("")}
  </tbody></table></div><p class="muted small">${esc(describeCircuit())} · ${shots} shots</p>`;
}

function renderProfiles() {
  const host = $("#profile-cards");
  if (!profiles.length) { host.innerHTML = ""; return; }
  host.innerHTML = profiles.map((p) => `
    <article class="profile card">
      <header><b>${esc(p.label)}</b><span class="badge ${p.validation.h_v3_8 === "SUPPORTED" ? "b-beginner" : "b-adv"}">H-V3-8 ${esc(p.validation.h_v3_8)}</span></header>
      <p class="muted small">CX dep. ${p.cx_depolarizing.toFixed(4)} · ${p.shots_per_circuit} shots · ΔTV ${p.validation.median_delta_tv_m_fit.toFixed(4)}</p>
      <table class="mini"><thead><tr><th>${esc(t("dev.qubit"))}</th>${p.p01.map((_, q) => `<th class="num">q${q}</th>`).join("")}</tr></thead><tbody>
        <tr><td>${esc(t("dev.p01"))}</td>${p.p01.map((v) => `<td class="num">${v.toFixed(4)}</td>`).join("")}</tr>
        <tr><td>${esc(t("dev.p10"))}</td>${p.p10.map((v) => `<td class="num">${v.toFixed(4)}</td>`).join("")}</tr>
        <tr><td>${esc(t("dev.xflip"))}</td>${p.x_bitflip.map((v) => `<td class="num${v > 0 ? " hot" : ""}">${v.toFixed(3)}</td>`).join("")}</tr>
      </tbody></table>
      <p class="muted small"><a href="https://github.com/timfromhcs/CQ-HECS/tree/main/${esc(p.evidence)}" rel="noopener">evidence</a></p>
    </article>`).join("");
  $("#vendor-strip").innerHTML = profiles.map((p) => `<span class="chip">${esc(p.label)}</span>`).join("");
}

// ------------------------------------------------------------------ device page

function renderDevicePage() {
  if (!device || !engineInfo || !limits) return;
  const kv = (pairs: [string, string][]) => pairs.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
  $("#device-list").innerHTML = kv([
    [t("dev.os"), device.os], [t("dev.browser"), device.browser], [t("dev.arch"), device.arch],
    [t("dev.cores"), String(device.cores)],
    [t("dev.ram"), device.ramGiB ? `≥ ${device.ramGiB} GiB (navigator.deviceMemory)` : t("boot.ramUnknown")],
    [t("dev.gpu"), `${device.gpuName}${device.gpuVendor ? ` (${device.gpuVendor})` : ""}`],
    [t("dev.webgpu"), device.webgpu ? `${t("dev.yes")} · ${t("dev.backend", { b: device.gpuBackend })}` : t("dev.no")],
    [t("dev.webgl"), device.webgl2 ? t("dev.yes") : t("dev.no")],
    [t("dev.simd"), engineInfo.wasm.simd ? t("dev.yes") : t("dev.no")],
    [t("dev.core"), `${(engineInfo.wasm.bytes / 1024).toFixed(0)} KiB · ${(engineInfo.wasmRate / 1e6).toFixed(0)} M/s`],
  ]);
  $("#limit-list").innerHTML = kv([
    [t("dev.budget"), formatBytes(limits.budgetBytes)],
    [t("dev.exact"), `${limits.exactQubits} qubits · ${formatBytes(16 * 2 ** limits.exactQubits)} · ${limits.exactVerified ? t("dev.verified") : t("dev.computed")}`],
    [t("dev.fast"), engineInfo.gpu.ok ? `${limits.gpuQubits} qubits · max ${formatBytes(engineInfo.gpu.maxBytes)}` : `${t("dev.no")}${engineInfo.gpu.error ? ` (${engineInfo.gpu.error})` : ""}`],
    [t("dev.time"), "90 s"],
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
    const url = `${location.origin}/#/code?qasm=${b64url(toQasm(currentCircuit()))}`;
    await navigator.clipboard?.writeText(url);
    $("#share").textContent = t("code.copied");
    setTimeout(() => ($("#share").textContent = t("code.share")), 1800);
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
    }
    return true;
  } catch {
    return false;
  }
}

// ------------------------------------------------------------------ start

function start() {
  setupChrome();
  setupGuide();
  setupLab();
  setupNoise();
  setupCode();
  setupRun();
  setupSat();
  $("#cmp-run").addEventListener("click", compareDevices);
  $("#reprobe").addEventListener("click", async () => {
    if (!device || !engineInfo) return;
    limits = computeLimits(device, engineInfo);
    await verifyLimit();
    onReady();
  });
  if (!loadFromHash()) loadPreset("bell");
  applyI18n(document);
  relocalize();
  window.addEventListener("hashchange", () => show(currentRoute()));
  show(currentRoute());

  worker = startWorker();
  loadProfiles()
    .then((doc) => { profiles = doc.profiles; fillNoiseSelect(); renderProfiles(); })
    .catch(() => { /* profiles are optional; the ideal and custom models still work */ });
  boot().catch((e) => {
    bootState = "failed";
    $("#hero-limit").textContent = t("err.boot", { e: String((e as Error).message ?? e) });
  });
}

start();
