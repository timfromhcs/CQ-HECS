# CQ-HECS v2.5.2 Execution Log

All times 2026-10-30 (UTC).

1. **Discovery.** Read GEMINI.md. Found `main` = `v2.5.1` = `1be682a`, no open
   PRs, and the v2.5.1 release audit (`f013407`) only on an unmerged branch.
   Cherry-picked it (`bd3de1a`).
2. **Baseline gates** on `1be682a` (BASELINE.md §4): all green. Installed
   `libvulkan-dev`, `glslang-tools`, `mesa-vulkan-drivers`, `spirv-tools` to
   build the native core.
3. **Audit of the newest code** (`hardware_bridge.py`,
   `noisy_density_matrix.py`): found CQ-V252-02 (gate error vs. depolarizing
   parameter) by computing `average_gate_fidelity` of the produced channels,
   and CQ-V252-04 by probing `BackendProfile` with invalid inputs.
4. **Differential fuzz** (all paths vs Qiskit). First run showed (a)
   artefacts of the fuzzer itself (instruction lists cannot declare idle top
   qubits; fixed by adding `id` on every qubit) and (b) Path B mismatches with
   TV ≈ 0.67. Delta-debugging reduced (b) to `h t s h`; root cause CQ-V252-01.
   After the fix a second fuzz seed showed Path A TV = 1 on `y q0; swap`;
   reduced to `x q0; swap q0,q1`; the Python tableau was right and the native
   `HybridEngine::apply_swap` applied the swap twice (CQ-V252-03).
5. **Fixes** (one targeted attempt each, no repair loop needed):
   Path B coefficient; native SWAP; `depolarizing_parameter_from_infidelity`;
   profile validation; DM controlled rotations (CQ-V252-05, found because the
   fuzz showed 48/150 DM refusals).
6. **Regression tests** written with independent oracles; checked to fail on
   the baseline (stash run, then a clean `1be682a` worktree with its own native
   build). One existing test used `crz` as its example of an unsupported gate;
   since `crz` is now supported (and verified against Qiskit), the example was
   changed to an unknown gate name. Its intent (the refusal names the gate) is
   unchanged.
7. **Mutation harness**: 4 mutants added. Mutant 24 survived its first check
   because the manifest arity check already refuses `sx` with three qubits;
   the check now uses a gate the manifest does not know, which is the case the
   width check protects. 24/24.
8. **Full local gates** (TEST_MATRIX.md §1): all green.
9. **Published v2.5.1 wheel** reproduces CQ-V252-01 and -02 in a clean venv.
10. **Version 2.5.2** on all surfaces; CHANGELOG, RELEASE_NOTES, README,
    USAGE_GUIDE, API_REFERENCE updated.
