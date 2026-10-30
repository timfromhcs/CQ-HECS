// Result views: histogram, table, Bloch spheres and amplitudes.

import { t } from "./i18n";
import type { RunResult } from "./protocol";

const NS = "http://www.w3.org/2000/svg";
const MAX_BARS = 32;

function svgEl<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>, parent?: Element) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  parent?.appendChild(node);
  return node;
}

function esc(s: string) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

/** Outcomes sorted by count, with the ideal probability when the bit layouts agree. */
function rows(r: RunResult) {
  const exact = new Map(r.exact.map((e) => [e.bits, e.p]));
  const keys = Object.keys(r.counts);
  const sameLayout = keys.length > 0 && keys[0].length === r.numQubits;
  const entries = keys.map((bits) => ({
    bits,
    count: r.counts[bits],
    freq: r.counts[bits] / r.shots,
    ideal: sameLayout ? exact.get(bits) ?? 0 : undefined,
  }));
  entries.sort((a, b) => b.count - a.count || a.bits.localeCompare(b.bits));
  return entries;
}

export function renderHistogram(host: HTMLElement, r: RunResult) {
  const data = rows(r).slice(0, MAX_BARS);
  host.replaceChildren();
  host.className = "res hist";
  const w = 480, h = 300, padL = 44, padB = Math.min(110, 16 + 8 * Math.max(...data.map((d) => d.bits.length))), padT = 12;
  const max = Math.max(...data.map((d) => Math.max(d.freq, d.ideal ?? 0)), 1e-9);
  const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": t("res.hist") }, host);
  const defs = svgEl("defs", {}, svg);
  const grad = svgEl("linearGradient", { id: "bargrad", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
  svgEl("stop", { offset: 0, "stop-color": "var(--accent)" }, grad);
  svgEl("stop", { offset: 1, "stop-color": "var(--accent-2)" }, grad);
  const plotH = h - padB - padT, plotW = w - padL - 8;
  for (let k = 0; k <= 4; k++) {
    const yy = padT + plotH - (k / 4) * plotH;
    svgEl("line", { x1: padL, x2: w - 8, y1: yy, y2: yy, class: "grid" }, svg);
    svgEl("text", { x: padL - 6, y: yy + 3, "text-anchor": "end", class: "axis" }, svg).textContent = `${((k / 4) * max * 100).toFixed(max < 0.1 ? 1 : 0)}%`;
  }
  const bw = plotW / Math.max(data.length, 1);
  data.forEach((d, i) => {
    const x = padL + i * bw;
    const bh = (d.freq / max) * plotH;
    const bar = svgEl("rect", { x: x + bw * 0.12, y: padT + plotH - bh, width: bw * 0.76, height: Math.max(bh, 0.5), rx: Math.min(4, bw * 0.2), class: "bar" }, svg);
    svgEl("title", {}, bar).textContent = `${d.bits}: ${d.count} (${(d.freq * 100).toFixed(2)} %)${d.ideal !== undefined ? ` · ${t("res.idealCol")} ${(d.ideal * 100).toFixed(3)} %` : ""}`;
    if (d.ideal !== undefined) {
      const iy = padT + plotH - (d.ideal / max) * plotH;
      svgEl("line", { x1: x + bw * 0.05, x2: x + bw * 0.95, y1: iy, y2: iy, class: "exact" }, svg);
    }
    const label = svgEl("text", { x: x + bw / 2, y: padT + plotH + 8, class: "axis", transform: `rotate(60 ${x + bw / 2} ${padT + plotH + 8})` }, svg);
    label.textContent = d.bits;
  });
  const legend = document.createElement("div");
  legend.className = "legend";
  const total = Object.keys(r.counts).length;
  legend.innerHTML = `<span><i style="background:linear-gradient(90deg,var(--accent),var(--accent-2))"></i>${esc(t("res.measured", { n: r.shots }))}</span>` +
    (data.some((d) => d.ideal !== undefined) ? `<span><i style="background:var(--warn)"></i>${esc(t("res.ideal"))}</span>` : "") +
    (total > MAX_BARS ? `<span>${esc(t("res.shown", { a: MAX_BARS, b: total }))}</span>` : "");
  host.appendChild(legend);
}

export function renderTable(host: HTMLElement, r: RunResult) {
  const data = rows(r).slice(0, 512);
  const hasIdeal = data.some((d) => d.ideal !== undefined);
  host.innerHTML = `<div class="table-wrap"><table><thead><tr><th>${t("res.outcome")}</th><th class="num">${t("res.count")}</th><th class="num">${t("res.freq")}</th>${hasIdeal ? `<th class="num">${t("res.idealCol")}</th>` : ""}</tr></thead><tbody>${
    data.map((d) => `<tr><td><code>${esc(d.bits)}</code></td><td class="num">${d.count}</td><td class="num">${(d.freq * 100).toFixed(3)} %</td>${hasIdeal ? `<td class="num">${((d.ideal ?? 0) * 100).toFixed(4)} %</td>` : ""}</tr>`).join("")
  }</tbody></table></div><p class="muted small">${t("res.bitorder")}</p>`;
}

function drawBloch(canvas: HTMLCanvasElement, v: [number, number, number]) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const size = canvas.clientWidth || 150;
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(dpr, dpr);
  const css = getComputedStyle(document.documentElement);
  const line = css.getPropertyValue("--line").trim() || "#444";
  const muted = css.getPropertyValue("--muted").trim();
  const accent = css.getPropertyValue("--accent").trim();
  const accent2 = css.getPropertyValue("--accent-2").trim();
  const c = size / 2, R = size * 0.38;
  // Oblique projection: x toward the viewer-left, y right, z up.
  const proj = (x: number, y: number, z: number): [number, number] => [c + R * (y - 0.45 * x), c - R * (z - 0.3 * x)];
  ctx.lineWidth = 1;
  ctx.strokeStyle = line;
  ctx.beginPath(); ctx.arc(c, c, R, 0, 2 * Math.PI); ctx.stroke();
  ctx.beginPath();
  for (let t = 0; t <= 64; t++) {
    const a = (t / 64) * 2 * Math.PI;
    const [px, py] = proj(Math.cos(a), Math.sin(a), 0);
    t ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
  }
  ctx.stroke();
  ctx.fillStyle = muted;
  ctx.font = "10px JetBrains Mono, monospace";
  ctx.textAlign = "center";
  for (const [lbl, p] of [["|0⟩", [0, 0, 1.18]], ["|1⟩", [0, 0, -1.25]], ["x", [1.3, 0, 0]], ["y", [0, 1.18, 0]]] as [string, number[]][]) {
    const [px, py] = proj(p[0], p[1], p[2]);
    ctx.fillText(lbl, px, py + 3);
  }
  const [ox, oy] = proj(0, 0, 0), [tx, ty] = proj(v[0], v[1], v[2]);
  const grad = ctx.createLinearGradient(ox, oy, tx, ty);
  grad.addColorStop(0, accent);
  grad.addColorStop(1, accent2);
  ctx.strokeStyle = grad;
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(tx, ty); ctx.stroke();
  ctx.fillStyle = accent2;
  ctx.beginPath(); ctx.arc(tx, ty, 4.5, 0, 2 * Math.PI); ctx.fill();
}

export function renderBloch(host: HTMLElement, r: RunResult) {
  if (!r.bloch.length) {
    host.innerHTML = `<p class="muted pad">${t("res.blochNone")}</p>`;
    return;
  }
  const grid = document.createElement("div");
  grid.className = "bloch-grid";
  host.replaceChildren(grid);
  r.bloch.forEach((v, q) => {
    const fig = document.createElement("figure");
    const canvas = document.createElement("canvas");
    const purity = Math.hypot(...v);
    const cap = document.createElement("figcaption");
    cap.textContent = `q${q} · |r|=${purity.toFixed(3)}${purity < 0.99 ? ` (${t("res.blochMixed")})` : ""}`;
    fig.append(canvas, cap);
    grid.appendChild(fig);
    requestAnimationFrame(() => drawBloch(canvas, v));
  });
  if (r.numQubits > r.bloch.length) {
    const note = document.createElement("p");
    note.className = "muted small";
    note.textContent = t("res.blochShown", { a: r.bloch.length, b: r.numQubits });
    host.appendChild(note);
  }
}

export function renderState(host: HTMLElement, r: RunResult) {
  if (!r.amplitudes.length) {
    const top = r.exact.slice(0, 64);
    host.innerHTML = top.length
      ? `<p class="muted small">${t("res.stateTop", { n: r.numQubits, k: top.length })}</p><div class="table-wrap"><table><thead><tr><th>Basis</th><th class="num">|a|²</th></tr></thead><tbody>${top.map((e) => `<tr><td><code>|${e.bits}⟩</code></td><td class="num">${e.p.toExponential(6)}</td></tr>`).join("")}</tbody></table></div>`
      : `<p class="muted pad">${t("res.stateNone")}</p>`;
    return;
  }
  host.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Basis</th><th class="num">Re</th><th class="num">Im</th><th class="num">|a|²</th><th class="num">Phase</th></tr></thead><tbody>${
    r.amplitudes.map((a) => {
      const p = a.re * a.re + a.im * a.im;
      const phase = p > 1e-24 ? `${((Math.atan2(a.im, a.re) / Math.PI) * 180).toFixed(1)}°` : "–";
      return `<tr><td><code>|${a.bits}⟩</code></td><td class="num">${a.re.toFixed(6)}</td><td class="num">${a.im.toFixed(6)}</td><td class="num">${p.toFixed(6)}</td><td class="num">${phase}</td></tr>`;
    }).join("")
  }</tbody></table></div>`;
}
