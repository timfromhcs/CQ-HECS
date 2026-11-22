// Quantum Gravity Lab (route #/qg). Lazy-loaded by main.ts.
//
// Rules (QGRAVITY.md 8.3, docs/DESIGN_SYSTEM.md): every number has a source; status is text, never
// colour alone; no fake live data, no fabricated queue depth, noise or "score"; empty states say
// which data is missing; the browser never holds credentials and never submits a paid job.
import { onLangChange } from "./i18n";
import { sha256Hex } from "./digest";
import { qt } from "./qg_i18n";
import {
  OBSERVABLES, SNAPSHOT, bmvQasm, measuredScan, modelCurve, parseBounded, qasmStats, runBmv, scanCsv,
  shortHash, submitRefusal, validatePlan, type BmvResult, type ChartPoint, type PlanInput,
} from "./qg_logic";

const TABS = ["overview", "theories", "model", "circuit", "design", "backends", "analysis", "evidence"] as const;
type Tab = (typeof TABS)[number];

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

interface Probe { at: string; wasm: boolean; gpu: { status: "AVAILABLE" | "UNAVAILABLE"; key: string; e?: string } }

const st = {
  tab: "overview" as Tab,
  theta: "pi/4", a: "0", b: "0",
  ack: false,
  result: null as null | { r: BmvResult; theta: number; a: number; b: number },
  modelErr: "" as string,
  design: {
    hypothesis: "", thetas: "0 pi/8 pi/4 3pi/8 pi/2", shots: "1000", seed: "20260101", fitFraction: "0.5",
    observable: "YZ", stopRule: "",
  } as PlanInput,
  designTouched: false,
  planJson: "" as string,
  designErr: "" as string,
  refusalJson: "" as string,
  probe: null as null | Probe,
  probing: false,
};

let host: HTMLElement | null = null;

const CSS = `
.qg{display:grid;gap:16px;grid-template-columns:minmax(0,1fr)}
.qg>*{min-width:0}
.qg-tabs{display:flex;gap:.25rem;overflow-x:auto;padding:.25rem;background:var(--panel);border:1px solid var(--line);border-radius:14px}
.qg-tabs button{min-height:36px;padding:.35rem .8rem;border:0;border-radius:10px;background:transparent;color:var(--muted);font:inherit;font-size:.88rem;cursor:pointer;white-space:nowrap}
.qg-tabs button:hover{color:var(--text)}
.qg-tabs button[aria-selected="true"]{background:var(--gate);color:var(--text);box-shadow:inset 0 -2px 0 var(--accent)}
.qg-grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr))}
.qg-grid>*{min-width:0}
.qg-chip{display:inline-block;font:600 .72rem var(--mono);padding:.2rem .55rem;border:1px solid var(--line);border-radius:999px;background:var(--bg-2);color:var(--text);margin:0 .3rem .3rem 0;white-space:nowrap}
.qg-chip.warn{border-color:var(--warn)}.qg-chip.bad{border-color:var(--bad)}.qg-chip.good{border-color:var(--good)}
.qg ul{margin:.3rem 0 .6rem;padding-left:1.2rem}
.qg p,.qg li,.qg h2,.qg h3,.qg h4{overflow-wrap:anywhere}
.qg dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:.2rem .9rem;margin:.4rem 0}
.qg dt{color:var(--muted)}.qg dd{margin:0;overflow-wrap:anywhere}
.qg .row{display:flex;flex-wrap:wrap;gap:.8rem;align-items:end}
.qg label{display:grid;gap:.25rem;font-size:.82rem;color:var(--muted)}
.qg input[type=text],.qg input[type=number],.qg select,.qg textarea{width:100%;min-height:38px}
.qg .row label{flex:1 1 9rem}
.qg label.inline{display:flex;gap:.5rem;align-items:center;color:var(--text);font-size:.9rem}
.qg label.inline input{width:20px;height:20px}
.qg .scroll{overflow:auto;max-width:100%;border:1px solid var(--line);border-radius:10px}
.qg .scroll table{min-width:34rem}
.qg pre{margin:.4rem 0;white-space:pre-wrap;overflow-wrap:anywhere}
.qg .sha{font-family:var(--mono);font-size:.78rem;overflow-wrap:anywhere}
.qg .err{color:var(--bad)}.qg .note{color:var(--muted);font-size:.84rem}
.qg-svg{width:100%;height:auto;display:block}
.qg-svg text{fill:var(--muted);font-size:11px;font-family:Inter,system-ui,sans-serif}
.qg-svg .axis{stroke:var(--wire);stroke-width:1;fill:none}
.qg-svg .grid{stroke:var(--line);stroke-width:1}
.qg-svg .gate{fill:var(--gate);stroke:var(--wire)}
.qg-svg .gate-t{fill:var(--text);font-size:12px}
.qg-leg{display:flex;flex-wrap:wrap;gap:.4rem 1.2rem;margin:.4rem 0;padding:0;list-style:none}
.qg-leg li{display:flex;align-items:center;gap:.4rem;font-size:.84rem}
.qg details summary{cursor:pointer;min-height:24px}
@media (prefers-reduced-motion:reduce){.qg *{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
`;

function injectCss() {
  if (document.getElementById("qg-style")) return;
  const s = document.createElement("style");
  s.id = "qg-style";
  s.textContent = CSS;
  document.head.append(s);
}

function chip(text: string, kind = "") { return `<span class="qg-chip ${kind}">${esc(text)}</span>`; }
const f6 = (x: number) => (Object.is(x, -0) ? 0 : x).toFixed(6);

function download(name: string, mime: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function bmvMethod() { return SNAPSHOT.methods.find((m) => m.method_id === "qg.bmv.zz.v1")!; }

function params(): { theta: number; a: number; b: number } | null {
  const theta = parseBounded(st.theta), a = parseBounded(st.a), b = parseBounded(st.b);
  return theta === null || a === null || b === null ? null : { theta, a, b };
}

// ------------------------------------------------------------------ panels

function panelOverview(): string {
  const rows = SNAPSHOT.tracks.map((tr) => `<tr><th scope="row">${esc(tr.id)}</th><td>${esc(tr.title)}</td><td>${chip(tr.status, /DEFERRED|PROPOSED/.test(tr.status) ? "warn" : "good")}</td></tr>`).join("");
  return `
  <h2>${qt("tab.overview")}</h2>
  <div class="qg-grid">
    <article class="card"><h3>${qt("ov.status")}</h3>
      <div class="scroll" role="region" tabindex="0" aria-label="${esc(qt("ov.status"))}"><table><thead><tr><th>${qt("ov.track")}</th><th>${qt("th.title")}</th><th>${qt("ov.statusCol")}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="note">${qt("ov.statusNote")}</p></article>
    <article class="card"><h3>${qt("ov.integrity")}</h3>
      <p>${qt("ov.integrityBody", { n: SNAPSHOT.files.length, campaign: SNAPSHOT.campaign })}</p>
      <h3>${qt("ov.recorded")}</h3>
      <p>${qt("ov.recordedBody", { a: SNAPSHOT.bmv_scan.length, backend: SNAPSHOT.backend, b: SNAPSHOT.smoke.length, c: SNAPSHOT.syk_v3.length })}</p></article>
    <article class="card"><h3>${qt("ov.capability")}</h3><p>${qt("ov.can")}</p><p>${qt("ov.cannot")}</p></article>
  </div>`;
}

function panelTheories(): string {
  const tracks = SNAPSHOT.tracks.map((tr) => `<li><b>${esc(tr.id)}</b> ${esc(tr.title)} ${chip(tr.status)}</li>`).join("");
  const li = (a: readonly string[]) => a.map((x) => `<li>${esc(x)}</li>`).join("");
  const methods = SNAPSHOT.methods.map((m) => `
    <article class="card" aria-labelledby="qg-m-${esc(m.method_id)}">
      <h3 id="qg-m-${esc(m.method_id)}">${esc(m.title)}</h3>
      <p>${chip(m.method_id)}${chip(`${qt("th.surface")}: ${m.surface}`)}${chip(m.status, /PROPOSED|DEFERRED/.test(m.status) ? "warn" : "good")}</p>
      <h4>${qt("th.assumptions")}</h4><ul>${li(m.assumptions)}</ul>
      <h4>${qt("th.observables")}</h4><p>${esc(m.observables.join(", "))}</p>
      <h4>${qt("th.established")}</h4><p>${esc(m.established)}</p>
      <h4>${qt("th.cannot")}</h4><ul>${li(m.cannot_establish)}</ul>
      <p class="note">${qt("th.refs")}: ${esc(m.references.join(", "))}</p>
      ${m.method_id === "qg.bmv.zz.v1" ? `<button class="btn ghost" data-qg-go="model">${qt("th.useModel")}</button>` : `<p class="note">${qt("th.noBrowser")}</p>`}
    </article>`).join("");
  return `<h2>${qt("th.title")}</h2><article class="card"><h3>${qt("th.tracks")}</h3><ul>${tracks}</ul></article>
    <h3>${qt("th.methods")}</h3><div class="qg-grid">${methods}</div>`;
}

function resultHtml(): string {
  const x = st.result;
  if (!x) return `<p class="muted">${qt("mb.noResult")}</p>`;
  const r = x.r;
  const rows: [string, string, string][] = [
    [qt("mb.concurrence"), f6(r.concurrence), qt("mb.dimensionless")],
    [qt("mb.negativity"), f6(r.negativity), qt("mb.dimensionless")],
    [qt("mb.entropy"), f6(r.entropyBits), qt("mb.bits")],
    [qt("mb.chsh"), f6(r.chshMax), qt("mb.dimensionless")],
    [qt("mb.phase"), f6(((r.entanglingPhase % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI)), qt("mb.rad")],
  ];
  return `<p>${chip("Simulator", "")}${chip("not QPU", "")}${chip("f64", "good")}${chip("COMPLETED", "good")}</p>
    <p>${qt("mb.surfaceLine")}</p>
    <p class="note">theta = ${f6(x.theta)}, a = ${f6(x.a)}, b = ${f6(x.b)} (${qt("mb.rad")})</p>
    <div class="scroll" role="region" tabindex="0" aria-label="${esc(qt("mb.result"))}"><table><thead><tr><th>${qt("mb.observable")}</th><th>${qt("mb.value")}</th><th>${qt("mb.unit")}</th></tr></thead><tbody>
    ${rows.map((r2) => `<tr><td>${esc(r2[0])}</td><td class="sha">${r2[1]}</td><td>${esc(r2[2])}</td></tr>`).join("")}</tbody></table></div>
    <h4>${qt("mb.probs")}</h4>
    <div class="scroll" role="region" tabindex="0" aria-label="${esc(qt("mb.probs"))}"><table><thead><tr><th>${qt("mb.outcome")}</th><th>${qt("mb.value")}</th></tr></thead><tbody>
    ${Object.entries(r.probabilities).map(([k, v]) => `<tr><td class="sha">${k}</td><td class="sha">${f6(v)}</td></tr>`).join("")}</tbody></table></div>
    <p class="note">${qt("mb.probNote")}</p><p class="note">${qt("mb.limits")}</p>`;
}

function panelModel(): string {
  const m = bmvMethod();
  return `<h2>${qt("mb.title")}</h2>
  <div class="qg-grid">
    <article class="card"><h3>${qt("mb.name")}</h3>
      <dl><dt>${qt("mb.hamiltonian")}</dt><dd class="sha">${esc(qt("mb.term"))}</dd>
      <dt>${qt("mb.encoding")}</dt><dd>${qt("mb.encodingBody")}</dd>
      <dt>${qt("mb.units")}</dt><dd>${qt("mb.unitsBody")}</dd>
      <dt>${qt("mb.symmetry")}</dt><dd>${qt("mb.symmetryBody")}</dd>
      <dt>${qt("mb.boundary")}</dt><dd>${qt("mb.boundaryBody")}</dd></dl>
      <h3>${qt("mb.assumptions")}</h3><ul>${m.assumptions.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>
    </article>
    <article class="card"><h3>${qt("mb.params")}</h3>
      <div class="row">
        <label>${qt("mb.theta")}<input id="qg-theta" type="text" inputmode="text" autocomplete="off" value="${esc(st.theta)}" aria-describedby="qg-hint"></label>
        <label>${qt("mb.phaseA")}<input id="qg-pa" type="text" inputmode="text" autocomplete="off" value="${esc(st.a)}" aria-describedby="qg-hint"></label>
        <label>${qt("mb.phaseB")}<input id="qg-pb" type="text" inputmode="text" autocomplete="off" value="${esc(st.b)}" aria-describedby="qg-hint"></label>
      </div>
      <p id="qg-hint" class="note">${qt("mb.hint")}</p>
      <label class="inline"><input id="qg-ack" type="checkbox" ${st.ack ? "checked" : ""} aria-describedby="qg-ack-note">${qt("mb.ack")}</label>
      <p id="qg-ack-note" class="note">${qt("mb.needAck")}</p>
      <button id="qg-run" class="btn primary" ${st.ack ? "" : "disabled"}>${qt("mb.run")}</button>
      <p id="qg-mb-err" class="err" role="alert">${esc(st.modelErr)}</p>
    </article>
  </div>
  <article class="card"><h3>${qt("mb.result")}</h3><div id="qg-mb-result" aria-live="polite">${resultHtml()}</div></article>`;
}

function circuitSvg(a: string, b: string): string {
  const W = 640, H = 150, y0 = 40, y1 = 100;
  const gate = (x: number, y: number, label: string) => `<rect class="gate" x="${x - 22}" y="${y - 15}" width="44" height="30" rx="6"/><text class="gate-t" x="${x}" y="${y + 4}" text-anchor="middle">${esc(label)}</text>`;
  const cx = (x: number) => `<line class="axis" x1="${x}" y1="${y0}" x2="${x}" y2="${y1}"/><circle cx="${x}" cy="${y0}" r="4" fill="var(--text)"/><circle class="gate" cx="${x}" cy="${y1}" r="11"/><path class="axis" d="M${x - 11} ${y1}H${x + 11}M${x} ${y1 - 11}V${y1 + 11}"/>`;
  const meas = (x: number, y: number) => `<rect class="gate" x="${x - 18}" y="${y - 15}" width="36" height="30" rx="6"/><path class="axis" d="M${x - 9} ${y + 6}A10 10 0 0 1 ${x + 9} ${y + 6}M${x} ${y + 6}L${x + 7} ${y - 6}"/>`;
  return `<svg class="qg-svg" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="qg-cd-t qg-cd-d"><title id="qg-cd-t">${qt("ci.diagram")}</title><desc id="qg-cd-d">${qt("ci.diagramDesc")}</desc>
    <text x="8" y="${y0 + 4}">q0</text><text x="8" y="${y1 + 4}">q1</text>
    <line class="axis" x1="34" y1="${y0}" x2="${W - 10}" y2="${y0}"/><line class="axis" x1="34" y1="${y1}" x2="${W - 10}" y2="${y1}"/>
    ${gate(70, y0, "H")}${gate(70, y1, "H")}${cx(135)}${gate(200, y1, "Rz(θ)")}${cx(265)}${gate(335, y0, "Rz(" + a + ")")}${gate(335, y1, "Rz(" + b + ")")}${meas(420, y0)}${meas(420, y1)}</svg>`;
}

function panelCircuit(): string {
  const p = params();
  if (!p) return `<h2>${qt("ci.title")}</h2><article class="card"><p class="err" role="alert">${qt("mb.bad", { field: "theta / a / b" })}</p></article>`;
  const qasm = bmvQasm({ theta: p.theta, phaseA: p.a, phaseB: p.b });
  const s = qasmStats(qasm);
  return `<h2>${qt("ci.title")}</h2>
  <article class="card"><p class="note">${qt("ci.params", { theta: f6(p.theta), a: f6(p.a), b: f6(p.b) })}</p>
    ${circuitSvg("a", "b")}
    <h3>${qt("ci.qasm")}</h3>
    <pre id="qg-qasm" tabindex="0" aria-label="${esc(qt("ci.qasmLabel"))}">${esc(qasm)}</pre>
    <dl><dt>${qt("ci.digest")}</dt><dd id="qg-digest" class="sha" aria-live="polite">${qt("ci.digestWait")}</dd></dl>
    <div class="row"><button id="qg-dl-qasm" class="btn ghost">${qt("ci.download")}</button><button id="qg-copy" class="btn ghost">${qt("ci.copy")}</button><span id="qg-copied" role="status" class="note"></span></div>
  </article>
  <article class="card"><h3>${qt("ci.stats")}</h3>
    <dl><dt>${qt("ci.width")}</dt><dd>${s.width}</dd><dt>${qt("ci.gates")}</dt><dd>${s.gates}</dd><dt>${qt("ci.depth")}</dt><dd>${s.depth}</dd>
    <dt>${qt("ci.counts")}</dt><dd>${esc(Object.entries(s.counts).map(([k, v]) => `${k}: ${v}`).join(", "))}</dd></dl>
    <p class="note">${qt("ci.lowering")}</p></article>`;
}

function panelDesign(): string {
  const d = st.design;
  if (!st.designTouched) { d.hypothesis = d.hypothesis || qt("ex.hypothesisDefault"); d.stopRule = d.stopRule || qt("ex.stopDefault"); }
  const sub = submitRefusal();
  return `<h2>${qt("ex.title")}</h2><p>${qt("ex.intro")}</p>
  <div class="qg-grid">
  <article class="card"><form id="qg-form" novalidate>
    <label>${qt("ex.hypothesis")}<textarea id="qg-hyp" rows="3">${esc(d.hypothesis)}</textarea></label>
    <label>${qt("ex.thetas")}<input id="qg-thetas" type="text" value="${esc(d.thetas)}" aria-describedby="qg-thetas-h"></label>
    <p id="qg-thetas-h" class="note">${qt("ex.thetasHelp")}</p>
    <div class="row">
      <label>${qt("ex.shots")}<input id="qg-shots" type="text" inputmode="numeric" value="${esc(d.shots)}"></label>
      <label>${qt("ex.seed")}<input id="qg-seed" type="text" inputmode="numeric" value="${esc(d.seed)}"></label>
      <label>${qt("ex.fit")}<input id="qg-fit" type="text" inputmode="decimal" value="${esc(d.fitFraction)}"></label>
    </div>
    <label>${qt("ex.observable")}<select id="qg-obs">${OBSERVABLES.map((o) => `<option ${o === d.observable ? "selected" : ""}>${o}</option>`).join("")}</select></label>
    <label>${qt("ex.stop")}<textarea id="qg-stop" rows="2">${esc(d.stopRule)}</textarea></label>
    <button class="btn primary" type="submit">${qt("ex.build")}</button>
    <p id="qg-design-err" class="err" role="alert">${esc(st.designErr)}</p>
  </form></article>
  <article class="card"><h3>${qt("ex.plan")}</h3>
    <div id="qg-plan">${st.planJson ? `<pre tabindex="0" aria-label="${esc(qt("ex.plan"))}">${esc(st.planJson)}</pre><button id="qg-dl-plan" class="btn ghost">${qt("ex.download")}</button>` : `<p class="muted">${qt("ex.planNone")}</p>`}</div>
    <h3>${qt("ex.credit")}</h3><p>${qt("ex.creditNone")}</p>
    <h3>${qt("ex.submit")}</h3><p>${chip(sub.status, "bad")}${chip("spend 0")}${chip("network none")}</p><p>${qt("ex.submitBody")}</p>
    <button id="qg-try" class="btn ghost">${qt("ex.try")}</button>
    <div id="qg-refusal" role="status">${st.refusalJson ? `<p><b>${qt("ex.refusal")}</b></p><pre tabindex="0" aria-label="${esc(qt("ex.refusal"))}">${esc(st.refusalJson)}</pre>` : ""}</div>
    <p class="note">${qt("ex.cancel")}</p>
  </article>
  <article class="card"><h3>${qt("ex.monitor")}</h3><p>${qt("ex.monitorBody")}</p></article>
  </div>`;
}

function probeRow(name: string, type: string, prec: string, status: string, statusKind: string, features: string, blockers: string): string {
  return `<tr><th scope="row">${esc(name)}</th><td>${chip(type)}</td><td>${prec ? chip(prec) : ""}</td><td>${chip(status, statusKind)}</td><td>${esc(features)}</td><td>${esc(blockers)}</td></tr>`;
}

function panelBackends(): string {
  const pr = st.probe;
  const when = pr ? qt("bk.checkedAt", { time: pr.at }) : qt("bk.probing");
  const wasm = pr ? (pr.wasm ? [qt("bk.available"), "good", qt("bk.wasmYes")] : [qt("bk.unavailable"), "bad", qt("bk.wasmNo")]) : [qt("bk.probing"), "", ""];
  const gpu = pr ? [pr.gpu.status === "AVAILABLE" ? qt("bk.available") : qt("bk.unavailable"), pr.gpu.status === "AVAILABLE" ? "good" : "bad", qt(pr.gpu.key, { e: pr.gpu.e ?? "" })] : [qt("bk.probing"), "", ""];
  const rows = [
    probeRow(qt("bk.qpu"), "QPU", "", "NOT QUERIED", "warn", qt("bk.qpuFeat"), qt("bk.qpuBlock")),
    probeRow(qt("bk.sim"), "Simulator", "", "NOT QUERIED", "warn", qt("bk.simFeat"), qt("bk.simBlock")),
    probeRow(qt("bk.cpu"), "CPU", "f64", "NOT QUERIED", "warn", qt("bk.cpuFeat"), qt("bk.cpuBlock")),
    probeRow(qt("bk.vk"), "Vulkan", "", "NOT QUERIED", "warn", qt("bk.vkFeat"), qt("bk.vkBlock")),
    probeRow(qt("bk.wasm"), "WASM", "f64", `${wasm[0]} · ${when}`, wasm[1], qt("bk.wasmFeat"), wasm[2]),
    probeRow(qt("bk.gpu"), "WebGPU", "f32", `${gpu[0]} · ${when}`, gpu[1], qt("bk.gpuFeat"), gpu[2]),
  ].join("");
  return `<h2>${qt("bk.title")}</h2><p>${qt("bk.intro")}</p>
  <article class="card"><div class="scroll" role="region" tabindex="0" aria-label="${esc(qt("bk.title"))}"><table style="min-width:56rem"><thead><tr><th>${qt("bk.name")}</th><th>${qt("bk.type")}</th><th>${qt("bk.precision")}</th><th>${qt("bk.status")}</th><th>${qt("bk.features")}</th><th>${qt("bk.blockers")}</th></tr></thead><tbody>${rows}</tbody></table></div>
  <p><button id="qg-reprobe" class="btn ghost" ${st.probing ? "disabled" : ""}>${qt("bk.reprobe")}</button></p></article>`;
}

function chartSvg(pts: ChartPoint[], curve: ChartPoint[]): string {
  const W = 640, H = 340, L = 58, R = 16, T = 14, B = 52;
  const xmax = 1.65, ymin = -0.1, ymax = 1.1;
  const X = (x: number) => L + (x / xmax) * (W - L - R);
  const Y = (y: number) => T + (1 - (y - ymin) / (ymax - ymin)) * (H - T - B);
  const xt = [0, 0.5, 1, 1.5], yt = [0, 0.25, 0.5, 0.75, 1];
  const grid = yt.map((y) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${Y(y)}" y2="${Y(y)}"/><text x="${L - 8}" y="${Y(y) + 4}" text-anchor="end">${y}</text>`).join("")
    + xt.map((x) => `<line class="grid" y1="${T}" y2="${H - B}" x1="${X(x)}" x2="${X(x)}"/><text x="${X(x)}" y="${H - B + 16}" text-anchor="middle">${x}</text>`).join("");
  const line = `<polyline fill="none" stroke="var(--muted)" stroke-width="2" stroke-dasharray="6 4" points="${curve.map((c) => `${X(c.x).toFixed(1)},${Y(c.y).toFixed(1)}`).join(" ")}"/>`;
  const mark = (p: ChartPoint) => {
    const cx = X(p.x), cy = Y(p.y), color = p.series === "YZ" ? "var(--accent)" : "var(--accent-2)";
    const bar = p.err ? `<line x1="${cx}" x2="${cx}" y1="${Y(p.y - p.err)}" y2="${Y(p.y + p.err)}" stroke="${color}" stroke-width="2"/><line x1="${cx - 4}" x2="${cx + 4}" y1="${Y(p.y + p.err)}" y2="${Y(p.y + p.err)}" stroke="${color}" stroke-width="2"/><line x1="${cx - 4}" x2="${cx + 4}" y1="${Y(p.y - p.err)}" y2="${Y(p.y - p.err)}" stroke="${color}" stroke-width="2"/>` : "";
    const shape = p.series === "YZ" ? `<circle cx="${cx}" cy="${cy}" r="5" fill="${color}"/>` : `<rect x="${cx - 5}" y="${cy - 5}" width="10" height="10" fill="${color}"/>`;
    return `<g><title>${p.series}: theta ${f6(p.x)} rad, ${p.y} ± ${p.err?.toFixed(4) ?? "?"}</title>${bar}${shape}</g>`;
  };
  return `<svg class="qg-svg" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="qg-ch-t qg-ch-d"><title id="qg-ch-t">${qt("an.chartTitle")}</title><desc id="qg-ch-d">${qt("an.chartDesc")}</desc>
    ${grid}<path class="axis" d="M${L} ${T}V${H - B}H${W - R}"/>${line}${pts.map(mark).join("")}
    <text x="${(L + W - R) / 2}" y="${H - 10}" text-anchor="middle">${qt("an.x")}</text>
    <text transform="translate(14 ${(T + H - B) / 2}) rotate(-90)" text-anchor="middle">${qt("an.y")}</text></svg>`;
}

function panelAnalysis(): string {
  const all = measuredScan();
  const chartPts = all.filter((p) => p.series === "YZ" || p.series === "ZY");
  const scanFile = SNAPSHOT.files.find((f) => f.path.endsWith("bmv_phase_scan.json"))!;
  const shots = SNAPSHOT.bmv_scan[0]?.shots ?? 0;
  const rows = all.map((p) => `<tr><td>${p.series}</td><td class="sha">${f6(p.x)}</td><td class="sha">${p.y}</td><td class="sha">${p.err?.toFixed(4) ?? ""}</td><td>QPU</td></tr>`).join("");
  const xx = SNAPSHOT.bmv_xx.map((p) => `<tr><td class="sha">${f6(p.theta)}</td><td class="sha">${p.xx}</td><td class="sha">${p.ci95[0].toFixed(3)} to ${p.ci95[1].toFixed(3)}</td><td>${p.source === "original" ? qt("an.original") : qt("an.followup")}</td></tr>`).join("");
  const smoke = SNAPSHOT.smoke.map((s) => `<tr><td>${esc(s.circuit_id)}</td><td class="sha">${s.in_support_fraction}</td><td>${s.shots}</td></tr>`).join("");
  const syk = SNAPSHOT.syk_v3.map((c) => `<tr><td>${esc(c.circuit_id)}</td><td class="sha">${c.p000} [${c.ci95[0].toFixed(3)}, ${c.ci95[1].toFixed(3)}]</td><td class="sha">${c.ideal_p000.toFixed(4)}</td><td class="sha">${c.uniform}</td><td>${c.shots}</td></tr>`).join("");
  const wrap = (label: string, body: string) => `<div class="scroll" role="region" tabindex="0" aria-label="${esc(label)}"><table>${body}</table></div>`;
  return `<h2>${qt("an.title")}</h2>
  <article class="card"><h3>${qt("an.chartTitle")}</h3>
    <p>${chip("QPU")}${chip("measured", "good")}${chip("Model", "")}${chip("analytic")}</p>
    ${chartSvg(chartPts, modelCurve())}
    <ul class="qg-leg"><li><svg width="26" height="10" aria-hidden="true"><line x1="0" x2="26" y1="5" y2="5" stroke="var(--muted)" stroke-width="2" stroke-dasharray="6 4"/></svg>${qt("an.legendModel")}</li>
    <li><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5" fill="var(--accent)"/></svg>${qt("an.legendYZ")}</li>
    <li><svg width="14" height="14" aria-hidden="true"><rect x="2" y="2" width="10" height="10" fill="var(--accent-2)"/></svg>${qt("an.legendZY")}</li></ul>
    <p class="note">${qt("an.err")}</p>
    <p class="note">${qt("an.prov", { backend: SNAPSHOT.backend, shots, src: scanFile.path, hash: shortHash(scanFile.sha256) })}</p>
    <details open><summary>${qt("an.table")}</summary>
    ${wrap(qt("an.table"), `<thead><tr><th>${qt("an.basis")}</th><th>${qt("an.theta")}</th><th>${qt("an.corr")}</th><th>${qt("an.stderr")}</th><th>${qt("an.src")}</th></tr></thead><tbody>${rows}</tbody>`)}</details>
    <div class="row"><button id="qg-csv" class="btn ghost">${qt("an.csv")}</button><button id="qg-json" class="btn ghost">${qt("an.json")}</button></div></article>
  <div class="qg-grid">
  <article class="card"><h3>${qt("an.xx")}</h3>${wrap(qt("an.xx"), `<thead><tr><th>${qt("an.theta")}</th><th>XX</th><th>${qt("an.ci")}</th><th>${qt("an.xxSrc")}</th></tr></thead><tbody>${xx}</tbody>`)}</article>
  <article class="card"><h3>${qt("an.smoke")}</h3>${wrap(qt("an.smoke"), `<thead><tr><th>${qt("an.circuit")}</th><th>${qt("an.inSupport")}</th><th>${qt("an.shots")}</th></tr></thead><tbody>${smoke}</tbody>`)}</article>
  <article class="card"><h3>${qt("an.syk")}</h3><p>${chip("QPU")}${chip("INCONCLUSIVE", "warn")}</p><p>${qt("an.sykStatus")}</p>
    ${wrap(qt("an.syk"), `<thead><tr><th>${qt("an.circuit")}</th><th>${qt("an.p000")} [95%]</th><th>${qt("an.ideal")}</th><th>${qt("an.uniform")}</th><th>${qt("an.shots")}</th></tr></thead><tbody>${syk}</tbody>`)}
    <p class="note">${qt("an.sykMissing", { ids: SNAPSHOT.syk_missing.join(", ") || "-" })}</p></article>
  <article class="card"><h3>${qt("an.missingTitle")}</h3><p>${qt("an.missing")}</p></article>
  </div>`;
}

function panelEvidence(): string {
  const rows = SNAPSHOT.files.map((f) => `<tr><td class="sha">${esc(f.path)}</td><td>${f.bytes}</td><td class="sha">${f.sha256}</td></tr>`).join("");
  return `<h2>${qt("ev.title")}</h2><article class="card"><p>${qt("ev.intro", { policy: SNAPSHOT.sha_policy })}</p>
    ${rows ? `<div class="scroll" role="region" tabindex="0" aria-label="${esc(qt("ev.title"))}"><table style="min-width:44rem"><thead><tr><th>${qt("ev.file")}</th><th>${qt("ev.bytes")}</th><th>${qt("ev.sha")}</th></tr></thead><tbody>${rows}</tbody></table></div>` : `<p class="muted">${qt("ev.empty")}</p>`}
    <p class="note">${qt("ev.excluded")}</p><p class="note">${qt("ev.where")}</p></article>`;
}

const PANELS: Record<Tab, () => string> = {
  overview: panelOverview, theories: panelTheories, model: panelModel, circuit: panelCircuit,
  design: panelDesign, backends: panelBackends, analysis: panelAnalysis, evidence: panelEvidence,
};

// ------------------------------------------------------------------ wiring

function bind(root: HTMLElement) {
  root.querySelectorAll<HTMLElement>("[data-qg-go]").forEach((b) => b.addEventListener("click", () => select(b.dataset.qgGo as Tab, true)));
  const val = (id: string) => (root.querySelector<HTMLInputElement>(id)!).value;
  if (st.tab === "model") {
    root.querySelector("#qg-theta")!.addEventListener("input", () => { st.theta = val("#qg-theta"); });
    root.querySelector("#qg-pa")!.addEventListener("input", () => { st.a = val("#qg-pa"); });
    root.querySelector("#qg-pb")!.addEventListener("input", () => { st.b = val("#qg-pb"); });
    const run = root.querySelector<HTMLButtonElement>("#qg-run")!;
    root.querySelector<HTMLInputElement>("#qg-ack")!.addEventListener("change", (e) => {
      st.ack = (e.target as HTMLInputElement).checked; run.disabled = !st.ack;
    });
    run.addEventListener("click", () => {
      const names: [string, number | null][] = [["theta", parseBounded(st.theta)], ["a", parseBounded(st.a)], ["b", parseBounded(st.b)]];
      const bad = names.find(([, v]) => v === null);
      const err = root.querySelector<HTMLElement>("#qg-mb-err")!;
      if (bad) { st.modelErr = qt("mb.bad", { field: bad[0] }); err.textContent = st.modelErr; return; }
      st.modelErr = ""; err.textContent = "";
      const [theta, a, b] = names.map(([, v]) => v as number);
      st.result = { r: runBmv({ theta, phaseA: a, phaseB: b }), theta, a, b };
      root.querySelector("#qg-mb-result")!.innerHTML = resultHtml();
    });
  }
  if (st.tab === "circuit") {
    const p = params();
    if (p) {
      const qasm = bmvQasm({ theta: p.theta, phaseA: p.a, phaseB: p.b });
      const out = root.querySelector<HTMLElement>("#qg-digest")!;
      let digest = "";
      sha256Hex(qasm).then((h) => { digest = h; out.textContent = h; }).catch(() => { out.textContent = qt("ci.digestNo"); });
      root.querySelector("#qg-dl-qasm")!.addEventListener("click", () => download("qg-bmv.qasm", "text/plain", qasm));
      root.querySelector("#qg-copy")!.addEventListener("click", async () => {
        if (!digest) return;
        try { await navigator.clipboard.writeText(digest); root.querySelector("#qg-copied")!.textContent = qt("ci.copied"); } catch { /* clipboard blocked */ }
      });
    }
  }
  if (st.tab === "design") {
    root.querySelector<HTMLFormElement>("#qg-form")!.addEventListener("submit", (e) => {
      e.preventDefault();
      st.designTouched = true;
      st.design = {
        hypothesis: val("#qg-hyp"), thetas: val("#qg-thetas"), shots: val("#qg-shots"), seed: val("#qg-seed"),
        fitFraction: val("#qg-fit"), observable: val("#qg-obs"), stopRule: val("#qg-stop"),
      };
      const res = validatePlan(st.design);
      if (!res.ok) {
        st.planJson = "";
        st.designErr = qt("ex.errors", { fields: res.errors.map((k) => qt(`ex.f.${k}`)).join("; ") });
      } else {
        st.designErr = "";
        st.planJson = JSON.stringify(res.plan, null, 2);
      }
      render();
      (st.designErr ? root.querySelector<HTMLElement>("#qg-design-err") : root.querySelector<HTMLElement>("#qg-plan pre"))?.focus?.();
    });
    root.querySelector("#qg-dl-plan")?.addEventListener("click", () => download("qg-experiment-design.json", "application/json", st.planJson + "\n"));
    root.querySelector("#qg-try")!.addEventListener("click", () => {
      st.refusalJson = JSON.stringify(submitRefusal(), null, 2);
      root.querySelector("#qg-refusal")!.innerHTML = `<p><b>${qt("ex.refusal")}</b></p><pre tabindex="0" aria-label="${esc(qt("ex.refusal"))}">${esc(st.refusalJson)}</pre>`;
    });
  }
  if (st.tab === "backends") {
    root.querySelector("#qg-reprobe")!.addEventListener("click", () => { void doProbe(); });
    if (!st.probe && !st.probing) void doProbe();
  }
  if (st.tab === "analysis") {
    root.querySelector("#qg-csv")!.addEventListener("click", () => download("qg-bmv-scan.csv", "text/csv", scanCsv(measuredScan())));
    root.querySelector("#qg-json")!.addEventListener("click", () => download("qg-bmv-scan.json", "application/json", JSON.stringify({
      schema: "cqhecs.web.qg_analysis_export.v1", surface: "QPU", backend: SNAPSHOT.backend,
      source: SNAPSHOT.files.find((f) => f.path.endsWith("bmv_phase_scan.json")), points: SNAPSHOT.bmv_scan,
    }, null, 2) + "\n"));
  }
}

async function doProbe() {
  st.probing = true;
  if (st.tab === "backends") render();
  const wasm = typeof WebAssembly === "object" && typeof WebAssembly.instantiate === "function";
  let gpu: Probe["gpu"];
  const nav = navigator as Navigator & { gpu?: { requestAdapter(): Promise<unknown | null> } };
  if (!nav.gpu) gpu = { status: "UNAVAILABLE", key: "bk.gpuNoApi" };
  else {
    try { gpu = (await nav.gpu.requestAdapter()) ? { status: "AVAILABLE", key: "bk.gpuYes" } : { status: "UNAVAILABLE", key: "bk.gpuNoAdapter" }; }
    catch (e) { gpu = { status: "UNAVAILABLE", key: "bk.gpuErr", e: String((e as Error).message ?? e) }; }
  }
  st.probe = { at: new Date().toISOString(), wasm, gpu };
  st.probing = false;
  if (st.tab === "backends") render();
}

function select(tab: Tab, focusPanel = false) {
  st.tab = tab;
  render();
  if (focusPanel) host?.querySelector<HTMLElement>(`#qg-tab-${tab}`)?.focus();
}

function render() {
  if (!host) return;
  const active = document.activeElement as HTMLElement | null;
  const keepFocus = active && host.contains(active) ? active.id : "";
  host.innerHTML = `<div class="qg">
    <header><h1>${qt("qg.title")}</h1><p class="lead">${qt("qg.lead")}</p><p class="note">${qt("qg.disclaimer")}</p></header>
    <div class="qg-tabs" role="tablist" aria-label="${esc(qt("qg.tablist"))}">${TABS.map((tb) =>
      `<button role="tab" id="qg-tab-${tb}" aria-controls="qg-panel" aria-selected="${tb === st.tab}" tabindex="${tb === st.tab ? 0 : -1}" data-tab="${tb}">${qt(`tab.${tb}`)}</button>`).join("")}</div>
    <div id="qg-panel" role="tabpanel" aria-labelledby="qg-tab-${st.tab}" tabindex="0">${PANELS[st.tab]()}</div></div>`;
  const tabs = host.querySelectorAll<HTMLButtonElement>("[role=tab]");
  tabs.forEach((b, i) => {
    b.addEventListener("click", () => select(b.dataset.tab as Tab));
    b.addEventListener("keydown", (e) => {
      const keys: Record<string, number> = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 };
      if (!(e.key in keys)) return;
      e.preventDefault();
      const next = (keys[e.key] + tabs.length) % tabs.length;
      select(TABS[next], true);
    });
  });
  bind(host);
  if (keepFocus) host.querySelector<HTMLElement>(`#${keepFocus}`)?.focus();
}

export function mountQg(el: HTMLElement) {
  if (host === el) return;
  host = el;
  injectCss();
  onLangChange(() => render());
  render();
}
