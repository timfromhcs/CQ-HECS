# CQ-HECS Architecture (v2)

> This document describes the architecture that v2.2.2 actually ships. It
> replaces an earlier aspirational "VRTS-300" specification whose bit-exact
> Z(2^32) CORDIC phase ring and GPU VRAM accounting are not part of the
> supported Python contract; the shipped native core does expose a 6x5x10
> lattice engine, but no physical GPU acceleration is verified. The canonical,
> regularly maintained architecture overview lives in the repository root at
> [`ARCHITECTURE.md`](../ARCHITECTURE.md).

## What the system actually consists of

| Layer | Component | Where | Notes |
| :--- | :--- | :--- | :--- |
| Parser / IR | Shared circuit parser and named-circuit library | `cqhecs/circuit_parsing.py`, `cqhecs/circuit_library.py` | one parser for all four Python paths; no `eval`, no silent fallbacks |
| Router | Capability-first four-path router | `cqhecs/router.py`, `cqhecs/circuit_analyzer.py` | fail-closed: forced paths never silently reroute; unknown inputs raise |
| Path A | Stabilizer tableau | `cqhecs/backends/path_a_stabilizer.py` | exact GF(2) symplectic arithmetic; Clifford gates only |
| Path B | Stabilizer-rank decomposition | `cqhecs/backends/path_b_stabilizer_rank.py` | algebraically exact expansion; float64 evaluation; dense evaluation is bounded by a documented 22-qubit ceiling |
| Path C | Exact MPS tensor chain | `cqhecs/backends/path_c_mps_exact.py` | untruncated bond dimension; rank selection uses a relative roundoff floor; private scratch dirs; dense statevector conversion capped at 20 qubits; MPS-native sampling capped at 500 qubits and subject to the RAM/shots budgets |
| Path D | Sparse-Pauli (Heisenberg) dynamics | `cqhecs/backends/path_d_sparse_pauli.py` | certified bound on requested observables (⟨Z_q⟩, ⟨Z_q Z_r⟩); joint counts opt-in and labelled |
| Result contract | `SimulationResult` | `cqhecs/result.py` | separates deliberate approximation, float roundoff and finite-shot sampling error; status enum (SUCCESS / UNRESOLVED / FAILED) |
| Qiskit integration | BackendV2 + provider | `cqhecs/backend.py`, `cqhecs/provider.py` | reports the real package version; classical-bit mapping verified against Aer |
| CLI | `cq-hecs` | `cqhecs/cli.py` | `version`, `doctor`, `backend list`, `analyze`, `run`, `verify`, `benchmark smoke` with a strict JSON contract |
| Native core | C++20 engine + shaders | `src/`, `shaders/`, `include/cq_hecs_api.h` | stabilizer tableau engine, exact ring module (`src/algebra/ring.cpp` with `test_exact_ring`), Vulkan 1.3 compute shaders; built via CMake, exercised with CTest |
| Legacy bridge | `python_bridge/` | historical reference model + ARX/SAT modules | not the supported entry point; `cq-hecs` is |

## Verification levels (what we claim, per level)

| Level | Meaning | Status in this cycle |
| :--- | :--- | :--- |
| CPU Python paths | verified against Qiskit Statevector/Aer/Stim oracles | verified |
| Native engine (CPU) | exercised through the bridge and native tests | verified in local suite + CI |
| Shader compilation | SPIR-V validation in CI | verified (compilation ≠ acceleration) |
| Software Vulkan (Lavapipe) | CI subsystem tier | verified in CI contexts, depends on runner |
| Vulkan loader | device enumeration | verified on the dev machine |
| Physical GPU compute dispatch | actual dispatch on disswcrete/integrated GPU | **not verified in this cycle** — no acceleration claim is made |

## Cross-cutting guarantees

1. Every subtle approximation is reported: no silent truncation; a
   `discarded_spectral_mass_diagnostic` exists where a certified bound is not
   yet derivable (Path C), and `numerical_error_bound = None` instead of an
   invented number.
2. Every error bound names what metric it covers (see
   `research/v2/FORMALIZATION_STATUS.md` for each proof's status).
3. Unsupported operations raise typed errors before execution; nothing falls
   through as identity.
4. The finite-shot confidence bound is support-size aware (Weissman et al.,
   2003) and never presented as a bound on other metrics.
