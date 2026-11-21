# EVIDENCE_LEDGER.md

Immutable evidence index. Every row: kind, path, digest, source classification, notes.
Digests for generated manifests are written by the runner at generation time.

| Evidence | Path | SHA-256 | Class | Notes |
|---|---|---|---|---|
| Baseline recon | `research/qg_2026/BASELINE.md` | n/a (doc) | n/a | session-1 facts |
| Circuit manifest | `research/qg_2026/qasm/CIRCUIT_MANIFEST.json` | `2607ADE156C00BB67350721862EAA2D7D285741FEA135316D4CC6D61424EC285` | MODEL_PREDICTION | 6 BMV circuits, deterministic |
| Model manifest | `research/qg_2026/MODEL_MANIFEST.json` | `AC3E1065D544DA2E85A715216035316AB2975C2D96345E96DCBD42CD68C276BD` | MODEL_PREDICTION | BMV + SYK model cards, deterministic |
| BMV oracle tests | `tests/test_quantum_gravity_bmv.py` | (see git) | CLASSICAL_REFERENCE | exact dense + Qiskit oracle |
| SYK oracle tests | `tests/test_quantum_gravity_syk.py` | (see git) | CLASSICAL_REFERENCE | Majorana + Qiskit oracle |
| Contract tests | `tests/test_quantum_gravity_contracts.py` | (see git) | SYNTHETIC_OR_FIXTURE | schema/observable/qasm contracts |
| Campaign runner tests | `tests/test_quantum_gravity_campaign.py` | (see git) | SYNTHETIC_OR_FIXTURE | generate/validate/gating |
| Open Quantum probe | session log (not stored) | n/a | n/a | 401 with Client-ID-as-token; **0 credits spent** |

No `OPENQUANTUM_QPU` or `OPENQUANTUM_SIMULATOR` evidence exists yet (blocker B-1).
Historical `research/v3/evidence/openquantum/**` remains untouched and is **not** part of
this ledger.

## Regenerating the manifests

```
python scripts/run_qg_openquantum_campaign.py generate
python scripts/run_qg_openquantum_campaign.py validate
```
