# CQ-HECS Release Notes

**Version:** 3.0.0 (Stable)
**Release date:** 2026-10-30
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v3.0.0.md`, prepends the exact source commit and required
> CI run, and appends the SHA256 values of the final assets. The content
> describes the code in this tree.

---

## 1. What this release is

`v3.0.0` is the first major release since 2.0. It is a major version for two
reasons: it changes contracts that callers can observe (SAT result
semantics, strict DIMACS parsing, checked exact arithmetic, profile schema
2.0), and it adds a measured real-hardware reference with a preregistered
hypothesis test. Every gate in `research/v3/RELEASE_PROCESS.md` passed before
the tag. **Upgrading:** `docs/MIGRATION_V3.md`.

| Surface | Status in 3.0.0 |
| :--- | :--- |
| Four-path router/backends | supported; unchanged semantics |
| Gate set | adds `fsim`, `syc`, `phased_x`, `sqrt_x`, `sqrt_y`, `sqrt_w` (lowered) |
| Noise bridge | real IBM calibration import, T1/T2 relaxation, profile schema 2.0 with migration |
| Noisy expectation values | exact density matrix and Heisenberg propagation with a certified truncation bound |
| Real-data reference | `r-io-5` (public IBM counts) and `r-io-7` (own 25-job Rigetti suite) |
| Python SAT engine | **breaking**: explicit `status`; a timeout is unknown, never UNSAT |
| DIMACS (Python) | **breaking**: native grammar, malformed input is an error |
| Exact rings (C++) | **breaking**: arithmetic throws on overflow, no longer `noexcept` |
| Dashboards | **breaking**: synthetic values only, require `--demo` |
| `RealHardwareProvider` | fail-closed boundary; the package submits no jobs |
| Vulkan compute primitives | software-ICD dispatch verified in CI; explicit device selection |

## 2. Fixed (`research/v3/DEFECT_REGISTER.md`)

Each defect was reproduced before it was fixed.

- **CQ-V3-01 (P0) — SAT timeout reported as a verified UNSAT.** The Python
  solver returned `satisfiable=False, verified=True` when its budget ran out.
- **CQ-V3-02 (P0) — hash pruning dropped satisfiable branches.** Python keyed
  search states by the first 32 variables; the native solver trusted a 64-bit
  hash match. A satisfiable formula could be reported as a verified UNSAT.
  Both now skip only states identical to an already refuted one.
- **CQ-V3-03 — Python DIMACS parser.** Clauses spanning lines were split and
  an empty clause was dropped (an UNSAT input became SAT).
- **CQ-V3-04 — exact-ring overflow.** Unchecked `int64`/`uint32` arithmetic in
  both ring implementations; equality swallowed overflow as "not equal".
- **CQ-V3-05 — Release builds compiled test checks out.** Four C++ test
  executables used `assert` without `#undef NDEBUG`.
- **CQ-V3-06/08 — synthetic telemetry shown as live.** Both dashboards drew
  sine curves labelled `ACTIVE` and `PHYSICAL HARVEST` with stale versions.
- **CQ-V3-07 — Vulkan device selection.** Now a tested policy with an
  explicit `CQ_HECS_VULKAN_DEVICE` override and no silent fallback.

## 3. Added

- Real IBM calibration import (`cqhecs.calibration_import`), schema 2.0
  `calibration_flags`/`source_sha256`, `ThermalRelaxationChannel` and Aer's
  relaxation-plus-depolarizing composition; channel parity with Aer ≤ 1e-12.
- `cqhecs.noisy_expectation`: noisy Pauli expectation values with a certified
  worst-case truncation bound.
- `cqhecs.reference` and `cq-hecs reference run` for `r-io-5` and `r-io-7`;
  `cqhecs.openquantum_suite` and its preregistered 25-job suite;
  `cq-hecs noise-fit` (per-qubit model, labelled exploratory).
- Sycamore gate set, profile migration (`cq-hecs profile migrate`), the
  metamorphic self-test (`cq-hecs selftest`), and property-based tests.

## 4. Measured evidence (not a performance claim)

- **H-V3-8 `SUPPORTED`** on `rigetti:cepheus-1-108q`, 25 jobs × 1000 shots,
  2026-10-30: a three-parameter noise model fitted on 5 FIT jobs beats the
  ideal distribution on 20 held-out jobs, median ΔTV −0.071905, 95 % CI
  [−0.135899, −0.006703]. One backend, one day, no calibration snapshot.
- **H-V3-9 rejected (post-hoc):** a per-qubit readout model does not transfer
  between jobs because the provider did not publish the qubit layout.
- **H-V3-1 `INCONCLUSIVE`** on the public `r-io-5` record (circuits not
  published).

## 5. Tests

- Linux CI with the native build required: 594 Python tests passed, 0 skipped
  (1 opt-in slow gate), branch coverage 86 %.
- CTest 21/21 on Linux and Windows, including a `WILL_FAIL` meta-test that
  proves checks run in Release builds; ASan/UBSan lane green.
- Source mutation gate: 40/40 killed (mutants 36–40 are new in 3.0).
- Python 3.12, 3.13 and 3.14 compatibility lanes green.

## 6. Limits and non-claims

- The package executes no job on real quantum hardware. The `r-io-7` counts
  were produced by a separate, manually approved runner and are reference data.
- "Closer to real hardware" holds only for the `r-io-7` suite on one backend
  and one day; it is not a general fidelity claim.
- No physical-GPU verification in this release; CI uses a software ICD.
- No mid-circuit measurement, reset or classical control. No performance claim.
- P versus NP is open; nothing here bears on it.

## 7. Installation and smoke test

```bash
python -m pip install cqhecs-3.0.0-py3-none-any.whl
cq-hecs version
cq-hecs selftest
cq-hecs --format json run name:bell --profile fake_manila --shots 1000
```

The pure-Python wheel does not contain the native C++/Vulkan binaries. Build
those from source with CMake and a C++20 toolchain if you need them.

## 8. Evidence

- `CHANGELOG.md` — `[3.0.0]` section.
- `research/v3/` — plan, gates, hypotheses, datasets, defect register,
  execution log and raw `r-io-7` counts.
- The published release body records the exact source SHA and required CI run.
