// Studio Quantum Gravity Lab. Loaded after app.js and uses its globals ($, el, fmt, api, toast).
// Every value comes from /api/qg/v1/* (local, credential-free). All text is set with textContent.
// No paid submission exists here: the Experiment Designer returns a typed UNAVAILABLE refusal.
(function () {
  const TABS = [
    ["overview", "Overview"], ["theories", "Theory catalog"], ["model", "Model builder"],
    ["circuit", "Circuit preview"], ["design", "Experiment designer"], ["backends", "Backend lab"],
    ["analysis", "Analysis"], ["evidence", "Evidence ledger"],
  ];
  const S = { tab: "overview", data: {}, errors: {}, loaded: false, ack: false, run: null, preview: null, refusal: null, runErr: "" };
  let root = null;

  const chip = (text, kind) => { const c = el("span", `tag ${kind || ""}`, text); c.style.marginRight = "6px"; return c; };
  const p = (text, cls) => el("p", cls || "hint", text);
  const list = (items) => { const ul = el("ul"); items.forEach((i) => ul.append(el("li", "", i))); return ul; };
  const unavailable = (what) => p(`${what}: data not loaded (${S.errors[what] || "no response"}). Nothing is substituted.`, "hint");

  function table(headers, rows, label) {
    const wrap = el("div", "table-wrap");
    wrap.tabIndex = 0; wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", label);
    const t = el("table"), head = el("tr");
    headers.forEach((h) => { const th = el("th", "", h); th.scope = "col"; head.append(th); });
    const th0 = el("thead"); th0.append(head); t.append(th0);
    const body = el("tbody");
    rows.forEach((r) => { const tr = el("tr"); r.forEach((c) => tr.append(el("td", "", c === null || c === undefined ? "not recorded" : String(c)))); body.append(tr); });
    t.append(body); wrap.append(t);
    return wrap;
  }
  const panel = (title, ...kids) => { const d = el("div", "panel"); d.append(el("h3", "", title), ...kids); return d; };

  async function load() {
    const get = async (key, path) => { try { S.data[key] = await api(path); } catch (e) { S.errors[key] = String(e.message || e); } };
    await Promise.all([get("health", "/api/qg/v1/health"), get("catalog", "/api/qg/v1/catalog"),
      get("models", "/api/qg/v1/models"), get("evidence", "/api/qg/v1/evidence")]);
    S.loaded = true; render();
  }

  function bmv() { const c = S.data.catalog; return c && c.methods.find((m) => m.method_id === "qg.bmv.zz.v1"); }

  function overview() {
    const c = S.data.catalog, h = S.data.health;
    if (!c) return [unavailable("catalog")];
    const kids = [panel("Track status", table(["Track", "Title", "Status"], c.tracks.map((t) => [t.id, t.title, t.status]), "Track status"),
      p("Status is text from the catalog. SUPPORTED_WITHIN_MODEL means a finite model is reproduced, not that a physical claim holds."))];
    if (h) kids.push(panel("Service", p(`Campaign ${h.campaign}; ${h.methods} methods; network: ${h.network}. This page never reads or shows provider credentials.`)));
    kids.push(panel("What this lab does not claim", list(c.non_claims)));
    return kids;
  }

  function theories() {
    const c = S.data.catalog;
    if (!c) return [unavailable("catalog")];
    return c.methods.map((m) => {
      const d = panel(m.title), row = el("div");
      d.append(row);
      row.append(chip(m.method_id), chip(`surface: ${m.surface}`), chip(m.status, /PROPOSED|DEFERRED/.test(m.status) ? "warn" : "ok"));
      d.append(el("h4", "", "Assumptions"), list(m.assumptions), el("h4", "", "Observables"), p(m.observables.join(", "), ""),
        el("h4", "", "Established"), p(m.established, ""), el("h4", "", "Cannot establish"), list(m.cannot_establish),
        p(`References: ${m.references.join(", ")}`));
      return d;
    });
  }

  function num(id, label, value) {
    const l = el("label", "", label); const i = el("input"); i.id = id; i.type = "number"; i.step = "any"; i.value = value; l.append(i); return l;
  }

  function model() {
    const m = bmv();
    if (!m) return [unavailable("catalog")];
    const form = el("div");
    const ack = el("input"); ack.type = "checkbox"; ack.id = "qgs-ack"; ack.checked = S.ack;
    const ackLabel = el("label", "", " I have read the assumptions above; theta is a model parameter, not a mass or distance.");
    ackLabel.prepend(ack);
    const run = el("button", "primary", "Run locally (exact, f64)"); run.id = "qgs-run"; run.disabled = !S.ack;
    ack.addEventListener("change", () => { S.ack = ack.checked; run.disabled = !S.ack; });
    const err = el("p", "hint", S.runErr); err.id = "qgs-err"; err.setAttribute("role", "alert");
    run.addEventListener("click", async () => {
      const body = { theta: Number($("#qgs-theta").value), local_phase_a: Number($("#qgs-a").value), local_phase_b: Number($("#qgs-b").value) };
      try {
        const [r, v] = await Promise.all([api("/api/qg/v1/experiments/run-local", { method: "POST", body: JSON.stringify(body) }),
          api("/api/qg/v1/experiments/validate", { method: "POST", body: JSON.stringify(body) })]);
        S.run = { body, r, v }; S.runErr = "";
      } catch (e) { S.run = null; S.runErr = `Refused: ${e.message}`; }
      render(); const t = $("#qgs-err") || root; if (S.runErr) t.focus && t.focus();
    });
    form.append(num("qgs-theta", "theta (rad)", S.run ? S.run.body.theta : 0.7853981633974483), num("qgs-a", "local phase a (rad)", S.run ? S.run.body.local_phase_a : 0),
      num("qgs-b", "local phase b (rad)", S.run ? S.run.body.local_phase_b : 0), ackLabel, run, err);
    const out = el("div"); out.setAttribute("aria-live", "polite");
    if (!S.run) out.append(p("No result yet. Confirm the assumptions, then run."));
    else {
      const { r, v } = S.run, o = r.observables;
      out.append(chip(`surface: ${r.execution_surface}`), chip("not QPU"), chip(r.precision), chip(r.status, "ok"),
        table(["Observable", "Value", "Unit"], [
          ["concurrence", fmt(o.concurrence, 6), "dimensionless"], ["negativity", fmt(o.negativity, 6), "dimensionless"],
          ["entanglement entropy", fmt(o.entanglement_entropy, 6), "bits"], ["CHSH max", fmt(o.chsh_max, 6), "dimensionless"],
          ["analytic concurrence (oracle)", fmt(v.concurrence_oracle, 6), "dimensionless"],
        ], "Model result"),
        table(["Outcome q0q1", "Probability"], Object.entries(r.probabilities).map(([k, x]) => [k, fmt(x, 6)]), "Outcome probabilities"),
        p(`Bit order: ${r.bit_order}. Limits: ${r.limitations.join("; ")}.`));
    }
    return [panel("Model: effective ZZ phase on |+>|+>", p("H = (theta/2) Z (x) Z; units: theta in radians (model parameter); local phases are factored out of the entangling invariant."),
      el("h4", "", "Assumptions (read before running)"), list(m.assumptions), form), panel("Result", out)];
  }

  function circuit() {
    const form = el("div");
    form.append(num("qgs-ptheta", "theta (rad)", S.preview ? S.preview.theta : 0.7853981633974483));
    const b = el("button", "primary", "Generate QASM and digest"); b.id = "qgs-prev";
    b.addEventListener("click", async () => {
      const theta = Number($("#qgs-ptheta").value);
      try { S.preview = { theta, r: await api("/api/qg/v1/experiments/preview", { method: "POST", body: JSON.stringify({ theta }) }), err: "" }; }
      catch (e) { S.preview = { theta, r: null, err: `Refused: ${e.message}` }; }
      render();
    });
    form.append(b);
    const kids = [panel("Parameters", form)];
    if (S.preview && S.preview.err) { const e = p(S.preview.err); e.setAttribute("role", "alert"); kids.push(panel("Refused", e)); }
    else if (S.preview) {
      const r = S.preview.r, pre = el("pre", "", r.qasm); pre.tabIndex = 0; pre.setAttribute("aria-label", "OpenQASM source");
      pre.style.cssText = "white-space:pre-wrap;overflow-wrap:anywhere";
      kids.push(panel("OpenQASM", pre, p(`SHA-256: ${r.qasm_sha256}`, "hint"), p(`${r.qubits} qubits; surface ${r.execution_surface}; spend ${r.spend_credits}; network ${r.network}. The preview takes theta only (local phases are web-only).`)));
    } else kids.push(panel("OpenQASM", p("No preview yet.")));
    return kids;
  }

  function design() {
    const btn = el("button", "", "Try to submit to a provider"); btn.id = "qgs-try";
    const out = el("div"); out.setAttribute("role", "status");
    btn.addEventListener("click", () => { S.refusal = refusal(); render(); });
    if (S.refusal) { const pre = el("pre", "", JSON.stringify(S.refusal, null, 2)); pre.tabIndex = 0; pre.setAttribute("aria-label", "Typed refusal"); out.append(pre); }
    return [panel("Experiment designer", p("Design and preview run locally. Quotes and paid submissions run only in the local CLI or MCP with an authorised, frozen campaign."),
      p("Credit estimate: none. An estimate exists only after an exact provider quote for the frozen QASM; this page never requests one."), btn, out)];
  }
  function refusal() {
    return { status: "UNAVAILABLE", code: "STUDIO_NO_PROVIDER_SUBMISSION", reason: "The Studio page has no provider credentials and does not submit jobs or quotes.", spend_credits: 0, network: "none", credentials_in_browser: false };
  }

  function backends() {
    const c = S.data.catalog;
    const rows = [
      ["QPU (recorded runs only)", "QPU", "", "NOT QUERIED", "Recorded measurements are shown in Analysis", "No live provider call from this page"],
      ["Open Quantum simulator", "Simulator", "", "NOT QUERIED", "n/a", "Local CLI/MCP only"],
      ["CQ-HECS CPU", "CPU", "f64", "AVAILABLE (this server, local)", "Exact reference for the BMV model", "Finite two-qubit model only"],
      ["Vulkan native", "Vulkan", "", "NOT QUERIED", "n/a", "No QG kernel is wired to it"],
      ["Browser WASM", "WASM", "f64", "see Web app", "Statevector", "Not run from Studio"],
      ["Browser WebGPU", "WebGPU", "f32", "see Web app", "Never exact", "Not run from Studio"],
    ];
    const kids = [panel("Backend lab", p("Type and precision are text, not colour. No queue depth, noise or score is shown because none was measured."),
      table(["Backend", "Type", "Precision", "Status", "Features", "Blockers"], rows, "Backends"))];
    if (c) kids.push(panel("Execution surfaces known to the catalog", list(c.execution_surfaces), p(`Physical surfaces: ${c.physical_surfaces.join(", ")}.`)));
    return kids;
  }

  function chartSvg(points) {
    const NS = "http://www.w3.org/2000/svg", W = 640, H = 320, L = 56, R = 14, T = 12, B = 48;
    const X = (x) => L + (x / 1.65) * (W - L - R), Y = (y) => T + (1 - (y + 0.1) / 1.2) * (H - T - B);
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("role", "img"); svg.style.cssText = "width:100%;height:auto";
    const add = (tag, attrs, text) => { const n = document.createElementNS(NS, tag); Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v)); if (text) n.textContent = text; svg.append(n); return n; };
    add("title", {}, "Measured two-qubit correlators against theta"); add("desc", {}, "Recorded QPU correlators with one standard error bars; the same values are in the table below.");
    [0, 0.25, 0.5, 0.75, 1].forEach((y) => { add("line", { x1: L, x2: W - R, y1: Y(y), y2: Y(y), stroke: "#22314f" }); add("text", { x: L - 8, y: Y(y) + 4, "text-anchor": "end", fill: "#93a3c4", "font-size": 11 }, String(y)); });
    [0, 0.5, 1, 1.5].forEach((x) => add("text", { x: X(x), y: H - B + 16, "text-anchor": "middle", fill: "#93a3c4", "font-size": 11 }, String(x)));
    add("path", { d: `M${L} ${T}V${H - B}H${W - R}`, stroke: "#93a3c4", fill: "none" });
    const pts = [];
    for (let i = 0; i <= 32; i++) { const x = (Math.PI / 2) * (i / 32); pts.push(`${X(x).toFixed(1)},${Y(Math.abs(Math.sin(x))).toFixed(1)}`); }
    add("polyline", { points: pts.join(" "), fill: "none", stroke: "#93a3c4", "stroke-width": 2, "stroke-dasharray": "6 4" });
    points.forEach((q) => {
      const c = q.basis === "YZ" ? "#55d7ff" : "#a78bfa", cx = X(q.theta), e = q.std_err || 0;
      if (e) add("line", { x1: cx, x2: cx, y1: Y(q.correlator - e), y2: Y(q.correlator + e), stroke: c, "stroke-width": 2 });
      if (q.basis === "YZ") add("circle", { cx, cy: Y(q.correlator), r: 5, fill: c });
      else add("rect", { x: cx - 5, y: Y(q.correlator) - 5, width: 10, height: 10, fill: c });
    });
    add("text", { x: (L + W - R) / 2, y: H - 8, "text-anchor": "middle", fill: "#93a3c4", "font-size": 11 }, "theta (rad); circuit parameter, not a physical quantity");
    add("text", { transform: `translate(14 ${(T + H - B) / 2}) rotate(-90)`, "text-anchor": "middle", fill: "#93a3c4", "font-size": 11 }, "correlator (dimensionless)");
    return svg;
  }

  function analysis() {
    const e = S.data.evidence;
    if (!e) return [unavailable("evidence")];
    const pts = e.bmv_scan || [];
    if (!pts.length) return [panel("Analysis", p("No recorded scan points are available (processed/bmv_phase_scan.json missing or empty). Nothing is substituted."))];
    const chartPts = pts.filter((q) => q.basis === "YZ" || q.basis === "ZY");
    return [panel("Measured correlators", chartSvg(chartPts),
      p("Dashed line: analytic |sin(theta)| of the toy model. Circles YZ, squares ZY. Bars: one standard error from shot noise only; no readout correction, no systematic error. Legend is by shape and text, not colour alone."),
      p(`Source: ${e.surface}, backend ${e.backend}, ${pts[0].shots} shots per point. A toy-model fit says nothing about gravity.`)),
    panel("Text alternative", table(["Basis", "theta (rad)", "Correlator", "Std error", "Shots", "Surface"],
      pts.map((q) => [q.basis, fmt(q.theta, 6), q.correlator, q.std_err === null || q.std_err === undefined ? null : fmt(q.std_err, 4), q.shots, "QPU"]), "Recorded scan"))];
  }

  function evidence() {
    const e = S.data.evidence;
    if (!e) return [unavailable("evidence")];
    const kids = [panel("Evidence ledger (read-only)", p(`Hash policy: ${e.sha_policy}. Excluded on purpose: ${e.excluded.join(", ")}.`),
      table(["File", "Status", "Bytes", "SHA-256"], e.files.map((f) => [f.path, f.status, f.bytes, f.sha256]), "Evidence files"))];
    if (e.files.every((f) => f.status !== "present")) kids.push(p("No evidence files are present in this checkout, so no hashes are shown."));
    return kids;
  }

  const PANELS = { overview, theories, model, circuit, design, backends, analysis, evidence };

  function render() {
    if (!root) return;
    const keep = document.activeElement && root.contains(document.activeElement) ? document.activeElement.id : "";
    root.replaceChildren();
    root.append(el("p", "lede", "Local, exact models and recorded evidence. Toy models do not measure gravity; a simulator is never a QPU."));
    const bar = el("div", "chips"); bar.setAttribute("role", "tablist"); bar.setAttribute("aria-label", "Quantum Gravity Lab workspaces");
    TABS.forEach(([id, label], i) => {
      const b = el("button", S.tab === id ? "primary" : "", label);
      b.id = `qgs-tab-${id}`; b.setAttribute("role", "tab"); b.setAttribute("aria-selected", String(S.tab === id));
      b.setAttribute("aria-controls", "qgs-panel"); b.tabIndex = S.tab === id ? 0 : -1;
      b.addEventListener("click", () => { S.tab = id; render(); });
      b.addEventListener("keydown", (ev) => {
        const k = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: TABS.length - 1 }[ev.key];
        if (k === undefined) return;
        ev.preventDefault(); S.tab = TABS[(k + TABS.length) % TABS.length][0]; render(); $(`#qgs-tab-${S.tab}`).focus();
      });
      bar.append(b);
    });
    const body = el("div"); body.id = "qgs-panel"; body.setAttribute("role", "tabpanel"); body.setAttribute("aria-labelledby", `qgs-tab-${S.tab}`); body.tabIndex = 0;
    if (!S.loaded) body.append(p("Loading local data..."));
    else PANELS[S.tab]().forEach((n) => body.append(n));
    root.append(bar, body);
    if (keep) { const n = $(`#${keep}`); if (n) n.focus(); }
  }

  window.qgStudioMount = function () {
    if (root) return;
    root = $("#qg-studio");
    render(); load();
  };
  window.qgStudioRefusal = refusal;
  const view = $("#view-qg");
  if (view && view.classList.contains("active")) window.qgStudioMount();
})();
