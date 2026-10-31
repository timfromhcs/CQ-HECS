# v6 execution log

Chronological record of commands, findings and decisions. Timestamps are local
unless marked UTC. Do not paste secrets or private keys here.

## 2026-10-31 — M0/M1 start

1. Read the supplied `PLAN.md` (v3.5-era, 1616 lines) and `PLAN-v3.6.0.md`
   (1708 lines). The v3.6 plan supersedes the target version but keeps the same
   evidence discipline. The root `PLAN.md` was not modified.
2. `git status --short`: only untracked `PLAN-v3.6.0.md` and
   `.claude/launch.json`; no tracked user modifications.
3. `git branch -a -vv`, `git log -12`: local `main` was stale at `488a05c`.
   `origin/main` was `33723dd` (merge of PR #38, v3.5.0 audit). The audit branch
   `agent/v3.5.0-audit` (`09467af`) is an ancestor with the same tree.
4. `git fetch origin --prune`; confirmed `origin/main` and
   `git diff --stat HEAD origin/main` empty.
5. `git switch -c agent/v3.6.0-sat-core origin/main`. Untracked user files were
   preserved.
6. `python --version` → 3.14.6. `python scripts/version.py` → 3.5.0.
   `python scripts/check_version.py` → OK.
7. `gh release view v3.5.0 --json …`: release published, six assets with SHA-256
   digests matching `research/v5/RELEASE_AUDIT.md`.
8. `gh run list`: CI `41178394449` success on `origin/main`; release pipeline
   `41178394448` success (no-op because the tag existed).
9. Baseline gates: `pytest` 1617 passed / 6 skipped / 1 deselected (190.44 s);
   `ctest` 21/21 (65.42 s); `npm test` 16/16; `npm run build` PASS;
   `compileall` exit 0. Logs under `.local/baseline/`.
10. Found defect F-01: `CNF.is_satisfied` treated unassigned variables as
    `False`, so any negative literal appeared satisfied on a partial assignment.
    Fixed with `_clause_satisfied`; `first_unsatisfied` uses the same helper.
11. Implemented `_WatchedDPLL` (`propagation="watched"`) with two-watched-literal
    BCP, trail/qhead, watch relocation and the existing pure-literal rule. The
    tree-resolution certificate path remains the independent scan-based search.
12. Added `tests/test_sat_watched.py` (134 tests): 120 random differential cases,
    pigeonhole certificate replay, edge cases, budget, determinism, invalid
    propagation name, and the partial-assignment regression.
13. Exhaustive scratch check: all 27,405 formulas over 3 variables with 0–4
    clauses from a 26-clause pool agreed with brute force and the scan engine
    (not committed; reproducible with the same generator).
14. Added `scripts/sat_propagation_benchmark.py`. Quick run on four families:
    no verdict disagreements, no bad models, UNSAT certificates replayed. Raw
    JSON at `.local/baseline/sat-propagation-quick.json`.
15. Wired `--engine watched` into the SAT CLI (additive; existing values
    unchanged) and added three CLI contract tests.
16. Full benchmark (`--repeat 5`, six families) committed as
    `research/v6/evidence/sat_propagation_benchmark.json`: no failures,
    scan/watched median ratios 1.04–1.74×, identical decision counts, every
    UNSAT certificate replayed. H-SAT-01 recorded `SUPPORTED_IN_SCOPE`, not a
    universal claim.
17. Updated `README.md` and `docs/API_REFERENCE.md` with the opt-in engine and
    its evidence boundary.
18. Root-caused the non-zero pytest exit (F-05): `gpu.status()` loaded the native
    Vulkan context and the process died with `0xC0000409` when the DLL was
    unloaded. Added `cq_omniwave_shutdown()` in the C ABI and an `atexit` hook in
    `cqhecs/omniwave/gpu.py`; rebuilt the native library. `tests/test_studio.py`
    now exits 0, and a fresh-process regression test was added.
19. Result contract 1.2: `CNF.original_sha256` and
    `SATResult.formula_original_sha256` retain the input digest; the CLI, MCP and
    Studio formula summaries expose it. `parse_dimacs` now normalizes repeated
    literals like the native parser while direct `CNF(...)` stays strict.
20. Added the watched engine to the Studio selector/API and the MCP engine enum,
    with tests in `test_studio.py` and `test_mcp_server.py`.
