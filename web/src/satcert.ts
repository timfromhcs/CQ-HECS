// Independent checker for tree-resolution refutations, same format and rules as
// cqhecs.sat.check_refutation. It shares no code with the solver in sat.ts: it
// re-reads the original clauses and replays the certificate step by step.
//
//   ["leaf", decisions]  unit propagation on the clauses under the decision
//                        literals must reach a conflict; derives ¬decisions
//   ["resolve", x]       the entry below the top contains -x, the top contains x;
//                        their resolvent replaces both
//
// Valid iff every step holds and exactly the empty clause is left.

export type CertStep = ["leaf", number[]] | ["resolve", number];

function upConflict(clauses: number[][], decisions: number[]): boolean {
  const value = new Map<number, boolean>();
  for (const lit of decisions) {
    const v = Math.abs(lit), want = lit > 0;
    if (v === 0) return false;
    if (value.has(v) && value.get(v) !== want) return true;
    value.set(v, want);
  }
  let changed = true;
  while (changed) {
    changed = false;
    for (const clause of clauses) {
      let open = 0, openLit = 0, satisfied = false;
      for (const lit of clause) {
        const known = value.get(Math.abs(lit));
        if (known === undefined) { open++; openLit = lit; }
        else if (known === lit > 0) { satisfied = true; break; }
      }
      if (satisfied) continue;
      if (open === 0) return true;
      if (open === 1) { value.set(Math.abs(openLit), openLit > 0); changed = true; }
    }
  }
  return false;
}

export function checkRefutation(clauses: number[][], certificate: CertStep[] | null | undefined): boolean {
  if (!certificate || certificate.length === 0) return false;
  const stack: Set<number>[] = [];
  for (const step of certificate) {
    if (!Array.isArray(step) || step.length !== 2) return false;
    const [kind, arg] = step;
    if (kind === "leaf") {
      if (!Array.isArray(arg) || !arg.every((l) => Number.isInteger(l))) return false;
      if (!upConflict(clauses, arg)) return false;
      stack.push(new Set(arg.map((l) => -l)));
    } else if (kind === "resolve") {
      if (!Number.isInteger(arg) || arg === 0 || stack.length < 2) return false;
      const x = arg as number;
      const falseBranch = stack.pop()!, trueBranch = stack.pop()!;
      if (!trueBranch.has(-x) || !falseBranch.has(x)) return false;
      const resolvent = new Set<number>();
      trueBranch.forEach((l) => { if (l !== -x) resolvent.add(l); });
      falseBranch.forEach((l) => { if (l !== x) resolvent.add(l); });
      stack.push(resolvent);
    } else {
      return false;
    }
  }
  return stack.length === 1 && stack[0].size === 0;
}
