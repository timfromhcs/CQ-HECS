# QPU_SMOKE.md — preregistered Open Quantum QPU smoke suite (Stage 2)

Campaign `qg-2026-01`. Frozen before any paid submission.

## Purpose
Validate, on a real QPU, the transport, bit order, measurement registers, entangling-gate
lowering and return-to-zero behaviour of the Open Quantum path — the gate the mission
requires before any BMV/SYK paid run. This is a **platform smoke test**; it makes no
scientific claim about gravity.

## Frozen inputs
Circuit files: `research/qg_2026/qasm/qpu_smoke/`.

| circuit_id | file | SHA-256 |
|---|---|---|
| qg-smoke-basis | `qg-smoke-basis.qasm` | `42dd5720f4c184fb4c7eed4a2b25bd6dae05ec50186697e215a24f316eb46cb2` |
| qg-smoke-bell | `qg-smoke-bell.qasm` | `3d3233edbee4eae1236032ac03b07e15e28b9c35eeced43612452c68f9264a94` |
| qg-smoke-ghz3 | `qg-smoke-ghz3.qasm` | `180e22170a49ea2469541ff3a9494f14ab9f98b8c90ad193130db09ec56aa409` |
| qg-smoke-mirror | `qg-smoke-mirror.qasm` | `c2e39dc4b91ac70fd5b3813dc9e4b0be270c7f15c60f2c3e391d89600e3fc8b4` |
| manifest | `MANIFEST.json` | `7b27005116556cd93f878f588fee88f7c00bf92b74b0f478b3a3b7c856373aad` |

## Declared parameters
- Backend: **`rigetti:cepheus-1-108q`** (live type `QPU`), cheapest Public/Standard candidate.
- Shots: **1000** per circuit.
- Plan/priority: **Public Plan / Standard Queue** (Spark-eligible; never Full/Private/Priority).
- Subcategory: `phys:oth`.
- Frozen quote ledger: `research/qg_2026/QUOTE_LEDGER.json` — **4 credits total** (1 per circuit).

## Preregistered expectations and analysis
| circuit | ideal prediction |
|---|---|
| basis | a single deterministic bitstring (records the platform bit order) |
| bell | two complementary bitstrings, each ~50% |
| ghz3 | all-zero and all-one, each ~50% |
| mirror | the all-zero string, deterministically |

Analysis (no tuning): report raw counts and totals; compare to the ideal above; classify any
deviation as noise/bit-order/transpilation. Acceptance: each circuit returns the ideal support
(or its bit-swapped equivalent) with counts summing to shots; the mirror returns all-zero.

## Budget and stop rule
- Authorised ceiling: **25 Spark**. Proposed spend: **4** (16% of ceiling). Full credits: **0**.
- Stop if any quote is not Public/Standard, if cumulative spend would exceed 25, or if the
  backend is not a live `QPU`.

## Non-claims
A QPU running these circuits demonstrates platform behaviour only. No quantum-gravity,
graviton or spacetime claim.
