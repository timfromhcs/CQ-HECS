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
| **QPU smoke raw counts** | `research/qg_2026/raw/qpu_smoke/*/counts.csv` | manifest `EVIDENCE_MANIFEST.json` | **OPENQUANTUM_QPU** | Rigetti Cepheus-1-108q, 1000 shots, real hardware |
| QPU calibration snapshot | `research/qg_2026/raw/qpu_smoke/*/calibration.json` | `DDF76F4C…615E7F` (all 4 identical) | OPENQUANTUM_QPU | device calibration at run time |
| QPU smoke analysis | `research/qg_2026/processed/qpu_smoke_analysis.json` | (see file) | OPENQUANTUM_QPU | in-support fractions |
| QPU job ledger | `research/qg_2026/JOB_LEDGER.jsonl` | append-only | n/a | 4 submitted + collected |
| QPU run manifest | `research/qg_2026/raw/qpu_smoke/EVIDENCE_MANIFEST.json` | 24 files | OPENQUANTUM_QPU | SHA-256 per artifact |
| **BMV QPU raw counts** | `research/qg_2026/raw/bmv_qpu/*/result.json` | `EVIDENCE_MANIFEST.json` (54 files) | **OPENQUANTUM_QPU** | 9 circuits, 1000 shots, Rigetti |
| BMV QPU analysis | `research/qg_2026/processed/bmv_qpu_analysis.json` | (see file) | OPENQUANTUM_QPU | correlators + 95% intervals |
| BMV phase-scan raw | `research/qg_2026/raw/bmv_scan2/*/result.json` | `EVIDENCE_MANIFEST.json` (24 files) | **OPENQUANTUM_QPU** | 4 circuits (θ=π/8, 3π/8) |
| BMV phase-scan (combined) | `research/qg_2026/processed/bmv_phase_scan.json` | (see file) | OPENQUANTUM_QPU | 13 points, 5 θ values |
| SYK QPU v3 raw | `research/qg_2026/raw/syk_qpu_v3/*/result.json` | `EVIDENCE_MANIFEST.json` (12 files) | **OPENQUANTUM_QPU** | corrected; mirror 0.947, forward 0.118 |
| SYK QPU v3 analysis | `research/qg_2026/processed/syk_qpu_v3_analysis.json` | (see file) | OPENQUANTUM_QPU | INCONCLUSIVE (F-10) |
| SYK QPU v1 (INVALID) | `research/qg_2026/raw/syk_qpu/*/result.json` | `EVIDENCE_MANIFEST.json` (12 files) | OPENQUANTUM_QPU | invalid design (F-09), retained |

No `OPENQUANTUM_QPU` or `OPENQUANTUM_SIMULATOR` evidence exists yet (blocker B-1).
Historical `research/v3/evidence/openquantum/**` remains untouched and is **not** part of
this ledger.

## Regenerating the manifests

```
python scripts/run_qg_openquantum_campaign.py generate
python scripts/run_qg_openquantum_campaign.py validate
```
