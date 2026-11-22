# Quantum Gravity Lab (campaign `qg-2026-01`)

A bounded, falsifiable Quantum Gravity **research workbench** built on CQ-HECS. It is a
model-and-evidence layer, not a claim about nature. Read
[`AGENTS.md`](../QGRAVITY.md)-style mission rules in `QGRAVITY.md` (repository root) and the
campaign record in `research/qg_2026/`.

## What it is — and is not

| It is | It is not |
|---|---|
| A reproducible study of declared finite models (BMV effective interaction, small-N SYK) | A measurement of quantum gravity |
| Each result tagged with its execution surface | A claim that a QPU coupled two masses |
| A ledger of immutable inputs, hashes and credits | A promise that a nonzero credit balance exists |

A processor running `U_ZZ(theta)` **emulates** a model. Finite-N SYK is a finite model
experiment, not a spacetime wormhole. Every value carries one of the nine
`ExecutionSurface` categories (`CLASSICAL_REFERENCE`, `CQ_HECS_CPU`, `CQ_HECS_VULKAN`,
`WEB_WASM_F64`, `WEBGPU_F32`, `OPENQUANTUM_SIMULATOR`, `OPENQUANTUM_QPU`,
`MODEL_PREDICTION`, `SYNTHETIC_OR_FIXTURE`).

## Package layout

```
cqhecs/quantum_gravity/
  catalog.py       # execution surfaces + method cards (assumptions, limits)
  models.py        # Track A: BMVEffectivePhaseModel  (qg.bmv.zz.v1)
  observables.py   # concurrence, negativity, entropy, partial trace/transpose, CHSH
  fermions.py      # Majorana algebra + Jordan-Wigner  (dense, <= 8 qubits)
  hamiltonians.py  # Track B: seeded sparse q=4 SYK    (qg.syk.q4.v1)
  references.py    # exact evolution, Loschmidt, Trotter error, OTOC
  circuits.py      # deterministic OpenQASM 2.0 + circuit manifests
  noise.py         # declared Kraus channels + finite-shot witness estimator (NOISY_CLASSICAL)
  gauge.py         # bounded Z2 lattice gauge toy model (Track C bridge)
  results.py       # cqhecs.qg.experiment.v1 experiment envelope
  errors.py        # typed refusals (QGUnsupported / QGResourceError / QGBlocker)
```

The package is imported on demand; importing `cqhecs` does not pull it in.

## Model A — BMV effective two-probe phase (`qg.bmv.zz.v1`)

`U_ZZ(theta) = exp(-i (theta/2) Z(x)Z)` on `|+>|+>`. The local-phase-invariant entangling
phase is `Phi = arg(c00 c11 conj(c01) conj(c10)) = -2*theta`; the factor 2 is *derived* from
the `Z(x)Z` eigenvalues and unit-tested. Closed-form oracles (also unit-tested):

```
concurrence C(theta) = |sin(theta)|          negativity N = C/2
entanglement S       = H2((1+sqrt(1-C^2))/2)   CHSH max = 2*sqrt(1+C^2)
```

`theta` is a model parameter — **not** a physical mass or separation. The tests validate
the model against a dense SciPy matrix exponential and (when Qiskit is installed) an
independent Qiskit Statevector.

## Model B — small-N sparse q=4 SYK (`qg.syk.q4.v1`)

`H = sum J_{ijkl} gamma_i gamma_j gamma_k gamma_l`, seeded Gaussian couplings, optional
seeded sparsification. The Majorana algebra `{gamma_i, gamma_j}=2 delta_ij I`, Hermiticity,
fermion-parity commutation and the spectrum are checked against independent oracles (a
dense Majorana-matrix product and Qiskit `SparsePauliOp`). Dense construction is capped at
8 qubits (dim 256); larger widths raise `QGResourceError` instead of allocating.

## Local API + MCP (no network, no spend)

Studio routes (loopback + bearer token, `127.0.0.1` only):

```
GET  /api/qg/v1/health            GET  /api/qg/v1/catalog            GET  /api/qg/v1/models
POST /api/qg/v1/experiments/validate
POST /api/qg/v1/experiments/preview       # QASM + SHA-256, spend = 0
POST /api/qg/v1/experiments/run-local     # exact CLASSICAL_REFERENCE run
```

MCP tools (stdio JSON-RPC, `cqhecs/mcp_server.py`):

`cqhecs_qg_catalog`, `cqhecs_qg_circuit_preview`, `cqhecs_qg_run_local` — all local; none
contacts Open Quantum or spends credits.

## Running it

```
# local CLI (no network, no credentials)
cq-hecs qg catalog
cq-hecs qg preview --theta 0.5
cq-hecs qg run-local --theta 1.5707963267948966
cq-hecs --format json qg run-local --theta 0.5

# offline, deterministic, no credentials
python scripts/run_qg_openquantum_campaign.py generate
python scripts/run_qg_openquantum_campaign.py validate

# read-only account check (proves auth without printing secrets)
python scripts/run_qg_openquantum_campaign.py doctor
python scripts/run_qg_openquantum_campaign.py discover --org <organisation-uuid>

# quote and submit a preregistered circuit set (set dir holds MANIFEST.json; --oq is oq.py)
python scripts/run_qg_openquantum_campaign.py quote  --backend rigetti:cepheus-1-108q \
       --set research/qg_2026/qasm/qpu_smoke --shots 1000 --oq <path-to-oq.py>
python scripts/run_qg_openquantum_campaign.py submit --budget 25 --yes --oq <path-to-oq.py>
python scripts/run_qg_openquantum_campaign.py collect --oq <path-to-oq.py>
```

`quote` spends nothing; `submit` enforces the cumulative 25-Spark ceiling itself and refuses
without `--yes`.

### Credentials (never committed)

An Open Quantum SDK key is a **Client ID** (`s_<uuid>`) **plus a Client Secret**. Set both
in the environment only:

```powershell
$env:OPENQUANTUM_CLIENT_ID    = "s_..."
$env:OPENQUANTUM_CLIENT_SECRET = "..."   # never commit, never paste into a prompt or log
```

## Spend policy (hard)

- Cumulative ceiling **25 Spark credits**, enforced in the runner, not only in the SDK.
- `execution_plan="public"`, `queue_priority="standard"` forced; the Full-credit plan is
  refused.
- `quote` never spends; `submit` requires a resolved account and a valid quote.
- `auto_approve_quote` is left `False`.

## Tests

```
python -m pytest tests/test_quantum_gravity_bmv.py tests/test_quantum_gravity_syk.py \
                 tests/test_quantum_gravity_contracts.py tests/test_quantum_gravity_campaign.py -q
```

## Wave B2 additions (model audit, Trotter oracle, leakage, plan parity, replay)

All values below are finite-model quantities. None measures gravity, a wormhole or a graviton.

| Module | Purpose | Tests |
|---|---|---|
| `cqhecs.quantum_gravity.bmv_competing` | branch-phase parameterisation, competing state-preparation predictions, separable null controls, Wootters oracle, fidelity witness; refuses a physical `theta` mapping | `tests/test_qg_bmv_competing.py` |
| `cqhecs.quantum_gravity.syk_trotter` | SYK Pauli terms, Trotter QASM compiler, mirror circuit, dense `expm` oracle, closed-form first-order commutator bound table | `tests/test_qg_syk_trotter.py` |
| `cqhecs.quantum_gravity.gauge` (leakage) | Gauss-law constraint leakage `1 - Tr[P_phys rho]`, per-vertex violation profile, gauge-breaking and gauge-preserving perturbation controls | `tests/test_qg_gauge_leakage.py` |
| `cqhecs.quantum_gravity.plan` | QG experiments get the generic `cqhecs.execution_plan/1` plan unchanged, plus engine, precision, surface and provenance; never plans a QPU job | `tests/test_qg_execution_plan.py` |
| `cqhecs.quantum_gravity.replay` | read-only offline replay of `research/qg_2026/processed/*` from raw counts and frozen QASM; SHA-256 manifest check | `tests/test_qg_replay.py` |

Notes: `research/qg_2026/BMV_MODEL_NOTES.md`; frozen tables under `research/qg_2026/models/`.

Plan parity scope: the Python module is done. CLI, MCP and Studio exposure of the QG plan envelope
is not wired in this wave (those files belong to other owners); see the wave B2 evidence file.

```
python -m pytest tests/test_qg_bmv_competing.py tests/test_qg_syk_trotter.py tests/test_qg_gauge_leakage.py \
                 tests/test_qg_execution_plan.py tests/test_qg_replay.py -q
```
