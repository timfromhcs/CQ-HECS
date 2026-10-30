# CQ-HECS v2.5.2 Test Matrix

Baseline SHA: `1be682a` (= `main` = `v2.5.1`). Candidate: branch
`claude/vigilant-ritchie-mscxry`. Local runs below were made on the candidate
working tree (code commit `a166ca0` plus the version/docs changes); exact-SHA
cloud results are listed in §3 once they exist.

Environment: see BASELINE.md §3 (CPython 3.13 main venv with latest
dependencies; CPython 3.11 with `constraints/ci-py311.txt`; GCC 13.3; Mesa
llvmpipe).

## 1. Local gates

| Level | Gate | Command | Baseline `1be682a` | Candidate |
|---|---|---|---|---|
| L1 | Compile | `python -m compileall -q cqhecs tests scripts python_bridge` | PASS | PASS |
| L1 | Fatal lint | `flake8 cqhecs tests scripts python_bridge --count --select=E9,F` | 0 | 0 |
| L1 | Versions | `python scripts/check_version.py` | PASS (2.5.1) | PASS (all 2.5.2) |
| L1 | Silent truncation | `python scripts/verify_no_silent_truncation.py` | PASS | PASS |
| L1 | Package | `python -m build`; `twine check dist/*` | — | PASS (wheel 153024 B, sdist 225595 B; local build, not the release artifact) |
| L1 | Clean-venv wheel smoke (CPython 3.11) | `cq-hecs --help`, `version`, `doctor`, `--format json run name:bell`, `--profile fake_manila`; Path B `h t s h` | v2.5.1 wheel: Path B `P(0)=0.8505` | PASS; `2.5.2`, Path B `P(0)=0.1471`, profile `NOISY_CLASSICAL` |
| L2 | Shaders | `python scripts/verify_vulkan_shaders.py` | 12/12 | 12/12 |
| L2 | CTest | `ctest --test-dir build` (GCC Release, Ninja) | 19/19 | 19/19 |
| L2 | Native SWAP regression | `test_hybrid_mps` with the new test, built from each tree | FAIL (assertion `"010"`) | PASS |
| L2 | Vulkan dispatch | `CQ_REQUIRE_VULKAN=1 ctest -R test_vulkan_compute_contract` | PASS, llvmpipe | PASS, llvmpipe (`SOFTWARE_ICD_DISPATCH_VERIFIED` only) |
| L3 | Python suite + native | `CQ_HECS_REQUIRE_NATIVE=1 coverage run --branch --source=cqhecs -m pytest tests/ -q` | 470 passed | 483 passed, 0 skipped |
| L3 | Branch coverage | `coverage report --fail-under=70` | 85 % | 86 % (`hardware_bridge.py` 86 %, `noisy_density_matrix.py` 89 %, `path_b_stabilizer_rank.py` 88 %) |
| L3 | Pinned lane (CPython 3.11, Qiskit 2.5.1, Aer 0.17.2, no native) | `pytest tests/test_v252_regressions.py tests/test_hardware_bridge.py tests/test_noisy_density_matrix*.py` | — | 58 passed |
| L4 | New regressions on baseline | `tests/test_v252_regressions.py` against a `1be682a` worktree (own native build) | 62 sub-cases + 3 tests fail, 10 pass | 13/13 pass |
| L4 | Differential fuzz | `research/v2_5_2/differential_fuzz.py` seeds 1–4 × 200 | Path B and native Path A systematic mismatches (TV up to 1) | 1 sampling excursion (TV 0.0225 vs bound 0.0215 at δ = 0.05; router = Path C counts), 0 systematic |
| L4 | Expectation values vs `SparsePauliOp` | 200 random circuits, methods auto/dense/sparse_pauli/stabilizer | 0 mismatches | 0 mismatches |
| L4 | Front-end parity | list vs Qiskit vs OpenQASM 2, Path C, 200 circuits | 84 identical; 116 refused by QASM (CQ-V252-06) | same |
| L5 | Mutation | `python scripts/run_mutation_tests.py` | 20/20 | 24/24 killed, baseline clean |
| L6 | Benchmarks | — | NOT RUN | NOT RUN (no performance claim) |
| L7 | Real QPU | — | NOT RUN | NOT RUN / BLOCKED (no authorization, no provider) |

## 2. Published-artifact checks

v2.5.1 assets downloaded and re-hashed (`sha256sum -c`: all OK); see
BASELINE.md §2.

## 3. Cloud gates (exact SHA)

Recorded after the merge (this file was not changed on the tested SHA):

- PR head `3f59729`: push run https://github.com/timfromhcs/CQ-HECS/actions/runs/40990556773
  and pull_request run https://github.com/timfromhcs/CQ-HECS/actions/runs/40990588972 —
  both success, 7/7 jobs.
- Merged `a65c35b` on `main`: https://github.com/timfromhcs/CQ-HECS/actions/runs/40991232761 — success.

See RELEASE_AUDIT.md.
