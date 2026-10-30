# CQ-HECS Release Notes

**Version:** 2.5.2
**Release date:** 2026-10-30
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v2.5.2.md`, prepends the exact source commit and required
> CI run, and appends the SHA256 values of the final assets. The content
> describes the code in this tree.

---

## 1. What this release is

`v2.5.2` is a **correction release**. It adds one helper function and changes
no existing signature. It fixes two wrong-result defects in exact simulation
paths, a noise-model parameter convention and missing validation in backend
profiles. No new simulation path, no performance claim.

**Re-run anything that used:**

- **Path B** (`preferred_path="B"`, or the router on low-T-count circuits) with
  `t`/`tdg` together with other phase gates — `t` and `tdg` were swapped there;
- **`--profile` / `BackendProfile.to_noise_model()`** — the modelled noise was
  too weak (one-qubit gate noise by a factor of 2, two-qubit by 4/3);
- **Path A with the native module built from source**, or `cq_apply_swap` in
  the C API — `swap` did nothing on Clifford circuits. The published
  pure-Python wheel was not affected by this one.

| Surface | Status in 2.5.2 |
| :--- | :--- |
| `cqhecs` four-path router/backends | supported; Path B `t`/`tdg` fixed |
| `cqhecs.expectation` (Pauli expectation values) | supported; unchanged (did not use Path B) |
| `cqhecs.hardware_bridge` profiles and Kraus channels | supported; gate errors are infidelities; stricter validation |
| `NoisyDensityMatrixBackend` (`NOISY_CLASSICAL`) | supported up to 10 qubits; all manifest gates incl. `cu1`/`crx`/`cry`/`crz` |
| `FakeHardwareProvider` | offline emulation only; never `REAL_HARDWARE` |
| `RealHardwareProvider` | fail-closed boundary; no provider is connected |
| Native C++ core / C API | SWAP fixed in the hybrid engine |
| Vulkan compute primitives | software-ICD dispatch verified in this audit; no end-to-end GPU acceleration |

## 2. Fixed

- **CQ-V252-01 (P0) — Path B: `t` and `tdg` swapped.** `T = c0 I + c1 Z` used
  `c1 = (e^{i pi/4} - 1)/2`, i.e. `diag(e^{i pi/4}, 1)` = `T†` up to a global
  phase. `h t h` is symmetric and came out right; `h t s h` gave `P(0) = 0.854`
  instead of `(1 + cos 3pi/4)/2 = 0.146`, labelled `EXACT`. Found by a seeded
  differential fuzz against Qiskit `Statevector`; earlier tests only used
  circuits whose probabilities are invariant under `T ↔ T†`.
- **CQ-V252-02 (P1) — gate error vs. depolarizing parameter.** A profile's
  `gate_errors` value goes to Qiskit as `InstructionProperties.error` (average
  gate infidelity `r`), but the noise model used it as the depolarizing `p`.
  For `E(ρ) = (1 − p) ρ + p I/d` the infidelity is `p (d − 1)/d`, so the
  model's noise was `r/2` (1q) or `3r/4` (2q). Now `p = d r/(d − 1)`, the same
  conversion Qiskit Aer applies when relaxation is ignored; values above
  `(d − 1)/d` are refused rather than clipped.
- **CQ-V252-03 (P0 for native builds) — SWAP on the native tableau.**
  `HybridEngine::apply_swap` swapped the tableau and then applied three more
  CX to it through `HybridEngine::apply_cx`. In tableau mode the SWAP was the
  identity.
- **CQ-V252-04 (P2) — profile validation.** `BackendProfile` refuses float or
  bool qubit indices, T1/T2/readout entries for absent qubits, `T2 > 2 T1`,
  non-finite times, invalid gate durations, repeated qubits in a key, keys
  whose width does not match the gate, and gate errors on more than two qubits
  (previously dropped silently by the noise model).
- **CQ-V252-05 (P3) — noisy DM gate set.** `cu1`, `crx`, `cry`, `crz` run
  instead of being refused.

## 3. Tests

- `tests/test_v252_regressions.py` (13 tests). Oracles: closed forms,
  `qiskit.quantum_info.Statevector`/`DensityMatrix` and
  `average_gate_fidelity` on the produced Kraus operators. On the v2.5.1
  source 62 sub-cases and 3 tests fail; the Path A SWAP cases fail as well
  when the native module is loaded.
- `tests/test_hybrid_mps.cpp`: native SWAP in tableau and statevector mode;
  fails on the v2.5.1 source.
- Mutation harness: 24/24 mutants killed (4 new).
- Local Linux results and exact-SHA CI runs: `research/v2_5_2/TEST_MATRIX.md`.

## 4. Limits and non-claims

- `NOISY_CLASSICAL` output is a modelled distribution, not a measurement.
  `error_bound = 0.0` means no deliberate approximation of the model; it is not
  a bound on model-vs-hardware error.
- Gate errors are modelled as depolarizing noise only. T1/T2 are validated but
  not turned into relaxation channels. Circuits are not transpiled to a
  profile's basis gates, so uncalibrated gates stay noiseless.
- Both built-in profiles are synthetic. No real quantum hardware was used.
- No mid-circuit measurement, reset or classical control.
- No performance claim; no benchmark was run for this release.

## 5. Installation and smoke test

```bash
python -m pip install cqhecs-2.5.2-py3-none-any.whl
cq-hecs version
cq-hecs profile list
cq-hecs --format json run name:bell --profile fake_manila --shots 1000
```

The pure-Python wheel does not contain the native C++/Vulkan binaries. Build
those from source with CMake and a C++20 toolchain if you need them.

## 6. Evidence

- `CHANGELOG.md` — `[2.5.2]` section.
- `research/v2_5_2/` — baseline, findings, test matrix, execution log.
- The published release body records the exact source SHA and required CI run.
