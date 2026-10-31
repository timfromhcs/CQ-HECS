const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  health: null,
  suite: null,
  noise: null,
  research: null,
  hardware: null,
  presetQasm: {},
};

const TITLES = {
  overview: ["Overview", "Classical four-path quantum emulation, measured noise, sound SAT."],
  circuit: ["Circuit lab", "Run QASM through the router or the exact noisy density matrix."],
  noise: ["Noise lab", "Measured r-io-7 counts against M-FIT and the post-hoc M-FIT-2."],
  sat: ["SAT lab", "Sound DPLL: SAT with a verified model, UNSAT only after exhaustion."],
  evidence: ["Evidence", "The 25 pinned jobs, their digests and their measured distributions."],
  research: ["Research", "P versus NP, ETH, and what a finite experiment can actually say."],
  hardware: ["Hardware", "External QPU runs, independent oracles, and finite P-vs-NP probes."],
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function fmt(value, digits = 4) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return String(value);
    if (Math.abs(value) >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (Math.abs(value) < 0.001 && value !== 0) return value.toExponential(2);
    return value.toFixed(digits).replace(/0+$/, "").replace(/\.$/, "");
  }
  return String(value);
}

function metric(k, v, cls = "") {
  const box = el("div", `metric ${cls}`);
  box.append(el("span", "k", k), el("span", "v", v));
  return box;
}

function toast(message) {
  let node = $("#toast");
  if (!node) {
    node = el("div");
    node.id = "toast";
    Object.assign(node.style, {
      position: "fixed", right: "20px", bottom: "20px", maxWidth: "420px",
      padding: "12px 14px", borderRadius: "12px", zIndex: 50,
      background: "#2a1320", border: "1px solid #7d2b3a", color: "#ffd7dc",
      font: "13px/1.5 var(--sans)", boxShadow: "0 18px 50px rgba(0,0,0,.4)",
    });
    document.body.append(node);
  }
  node.textContent = message;
  node.style.display = "block";
  clearTimeout(node._timer);
  node._timer = setTimeout(() => { node.style.display = "none"; }, 8000);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = payload.error || {};
    throw new Error(`${error.code || response.status}: ${error.message || response.statusText}`);
  }
  return payload;
}

function setView(name) {
  $$("#nav button").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === name));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${name}`));
  const [title, sub] = TITLES[name] || ["CQ-HECS", ""];
  $("#view-title").textContent = title;
  $("#view-sub").textContent = sub;
  history.replaceState(null, "", `#${name}`);
  if (name === "noise" && state.noise && !$("#job-select").childElementCount) {
    fillJobs();
  }
}

/* ---------------------------------------------------------------- overview */

function renderHealth() {
  const h = state.health;
  if (!h) return;
  $("#health-dot").className = "dot ok";
  $("#health-text").textContent = "engine online";
  $("#foot-version").textContent = `v${h.version}`;
  const chips = $("#top-chips");
  chips.innerHTML = "";
  chips.append(
    chip("version", h.version),
    chip("dataset", h.dataset.available ? h.dataset.id : "unavailable"),
    chip("model", h.model.id || "no fit"),
  );

  $("#overview-stats").append(
    stat("Simulation paths", "4", "A stabilizer · B rank · C MPS · D sparse Pauli"),
    stat("Measured jobs", h.dataset.available ? h.dataset.jobs : "—", h.dataset.available ? h.dataset.backend : "dataset unavailable"),
    stat("Sound SAT", "SAT / UNSAT", "timeout is UNKNOWN, never UNSAT"),
    stat("Studio", "local", "127.0.0.1 · no telemetry"),
  );
  $("#real-list").append(
    li("25 measured circuits, pinned by SHA-256 before submission."),
    li("Per-qubit readout and one fitted CX term from real counts."),
    li("Four exact/certified simulation paths with typed refusals."),
    li("SAT models verified clause by clause."),
  );
  $("#not-list").append(
    li("No claim that this emulator is nature."),
    li("No P = NP result and no ETH proof."),
    li("No quantum-hardware execution by this package."),
    li("No silent approximation at a path boundary."),
  );
}

function chip(key, value) {
  const node = el("div", "chip");
  node.append(document.createTextNode(key + " "), el("b", "", value));
  return node;
}

function stat(k, v, s) {
  const node = el("div", "stat");
  node.append(el("div", "k", k), el("div", "v", String(v)), el("div", "s", s));
  return node;
}

function li(text) {
  return el("li", "", text);
}

function renderOverviewEvidence() {
  const s = state.suite;
  if (!s) return;
  const ev = s.evaluation || {};
  const agg = ev.aggregate || {};
  const fit = s.fit2_evaluation || {};
  const models = fit.models || {};
  const box = $("#overview-evidence");
  box.innerHTML = "";
  box.append(
    stat("H-V3-8 (frozen)", agg.verdict || "—", `median ΔTV ${fmt(agg.median_delta_tv)} · CI [${fmt(agg.ci95_low)}, ${fmt(agg.ci95_high)}]`),
    stat("M-FIT-2 (post-hoc)", fmt(models["M-FIT-2"]?.median_delta_tv), `${models["M-FIT-2"]?.n_noisy_better ?? "—"}/20 EVAL jobs closer`),
    stat("Dataset digest", (s.dataset.sha256 || "—").slice(0, 12), s.dataset.backend || "—"),
  );
  $("#dataset-tag").textContent = s.dataset.available ? "measured" : "missing";
}

/* ----------------------------------------------------------------- circuit */

async function loadPreset(name) {
  if (!state.presetQasm[name]) {
    const data = await api(`/api/preset?name=${encodeURIComponent(name)}`);
    state.presetQasm[name] = data.qasm;
  }
  $("#qasm").value = state.presetQasm[name];
}

function fillPresets() {
  const select = $("#preset");
  select.innerHTML = "";
  for (const name of state.health?.presets || ["bell"]) {
    const option = el("option", "", name);
    option.value = name;
    select.append(option);
  }
  select.value = "bell";
}

async function runCircuit() {
  const button = $("#run-circuit");
  button.disabled = true;
  button.textContent = "Running…";
  try {
    const source = $("#qasm").value.trim();
    const payload = await api("/api/simulate", {
      method: "POST",
      body: JSON.stringify({
        source,
        shots: Number($("#shots").value),
        seed: Number($("#seed").value),
        path: $("#path").value,
        noise: $("#noise").value,
      }),
    });
    renderCircuit(payload);
  } catch (error) {
    toast(error.message);
    $("#circuit-state").textContent = "refused";
    $("#circuit-state").className = "tag bad";
  } finally {
    button.disabled = false;
    button.textContent = "Run circuit";
  }
}

function renderCircuit(payload) {
  const result = payload.result;
  const stateTag = $("#circuit-state");
  stateTag.textContent = result.state;
  stateTag.className = `tag ${result.state === "EXACT" ? "ok" : result.state === "UNRESOLVED" ? "bad" : "warn"}`;
  const metrics = $("#circuit-metrics");
  metrics.innerHTML = "";
  metrics.append(
    metric("path", result.path),
    metric("state", result.state, result.state === "EXACT" ? "ok" : "warn"),
    metric("exact", String(result.exact)),
    metric("error bound", fmt(result.error_bound)),
    metric("shots", result.metadata?.shots ?? "—"),
    metric("time ms", fmt(result.execution_time_ms, 2)),
    metric("noise", payload.noise.model),
  );
  const outcomes = payload.outcomes || [];
  drawHistogram($("#circuit-chart"), outcomes.map((row) => ({
    label: row.state,
    value: row.probability ?? row.frequency,
    extra: row.count,
  })));
  renderOutcomeTable($("#circuit-table"), outcomes);
  const details = $("#circuit-json");
  details.querySelector("pre").textContent = JSON.stringify(payload, null, 2);
  $("#circuit-note").textContent = payload.notes?.length ? payload.notes.join(" ") : "";
}

function drawHistogram(container, rows) {
  container.innerHTML = "";
  if (!rows.length) {
    container.append(el("p", "empty", "No outcomes."));
    return;
  }
  const shown = rows.slice(0, 14);
  const rest = rows.slice(14);
  if (rest.length) {
    shown.push({ label: "other", value: rest.reduce((a, b) => a + (b.value || 0), 0), extra: rest.reduce((a, b) => a + (b.extra || 0), 0) });
  }
  const max = Math.max(...shown.map((row) => row.value || 0), 1e-12);
  for (const row of shown) {
    const line = el("div", "bar-row");
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill");
    fill.style.width = `${Math.max(1, (row.value / max) * 100)}%`;
    if (row.label === "other") fill.classList.add("alt");
    track.append(fill);
    line.append(
      el("span", "label", row.label),
      track,
      el("span", "val", row.extra !== undefined ? `${fmt(row.value * 100, 2)}% · ${row.extra}` : `${fmt(row.value * 100, 2)}%`),
    );
    container.append(line);
  }
}

function renderOutcomeTable(container, rows) {
  if (!rows.length) { container.innerHTML = ""; return; }
  const table = el("table");
  const head = el("tr");
  for (const [label, cls] of [["state", ""], ["count", "num"], ["frequency", "num"], ["probability", "num"]]) {
    const th = el("th", cls, label); head.append(th);
  }
  table.append(head);
  for (const row of rows.slice(0, 24)) {
    const tr = el("tr");
    tr.append(
      el("td", "", row.state),
      el("td", "num", String(row.count)),
      el("td", "num", fmt(row.frequency * 100, 2) + "%"),
      el("td", "num", row.probability === null ? "—" : fmt(row.probability * 100, 2) + "%"),
    );
    table.append(tr);
  }
  container.innerHTML = "";
  container.append(table);
}

/* ------------------------------------------------------------------- noise */

function renderNoise() {
  const data = state.noise;
  if (!data) return;
  if (!data.available) {
    $("#noise-summary").textContent = state.health.dataset.note;
    $("#noise-cards").innerHTML = "";
    $("#noise-qubits").innerHTML = "";
    return;
  }
  const model = data.model;
  const ev = data.evaluation || {};
  const models = ev.models || {};
  const fit = model.fit || {};
  const m2 = models["M-FIT-2"] || {};
  const m1 = models["M-FIT"] || {};
  $("#noise-summary").textContent =
    `${model.dataset_id} on ${model.backend}. ${model.identifiability.statement} ` +
    `${model.warnings[0]}`;
  const cards = $("#noise-cards");
  cards.innerHTML = "";
  cards.append(
    stat("FIT residual", fmt(fit.fit_tv), `M-FIT ${fmt(fit.mfit_fit_tv)} · lower is better`),
    stat("M-FIT-2 held-out", fmt(m2.median_delta_tv), `CI [${fmt(m2.ci95_low)}, ${fmt(m2.ci95_high)}]`),
    stat("M-FIT held-out", fmt(m1.median_delta_tv), `${m1.n_noisy_better ?? "—"}/20 jobs closer`),
    stat("Anomalous qubits", (model.identifiability.anomalous_qubits || []).join(", ") || "none", `X bit-flip ${fmt(model.x_bitflip?.[0], 3)}`),
  );

  const table = el("table");
  const head = el("tr");
  ["qubit", "p01", "p10 fitted", "p10 from OQ-02", "X bit-flip", "readout bar"].forEach((label, i) => head.append(el("th", i ? "num" : "", label)));
  table.append(head);
  const maxP = Math.max(...(model.readout.p10 || [0]), 0.1);
  (model.readout.p01 || []).forEach((p01, q) => {
    const tr = el("tr");
    const bar = el("div", "bar-track");
    const fill = el("div", "bar-fill");
    fill.style.width = `${Math.max(2, (model.readout.p10[q] / maxP) * 100)}%`;
    bar.append(fill);
    const barCell = el("td");
    barCell.append(bar);
    tr.append(
      el("td", "", `q${q}`),
      el("td", "num", fmt(p01)),
      el("td", "num", fmt(model.readout.p10[q])),
      el("td", "num", fmt(model.readout.p10_observed_from_OQ02[q])),
      el("td", "num", fmt(model.x_bitflip[q])),
      barCell,
    );
    table.append(tr);
  });
  $("#noise-qubits").innerHTML = "";
  $("#noise-qubits").append(table);

  const chart = $("#noise-delta");
  chart.innerHTML = "";
  const rows = (ev.circuits || []).slice();
  rows.sort((a, b) => (a.delta_mfit2 ?? 0) - (b.delta_mfit2 ?? 0));
  const maxAbs = Math.max(0.01, ...rows.flatMap((row) => [Math.abs(row.delta_mfit || 0), Math.abs(row.delta_mfit2 || 0)]));
  for (const row of rows) {
    chart.append(deltaRow(row.name, "M-FIT", row.delta_mfit, maxAbs));
    chart.append(deltaRow(row.name, "M-FIT-2", row.delta_mfit2, maxAbs, true));
  }
}

function deltaRow(label, model, value, maxAbs, alt) {
  const line = el("div", "bar-row");
  const track = el("div", "bar-track");
  const fill = el("div", "bar-fill");
  fill.classList.toggle("alt", alt);
  const width = Math.min(100, Math.abs(value || 0) / maxAbs * 100);
  fill.style.width = `${Math.max(1, width)}%`;
  if ((value || 0) < 0) fill.style.background = "linear-gradient(90deg, var(--green), #2bbd7e)";
  track.append(fill);
  line.append(el("span", "label", `${label} · ${model}`), track, el("span", "val", fmt(value)));
  return line;
}

function fillJobs() {
  const select = $("#job-select");
  select.innerHTML = "";
  for (const job of state.suite?.jobs || []) {
    if (!job.has_counts) continue;
    const option = el("option", "", `${job.job_id} · ${job.name}`);
    option.value = job.job_id;
    select.append(option);
  }
  if (select.options.length) {
    select.value = "OQ-06";
    if (!select.value) select.selectedIndex = 0;
    inspectJob();
  }
}

async function inspectJob(overrides = null) {
  const jobId = $("#job-select").value;
  if (!jobId) return;
  try {
    const payload = await api("/api/noise/compare", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, ...(overrides ? { overrides } : {}) }),
    });
    const metrics = $("#job-metrics");
    metrics.innerHTML = "";
    const job = payload.job;
    const custom = payload.models.custom;
    metrics.append(
      metric("job", `${job.job_id} · ${job.name}`),
      metric("qubits", job.num_qubits),
      metric("cx", job.cx_count),
      metric("ideal TV", fmt(payload.models.ideal.tv)),
      metric("M-FIT TV", fmt(payload.models["M-FIT"].tv)),
      metric("M-FIT-2 TV", fmt(payload.models["M-FIT-2"]?.tv), "ok"),
    );
    if (custom) metrics.append(metric("custom TV", fmt(custom.tv), "warn"));
    const table = el("table");
    const head = el("tr");
    const columns = ["state", "measured", "ideal", "M-FIT", "M-FIT-2"];
    if (custom) columns.push("custom");
    columns.forEach((label, i) => head.append(el("th", i ? "num" : "", label)));
    table.append(head);
    const maps = {};
    for (const name of ["ideal", "M-FIT", "M-FIT-2", "custom"]) {
      maps[name] = new Map((payload.models[name]?.outcomes || []).map((row) => [row.state, row.probability ?? row.frequency]));
    }
    for (const row of payload.measured_top.slice(0, 14)) {
      const measured = row.count / job.shots;
      const tr = el("tr");
      tr.append(
        el("td", "", row.state),
        el("td", "num", fmt(measured * 100, 2) + "%"),
        el("td", "num", fmt((maps.ideal.get(row.state) || 0) * 100, 2) + "%"),
        el("td", "num", fmt((maps["M-FIT"].get(row.state) || 0) * 100, 2) + "%"),
        el("td", "num", fmt((maps["M-FIT-2"].get(row.state) || 0) * 100, 2) + "%"),
      );
      if (custom) tr.append(el("td", "num", fmt((maps.custom.get(row.state) || 0) * 100, 2) + "%"));
      table.append(tr);
    }
    $("#job-chart").innerHTML = "";
    $("#job-chart").append(table);
  } catch (error) {
    toast(error.message);
  }
}

/* --------------------------------------------------------------------- sat */

async function satSolve(random = false) {
  try {
    const timeout = Number($("#sat-timeout").value);
    const budget = Number($("#sat-budget").value);
    const body = random
      ? { random: { num_vars: Number($("#sat-n").value), ratio: Number($("#sat-ratio").value), seed: Date.now() % 2147483647 }, timeout }
      : { cnf: $("#cnf").value, timeout };
    if (Number.isFinite(budget) && budget > 0) body.node_budget = budget;
    body.engine = $("#sat-engine").value;
    const payload = await api("/api/sat/solve", { method: "POST", body: JSON.stringify(body) });
    renderSAT(payload);
  } catch (error) {
    toast(error.message);
  }
}

function renderSAT(payload) {
  const result = payload.result;
  const tag = $("#sat-status");
  tag.textContent = result.status;
  tag.className = `tag ${result.status === "SAT" ? "ok" : result.status === "UNSAT" ? "warn" : "bad"}`;
  const metrics = $("#sat-metrics");
  metrics.innerHTML = "";
  metrics.append(
    metric("vars", payload.formula.num_vars),
    metric("clauses", payload.formula.num_clauses),
    metric("decisions", result.decisions),
    metric("propagations", result.propagations),
    metric("conflicts", result.conflicts),
    metric("nodes", result.nodes),
    metric("time ms", fmt(result.elapsed_ms, 2)),
    metric("model verified", String(result.model_verified), result.model_verified ? "ok" : "warn"),
    metric("engine", result.engine || "dpll"),
    metric("evidence", result.certification || "NONE",
      ["MODEL_VERIFIED", "TREE_RESOLUTION_CHECKED", "DRAT_CHECKED"].includes(result.certification) ? "ok" : "warn"),
  );
  const assignment = $("#sat-assignment");
  assignment.innerHTML = "";
  if (result.assignment) {
    for (const [name, value] of Object.entries(result.assignment).slice(0, 80)) {
      assignment.append(el("span", `lit ${value ? "true" : "false"}`, `${name}=${value ? "1" : "0"}`));
    }
  } else {
    assignment.append(el("p", "hint", result.note));
  }
  const table = el("table");
  const head = el("tr");
  ["field", "value"].forEach((label) => head.append(el("th", "", label)));
  table.append(head);
  for (const [key, value] of Object.entries({
    formula_sha256: payload.formula.sha256,
    clause_widths: JSON.stringify(payload.formula.clause_widths),
    status: result.status,
    note: result.note,
    timeout_seconds: result.timeout_seconds,
  })) {
    const tr = el("tr");
    tr.append(el("td", "", key), el("td", "num", String(value)));
    table.append(tr);
  }
  $("#sat-table").innerHTML = "";
  $("#sat-table").append(table);
}

async function satSweep() {
  const button = $("#sat-sweep");
  button.disabled = true;
  button.textContent = "Sweeping…";
  try {
    const sizes = $("#sweep-sizes").value.split(",").map((v) => Number(v.trim())).filter((v) => Number.isFinite(v));
    const ratios = $("#sweep-ratios").value.split(",").map((v) => Number(v.trim())).filter((v) => Number.isFinite(v));
    const payload = await api("/api/sat/sweep", {
      method: "POST",
      body: JSON.stringify({
        sizes,
        ratios,
        trials: Number($("#sweep-trials").value),
        timeout: Number($("#sweep-timeout").value),
      }),
    });
    drawSweep(payload.rows);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Run sweep";
  }
}

function drawSweep(rows) {
  const container = $("#sweep-chart");
  container.innerHTML = "";
  if (!rows.length) return;
  const sizes = [...new Set(rows.map((row) => row.num_vars))];
  const ratios = [...new Set(rows.map((row) => row.ratio))].sort((a, b) => a - b);
  const colors = ["#55d7ff", "#a78bfa", "#46e39a", "#f7c45c", "#ff7b84", "#7dd3fc", "#f0abfc", "#bef264"];
  const W = 760, H = 320, L = 52, R = 18, T = 18, B = 42;
  const maxY = Math.max(1, ...rows.map((row) => row.median_decisions));
  const x = (ratio) => L + (ratios.indexOf(ratio) / Math.max(1, ratios.length - 1)) * (W - L - R);
  const y = (value) => H - B - (value / maxY) * (H - T - B);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", "100%");
  svg.style.overflow = "visible";
  for (let i = 0; i <= 4; i++) {
    const gy = T + (i / 4) * (H - T - B);
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", L); line.setAttribute("x2", W - R);
    line.setAttribute("y1", gy); line.setAttribute("y2", gy);
    line.setAttribute("stroke", "#22314f"); line.setAttribute("stroke-width", "1");
    svg.append(line);
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", L - 8); label.setAttribute("y", gy + 4);
    label.setAttribute("text-anchor", "end"); label.setAttribute("fill", "#93a3c4");
    label.setAttribute("font-size", "10");
    label.textContent = Math.round(maxY - (i / 4) * maxY);
    svg.append(label);
  }
  for (const ratio of ratios) {
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", x(ratio)); label.setAttribute("y", H - B + 18);
    label.setAttribute("text-anchor", "middle"); label.setAttribute("fill", "#93a3c4");
    label.setAttribute("font-size", "10");
    label.textContent = ratio.toFixed(2);
    svg.append(label);
  }
  sizes.forEach((size, index) => {
    const series = ratios.map((ratio) => rows.find((row) => row.num_vars === size && row.ratio === ratio)).filter(Boolean);
    const path = document.createElementNS(ns, "polyline");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", colors[index % colors.length]);
    path.setAttribute("stroke-width", "2.5");
    path.setAttribute("points", series.map((row) => `${x(row.ratio)},${y(row.median_decisions)}`).join(" "));
    svg.append(path);
    for (const row of series) {
      const dot = document.createElementNS(ns, "circle");
      dot.setAttribute("cx", x(row.ratio)); dot.setAttribute("cy", y(row.median_decisions));
      dot.setAttribute("r", "3.2"); dot.setAttribute("fill", colors[index % colors.length]);
      const title = document.createElementNS(ns, "title");
      title.textContent = `n=${row.num_vars} ratio=${row.ratio} median decisions=${row.median_decisions}`;
      dot.append(title); svg.append(dot);
    }
  });
  container.append(svg);
  const legend = el("div", "legend");
  sizes.forEach((size, index) => {
    const item = el("span", "", `n = ${size}`);
    item.style.setProperty("--c", colors[index % colors.length]);
    item.querySelector; // no-op
    item.style.color = colors[index % colors.length];
    legend.append(item);
  });
  container.append(legend);
}

/* ---------------------------------------------------------------- evidence */

function renderEvidence() {
  const suite = state.suite;
  if (!suite) return;
  $("#evidence-sha").textContent = (suite.dataset.sha256 || "unavailable").slice(0, 16);
  const table = el("table");
  const head = el("tr");
  ["job", "circuit", "split", "q", "cx", "provider id", "ideal TV", "M-FIT Δ", "M-FIT-2 Δ"].forEach((label, i) => head.append(el("th", i > 2 && i < 7 ? "num" : "", label)));
  table.append(head);
  for (const job of suite.jobs) {
    const tr = el("tr");
    tr.style.cursor = job.has_counts ? "pointer" : "default";
    if (job.has_counts) {
      tr.onclick = () => {
        setView("noise");
        const select = $("#job-select");
        if (!select.childElementCount) fillJobs();
        select.value = job.job_id;
        inspectJob();
      };
    }
    tr.append(
      el("td", "", job.job_id),
      el("td", "", job.name),
      el("td", `split-${job.split}`, job.split),
      el("td", "num", String(job.num_qubits)),
      el("td", "num", String(job.cx_count)),
      el("td", "", job.provider_job_id ? job.provider_job_id.slice(0, 8) : "—"),
      el("td", "num", fmt(job.tv_ideal)),
      el("td", `num ${job.delta_mfit < 0 ? "neg" : "pos"}`, fmt(job.delta_mfit)),
      el("td", `num ${job.delta_mfit2 < 0 ? "neg" : "pos"}`, fmt(job.delta_mfit2)),
    );
    table.append(tr);
  }
  $("#evidence-table").innerHTML = "";
  $("#evidence-table").append(table);
}

/* ---------------------------------------------------------------- hardware */

function renderHardware() {
  const data = state.hardware;
  if (!data) return;
  const datasets = data.datasets || [];
  const cards = $("#hardware-datasets");
  cards.innerHTML = "";
  for (const item of datasets) {
    cards.append(stat(item.id, `${fmt(item.median_delta_tv)}`, `${item.verdict} · ${item.n_eval} EVAL · ${item.shots ?? "?"} shots`));
  }
  const qr = data.quantumrings || {};
  $("#hardware-qr").textContent = qr.verdict ? `QuantumRings ${qr.verdict} ${qr.passed}/${qr.n}` : "QuantumRings n/a";
  const pnp = data.pnp || {};
  const metrics = $("#hardware-pnp-metrics");
  metrics.innerHTML = "";
  metrics.append(
    metric("verdict", pnp.verdict || "—", pnp.verdict === "EXACTLY_EMULABLE_AND_QPU_CONSISTENT" ? "ok" : "warn"),
    metric("probes", (pnp.exact_emulation || []).length),
    metric("QPU runs", (pnp.qpu_runs || []).length),
    metric("SAT DPLL", pnp.sat?.dpll_model || "—"),
  );
  const table = el("table");
  const head = el("tr");
  ["probe", "q", "gates", "TV vs Statevector", "exact"].forEach((label, i) => head.append(el("th", i > 0 ? "num" : "", label)));
  table.append(head);
  for (const row of pnp.exact_emulation || []) {
    const tr = el("tr");
    tr.append(el("td", "", row.probe_id), el("td", "num", String(row.num_qubits)), el("td", "num", String(row.gate_count)), el("td", "num", fmt(row.cqhecs_vs_qiskit_statevector_tv, 2)), el("td", "", row.exact_classically_emulable ? "yes" : "no"));
    table.append(tr);
  }
  $("#hardware-pnp-table").innerHTML = "";
  $("#hardware-pnp-table").append(table);

  const sat = data.sat_oracles || {};
  const satMetrics = $("#hardware-sat-metrics");
  satMetrics.innerHTML = "";
  satMetrics.append(
    metric("top is model", String(sat.all_qpu_top_outcomes_are_models)),
    metric("strict MPS lossless", String(sat.all_mps_strictly_lossless), sat.all_mps_strictly_lossless ? "ok" : "warn"),
    metric("runs", sat.runs ?? "—"),
  );
  const satTable = el("table");
  const satHead = el("tr");
  ["backend", "oracle", "top", "mass", "models"].forEach((label, i) => satHead.append(el("th", i === 3 ? "num" : "", label)));
  satTable.append(satHead);
  for (const run of data.sat_oracle_runs || []) {
    for (const row of run.oracles || []) {
      const tr = el("tr");
      tr.append(el("td", "", run.backend), el("td", "", row.probe_id), el("td", "", row.top_outcome), el("td", "num", fmt(row.model_mass, 3)), el("td", "", (row.dpll_models || []).join(", ")));
      satTable.append(tr);
    }
  }
  $("#hardware-sat-table").innerHTML = "";
  $("#hardware-sat-table").append(satTable);

  const dsTable = el("table");
  const dsHead = el("tr");
  ["dataset", "backend", "shots", "verdict", "median ΔTV", "CI", "closer"].forEach((label, i) => dsHead.append(el("th", [2, 4, 6].includes(i) ? "num" : "", label)));
  dsTable.append(dsHead);
  for (const item of datasets) {
    const tr = el("tr");
    tr.append(el("td", "", item.id), el("td", "", item.backend || "—"), el("td", "num", item.shots ?? "—"), el("td", "", item.verdict || "—"), el("td", "num", fmt(item.median_delta_tv)), el("td", "num", `[${fmt(item.ci95_low)}, ${fmt(item.ci95_high)}]`), el("td", "num", item.n_noisy_better != null ? `${item.n_noisy_better}/${item.n_eval}` : "—"));
    dsTable.append(tr);
  }
  $("#hardware-dataset-table").innerHTML = "";
  $("#hardware-dataset-table").append(dsTable);
}

/* ---------------------------------------------------------------- research */

function renderResearch() {
  const data = state.research;
  if (!data) return;
  $("#research-headline").textContent = data.headline;
  const box = $("#research-sections");
  box.innerHTML = "";
  for (const section of data.sections) {
    const card = el("div", "research-card");
    const h = el("h4", "", section.title);
    h.append(el("span", "tag", section.status));
    card.append(h, el("p", "", section.body), el("div", "do", section.what_this_repo_does));
    box.append(card);
  }
  const list = $("#citations");
  list.innerHTML = "";
  for (const citation of data.citations) list.append(el("li", "", citation));
}

/** Add every measured device profile to the noise selector. */
async function fillDevices() {
  try {
    const { devices } = await api("/api/devices");
    const select = $("#noise");
    for (const d of devices) {
      const option = el("option", "", `${d.label} (measured)`);
      option.value = `device:${d.id}`;
      select.append(option);
    }
  } catch (error) {
    toast(`device profiles unavailable: ${error.message}`);
  }
}

/* -------------------------------------------------------------------- boot */

async function init() {
  try {
    const [health, suite, noise, research, hardware] = await Promise.all([
      api("/api/health"),
      api("/api/suite"),
      api("/api/noise"),
      api("/api/research"),
      api("/api/hardware"),
    ]);
    state.health = health;
    state.suite = suite;
    state.noise = noise;
    state.research = research;
    state.hardware = hardware;
    renderHealth();
    renderOverviewEvidence();
    renderNoise();
    renderEvidence();
    renderResearch();
    renderHardware();
    fillPresets();
    await fillDevices();
    await loadPreset("bell");
    fillJobs();
  } catch (error) {
    $("#health-dot").className = "dot bad";
    $("#health-text").textContent = "engine error";
    toast(error.message);
  }
}

$$("#nav button").forEach((btn) => btn.addEventListener("click", () => setView(btn.dataset.view)));
$$("[data-go]").forEach((btn) => btn.addEventListener("click", () => setView(btn.dataset.go)));
$("#run-circuit").addEventListener("click", runCircuit);
$("#preset").addEventListener("change", (event) => loadPreset(event.target.value).catch((error) => toast(error.message)));
$("#job-select").addEventListener("change", inspectJob);
$("#apply-override").addEventListener("click", () =>
  inspectJob({ cx_depolarizing: Number($("#cx-override").value) })
);
$("#sat-solve").addEventListener("click", () => satSolve(false));
$("#sat-count").addEventListener("click", async () => {
  try {
    const payload = await api("/api/sat/count", {
      method: "POST",
      body: JSON.stringify({ cnf: $("#cnf").value, timeout: Number($("#sat-timeout").value) }),
    });
    const r = payload.result;
    const tag = $("#sat-status");
    tag.textContent = r.status === "COUNTED" ? `#models = ${r.count}` : "UNKNOWN";
    tag.className = `tag ${r.status === "COUNTED" ? "ok" : "bad"}`;
    const metrics = $("#sat-metrics");
    metrics.innerHTML = "";
    metrics.append(
      metric("vars", payload.formula.num_vars),
      metric("clauses", payload.formula.num_clauses),
      metric("nodes", r.nodes),
      metric("cache hits", r.cache_hits),
      metric("time ms", fmt(r.elapsed_ms, 2)),
    );
    $("#sat-assignment").innerHTML = "";
    $("#sat-assignment").append(el("p", "hint", `${r.method}. ${r.note}`));
    $("#sat-table").innerHTML = "";
  } catch (error) {
    toast(error.message);
  }
});
$("#sat-random").addEventListener("click", () => satSolve(true));
$("#sat-sweep").addEventListener("click", satSweep);

const initial = location.hash.replace("#", "");
if (initial && TITLES[initial]) setView(initial);
init();
