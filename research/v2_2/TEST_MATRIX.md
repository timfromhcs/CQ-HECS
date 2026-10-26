# CQ-HECS v2.2 test matrix

## v2.2.1 release candidate (2026-10-26)

**Branch:** `agent/cq-hecs-v2.2.1-hardening`
**Base:** `v2.2.0` / `ce1c66e8ba79f5f3fe1ac68ced151365e2be3010`

Local results for the release candidate:

| Gate | Result | Evidence |
| :--- | :--- | :--- |
| Python suite (3.14 + native) | PASS | **309 passed**, `CQ_HECS_REQUIRE_NATIVE=1` |
| Native CTest (MSVC Release) | PASS | **14/14 passed** |
| Branch coverage | PASS | **81 %** total (2666 statements, 1068 branches); CI gate 70 % |
| Mutation gate | PASS | **11/11 killed**, baseline clean |
| Fatal-error lint | PASS | `flake8 ... --select=E9,F63,F7,F82` |
| Version consistency | PASS | all surfaces report `2.2.1` |
| Silent-truncation audit | PASS | no patterns found |
| SPIR-V shaders | PASS | 12/12 |
| Wheel/sdist + `twine check` | PASS | `cqhecs-2.2.1-*` |
| Clean-install smoke | PASS | fresh venv: `version`, `doctor`, `run name:bell` JSON |
| GitHub Actions on release SHA | required by release workflow | the release job waits for a green `ci.yml` run on the exact tag SHA and puts its URL in the release body |
| Cloud Build | **NOT_VERIFIED** | no Google Cloud project/credentials available |
| Physical GPU | **NOT_VERIFIED** | no physical-device compute run |

### New regression evidence

- `tests/test_hardening_v221.py`: 55 tests covering strict QASM parsing,
  Python/native differential categories, register offsets, whole-register
  expansion, measurement placement/remapping, `cp`/`crz` routing, `reset` and
  mid-circuit refusal, Qiskit `Target`/transpile, Path D grammar/algebra and
  Path C RAM/RSS accounting.
- Qiskit `transpile(qc, backend=backend)` is exercised for Path C gates
  (`cp`, `crz`, ...) on the linear coupling map.
- Differential references: Stim, Qiskit Aer statevector and Aer MPS where
  installed; the native executable for parser categories.

### Release-integrity checks

- The target tag `v2.2.1` did not exist when the candidate was prepared.
- The release workflow refuses to publish unless `ci.yml` succeeded for the
  tagged commit; it also appends final SHA256 values to the release body.
- The Python wheel is pure Python and does not claim to contain native/GPU
  artifacts.

---

## v2.2.0 test matrix

**Date:** 2026-10-23
**Code branch:** `agent/v2.2.0-stable-hardening`
**Base commit:** `22fd300ff2984ad3aaf473d14a71ae1fe043e559`

Results below are local evidence recorded during hardening. CI and Cloud Build
status is recorded separately and must not be inferred from this file.

## Quick gate summary

| Gate | Result | Evidence |
| :--- | :--- | :--- |
| Version consistency | PASS | `python scripts/check_version.py` |
| Silent-truncation audit | PASS | `python scripts/verify_no_silent_truncation.py` |
| SPIR-V shader verification | PASS | 12/12 shaders, `verify_vulkan_shaders.py` |
| Python fatal-error lint | PASS | `flake8 cqhecs tests scripts --select=E9,F63,F7,F82` |
| Native build (MSVC Release) | PASS | `cmake --build build --config Release` |
| CTest | PASS | 14/14 tests, `ctest --test-dir build -C Release` |
| Python suite (3.14 + native) | PASS | 254 passed, `CQ_HECS_REQUIRE_NATIVE=1` |
| Python suite (3.11 pinned deps, no native) | PASS with explicit skips | 251 passed, 3 skipped |
| Branch coverage | PASS (local baseline) | 76% total, `coverage run --branch --source=cqhecs` |
| Mutation gate | PASS | 11/11 killed, baseline clean |
| ASan/UBSan | PASS in CI | GitHub Actions job; Windows/MSVC cannot run it locally |
| GitHub Actions on hardening SHA | PASS | `62559d2`, run <https://github.com/timfromhcs/CQ-HECS/actions/runs/39952077909> (7/7 jobs) |
| GitHub Actions on final docs SHA | RE-VERIFIED AFTER PUSH | final docs commit; result recorded in the release report, not in this file |
| Cloud Build | BLOCKED | `gcloud` not installed; not observed |
| Physical GPU verification | NOT VERIFIED | no physical-device run performed |

## Native CTest detail

Command:

```powershell
ctest --test-dir build -C Release --output-on-failure
```

Result: **14/14 passed** in ~8.0 s.

| # | Test | Result |
| :--- | :--- | :--- |
| 1 | `test_reversibility` | PASS |
| 2 | `test_ghz300` | PASS |
| 3 | `test_constraint_solver` | PASS |
| 4 | `cq_hecs_cpp_hardening` | PASS (updated for fail-closed QASM) |
| 5 | `cq_hecs_full_verification` | PASS |
| 6 | `test_bitexact_and_stress` | PASS |
| 7 | `test_exact_algebra` | PASS |
| 8 | `test_stabilizer` | PASS |
| 9 | `test_hybrid_mps` | PASS |
| 10 | `test_stress_limits` | PASS |
| 11 | `test_exact_ring` | PASS |
| 12 | `test_stabilizer_extreme` | PASS |
| 13 | `test_300q_stress` | PASS |
| 14 | `test_qasm_contract` | PASS |

The `cq_hecs_cpp_hardening` test was corrected: it previously required malformed
QASM to be accepted as one command. It now requires rejection, an empty command
list, and the correct error categories.

## Python suite detail

Command:

```powershell
$env:PYTHONPATH="."
$env:CQ_HECS_REQUIRE_NATIVE="1"
python -m pytest tests/ -q
```

Result on CPython 3.14.6: **254 passed** in ~66 s.

Branch coverage command:

```powershell
python -m coverage run --branch --source=cqhecs -m pytest tests/ -q
python -m coverage report -m
```

Result: **76%** total branch coverage (2198 statements, 786 branches).
CI enforces `--fail-under=70`; the threshold is deliberately below the measured
baseline so it is a regression gate rather than a vanity target. The report is
not a claim that every untested branch is correct.

CPython 3.11 pinned-lane rehearsal:

```powershell
# separate venv, constraints/ci-py311.txt, editable install without native build
python -m pytest tests/ -q
```

Result: **251 passed, 3 skipped**. The skips are native-artifact tests and
Qiskit transpiler smoke checks that require the built shared library; the CI
native jobs set `CQ_HECS_REQUIRE_NATIVE=1` so they cannot silently skip there.

## Mutation gate detail

Command:

```powershell
$env:PYTHONPATH="."
python scripts/run_mutation_tests.py
```

Result:

```text
mutants: 11 | checks: 11
Baseline OK: 11 checks pass on unmutated source.
Mutation score: 11/11 killed (100.0%)
```

Scope: the 11 source patches in `scripts/run_mutation_tests.py`, covering the
historically observed defect classes (bit order, CZ conjugation, rank budget,
MPS normalization, fabricated wide-register counts, sparse-Pauli bound,
unresolved suppression, governor budget, CLI exit status, JSON schema field,
T-count classification). This is a scoped regression gate, **not** a proof of
correctness and not a claim of 100% mutation coverage for the whole codebase.

## Parser and CLI contract checks

- `tests/test_fuzz_qasm.py`: 15 tests, strict invalid-input rejection, declared
  register bounds, whole-register expansion, angle edge cases, JSON error shape,
  exit code 2, native-required mode.
- `tests/test_qasm_circuits.py`, `tests/test_cli_powershell.py`,
  `tests/test_c_api.py`: native CLI and C ABI integration.
- `docs/QASM_CONTRACT.md` records the grammar and exit codes.
- Manual smoke:
  - `cq_hecs qasm <invalid> --json` -> exit 2, JSON on stdout, diagnostics on
    stderr.
  - unknown gate -> category `unsupported_gate`.
  - invalid angle -> category `invalid_parameter`.

## CI gates added

See `.github/workflows/ci.yml`:

1. Static/package smoke on Ubuntu.
2. Pinned-dependency Linux native job: CTest, full Python suite, branch coverage
   (70% floor), mutation gate.
3. Pinned-dependency Windows native job: CTest, full Python suite, mutation gate.
4. Python 3.12/3.13/3.14 compatibility matrix with newest dependencies, no
   native build (skips are visible).
5. Linux ASan/UBSan job: builds with `CQ_ENABLE_SANITIZERS=ON`, proves flags in
   `compile_commands.json`, runs parser/solver/hardening CTest subset.

## Not proven

- No physical GPU benchmark was run.
- No performance claim is made from the CTest timing numbers above.
- Cloud Build was not observed because `gcloud` is unavailable.
- A green run on an earlier SHA is not evidence for the final pushed SHA.
