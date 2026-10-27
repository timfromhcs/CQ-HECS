# Execution log — CQ-HECS v2.2.2 hardening (cycle 2)

- Started: 2026-10-27 (local, Windows 11)
- Base SHA: `812da806d9b4528f1c4f8ccd3cbb7b37b6f009ce` (`main`, merge of PR #7)
- Feature branch: `agent/cq-hecs-v2.2.2-stable-hardening`
- Target version: `2.2.2` (live metadata still showed `v2.2.1` as the latest
  release and no `v2.2.2` tag/release at baseline)
- OS/toolchain: Windows 11 Pro; Python 3.14.6; MSVC 19.44; CMake Release;
  Vulkan SDK 1.4.357.0; qiskit 2.5.1, qiskit-aer 0.17.2, numpy 2.4.6,
  hypothesis 6.170.12
- Fix commits: `0691a587a8c5a3b717625ef4d9ff25154d30e902` (code/tests),
  `bd5cbec3d361d2f507acc4e31ae9fb108abb7c50` (CI/supply chain)

## Finding summary

All 14 CQ items were checked against the merged tree. Twelve were confirmed and
fixed; CQ-09 was verified as already accurate. The detailed root-cause table is
in `FINDINGS.md`. The one defect discovered during this cycle that was not in
the original checklist is recorded here as **CQ-01b**.

### CQ-01 — reversed Path C two-qubit operand order

- Status: CONFIRMED → FIXED
- Source: `cqhecs/backends/path_c_mps_exact.py`,
  `ExactMPSTensorChain.apply_two_qubit_gate`
- Reproduction: `tests/test_path_c_operand_order.py`; the `q1 > q2` branch was
  exercised with non-adjacent CX/CP/SWAP and compared to `Statevector`.
- Before: the reversed branch used `basm,lsmp->labp`, which swapped output axes
  only; input axes remained in chain order, so the gate acted with transposed
  operands.
- Root cause: output-axis reordering was mistaken for full operand reordering.
- Fix: `abcd,ldcp->lbap` plus an explicit tensor-dimension derivation comment.
- Fix commit: `0691a58`
- Regression: 8 tests pass; reversed gates match `Statevector` at fidelity 1.0.

### CQ-01b — Path C hardcoded matrices on the wrong basis block (new)

- Status: CONFIRMED → FIXED
- Source: `PathCMPSExactBackend.execute` two-qubit dispatch.
- Reproduction: backend-level CRX/CRY/CRZ in both operand orders vs
  `Statevector`; all raw-matrix and hand-written `crx`/`cry`/`crz` forms failed
  before conversion.
- Root cause: Qiskit matrices are little-endian, while the chain orders the
  first gate operand as the outermost axis; `crx`/`cry`/`crz` were also written
  on the wrong 2×2 block.
- Fix: canonical little-endian matrices for every two-qubit gate plus
  `_chain_two_qubit_matrix()` (transpose `(1,0,3,2)`).
- Fix commit: `0691a58`
- Regression: same 8-test suite; backend CRX/CRY/CRZ both orders at fidelity 1.0.

### CQ-02 — Path C budgets, preflight and paging

- Status: CONFIRMED → FIXED
- Source: `path_c_mps_exact.py` (`__init__`, `_preflight_two_site`,
  `_ensure_site_in_ram`, `sample`).
- Reproduction: `tests/test_path_c_resources.py` (12 tests).
- Before: unvalidated budgets; allocations before budget checks; sampling
  rehydrated every page regardless of RAM; missing pages could leave `None`
  sites.
- Fix: finite/positive/bounded budgets; pre-allocation preflight including a
  documented SVD workspace multiplier; fail-closed sampling refusal;
  `MPSResourceError` for missing/corrupt pages; `MAX_MPS_QUBITS=4096`,
  `MAX_SHOTS=10_000_000`.
- Fix commit: `0691a58`
- Regression: 12 tests pass.

### CQ-03 / CQ-04 — measurement mapping and index coercion

- Status: CONFIRMED → FIXED
- Source: `cqhecs/circuit_parsing.py`; `cqhecs/backend.py` retained layout path.
- Reproduction: `tests/test_parser_strictness.py` (18 tests).
- Before: `measure(q[i]) -> c[j]` with `i != j` was silently relabelled; `int()`
  coerced floats, strings and booleans; terminal measurement order was
  source-dependent.
- Fix: direct `parse_circuit()` accepts only identity terminal measurements;
  `CQHecsBackend` preserves arbitrary layouts via
  `_normalize_measurements()`/`_pad_counts()`; terminal measurements sorted and
  deduplicated; only `numbers.Integral` (excluding `bool`) accepted, with a
  `1<<20` index ceiling and iterable operand checks.
- Fix commit: `0691a58`
- Regression: 18 tests pass.

### CQ-05 / CQ-14 — differential and property coverage

- Status: CONFIRMED (under-proof) → FIXED
- Source: `tests/test_adversarial_aer_and_stim.py`,
  `tests/test_property_parser.py`.
- Fix: real statevector fidelity, 5σ/TVD sampling envelopes, untruncated Aer MPS
  where supported, Aer statevector for `crx`/`cry`; deterministic Hypothesis
  parser properties.
- Dependency: `hypothesis>=6.0.0` dev extra; `6.170.12` pinned for CI.
- Fix commits: `0691a58`, `bd5cbec`
- Regression: 6 + 5 tests pass.

### CQ-06 — native SAT parser and timeout

- Status: CONFIRMED → FIXED
- Source: `src/sat_solver.cpp`, `src/sat_solver.hpp`, `src/main.cpp`.
- Reproduction: `tests/cpp/test_sat_parser.cpp` (`test_sat_parser`),
  `tests/test_fuzz_sat.py` (14 tests).
- Fix: strict DIMACS grammar and ceilings; timeout is an explicit error (exit
  1), invalid input exits 2, never UNSAT; hash covers all assigned variables;
  literals above the declared header count rejected; 30 s test timeout.
- Fix commit: `0691a58`
- Regression: native suite passes; Python fuzz tests pass.

### CQ-07 / CQ-08 / CQ-11 — claim alignment

- Status: CONFIRMED → FIXED (documentation)
- Fix: Path B no longer advertised as "Bit-Exact"; Path C discarded mass is
  documented as `discarded_spectral_mass_diagnostic` with
  `numerical_error_bound=None`; the 20-qubit dense conversion cap is separated
  from the 500-qubit MPS-native sampling ceiling in `ARCHITECTURE.md`,
  `docs/ARCHITECTURE.md` and `docs/USAGE_GUIDE.md`.
- Fix commit: docs commit on this branch.
- Verification: `python scripts/check_version.py` → all surfaces `2.2.2`.

### CQ-09 — Vulkan/native status

- Status: VERIFIED, no defect
- Evidence: README/ARCHITECTURE/V2 matrix continue to label
  `PLANNER_ONLY`, `CPU_REFERENCE`, `LEGACY_DIAGNOSTIC` and
  `PHYSICAL_GPU_UNVERIFIED`. Shader check is compile-only.

### CQ-10 — large-register validation

- Status: CONFIRMED → FIXED
- Source: Path A/B/C/D backends; `path_c_mps_exact.py` module constants.
- Fix: A/D `MAX_QUBITS=4096`; B `MAX_QUBITS=22` (dense statevector);
  C `MAX_QUBITS=4096`; all `MAX_SHOTS=10_000_000`; refusals precede tableau,
  statevector, observable and shot-matrix allocation.
- Fix commit: `0691a58`
- Regression: `tests/test_circuit_size_limits.py` (3 tests) and Path C resource
  tests pass.

### CQ-12 — CI actions and permissions

- Status: CONFIRMED → FIXED
- Fix: Node 24 actions pinned by full SHA, verified against upstream tags with
  `git ls-remote`:

  | Action | Version | Pinned commit |
  | :--- | :--- | :--- |
  | `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
  | `actions/setup-python` | `v7.1.0` | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
  | `actions/upload-artifact` | `v7.0.2` | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
  | `softprops/action-gh-release` | `v3.0.3` | `efb35369e0ad2afab669f228072c1b0d510eae64` (peeled) |
  | `jakoch/install-vulkan-sdk-action` | `v1.7.0` | `d17de7e2f5e50efb5d2123efed18497d3c58c533` |

- Permissions: workflow `contents: read`; release job `contents: write`.
- Fix commit: `bd5cbec`
- Verification: all three workflow files parse as YAML.

### CQ-13 — QFT deprecation

- Status: CONFIRMED → FIXED
- Fix: `QFT(4).decompose()` replaced with `synth_qft_full(4)` in
  `tests/python/test_qiskit_backend_contract.py`.
- Fix commit: `0691a58`

## Gate evidence (local candidate)

| Gate | Exact command | SHA | Result | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Python suite | `$env:PYTHONPATH="."; python -m pytest tests/ -q` | `0691a58` + docs tree | **366 passed in 83.85s** | 0 failed, 0 skipped; re-run after Path D class cleanup: 366 passed in 73.70s |
| Native build | `cmake --build build --config Release --parallel` | `0691a58` | PASS | MSVC 19.44 |
| Native suite | `ctest --test-dir build -C Release --output-on-failure` | `0691a58` | **18/18 passed in 17.13s** | re-run 17.34s |
| Coverage | `python -m coverage run --branch --source=cqhecs -m pytest tests/ -q`; `python -m coverage report --fail-under=70` | `0691a58` | **82%**, exit 0 | threshold 70% |
| Mutation | `python scripts/run_mutation_tests.py` | `0691a58` | **11/11 killed** | clean baseline |
| Shaders | `python scripts/verify_vulkan_shaders.py` | `0691a58` | **12/12**, 0 warnings | compile-only; no GPU claim |
| Compile | `python -m compileall -q cqhecs tests scripts` | `0691a58` | PASS | exit 0 |
| Silent truncation | `python scripts/verify_no_silent_truncation.py` | `0691a58` | PASS | |
| Version | `python scripts/check_version.py` | `0691a58` + docs tree | PASS — `2.2.2` | |
| Workflow YAML | `python -c "import yaml; ..."` | `bd5cbec` | PASS | ci/nightly/release |
| Action refs | `git ls-remote --tags <repo> refs/tags/<version>` | `bd5cbec` | PASS | all five SHAs verified |
| Whitespace | `git diff --check` | docs tree | PASS | pre-existing `GEMINI.md` trailing spaces removed, content preserved |
| Package build | `python -m build` | docs tree | PASS | wheel + sdist `2.2.2` |
| Twine | `python -m twine check dist/cqhecs-2.2.2-*` | docs tree | PASS | `dist/*` also contains SBOM JSON, which twine rejects as a non-distribution |
| Fresh venv | install `cqhecs-2.2.2-py3-none-any.whl`; `cq-hecs version/doctor`; JSON bell run | docs tree | PASS | run from `%TEMP%`; counts `{"00":491,"11":509}` sum to 1000; state `EXACT` |

## Not run locally

| Gate | Status | Reason |
| :--- | :--- | :--- |
| Linux native build and full CI | PENDING | Recorded on the PR after push |
| ASan/UBSan | PENDING | Delegated to CI; MSVC cannot build the sanitizer target |
| Cloud Build | NOT VERIFIED | No project/trigger access |
| Physical GPU compute | NOT VERIFIED | No device dispatch exercised |
| Published release assets | PENDING | Requires merged SHA, tag and release workflow |

## CI / release status

- PR, CI run URLs and the exact merged SHA are appended to the final report
  after the branch is pushed and checks complete.
- `v2.2.2` is tagged only from the verified merged SHA and only after the
  tag-triggered release workflow succeeds.
