# CQ-HECS Release Notes

**Version:** 2.5.1
**Release date:** 2026-10-30
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v2.5.1.md`, prepends the exact source commit and required
> CI run, and appends the SHA256 values of the final assets. The content
> describes the code in this tree.

---

## 1. What this release is

`v2.5.1` is a **correction release** for the Hardware-Aware Quantum Bridge that
`v2.5.0` introduced. It changes no public signature and adds no new capability.
It fixes wrong outputs of the noisy density-matrix path and a false provenance
label on a built-in profile. Anyone who used `--profile` or
`NoisyDensityMatrixBackend` with v2.5.0 should re-run: results on circuits that
are not mirror-symmetric were wrong.

| Surface | Status in 2.5.1 |
| :--- | :--- |
| `cqhecs` four-path router/backends | supported; unchanged |
| `cqhecs.expectation` (Pauli expectation values) | supported; unchanged |
| `cqhecs.hardware_bridge` profiles and Kraus channels | supported; both built-in profiles are synthetic |
| `NoisyDensityMatrixBackend` (`NOISY_CLASSICAL`) | supported up to 10 qubits; output convention now matches the router |
| `FakeHardwareProvider` | offline emulation only; never `REAL_HARDWARE` |
| `RealHardwareProvider` | fail-closed boundary; no provider is connected |
| Vulkan compute primitives | dispatch verified on one AMD iGPU; no end-to-end GPU acceleration |

## 2. Fixed

- **CQ-V251-01 (P0) — mirrored bitstrings.** The density matrix was flattened
  with qubit 0 as the most-significant bit. The same circuit (`x q[0]`) gave
  `01` on the router and `10` with `--profile`, and readout errors hit the
  mirrored qubit. Qubit 0 is now rendered rightmost, as everywhere else.
- **CQ-V251-02 (P1) — measurements.** Terminal measurements were ignored and
  every qubit was reported; a mid-circuit measurement in an instruction list
  was dropped. Only measured qubits are reported now, and mid-circuit
  measurement is refused (as the router does).
- **CQ-V251-03 (P0) — provenance.** `fake_manila` claimed to be an IBM
  calibration snapshot (`is_synthetic=False`, timestamp, URI). Its numbers do
  not match IBM's `FakeManila` data; only the topology does. It is now marked
  synthetic, and `BackendProfile` refuses a non-synthetic profile that lacks
  `capture_timestamp` and `provenance_uri`.
- **CQ-V251-04 (P1) — noise on the wrong gate.** Composite gates were lowered
  before the noise lookup, so the `sx` error in `fake_manila` never applied and
  `h` noise applied twice per `sx`. Noise now attaches to each gate as written.
- **CQ-V251-05 (P2) — validation.** Invalid `shots`/`seed` are rejected before
  parsing; a gate with a missing or extra angle is refused instead of acting as
  the identity; all operations are checked before the density matrix is
  allocated.
- **CLI:** unknown `--profile` and topology violations exit with `2` and a JSON
  `error`, not a traceback.

## 3. Tests

- `tests/test_noisy_density_matrix_contract.py` (18 tests). The oracle is
  independent of the code under test: `qiskit.quantum_info.DensityMatrix`
  evolves the gates, `qiskit_aer.noise` builds the channels, and readout is
  computed from its definition. 25 random noisy 3-qubit circuits (asymmetric
  per-qubit noise, full and partial measurement) and 10 ideal 4-qubit circuits
  agree to `1e-10`. The same file fails 60 checks on the v2.5.0 code.
- Mutation harness: 20/20 mutants killed (4 new).
- Local Linux run: 470 Python tests with the native core required, 19/19
  CTest, 85 % branch coverage. Exact-SHA CI results are recorded in the pull
  request and in `research/v2_5_1/TEST_MATRIX.md`.

## 4. Limits and non-claims

- `NOISY_CLASSICAL` output is a modelled distribution, not a measurement. The
  density matrix is exact float64 up to 10 qubits; `error_bound = 0.0` means
  no deliberate approximation, and `sampling_error_bound` covers the sampled
  counts only.
- Noise applies to the gates and qubits a model names. Circuits are not
  transpiled to a profile's basis gates, so uncalibrated gates stay noiseless.
- Both built-in profiles are synthetic. No provider calibration data ships
  with CQ-HECS and no real quantum hardware was used.
- No mid-circuit measurement, reset or classical control.
- No new performance claim. No benchmark was run for this release.

## 5. Installation and smoke test

```bash
python -m pip install cqhecs-2.5.1-py3-none-any.whl
cq-hecs version
cq-hecs profile list
cq-hecs --format json run name:bell --profile fake_manila --shots 1000
```

The pure-Python wheel does not contain the native C++/Vulkan binaries. Build
those from source with CMake and a C++20 toolchain if you need the native
reference paths.

## 6. Evidence

- `CHANGELOG.md` — `[2.5.1]` section.
- `research/v2_5_1/` — baseline, findings, test matrix, execution log.
- `tests/test_noisy_density_matrix_contract.py`, `scripts/run_mutation_tests.py`.
- The published release body records the exact source SHA and required CI run.
