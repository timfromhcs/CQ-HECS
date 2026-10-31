// Sound DPLL SAT solver, same contract as cqhecs.sat:
//   SAT     - a model was found and verified clause by clause,
//   UNSAT   - exhaustive search finished; the search tree is recorded as a
//             tree-resolution certificate and replayed by satcert.ts (a separate
//             checker); `certification` says whether that check passed,
//   UNKNOWN - time or node budget exhausted; never reported as UNSAT.
// #SAT has its own function, countModels, and its own result type.

import { checkRefutation, type CertStep } from "./satcert";

export interface CNF {
  numVars: number;
  clauses: number[][];
}

export type SatStatus = "SAT" | "UNSAT" | "UNKNOWN";

export type Certification = "MODEL_VERIFIED" | "TREE_RESOLUTION_CHECKED" | "UNCERTIFIED" | "NONE";

/** Certificates larger than this are not kept; the UNSAT then stays UNCERTIFIED. */
export const MAX_CERTIFICATE_STEPS = 200_000;

export interface SatResult {
  status: SatStatus;
  model: boolean[] | null; // model[v] for v = 1..numVars
  verified: boolean;
  certification: Certification;
  certificateSteps: number;
  decisions: number;
  propagations: number;
  conflicts: number;
  elapsedMs: number;
  note: string;
}

export function parseDimacs(text: string): CNF {
  let numVars = -1, numClauses = -1;
  const clauses: number[][] = [];
  let current: number[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("c") || line.startsWith("%")) continue;
    if (line.startsWith("p")) {
      const m = line.match(/^p\s+cnf\s+(\d+)\s+(\d+)$/);
      if (!m) throw new Error(`invalid header '${line}'`);
      numVars = Number(m[1]);
      numClauses = Number(m[2]);
      continue;
    }
    if (numVars < 0) throw new Error("missing 'p cnf <vars> <clauses>' header");
    for (const tok of line.split(/\s+/)) {
      const lit = Number(tok);
      if (!Number.isInteger(lit)) throw new Error(`invalid literal '${tok}'`);
      if (lit === 0) { clauses.push(current); current = []; continue; }
      if (Math.abs(lit) > numVars) throw new Error(`literal ${lit} exceeds ${numVars} variables`);
      current.push(lit);
    }
  }
  if (current.length) clauses.push(current);
  if (numVars < 0) throw new Error("missing 'p cnf' header");
  if (numClauses >= 0 && clauses.length !== numClauses) {
    throw new Error(`header declares ${numClauses} clauses, found ${clauses.length}`);
  }
  return { numVars, clauses };
}

export function toDimacs(f: CNF): string {
  return [`p cnf ${f.numVars} ${f.clauses.length}`, ...f.clauses.map((c) => `${c.join(" ")} 0`)].join("\n") + "\n";
}

export function satisfies(f: CNF, model: boolean[]): boolean {
  return f.clauses.every((c) => c.some((lit) => model[Math.abs(lit)] === lit > 0));
}

/** Uniform random 3-SAT with a seeded PRNG. */
export function random3Sat(numVars: number, numClauses: number, seed: number): CNF {
  let a = seed >>> 0;
  const r = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), a | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const clauses: number[][] = [];
  for (let k = 0; k < numClauses; k++) {
    const vars = new Set<number>();
    while (vars.size < Math.min(3, numVars)) vars.add(1 + Math.floor(r() * numVars));
    clauses.push([...vars].map((v) => (r() < 0.5 ? -v : v)));
  }
  return { numVars, clauses };
}

/** Pigeonhole PHP(n+1, n): always UNSAT, exponentially hard for resolution. */
export function pigeonhole(holes: number): CNF {
  const pigeons = holes + 1;
  const v = (p: number, h: number) => p * holes + h + 1;
  const clauses: number[][] = [];
  for (let p = 0; p < pigeons; p++) clauses.push(Array.from({ length: holes }, (_, h) => v(p, h)));
  for (let h = 0; h < holes; h++)
    for (let p = 0; p < pigeons; p++)
      for (let q = p + 1; q < pigeons; q++) clauses.push([-v(p, h), -v(q, h)]);
  return { numVars: pigeons * holes, clauses };
}

class Budget extends Error {}

export function solve(f: CNF, timeoutMs = 5000, nodeBudget = Infinity): SatResult {
  const started = performance.now();
  const n = f.numVars;
  const value = new Int8Array(n + 1); // 0 unassigned, 1 true, -1 false
  const trail: number[] = [];
  const occurs: number[][] = Array.from({ length: 2 * n + 2 }, () => []);
  const idx = (lit: number) => (lit > 0 ? 2 * lit : 2 * -lit + 1);
  f.clauses.forEach((c, i) => c.forEach((lit) => occurs[idx(lit)].push(i)));
  let decisions = 0, propagations = 0, conflicts = 0, nodes = 0, ticks = 0;
  const path: number[] = []; // decision literals on the current branch
  let proof: CertStep[] | null = [];
  const record = (step: CertStep) => {
    if (!proof) return;
    if (proof.length >= MAX_CERTIFICATE_STEPS) { proof = null; return; }
    proof.push(step);
  };
  const litVal = (lit: number) => (lit > 0 ? value[lit] : -value[-lit]);
  const assign = (lit: number) => { value[Math.abs(lit)] = lit > 0 ? 1 : -1; trail.push(lit); };
  const undo = (mark: number) => { while (trail.length > mark) value[Math.abs(trail.pop()!)] = 0; };

  const propagate = (): boolean => {
    let changed = true;
    while (changed) {
      changed = false;
      for (const c of f.clauses) {
        let unassigned = 0, last = 0, sat = false;
        for (const lit of c) {
          const v = litVal(lit);
          if (v === 1) { sat = true; break; }
          if (v === 0) { unassigned++; last = lit; }
        }
        if (sat) continue;
        if (unassigned === 0) { conflicts++; return false; }
        if (unassigned === 1) { assign(last); propagations++; changed = true; }
      }
    }
    return true;
  };

  const pick = (): number => {
    // Most occurrences among unassigned variables in unsatisfied clauses.
    let best = 0, bestScore = -1;
    for (let v = 1; v <= n; v++) {
      if (value[v] !== 0) continue;
      const score = occurs[idx(v)].length + occurs[idx(-v)].length;
      if (score > bestScore) { bestScore = score; best = v; }
    }
    return best;
  };

  const search = (): boolean => {
    if (++ticks % 256 === 0 && performance.now() - started > timeoutMs) throw new Budget("time");
    if (++nodes > nodeBudget) throw new Budget("nodes");
    if (!propagate()) { record(["leaf", [...path]]); return false; }
    const v = pick();
    if (v === 0) return true;
    const order = occurs[idx(v)].length >= occurs[idx(-v)].length ? [v, -v] : [-v, v];
    for (const lit of order) {
      const mark = trail.length;
      decisions++;
      assign(lit);
      path.push(lit);
      const found = search();
      path.pop();
      if (found) return true;
      undo(mark);
    }
    // Under order[0] the subtree derived a clause containing -order[0], under
    // order[1] one containing order[0]: resolve on order[0].
    record(["resolve", order[0]]);
    return false;
  };

  let status: SatStatus, model: boolean[] | null = null, note: string;
  let certification: Certification = "NONE";
  if (f.clauses.some((c) => c.length === 0)) {
    status = "UNSAT";
    proof = [["leaf", []]];
    note = "empty clause: UNSAT without search";
  } else {
    try {
      if (search()) {
        model = Array.from({ length: n + 1 }, (_, v) => value[v] === 1);
        if (satisfies(f, model)) { status = "SAT"; note = "model verified clause by clause"; }
        else { status = "UNKNOWN"; model = null; note = "engine model failed verification; refused"; }
      } else {
        status = "UNSAT";
        note = "exhaustive DPLL search";
      }
    } catch (e) {
      if (!(e instanceof Budget)) throw e;
      status = "UNKNOWN";
      note = e.message === "time" ? `timeout after ${timeoutMs} ms; not decided` : "node budget exhausted; not decided";
    }
  }
  let certificateSteps = 0;
  if (status === "SAT") certification = "MODEL_VERIFIED";
  if (status === "UNSAT") {
    if (proof && checkRefutation(f.clauses, proof)) {
      certification = "TREE_RESOLUTION_CHECKED";
      certificateSteps = proof.length;
      note += `; tree-resolution certificate replayed by an independent checker (${proof.length} steps)`;
    } else {
      certification = "UNCERTIFIED";
      note += proof ? "; certificate failed its check (uncertified)" : `; certificate larger than ${MAX_CERTIFICATE_STEPS} steps not kept (uncertified)`;
    }
  }
  return {
    status, model, verified: status === "SAT", certification, certificateSteps, decisions, propagations, conflicts,
    elapsedMs: performance.now() - started, note,
  };
}

export interface SweepPoint { ratio: number; satFraction: number; medianDecisions: number; medianMs: number; unknown: number }

/** Random 3-SAT phase-transition sweep (empirical; not a complexity statement). */
export function sweep(numVars: number, ratios: number[], trials: number, timeoutMs: number, seed = 20261030): SweepPoint[] {
  const median = (xs: number[]) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
  return ratios.map((ratio, ri) => {
    const results = Array.from({ length: trials }, (_, t) =>
      solve(random3Sat(numVars, Math.round(ratio * numVars), seed + ri * 1000 + t), timeoutMs));
    const decided = results.filter((r) => r.status !== "UNKNOWN");
    return {
      ratio,
      satFraction: decided.length ? decided.filter((r) => r.status === "SAT").length / decided.length : 0,
      medianDecisions: median(results.map((r) => r.decisions)),
      medianMs: median(results.map((r) => r.elapsedMs)),
      unknown: results.length - decided.length,
    };
  });
}

export interface CountResult {
  status: "COUNTED" | "UNKNOWN";
  /** Exact model count as a decimal string (BigInt), or null when not determined. */
  count: string | null;
  nodes: number;
  cacheHits: number;
  elapsedMs: number;
  note: string;
}

/**
 * Exact model count #F over all 2^numVars assignments (same method as
 * cqhecs.sat.count_models): unit propagation, variable-disjoint components whose
 * counts multiply, a cache keyed by the component's clauses, and 2^k for free
 * variables. Budget exhaustion gives UNKNOWN, never a number.
 */
export function countModels(f: CNF, timeoutMs = 5000, nodeBudget = Infinity): CountResult {
  const started = performance.now();
  let nodes = 0, cacheHits = 0;
  const cache = new Map<string, bigint>();
  const keyOf = (cs: number[][]) => cs.map((c) => [...c].sort((a, b) => a - b).join(",")).sort().join("|");
  const simplify = (cs: number[][], lit: number): number[][] | null => {
    const out: number[][] = [];
    for (const c of cs) {
      if (c.includes(lit)) continue;
      if (c.includes(-lit)) {
        const reduced = c.filter((l) => l !== -lit);
        if (reduced.length === 0) return null;
        out.push(reduced);
      } else out.push(c);
    }
    return out;
  };
  const count = (clausesIn: number[][], varsIn: Set<number>): bigint => {
    nodes++;
    if (nodes > nodeBudget || (nodes % 256 === 0 && performance.now() - started > timeoutMs)) throw new Budget("count");
    let clauses = clausesIn;
    const vars = new Set(varsIn);
    for (;;) {
      const unit = clauses.find((c) => c.length === 1);
      if (!unit) break;
      const reduced = simplify(clauses, unit[0]);
      if (!reduced) return 0n;
      clauses = reduced;
      vars.delete(Math.abs(unit[0]));
    }
    if (clauses.length === 0) return 1n << BigInt(vars.size);
    const constrained = new Set<number>();
    clauses.forEach((c) => c.forEach((l) => constrained.add(Math.abs(l))));
    let free = 0;
    vars.forEach((v) => { if (!constrained.has(v)) free++; });
    const key = keyOf(clauses);
    const cached = cache.get(key);
    if (cached !== undefined) { cacheHits++; return cached << BigInt(free); }
    // Variable-disjoint components: their counts multiply.
    const comps: { clauses: number[][]; vars: Set<number> }[] = [];
    for (const c of clauses) {
      const cv = new Set(c.map(Math.abs));
      const merged = comps.filter((k) => [...cv].some((v) => k.vars.has(v)));
      const next = { clauses: [c], vars: cv };
      for (const m of merged) {
        comps.splice(comps.indexOf(m), 1);
        next.clauses.push(...m.clauses);
        m.vars.forEach((v) => next.vars.add(v));
      }
      comps.push(next);
    }
    let total: bigint;
    if (comps.length > 1) {
      total = 1n;
      for (const k of comps) {
        const part = count(k.clauses, k.vars);
        if (part === 0n) { total = 0n; break; }
        total *= part;
      }
    } else {
      const occ = new Map<number, number>();
      clauses.forEach((c) => c.forEach((l) => occ.set(Math.abs(l), (occ.get(Math.abs(l)) ?? 0) + 1)));
      let best = 0, bestN = -1;
      occ.forEach((n, v) => { if (n > bestN || (n === bestN && v < best)) { best = v; bestN = n; } });
      const rest = new Set(constrained);
      rest.delete(best);
      total = 0n;
      for (const lit of [best, -best]) {
        const branch = simplify(clauses, lit);
        if (branch) total += count(branch, rest);
      }
    }
    cache.set(key, total);
    return total << BigInt(free);
  };
  try {
    if (f.clauses.some((c) => c.length === 0)) {
      return { status: "COUNTED", count: "0", nodes, cacheHits, elapsedMs: performance.now() - started, note: "empty clause; count is 0" };
    }
    const vars = new Set(Array.from({ length: f.numVars }, (_, i) => i + 1));
    const value = count(f.clauses.map((c) => [...new Set(c)]), vars);
    return { status: "COUNTED", count: value.toString(), nodes, cacheHits, elapsedMs: performance.now() - started, note: "exact DPLL counting with components and cache" };
  } catch (e) {
    if (!(e instanceof Budget)) throw e;
    return { status: "UNKNOWN", count: null, nodes, cacheHits, elapsedMs: performance.now() - started, note: "budget exhausted; no count claimed" };
  }
}
