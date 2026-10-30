// Circuit model, gate matrices, OpenQASM 2.0 import/export and compilation.
//
// Every gate compiles to "controlled 2x2 unitary" ops plus measure/reset, so the
// WebAssembly and WebGPU engines share one tiny kernel. SWAP and CSWAP are
// decomposed into CNOT/Toffoli, which is exact.

export type GateName =
  | "id" | "x" | "y" | "z" | "h" | "s" | "sdg" | "t" | "tdg" | "sx" | "sxdg"
  | "rx" | "ry" | "rz" | "p" | "u" | "u2"
  | "cx" | "cy" | "cz" | "ch" | "cp" | "crx" | "cry" | "crz" | "cu"
  | "swap" | "ccx" | "cswap" | "mcx" | "mcz"
  | "measure" | "reset" | "barrier";

export interface Gate {
  name: GateName;
  qubits: number[];
  params?: number[];
  clbit?: number; // for measure
}

export interface Circuit {
  numQubits: number;
  numClbits: number;
  gates: Gate[];
}

/** Complex 2x2 matrix as [ar, ai, br, bi, cr, ci, dr, di] for [[a, b], [c, d]]. */
export type Mat2 = [number, number, number, number, number, number, number, number];

/** One engine operation. */
export type Op =
  | { kind: "u"; target: number; ctrl: number; m: Mat2; arity: number }
  | { kind: "measure"; qubit: number; clbit: number }
  | { kind: "reset"; qubit: number };

export interface GateSpec {
  name: GateName;
  label: string;
  qubits: number;
  params: number;
  group: "1q" | "rot" | "2q" | "3q" | "meta";
  info: string;
}

export const GATES: GateSpec[] = [
  { name: "h", label: "H", qubits: 1, params: 0, group: "1q", info: "Hadamard: |0> to |+>" },
  { name: "x", label: "X", qubits: 1, params: 0, group: "1q", info: "Pauli-X (NOT)" },
  { name: "y", label: "Y", qubits: 1, params: 0, group: "1q", info: "Pauli-Y" },
  { name: "z", label: "Z", qubits: 1, params: 0, group: "1q", info: "Pauli-Z (Phase flip)" },
  { name: "s", label: "S", qubits: 1, params: 0, group: "1q", info: "Phase pi/2" },
  { name: "sdg", label: "S†", qubits: 1, params: 0, group: "1q", info: "Phase -pi/2" },
  { name: "t", label: "T", qubits: 1, params: 0, group: "1q", info: "Phase pi/4" },
  { name: "tdg", label: "T†", qubits: 1, params: 0, group: "1q", info: "Phase -pi/4" },
  { name: "sx", label: "√X", qubits: 1, params: 0, group: "1q", info: "Square root of X" },
  { name: "rx", label: "RX", qubits: 1, params: 1, group: "rot", info: "Rotation about X by theta" },
  { name: "ry", label: "RY", qubits: 1, params: 1, group: "rot", info: "Rotation about Y by theta" },
  { name: "rz", label: "RZ", qubits: 1, params: 1, group: "rot", info: "Rotation about Z by theta" },
  { name: "p", label: "P", qubits: 1, params: 1, group: "rot", info: "Phase gate P(lambda)" },
  { name: "u", label: "U", qubits: 1, params: 3, group: "rot", info: "U(theta, phi, lambda)" },
  { name: "cx", label: "CX", qubits: 2, params: 0, group: "2q", info: "CNOT: control, target" },
  { name: "cz", label: "CZ", qubits: 2, params: 0, group: "2q", info: "Controlled Z" },
  { name: "cy", label: "CY", qubits: 2, params: 0, group: "2q", info: "Controlled Y" },
  { name: "ch", label: "CH", qubits: 2, params: 0, group: "2q", info: "Controlled Hadamard" },
  { name: "cp", label: "CP", qubits: 2, params: 1, group: "2q", info: "Controlled phase" },
  { name: "crz", label: "CRZ", qubits: 2, params: 1, group: "2q", info: "Controlled RZ" },
  { name: "swap", label: "SWAP", qubits: 2, params: 0, group: "2q", info: "Swap two qubits" },
  { name: "ccx", label: "CCX", qubits: 3, params: 0, group: "3q", info: "Toffoli" },
  { name: "cswap", label: "CSWAP", qubits: 3, params: 0, group: "3q", info: "Fredkin" },
  { name: "measure", label: "M", qubits: 1, params: 0, group: "meta", info: "Measure into classical bit" },
  { name: "reset", label: "|0⟩", qubits: 1, params: 0, group: "meta", info: "Reset to |0>" },
];

const SPEC = new Map<string, GateSpec>(GATES.map((g) => [g.name, g]));
const EXTRA_ARITY: Record<string, [number, number]> = {
  id: [1, 0], sxdg: [1, 0], u2: [1, 2], u1: [1, 1], u3: [1, 3], cu1: [2, 1], cu3: [2, 3],
  crx: [2, 1], cry: [2, 1], cu: [2, 4], barrier: [-1, 0],
  // CQ-HECS extension (not qelib1): controls..., target; any width >= 2.
  mcx: [-1, 0], mcz: [-1, 0],
};

export function arity(name: string): [number, number] | undefined {
  const s = SPEC.get(name);
  if (s) return [s.qubits, s.params];
  return EXTRA_ARITY[name];
}

const R = Math.SQRT1_2;

function phase(l: number): Mat2 {
  return [1, 0, 0, 0, 0, 0, Math.cos(l), Math.sin(l)];
}

function u3(theta: number, phi: number, lam: number): Mat2 {
  const c = Math.cos(theta / 2), s = Math.sin(theta / 2);
  return [
    c, 0,
    -Math.cos(lam) * s, -Math.sin(lam) * s,
    Math.cos(phi) * s, Math.sin(phi) * s,
    Math.cos(phi + lam) * c, Math.sin(phi + lam) * c,
  ];
}

/** The 2x2 matrix of a single-qubit gate (or of the target action of a controlled gate). */
export function matrix(name: string, p: number[] = []): Mat2 {
  switch (name) {
    case "id": return [1, 0, 0, 0, 0, 0, 1, 0];
    case "x": case "cx": case "ccx": return [0, 0, 1, 0, 1, 0, 0, 0];
    case "y": case "cy": return [0, 0, 0, -1, 0, 1, 0, 0];
    case "z": case "cz": return [1, 0, 0, 0, 0, 0, -1, 0];
    case "h": case "ch": return [R, 0, R, 0, R, 0, -R, 0];
    case "s": return phase(Math.PI / 2);
    case "sdg": return phase(-Math.PI / 2);
    case "t": return phase(Math.PI / 4);
    case "tdg": return phase(-Math.PI / 4);
    case "sx": return [0.5, 0.5, 0.5, -0.5, 0.5, -0.5, 0.5, 0.5];
    case "sxdg": return [0.5, -0.5, 0.5, 0.5, 0.5, 0.5, 0.5, -0.5];
    case "rx": case "crx": {
      const c = Math.cos(p[0] / 2), s = Math.sin(p[0] / 2);
      return [c, 0, 0, -s, 0, -s, c, 0];
    }
    case "ry": case "cry": {
      const c = Math.cos(p[0] / 2), s = Math.sin(p[0] / 2);
      return [c, 0, -s, 0, s, 0, c, 0];
    }
    case "rz": case "crz": {
      const c = Math.cos(p[0] / 2), s = Math.sin(p[0] / 2);
      return [c, -s, 0, 0, 0, 0, c, s];
    }
    case "p": case "u1": case "cp": case "cu1": return phase(p[0]);
    case "u": case "u3": case "cu3": return u3(p[0], p[1], p[2]);
    case "u2": return u3(Math.PI / 2, p[0], p[1]);
    case "cu": {
      // Qiskit cu(theta, phi, lambda, gamma): global phase gamma on the controlled block.
      const m = u3(p[0], p[1], p[2]);
      const g = p[3] ?? 0, cg = Math.cos(g), sg = Math.sin(g);
      const out = [...m] as Mat2;
      for (let k = 0; k < 8; k += 2) {
        out[k] = m[k] * cg - m[k + 1] * sg;
        out[k + 1] = m[k] * sg + m[k + 1] * cg;
      }
      return out;
    }
    default: throw new Error(`no matrix for gate '${name}'`);
  }
}

const X: Mat2 = [0, 0, 1, 0, 1, 0, 0, 0];

/** Compile a circuit to engine ops. Throws on invalid qubit indices. */
export function compile(c: Circuit): Op[] {
  const ops: Op[] = [];
  const bit = (q: number) => {
    if (!Number.isInteger(q) || q < 0 || q >= c.numQubits) throw new Error(`qubit ${q} out of range`);
    return 1 << q;
  };
  const cx = (ctl: number, tgt: number, extra = 0) =>
    ops.push({ kind: "u", target: tgt, ctrl: bit(ctl) | extra, m: X, arity: extra ? 3 : 2 });
  for (const g of c.gates) {
    const q = g.qubits;
    if (new Set(q).size !== q.length) throw new Error(`${g.name}: repeated qubit`);
    switch (g.name) {
      case "barrier": break;
      case "measure":
        bit(q[0]);
        ops.push({ kind: "measure", qubit: q[0], clbit: g.clbit ?? q[0] });
        break;
      case "reset": bit(q[0]); ops.push({ kind: "reset", qubit: q[0] }); break;
      case "swap": cx(q[0], q[1]); cx(q[1], q[0]); cx(q[0], q[1]); break;
      case "cswap": cx(q[2], q[1]); cx(q[1], q[2], bit(q[0])); cx(q[2], q[1]); break;
      case "ccx":
        ops.push({ kind: "u", target: q[2], ctrl: bit(q[0]) | bit(q[1]), m: X, arity: 3 });
        break;
      case "mcx": case "mcz": {
        if (q.length < 2) throw new Error(`${g.name} needs at least 2 qubits`);
        const target = q[q.length - 1];
        bit(target);
        const ctrl = q.slice(0, -1).reduce((m, c) => m | bit(c), 0);
        ops.push({ kind: "u", target, ctrl, m: matrix(g.name === "mcx" ? "x" : "z"), arity: q.length });
        break;
      }
      case "cx": case "cy": case "cz": case "ch": case "cp": case "crx": case "cry": case "crz": case "cu":
        bit(q[1]);
        ops.push({ kind: "u", target: q[1], ctrl: bit(q[0]), m: matrix(g.name, g.params), arity: 2 });
        break;
      default:
        bit(q[0]);
        ops.push({ kind: "u", target: q[0], ctrl: 0, m: matrix(g.name, g.params), arity: 1 });
    }
  }
  return ops;
}

/** True when every measurement is terminal and there is no reset (shots can be sampled once). */
export function isTerminalOnly(ops: Op[]): boolean {
  const measured = new Set<number>();
  for (const op of ops) {
    if (op.kind === "reset") return false;
    if (op.kind === "measure") measured.add(op.qubit);
    else if (op.kind === "u") {
      if (measured.has(op.target)) return false;
      for (const q of measured) if (op.ctrl & (1 << q)) return false;
    }
  }
  return true;
}

// ---------------------------------------------------------------- OpenQASM 2.0

function evalParam(expr: string): number {
  const cleaned = expr.trim().replace(/\bpi\b/gi, "PI");
  if (!/^[0-9+\-*/().\sPIe]*$/.test(cleaned)) throw new Error(`invalid parameter '${expr}'`);
  const value = Function("PI", `"use strict"; return (${cleaned});`)(Math.PI);
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`invalid parameter '${expr}'`);
  return value;
}

/** Parse the OpenQASM 2.0 subset used by the emulator (qelib1 gates, measure, reset, barrier). */
export function parseQasm(src: string): Circuit {
  const text = src.replace(/\/\/[^\n]*/g, "");
  const regs = new Map<string, { offset: number; size: number; kind: "q" | "c" }>();
  let nq = 0, nc = 0;
  const gates: Gate[] = [];
  const stmts = text.split(";").map((s) => s.trim()).filter(Boolean);
  const resolve = (ref: string, kind: "q" | "c"): number[] => {
    const m = ref.trim().match(/^([A-Za-z_]\w*)(?:\[(\d+)\])?$/);
    if (!m) throw new Error(`invalid operand '${ref}'`);
    const reg = regs.get(m[1]);
    if (!reg || reg.kind !== kind) throw new Error(`unknown ${kind === "q" ? "qreg" : "creg"} '${m[1]}'`);
    if (m[2] === undefined) return Array.from({ length: reg.size }, (_, i) => reg.offset + i);
    const i = Number(m[2]);
    if (i >= reg.size) throw new Error(`${m[1]}[${i}] out of range`);
    return [reg.offset + i];
  };
  for (const stmt of stmts) {
    if (/^OPENQASM\s/i.test(stmt) || /^include\s/.test(stmt)) continue;
    let m = stmt.match(/^(qreg|creg)\s+([A-Za-z_]\w*)\s*\[\s*(\d+)\s*\]$/);
    if (m) {
      const size = Number(m[3]);
      if (m[1] === "qreg") { regs.set(m[2], { offset: nq, size, kind: "q" }); nq += size; }
      else { regs.set(m[2], { offset: nc, size, kind: "c" }); nc += size; }
      continue;
    }
    m = stmt.match(/^measure\s+(.+?)\s*->\s*(.+)$/);
    if (m) {
      const qs = resolve(m[1], "q"), cs = resolve(m[2], "c");
      if (qs.length !== cs.length) throw new Error(`measure size mismatch in '${stmt}'`);
      qs.forEach((q, i) => gates.push({ name: "measure", qubits: [q], clbit: cs[i] }));
      continue;
    }
    m = stmt.match(/^([a-z][\w]*)\s*(?:\(([^)]*)\))?\s+(.+)$/);
    if (!m) throw new Error(`cannot parse '${stmt}'`);
    let name = m[1];
    const params = m[2] ? m[2].split(",").map(evalParam) : [];
    const operands = m[3].split(",").map((o) => resolve(o, "q"));
    if (name === "barrier") continue;
    const ar = arity(name);
    if (!ar) throw new Error(`unsupported gate '${name}'`);
    if (ar[1] !== params.length) throw new Error(`${name} expects ${ar[1]} parameter(s)`);
    if (ar[0] > 0 && operands.length !== ar[0]) throw new Error(`${name} expects ${ar[0]} qubit(s)`);
    if (ar[0] < 0 && operands.length < 2) throw new Error(`${name} expects at least 2 qubits`);
    if (name === "u1") name = "p";
    if (name === "u3") name = "u";
    if (name === "cu1") name = "cp";
    // Register broadcast: h q; applies to every qubit.
    const width = Math.max(...operands.map((o) => o.length));
    for (let k = 0; k < width; k++) {
      const qubits = operands.map((o) => (o.length === 1 ? o[0] : o[k]));
      gates.push({ name: name as GateName, qubits, params });
    }
  }
  if (nq === 0) throw new Error("no qreg declared");
  return { numQubits: nq, numClbits: Math.max(nc, 0), gates };
}

function fmt(x: number): string {
  for (const [v, s] of [[Math.PI, "pi"], [Math.PI / 2, "pi/2"], [Math.PI / 4, "pi/4"], [Math.PI / 8, "pi/8"]] as [number, string][]) {
    if (Math.abs(x - v) < 1e-12) return s;
    if (Math.abs(x + v) < 1e-12) return `-${s}`;
  }
  return String(+x.toPrecision(15));
}

export function toQasm(c: Circuit): string {
  const lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', `qreg q[${c.numQubits}];`];
  if (c.numClbits > 0) lines.push(`creg c[${c.numClbits}];`);
  for (const g of c.gates) {
    if (g.name === "measure") { lines.push(`measure q[${g.qubits[0]}] -> c[${g.clbit ?? g.qubits[0]}];`); continue; }
    const p = g.params?.length ? `(${g.params.map(fmt).join(", ")})` : "";
    lines.push(`${g.name}${p} ${g.qubits.map((q) => `q[${q}]`).join(", ")};`);
  }
  return lines.join("\n") + "\n";
}

// ---------------------------------------------------------------- builder API

/** Fluent builder used by the code mode: `circuit(3).h(0).cx(0, 1).measureAll()`. */
export class Builder implements Circuit {
  gates: Gate[] = [];
  numClbits = 0;
  constructor(public numQubits: number) {
    if (!Number.isInteger(numQubits) || numQubits < 1) throw new Error("circuit(n) needs n >= 1");
  }
  private add(name: GateName, qubits: number[], params?: number[]) {
    this.gates.push({ name, qubits, params });
    return this;
  }
  h(q: number) { return this.add("h", [q]); }
  x(q: number) { return this.add("x", [q]); }
  y(q: number) { return this.add("y", [q]); }
  z(q: number) { return this.add("z", [q]); }
  s(q: number) { return this.add("s", [q]); }
  sdg(q: number) { return this.add("sdg", [q]); }
  t(q: number) { return this.add("t", [q]); }
  tdg(q: number) { return this.add("tdg", [q]); }
  sx(q: number) { return this.add("sx", [q]); }
  rx(theta: number, q: number) { return this.add("rx", [q], [theta]); }
  ry(theta: number, q: number) { return this.add("ry", [q], [theta]); }
  rz(theta: number, q: number) { return this.add("rz", [q], [theta]); }
  p(lambda: number, q: number) { return this.add("p", [q], [lambda]); }
  u(theta: number, phi: number, lambda: number, q: number) { return this.add("u", [q], [theta, phi, lambda]); }
  cx(c: number, t: number) { return this.add("cx", [c, t]); }
  cy(c: number, t: number) { return this.add("cy", [c, t]); }
  cz(c: number, t: number) { return this.add("cz", [c, t]); }
  ch(c: number, t: number) { return this.add("ch", [c, t]); }
  cp(lambda: number, c: number, t: number) { return this.add("cp", [c, t], [lambda]); }
  crz(theta: number, c: number, t: number) { return this.add("crz", [c, t], [theta]); }
  swap(a: number, b: number) { return this.add("swap", [a, b]); }
  ccx(a: number, b: number, t: number) { return this.add("ccx", [a, b, t]); }
  /** Multi-controlled X: controls..., target (last argument). */
  mcx(...qubits: number[]) { return this.add("mcx", qubits); }
  /** Multi-controlled Z: symmetric in its qubits. */
  mcz(...qubits: number[]) { return this.add("mcz", qubits); }
  cswap(c: number, a: number, b: number) { return this.add("cswap", [c, a, b]); }
  reset(q: number) { return this.add("reset", [q]); }
  measure(q: number, c = q) {
    this.numClbits = Math.max(this.numClbits, c + 1);
    this.gates.push({ name: "measure", qubits: [q], clbit: c });
    return this;
  }
  measureAll() {
    for (let q = 0; q < this.numQubits; q++) this.measure(q, q);
    return this;
  }
}
