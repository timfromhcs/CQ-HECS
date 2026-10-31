# v3.5.0 final report (PLAN.md M0–M12 + OMNIWAVE P0–P10)

Released 2026-10-31 as `v3.5.0` (`725d2c3`). See `RELEASE_AUDIT.md` for the asset hashes.

## What changed

| Area | Result |
| :--- | :--- |
| SAT evidence | The result contract 1.1 adds `certification` on every surface. New: an independent DRAT checker `cqhecs.drat`, an optional CaDiCaL backend whose proofs are DRAT-checked, and tree-resolution certificates replayed in the browser |
| #SAT | Exact `count_models`, available in the CLI, MCP, Studio and the web app |
| ETH audit | `COMPLEXITY_CLAIM_AUDIT.md`: ETH (and SETH) is *claimed refuted* and was not re-run here. P vs NP stays open |
| Web | Playwright E2E and axe in CI, screenshots at six viewports, a provenance panel and JSON export. Five defects found and fixed |
| OMNIWAVE | Experimental multi-front engine. UNSAT only with an accepted DRAT proof. Vulkan BCP kernel verified on every pass. Available in the CLI, MCP and the Studio lab. Details in `OMNIWAVE.md` |

## Tests

- **Python:** 1669 passed, 4 skipped, coverage 84 %, in the Linux CI lane.
- **Native and mutation:** CTest 21/21; mutation testing 54/54 killed.
- **Web:** 16 unit tests and 13 E2E tests, passing both in CI and against production.
- **Local GPU:** the OMNIWAVE kernel ran on an AMD Radeon iGPU and matched the CPU bit for bit.

## Benchmarks (OMNIWAVE, `OMNIWAVE.md` §5–6)

- 24 instances × 5 engines: no disagreement and no unchecked UNSAT.
- **H1** (nogood sharing reduces work): not supported. Multiple waves change the work in both directions.
- **H2** (algebraic compression): supported only where it was already known, namely XOR structure and small separators.
- OMNIWAVE is 3–11× slower than DPLL on UNSAT instances. CaDiCaL is the fastest engine everywhere.

## Proof status

- `cqhecs.drat` checks every OMNIWAVE and CaDiCaL UNSAT result. The checker is independent of the solvers but has not been formally verified.
- If a proof check is undecided, the result is `UNKNOWN`. This happened once in the benchmark.

## Limitations

- OMNIWAVE threads share the GIL.
- The batch and Vulkan modes are reference implementations, not fast paths.
- OMNIWAVE has no CDCL.
- The Lean artifacts behind the ETH claim were not re-run (B-01).
- The exe does not include the Vulkan path.

## Non-claims

This release makes no P = NP claim, no ETH refutation of its own, no universal speedup claim and no GPU acceleration claim.
