# CQ-HECS Release Notes

**Version:** 2.3.0
**Release date:** 2026-10-29
**License:** Apache 2.0
**Repository:** [https://github.com/timfromhcs/CQ-HECS](https://github.com/timfromhcs/CQ-HECS)

> The release workflow copies this file to
> `dist/RELEASE_NOTES_v2.3.0.md`, prepends the exact source commit and required
> CI run, and appends the SHA256 values of the final assets. The content
> describes the code in this tree.

---

## 1. What this release is

`v2.3.0` is a **feature release**. Standard composite gates that every path
previously refused are now executed through an exact lowering onto the native
gate set. It also repairs the nightly CI lane, adds three reference circuits,
tightens the lint gate and ships the verified Vulkan primitive-dispatch fix that
was unreleased after `v2.2.2`. It adds **no new simulator, no new exactness
claim and no end-to-end GPU acceleration**.

The four-path interface and result metadata are unchanged. The only behavioural
change is intentional: circuits containing the gates below used to raise
`UnsupportedCircuitError`; they now run.

| Surface | Status in 2.3.0 |
| :--- | :--- |
| `cqhecs` four-path router/backends | supported; composite gates lowered exactly |
| `cq_hecs::core::StateVectorSimulator` | supported dense reference, ≤ 28 qubits |
| `cq_hecs::core::MPSSimulator` | experimental CPU reference with SVD updates and seeded sampling |
| `cq_hecs::core::VulkanQpuEngine` | CPU reference facade; QASM operands limited to qubits 0–255 |
| Vulkan compute primitives | dispatch verified (state reset, CORDIC gate, Q30 contraction); fail closed on errors |
| `cqhecs::vulkan::VulkanEngine` | planner-only memory allocator |
| Legacy native QASM executor | legacy phase ledger, not a statevector simulator; keeps its smaller gate set |

## 2. Added — exact composite-gate lowering

`cqhecs/gate_lowering.py` rewrites each composite gate inside
`parse_circuit()`, so the analyzer, router and every backend see the same
primitive circuit. Every rule is an exact unitary identity, **global phase
included**:

| Gate(s) | Lowering |
| :--- | :--- |
| `u`, `u3` (θ, φ, λ) | `p(λ)`, `ry(θ)`, `p(φ)` |
| `u2` (φ, λ) | `u3(π/2, φ, λ)` |
| `sx`, `sxdg` | `h`, `s`/`sdg`, `h` |
| `cy` | `sdg(t)`, `cx`, `s(t)` |
| `ch` | `ry(t, π/4)`, `cx`, `ry(t, −π/4)` |
| `cs`, `csdg` | controlled phase ±π/2 via `p`/`cx` |
| `rzz` | `cx`, `rz(t)`, `cx`; `rxx`/`ryy` by local basis change |
| `ccx`/`toffoli` | standard 7-T Clifford+T circuit |
| `ccz` | `h(t)`, `ccx`, `h(t)` |
| `cswap`/`fredkin` | `cx`, `ccx`, `cx` |

Consequences:

- Routing uses the lowered circuit: Clifford composites (`sx`, `cy`,
  `rzz(π/2)`) still reach Path A; a Toffoli costs its real T-count.
- Wrong arity, wrong parameter count or repeated operands are refused before
  lowering with `UnsupportedCircuitInputError`.
- The Qiskit `Target` advertises the one- and two-qubit composites. Three-qubit
  gates are left to the transpiler on the linear target and are lowered when
  submitted untranspiled.
- `reset` is now the only manifest operation that no path executes.

New builtins for `cq-hecs run name:<builtin>`: `toffoli_adder` (measured CCX
full adder), `qft4` (controlled-phase QFT of a basis state) and `ising6`
(RZZ/RX Trotter steps).

## 3. Fixed

- **Nightly CI** failed at test collection since 2026-10-28 because the
  workflow did not install `hypothesis`; it now installs it like `ci.yml`.
- **`python_bridge/cli_runner.py`** annotated `Optional` without importing it.
- **Vulkan compute dispatch** (unreleased after 2.2.2): `shaderInt64` is
  enabled before device creation; command-buffer allocation, recording,
  submission and waits are checked and partial state released on errors.
- Dead locals and unused imports removed; CI lint now enforces the full
  pyflakes `F` rule set and covers `python_bridge`.

## 4. Tests

- New `tests/test_gate_lowering.py` (10 tests): every rule against Qiskit's
  reference matrix in both operand orders, Toffoli truth table, Path A routing
  of Clifford composites, a mixed composite circuit and the Qiskit provider
  (raw and transpiled) against `Statevector`.
- Contract tests that pinned the old refusal now assert execution; `reset`
  keeps the refusal contract.
- New mutant `Toffoli lowering phase error` (checks the full unitary — a
  truth-table check alone does not see control-qubit phase errors).
- Local verification on Windows 11 / Python 3.14.6 / MSVC 19.44 / Vulkan SDK
  1.4.357:
  - `python -m pytest tests/ -q` with `CQ_HECS_REQUIRE_NATIVE=1` → **377 passed**.
  - `ctest --test-dir build -C Release` → **19/19 passed**.
  - Branch coverage → **83%** (CI threshold 70%).
  - Mutation harness → **12/12 killed**, clean baseline.
  - `verify_vulkan_shaders.py` → **12/12 shaders**.
  - `check_version.py`, `verify_no_silent_truncation.py`, `twine check` → PASS.
- Exact-SHA Linux/Windows CI results are recorded in the pull request and the
  published release, not inferred from these local runs.

## 5. Limits and non-claims

- Lowering is exact as unitary algebra; execution keeps each path's numerics
  (float64 in B/C/D, Path C's `1e-13` rank floor). Decompositions add gates, so
  a Toffoli-heavy circuit raises Path B's rank and Path C's bond dimension.
- The native legacy QASM executor still rejects `u`/`u2`/`u3` and the other
  composites; only the Python stack lowers them.
- Vulkan evidence covers primitive dispatch only; no end-to-end GPU simulator
  acceleration is claimed.
- `MPSSimulator` truncation diagnostics are not a global error bound;
  `numerical_error_bound` stays `None` on Path C.
- Path C MPS-native sampling stays capped at 500 qubits; dense conversion at 20.
- Mid-circuit measurement, `reset` and classical control remain unsupported.

## 6. Installation and smoke test

```bash
python -m pip install cqhecs-2.3.0-py3-none-any.whl
cq-hecs version
cq-hecs doctor
cq-hecs --format json run name:toffoli_adder --shots 128
```

The pure-Python wheel does not contain the native C++/Vulkan binaries. Build
those from source with CMake and a C++20 toolchain if you need the native
reference paths.

## 7. Evidence

- `CHANGELOG.md` — `[2.3.0]` section.
- `docs/QASM_CONTRACT.md` §6 — native, composite and refused gate groups.
- `tests/test_gate_lowering.py` — lowering identities and end-to-end checks.
- `research/next_stable/` — earlier audit cycles (2.2.x).
- The published release body records the exact source SHA and required CI run.
