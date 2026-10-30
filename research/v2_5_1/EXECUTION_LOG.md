# CQ-HECS v2.5.1 Execution Log

## 1. Discovery (2026-10-30)

- Read `GEMINI.md`. `main` = `a94ffb8`; `v2.5.0` released from `bd2a114`;
  CI on `a94ffb8` green; no open PRs; clean working tree.
- Compared the v2.5 research records with git and GitHub: the candidate SHA in
  `research/v2_5/RELEASE_AUDIT.md` does not exist (CQ-V251-06).
- Re-hashed the four published v2.5.0 assets; all match.

## 2. Baseline on this machine

- First Python run without a native build: 398 passed, 54 skipped (not a valid
  baseline because native tests skip). Installed `libvulkan-dev`,
  `glslang-tools`, `mesa-vulkan-drivers` (CI's package list), built with Ninja:
  CTest 19/19, then `CQ_HECS_REQUIRE_NATIVE=1` suite 452 passed, coverage 84 %.

## 3. Audit of the v2.5.0 feature (Loop A)

- Probed `NoisyDensityMatrixBackend` with asymmetric circuits: X on qubit 0
  rendered `10` (Qiskit `01`) → CQ-V251-01. Confirmed end to end through the
  CLI and with the published wheel.
- Partial measurement reported all qubits; mid-circuit measure from an
  instruction list dropped; `rx` without angle → identity; bool/float shots
  accepted → CQ-V251-02, -05.
- Compared `fake_manila` with `props_manila.json` from qiskit-ibm-runtime
  0.40.1 (downloaded wheel, read with `python -I`, not installed): values
  differ → CQ-V251-03.
- Existing Aer parity test: Bell circuit, identical noise on both qubits —
  insensitive to mirroring.

## 4. Fixes

1. Bit order, measurement marginal, mid-circuit refusal, argument and arity
   validation in `cqhecs/backends/noisy_density_matrix.py`.
2. Wrote `tests/test_noisy_density_matrix_contract.py` with an independent
   oracle (Qiskit `DensityMatrix`, `qiskit_aer.noise` channels, readout from
   its definition).
3. First differential run after fix 1 still failed (max deviation 0.057):
   diagnosed as noise keyed on lowered gate names (`sx` → `h s h`) →
   CQ-V251-04. Added `parse_source_circuit()` and per-instruction lowering.
   Second run: all pass. (Attempt count for this root cause: 1.)
4. A test bug (measuring qubit 2 into clbit 1, which `parse_circuit` correctly
   rejects) was fixed in the test, not in the product.
5. `fake_manila` marked synthetic; provenance rule in `BackendProfile`.
6. CLI usage errors for unknown profile / topology violation.
7. Re-ran the new test file against an untouched `a94ffb8` worktree: 60 failed,
   10 passed — the tests detect the shipped defects.
8. Four new source mutants; harness 20/20 killed.
9. Version 2.5.1 on all surfaces (`check_version.py` PASS); native rebuilt.

## 5. Candidate local gates

See TEST_MATRIX.md §1: 470 passed with native required, 19/19 CTest, 85 %
coverage, 20/20 mutants, lint/compile/truncation/version PASS, wheel and sdist
build, `twine check` PASS, clean-venv smoke PASS.

## 6. Not done here

- Merge, tag and release need the repository owner's go-ahead; this session
  stops at a pushed branch / pull request.
- No benchmarks (no performance claim). No real QPU (no authorization).
