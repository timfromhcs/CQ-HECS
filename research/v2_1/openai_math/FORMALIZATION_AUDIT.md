# OpenAI Math Formalization Audit

**Audit Date:** 2026-10-19  
**Repository Toolchain:** Lean 4 (`leanprover/lean4:v4.16.0` declared in `lean-toolchain`).  
**Formalized Sources Count:** 475 manuscripts across 242 documented families in `lean/docs/`.  

---

## 1. Toolchain & Environment Verification

- Declared Lean version: `v4.16.0`
- Lake build configuration: `lean/lakefile.lean`, dependencies in `lean/lake-manifest.json` (includes `mathlib4`).
- Formalization catalog schema: `formalization.schema.json` version v0.4.

---

## 2. Quantum Formalizations Audited

### Family 279: Exact Quantum Factoring
- **Scope File:** `lean/docs/279.md`
- **Lean Comparator Target:** `lean/ComparatorChallenges/ExactQuantumFactoring.lean`
- **Theorem Content:** Verifies that an explicit polynomial-time uniform quantum circuit family factors integers $N \ge 2$ with probability exactly 1 using a fixed gate set.
- **Audit Finding:** The formalized statement matches the headline claim of the paper. It specifies quantum circuits operating on a quantum computer, not a classical simulator.

---

## 3. Formalization Integrity Criteria
Per `GEMINI.md` §4:
- Lean formalization of an adjacent lemma or sub-case does not automatically prove the full headline claim of an unformalized paper.
- All load-bearing claims transferred to CQ-HECS must be verified independently against the primary mathematical literature and tested with reproducible code.
