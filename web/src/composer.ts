// Visual circuit composer: a qubit × time grid rendered as SVG.

import { GATES, type Circuit, type Gate, type GateName, type GateSpec } from "./circuit";

interface Placed { col: number; gate: Gate }

const CELL = 52, LEFT = 46, TOP = 20;
const NS = "http://www.w3.org/2000/svg";

function el<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>, parent?: Element) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  parent?.appendChild(node);
  return node;
}

function shortParam(x: number): string {
  const r = x / Math.PI;
  for (const [v, s] of [[1, "π"], [0.5, "π/2"], [0.25, "π/4"], [0.125, "π/8"], [2, "2π"]] as [number, string][]) {
    if (Math.abs(r - v) < 1e-9) return s;
    if (Math.abs(r + v) < 1e-9) return `-${s}`;
  }
  return x.toFixed(2);
}

export class Composer {
  private placed: Placed[] = [];
  private tool: GateName | "erase" = "h";
  private pending: { col: number; qubits: number[] } | null = null;
  numQubits = 2;
  onChange: () => void = () => {};

  constructor(private host: HTMLElement, private palette: HTMLElement) {
    this.buildPalette();
    this.host.addEventListener("contextmenu", (e) => e.preventDefault());
    this.render();
  }

  private spec(name: string): GateSpec | undefined {
    return GATES.find((g) => g.name === name);
  }

  private buildPalette() {
    const add = (label: string, value: string, group: string, title: string) => {
      const b = document.createElement("button");
      b.textContent = label;
      b.dataset.tool = value;
      b.dataset.group = group;
      b.title = title;
      b.setAttribute("aria-pressed", String(value === this.tool));
      b.addEventListener("click", () => this.setTool(value as GateName | "erase"));
      this.palette.appendChild(b);
    };
    let group = "";
    for (const g of GATES) {
      if (group && g.group !== group) {
        const sep = document.createElement("span");
        sep.className = "sep";
        this.palette.appendChild(sep);
      }
      group = g.group;
      add(g.label, g.name, g.group, g.info);
    }
    add("⌫", "erase", "meta", "Radierer: Gatter löschen");
  }

  setTool(tool: GateName | "erase") {
    this.tool = tool;
    this.pending = null;
    this.palette.querySelectorAll<HTMLButtonElement>("button").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.tool === tool)));
    this.render();
  }

  setQubits(n: number) {
    this.numQubits = n;
    this.placed = this.placed.filter((p) => p.gate.qubits.every((q) => q < n));
    this.pending = null;
    this.render();
  }

  load(c: Circuit) {
    this.numQubits = c.numQubits;
    this.placed = [];
    const depth = new Array(c.numQubits).fill(0);
    for (const gate of c.gates) {
      if (gate.name === "barrier") continue;
      const span = gate.qubits.length > 1
        ? Array.from({ length: Math.max(...gate.qubits) - Math.min(...gate.qubits) + 1 }, (_, i) => Math.min(...gate.qubits) + i)
        : gate.qubits;
      const col = Math.max(...span.map((q) => depth[q]));
      span.forEach((q) => (depth[q] = col + 1));
      this.placed.push({ col, gate: { ...gate, qubits: [...gate.qubits], params: gate.params ? [...gate.params] : undefined } });
    }
    this.pending = null;
    this.render();
  }

  clear() {
    this.placed = [];
    this.pending = null;
    this.render();
    this.onChange();
  }

  circuit(): Circuit {
    const gates = [...this.placed].sort((a, b) => a.col - b.col).map((p) => p.gate);
    const numClbits = gates.reduce((m, g) => (g.name === "measure" ? Math.max(m, (g.clbit ?? 0) + 1) : m), 0);
    return { numQubits: this.numQubits, numClbits, gates };
  }

  private occupied(col: number, qubits: number[]): Placed | undefined {
    const lo = Math.min(...qubits), hi = Math.max(...qubits);
    return this.placed.find((p) => {
      if (p.col !== col) return false;
      const plo = Math.min(...p.gate.qubits), phi = Math.max(...p.gate.qubits);
      return plo <= hi && lo <= phi;
    });
  }

  private askParams(spec: GateSpec): number[] | null {
    if (spec.params === 0) return [];
    const defaults = spec.params === 3 ? "pi/2, 0, pi" : "pi/2";
    const answer = prompt(`${spec.label}: ${spec.params} Parameter (z. B. pi/4, 0.3)`, defaults);
    if (answer === null) return null;
    try {
      const values = answer.split(",").map((s) => {
        const e = s.trim().replace(/\bpi\b/gi, "PI").replace(/π/g, "PI");
        if (!/^[0-9+\-*/().\sPIe]+$/.test(e)) throw new Error();
        return Function("PI", `"use strict";return (${e})`)(Math.PI) as number;
      });
      if (values.length !== spec.params || values.some((v) => !Number.isFinite(v))) throw new Error();
      return values;
    } catch {
      alert("Ungültiger Parameter");
      return null;
    }
  }

  private click(col: number, q: number) {
    if (this.tool === "erase") {
      const hit = this.placed.findIndex((p) => p.col === col && p.gate.qubits.includes(q));
      if (hit >= 0) { this.placed.splice(hit, 1); this.render(); this.onChange(); }
      return;
    }
    const spec = this.spec(this.tool)!;
    const need = spec.qubits;
    if (need === 1) {
      if (this.occupied(col, [q])) return;
      const params = this.askParams(spec);
      if (params === null) return;
      const gate: Gate = { name: spec.name, qubits: [q], params: params.length ? params : undefined };
      if (spec.name === "measure") gate.clbit = q;
      this.placed.push({ col, gate });
      this.render();
      this.onChange();
      return;
    }
    if (!this.pending || this.pending.col !== col) this.pending = { col, qubits: [] };
    if (this.pending.qubits.includes(q)) { this.pending = null; this.render(); return; }
    this.pending.qubits.push(q);
    if (this.pending.qubits.length === need) {
      const qubits = this.pending.qubits;
      this.pending = null;
      if (!this.occupied(col, qubits)) {
        const params = this.askParams(spec);
        if (params !== null) {
          this.placed.push({ col, gate: { name: spec.name, qubits, params: params.length ? params : undefined } });
          this.onChange();
        }
      }
    }
    this.render();
  }

  render() {
    const cols = Math.max(8, ...this.placed.map((p) => p.col + 3));
    const n = this.numQubits;
    const width = LEFT + cols * CELL + 16, height = TOP * 2 + n * CELL - 10;
    const svg = el("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": `Schaltung mit ${n} Qubits` });
    const y = (q: number) => TOP + q * CELL + CELL / 2 - 5;
    const x = (c: number) => LEFT + c * CELL + CELL / 2;
    for (let q = 0; q < n; q++) {
      el("text", { x: 8, y: y(q) + 4, class: "qlabel" }, svg).textContent = `q${q}`;
      el("line", { x1: LEFT - 6, y1: y(q), x2: width - 8, y2: y(q), class: "wire" }, svg);
    }
    for (let c = 0; c < cols; c++) {
      for (let q = 0; q < n; q++) {
        const pending = this.pending?.col === c && this.pending.qubits.includes(q);
        const cell = el("rect", { x: LEFT + c * CELL + 2, y: y(q) - CELL / 2 + 2, width: CELL - 4, height: CELL - 4, rx: 10, class: `cell${pending ? " pending" : ""}` }, svg);
        cell.addEventListener("click", () => this.click(c, q));
        cell.addEventListener("contextmenu", (e) => {
          e.preventDefault();
          const hit = this.placed.findIndex((p) => p.col === c && p.gate.qubits.includes(q));
          if (hit >= 0) { this.placed.splice(hit, 1); this.render(); this.onChange(); }
        });
      }
    }
    for (const p of this.placed) {
      const g = el("g", { class: "placed" }, svg);
      const qs = p.gate.qubits, cx = x(p.col);
      const name = p.gate.name;
      const remove = (e: Event) => {
        e.preventDefault();
        if (e.type === "contextmenu" || this.tool === "erase") {
          this.placed.splice(this.placed.indexOf(p), 1);
          this.render();
          this.onChange();
        }
      };
      g.addEventListener("click", remove);
      g.addEventListener("contextmenu", remove);
      if (qs.length > 1) {
        el("line", { x1: cx, y1: y(Math.min(...qs)), x2: cx, y2: y(Math.max(...qs)), class: "link" }, g);
        const controls = name === "swap" ? [] : name === "cswap" ? [qs[0]] : name === "mcz" ? qs : qs.slice(0, -1);
        controls.forEach((q) => el("circle", { cx, cy: y(q), r: 5.5, class: "ctrl" }, g));
        const target = qs[qs.length - 1];
        if (name === "swap" || name === "cswap") {
          for (const q of name === "swap" ? qs : qs.slice(1)) {
            el("path", { d: `M${cx - 7} ${y(q) - 7}L${cx + 7} ${y(q) + 7}M${cx + 7} ${y(q) - 7}L${cx - 7} ${y(q) + 7}`, class: "link" }, g);
          }
        } else if (name === "cx" || name === "ccx" || name === "mcx") {
          el("circle", { cx, cy: y(target), r: 11, class: "target-ring" }, g);
          el("path", { d: `M${cx - 11} ${y(target)}H${cx + 11}M${cx} ${y(target) - 11}V${y(target) + 11}`, class: "link" }, g);
        } else if (name !== "cz" && name !== "mcz") {
          const label = this.spec(name)?.label.replace(/^C/, "") ?? name.toUpperCase();
          el("rect", { x: cx - 18, y: y(target) - 16, width: 36, height: 32, class: "gbox" }, g);
          el("text", { x: cx, y: y(target) + 4, "text-anchor": "middle", class: "gtext" }, g).textContent = label;
        } else {
          el("circle", { cx, cy: y(target), r: 5.5, class: "ctrl" }, g);
        }
        continue;
      }
      const spec = this.spec(name);
      const cls = name === "measure" ? "gbox meas" : spec?.group === "rot" ? "gbox rot" : "gbox";
      el("rect", { x: cx - 19, y: y(qs[0]) - 17, width: 38, height: 34, class: cls }, g);
      el("text", { x: cx, y: y(qs[0]) + (p.gate.params ? 0 : 4), "text-anchor": "middle", class: "gtext" }, g).textContent = spec?.label ?? name;
      if (p.gate.params) {
        el("text", { x: cx, y: y(qs[0]) + 12, "text-anchor": "middle", class: "gparam" }, g).textContent = p.gate.params.map(shortParam).join(",");
      }
    }
    this.host.replaceChildren(svg);
  }
}
