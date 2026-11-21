# AGENTS_V6.md — Multi-Agent Wave Plan to the Next Major Release

Status: **ACTIVE**. Owner: repository maintainer (`timfromhcs`). Audience: autonomous
coding/research agents.

This is the operating contract for the work between the current release and the next major
release. It is written for **several agents working in parallel waves**, with **self-healing
loops**, layered tests and hard release gates. It assumes `AGENTS.md` (v4 mission) and
`QGRAVITY.md` (Quantum Gravity mission) are also in force; where they conflict, the stricter
rule wins, and the repository maintainer decides.

> Golden rule (unchanged): never manufacture success. Preserve evidence, report uncertainty,
> and stop at a clearly identified blocker rather than crossing a correctness boundary.

---

## 0. Mission and definition of done

Turn the current `main` into the next major release by completing the outstanding engineering
and research tracks with reproducible evidence. The next release is complete only when:

1. Every shipped feature has source, tests (positive + negative/control), an independent oracle
   where practical, documented limits, and provenance in every result.
2. The Quantum Gravity layer is integrated into the router/result/provenance contracts and the
   UI (`docs/QUANTUM_GRAVITY_LAB.md`), with its real-QPU evidence reproducible.
3. The native build can be produced **CPU-only** and **Vulkan**, with accurate capability
   reporting and CPU/Vulkan differential tests.
4. The browser WASM f64 and WebGPU f32 paths are documented and cross-checked on a shared
   conformance corpus; precision limits are labelled.
5. Packages (wheel, sdist, CPU/Vulkan Windows builds, web bundle) build from the exact release
   SHA with SBOM and SHA-256 manifests.
6. Local and remote release gates pass on the exact candidate SHA; `main` deploys only through
   the documented path.
7. The final report names what was proposed but **not** promoted, and every remaining limitation.

The version number is always whatever `scripts/version.py` reports; never hard-code a release
number. `release.yml` auto-creates the tag `v<version>` on a `main` push **only if that tag does
not already exist** — so shipping a release = bump the version everywhere (checked by
`scripts/check_version.py`) and merge to `main`.

---

## 1. Baseline (verified 2026-11-21)

- `main` at the time of writing carries the QGRAVITY research layer, the local API/MCP/CLI, and
  a real-QPU campaign (see `research/qg_2026/`). Package version **5.0.0** (tag `v5.0.0` exists).
- Local suite: ~2 800 Python tests green; native CTest and web builds green in CI.
- Real-QPU campaign `qg-2026-01` complete: 25/25 Spark spent (org **Tim Stark**), evidence under
  `research/qg_2026/raw/`. Findings F-01…F-11.
- Open items carried into this plan: M9 (Web/Studio QG UI), M10 (native CPU/Vulkan split),
  M11 (WebGPU conformance), M12 (packaging), and the SYK hardware follow-up (F-10/F-11).

---

## 2. Multi-agent topology

One **integrator** owns `main`, interfaces, merge order and the final truthfulness of the release.
Specialist agents own bounded areas and never merge to `main`, bump versions, or publish.

| Agent | Owns | May write |
|---|---|---|
| `integrator` | router/result/provenance contracts, merge order, release gates, this plan | `cqhecs/result.py`, `cqhecs/router.py`, `cqhecs/execution_plan.py`, root docs |
| `qg-physics` | `cqhecs/quantum_gravity/*`, QG models/observables/noise | `cqhecs/quantum_gravity/**`, `research/qg_2026/{models,processed}` |
| `qg-platform` | Open Quantum runner, campaign ledgers, QPU experiments | `scripts/run_qg_openquantum_campaign.py`, `research/qg_2026/{raw,JOB_LEDGER.jsonl}` |
| `sat` | `cqhecs/sat*.py`, `cqhecs/omniwave/**`, `cqhecs/drat.py` | SAT sources and their tests |
| `native` | `src/**`, `include/**`, `CMakeLists.txt`, `tests/cpp/**` | native sources and CTest |
| `web` | `web/**`, `docs/WEB_*.md` | web app, WASM, WGSL, its tests |
| `verification` | independent audit, mutation, fuzz, benchmark, literature pins | `research/**` evidence, never product source |
| `docs` | README/CHANGELOG/migration/API docs | documentation only |

Rules: one writer per file area; all changes go through the integrator's tests; no agent pushes
to `main`; no agent rotates credentials or spends credits without the campaign ledger.

---

## 3. Wave plan

Execute waves in order; each wave has an **exit gate** that must pass before the next begins.
Waves may overlap only if their file areas are disjoint and the integrator records the order.

### W0 — Baseline & provenance (gate: reproducible baseline)
- Reproduce the current baseline on the exact checkout: `python scripts/check_version.py`,
  `python -m pytest tests/ -q`, native CTest, `web: npm ci && npm test && npm run build`.
- Record SHA, environment, counts, skips in `research/v7/BASELINE.md`.
- **Gate:** baseline reproduced or every divergence has a minimal reproducer.

### W1 — Contract freeze (gate: no silent schema change)
- Freeze `SimulationResult`, `hcs.run.v2`, `cqhecs.qg.experiment.v1` and CLI/MCP JSON.
- Any change needs a version bump + `docs/MIGRATION_V6.md` + schema-migration fixtures.
- **Gate:** old valid results do not change meaning; consumers can detect unknown fields.

### W2 — QG UI + routing integration (gate: M9/M5)
- Studio + Web QG Lab: catalog, model builder, circuit studio (preview exact QASM + hash, no
  spend), backend lab (type + live status), run monitor, analysis, evidence ledger, export.
- Expose the QG `ExecutionPlan` (dry run) through Python/CLI/MCP/Studio with one schema.
- Provenance-first run cards for every QG result; SIMULATOR vs QPU never blurred.
- **Gate:** every route reachable; axe/WCAG 2.2 AA (no serious/critical); Playwright e2e green;
  empty/failed/refused states honest.

### W3 — Native CPU/Vulkan split (gate: M10)
- A genuine **CPU-only** build: `cmake -S . -B build-cpu -DCQ_ENABLE_VULKAN=OFF` configures,
  builds, tests, installs; the CPU binary must not link the Vulkan loader.
- A separate Vulkan target implementing the same numerical contract.
- **Gate:** `-DCQ_ENABLE_VULKAN=OFF` passes configure+build+CTest; CPU/Vulkan differential tests
  pass; no GPU-acceleration claim without end-to-end evidence.

### W4 — Web conformance + WebGPU (gate: M11)
- One machine-readable conformance corpus run through Python, WASM f64 and WebGPU f32 within a
  declared width; report f32 drift; explicit fallback when WebGPU is unavailable.
- Add device-loss, allocation-failure, worker-cancellation and low-memory tests.
- **Gate:** declared common subset passes; non-common features explicitly labelled.

### W5 — SAT/#SAT (gate: proofs sound)
- Keep the scan DPLL reference and the unified solver; keep separator DP and OMNIWAVE as
  documented, budgeted options. No default engine change without correctness + measured niche.
- **Gate:** every SAT model verified against the original CNF; every UNSAT certificate replayed;
  budget exhaustion returns `UNKNOWN`, never a partial count.

### W6 — Packaging (gate: M12)
- Build wheel + sdist + CPU/Vulkan Windows builds + web bundle from the exact SHA.
- Clean-venv install (`cq-hecs version|doctor|qg …`), Studio health endpoint, SBOM, SHA-256
  manifest, version consistency, secret scan, license inventory.
- **Gate:** clean-environment smoke passes; artifacts match the manifest; no secrets/paths leak.

### W7 — Hardening & audit (gate: M13)
- Mutation/fuzz/property/resource tests on all new high-risk logic; sanitizers on native.
- Independent verification agent re-derives the key claims; failed hypotheses are recorded.
- **Gate:** no unexplained skips; no unreported high/critical defect; claims match evidence.

### W8 — Release candidate & push (gate: M17/M18)
- Create the release branch, bump the version everywhere, regenerate docs/CHANGELOG/migration.
- Push the branch, open a PR, run all gates on the exact head SHA, repair until green.
- **Gate:** every required check green on the exact candidate SHA; preview verified (or marked
  `BLOCKED` with reason).

### W9 — Release decision (gate: M19)
- Merge to `main` (the merge is the release trigger); verify the auto-created tag points at the
  tested SHA; verify assets and the deployed bundle report the same version.
- **Gate:** independent release audit signs off; any unmet condition stays open, never waived.

---

## 4. Self-healing loop (per defect, bounded)

1. **Snapshot** branch/SHA/env/command/input hashes and the full error.
2. **Classify** (correctness, numerical, resource, performance, interop, hardware, security,
   UX/a11y, docs, research, release).
3. **Reproduce** the smallest deterministic failing case; if remote, archive provider/job IDs.
4. **Hypothesise** falsifiable causes; do not edit source while guessing.
5. **Discriminating test** that fails for one reason and passes only after the fix.
6. **Patch minimally**; never weaken an assertion to get green.
7. **Add regression coverage** (unit/property/differential/metamorphic/integration/e2e).
8. **Targeted gates**, then **subsystem gates**, then the **wave gate**.
9. **Update docs + ledgers**; **commit** on a feature branch with a precise message.
10. **Record** the outcome `PASS | FAIL_FIXED | BLOCKED | NOT_RUN | DEFERRED`.

Bounds: at most **3 distinct diagnosis/fix cycles** per root cause before declaring `BLOCKED`
(preserve the reproducer, continue independent work). Paid jobs are **never** auto-retried after
an ambiguous submit; reconcile remote state first. No infinite loops, no uncontrolled spend.

Concrete examples already proven in this repo:
- SYK v1 → **invalid** (exact-vs-Trotter mislabel, non-inverse mirror) → fixed in v3 by
  re-simulating the exported QASM against the ideal (F-09).
- SYK v3 forward/mirror **inconsistent** → **INCONCLUSIVE**, not forced into a claim (F-10).
- SYK v4 no-rewiring **failed** on the contiguous-virtual-qubit constraint → recorded, refunded
  (F-11).

---

## 5. Test matrix (layers; one layer never substitutes for another)

| Layer | Examples | Gate |
|---|---|---|
| Static | `compileall`, `flake8 --select=E9,F`, `check_version.py`, `verify_no_silent_truncation.py` | clean |
| Unit | per module, positive + negative | all pass |
| Contracts | result/provenance/schema + migration fixtures | no silent change |
| Differential | Python↔WASM↔WebGPU, CPU↔Vulkan, CQ-HECS↔Qiskit/Stim/Aer | within declared tolerance |
| Property/fuzz | Hypothesis generators, DIMACS/QASM fuzz | shrinkable counterexamples |
| Metamorphic | inverse circuit, permutation, phase invariance | pass |
| Resource/adversarial | oversized inputs, disk/GPU failure, cancellation | typed refusal |
| Native | CTest, ASan/UBSan, C ABI bounds | pass |
| Web/UI | unit + Playwright + axe (all routes, 360px, keyboard) | no serious/critical |
| Proof | model vs original CNF; UNSAT certificates replayed | certified |
| Research | independent oracles; held-out evaluation | preregistered |
| Performance | fixed seeds, raw JSON, transfer-inclusive GPU timing | reproducible |

Counts and skips are reported and explained; a changed count is not automatically a failure, but
an undocumented deletion/skip/relaxation is.

---

## 6. Release gates (all required; unavailable ⇒ `NOT_RUN`/`BLOCKED`, never green-by-inference)

- Python, CPU native, Vulkan native, web/WASM/WebGPU, API, MCP, Studio and packaging gates pass.
- Windows CPU and Vulkan distributions run on a clean target environment.
- Wheels install and execute outside the source tree.
- No unreported high/critical security defect, test deletion, skipped gate, unsupported claim or
  broken public schema.
- Docs, changelog, migration notes, SBOM, checksums and version surfaces agree.
- `FINAL_REPORT.md` + exact reproduction commands exist; the tested SHA is the tagged SHA.

---

## 7. Credentials and spend policy (Open Quantum)

- Credentials are **environment/saved-account only**, never committed, never printed, never in
  EXEs/wheels/bundles. `oq.py doctor` proves auth without echoing secrets.
- Campaign budget is a **strict cumulative ceiling** enforced by the runner, not only the SDK.
  Never use Full credits/Private/Priority unless the maintainer authorises it for a specific run.
- `quote` never spends; `submit` needs an explicit `--yes` and a resolved account; every job is
  reconciled; failed/canceled jobs are refunded but never assumed refunded until the ledger says so.
- Historical evidence (`research/v3`, `research/v4`, … the `r-io-7` campaign) is **immutable**.
- Rotate keys after any session where a secret was shared in plaintext.

---

## 8. Evidence and reporting

Every non-trivial change produces: problem + use case, spec, owner file, baseline/counterexample,
a failing-then-passing test, an independent oracle where practical, a benchmark with fixed seeds
if performance is claimed, a stated acceptance/falsification threshold, and an honest status
(`PROPOSED | IN_PROGRESS | SUPPORTED_IN_SCOPE | NOT_SUPPORTED | INCONCLUSIVE | BLOCKED |
DEFERRED | REJECTED`).

Immutable evidence lives under `research/**` with SHA-256 manifests. Processed results reference
the raw file hash. Times are UTC ISO-8601. A rerun is a new attempt id, never an overwrite.

---

## 9. Backlog for the next release (task IDs)

| ID | Task | Owner | Gate |
|---|---|---|---|
| T6-01 | QG `ExecutionPlan` in Python/CLI/MCP/Studio, one schema | integrator | parity test |
| T6-02 | Studio + Web QG Lab screens | web | e2e + axe |
| T6-03 | Native CPU-only CMake target (`-DCQ_ENABLE_VULKAN=OFF`) | native | configure+build+CTest |
| T6-04 | Vulkan target parity + device-loss/teardown tests | native | differential |
| T6-05 | Web conformance corpus (Python/WASM/WebGPU) | web | f32 drift reported |
| T6-06 | WebGPU fallback + device-loss/low-memory tests | web | explicit fallback |
| T6-07 | Packaging: wheels, sdist, CPU/Vulkan EXEs, SBOM, checksums | integrator | clean-venv smoke |
| T6-08 | SAT separator/OMNIWAVE: keep budgets + proof soundness | sat | certificate replay |
| T6-09 | SYK hardware follow-up: forward+mirror on one layout (fresh key) | qg-platform | F-10 resolved or re-classified |
| T6-10 | BMV extended scan + drift/uncertainty reporting | qg-physics | preregistered |
| T6-11 | Mutation/fuzz/resource hardening across new code | verification | kills reported |
| T6-12 | Version bump + `MIGRATION_V6.md` + CHANGELOG + release notes | integrator | version check |
| T6-13 | Independent release audit on the candidate SHA | verification | sign-off |

---

## 10. Handoff

At the end of every wave: update this file's status notes and `research/v7/EXECUTION_LOG.md`,
list open blockers with owner/next action, and leave the worktree clean. A new agent must be able
to reproduce the documented result and pick up the next wave **without chat history**.

**Never optimise for the appearance of a release. Optimise for a result another engineer can
challenge, reproduce and trust.**
