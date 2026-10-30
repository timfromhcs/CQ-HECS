// Sound DPLL SAT solver, same contract as cqhecs.sat:
//   SAT     - a model was found and verified clause by clause,
//   UNSAT   - exhaustive search finished (no proof object is produced),
//   UNKNOWN - time or node budget exhausted; never reported as UNSAT.

export interface CNF {
  numVars: number;
  clauses: number[][];
}

export type SatStatus = "SAT" | "UNSAT" | "UNKNOWN";

export interface SatResult {
  status: SatStatus;
  model: boolean[] | null; // model[v] for v = 1..numVars
  verified: boolean;
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
    if (!propagate()) return false;
    const v = pick();
    if (v === 0) return true;
    for (const lit of occurs[idx(v)].length >= occurs[idx(-v)].length ? [v, -v] : [-v, v]) {
      const mark = trail.length;
      decisions++;
      assign(lit);
      if (search()) return true;
      undo(mark);
    }
    return false;
  };

  let status: SatStatus, model: boolean[] | null = null, note: string;
  if (f.clauses.some((c) => c.length === 0)) {
    status = "UNSAT";
    note = "empty clause: UNSAT without search";
  } else {
    try {
      if (search()) {
        model = Array.from({ length: n + 1 }, (_, v) => value[v] === 1);
        if (satisfies(f, model)) { status = "SAT"; note = "model verified clause by clause"; }
        else { status = "UNKNOWN"; model = null; note = "engine model failed verification; refused"; }
      } else {
        status = "UNSAT";
        note = "exhaustive DPLL search; no independently checkable proof object";
      }
    } catch (e) {
      if (!(e instanceof Budget)) throw e;
      status = "UNKNOWN";
      note = e.message === "time" ? `timeout after ${timeoutMs} ms; not decided` : "node budget exhausted; not decided";
    }
  }
  return {
    status, model, verified: status === "SAT", decisions, propagations, conflicts,
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
