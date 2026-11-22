"""Offline, read-only replay of the historical QG QPU evidence.

Re-derives every number in ``research/qg_2026/processed/*.json`` from the immutable raw
counts (``research/qg_2026/raw/**/result.json``) and the frozen circuits
(``research/qg_2026/qasm/**``). Nothing is written, no network or provider SDK is touched,
and no credential is read: this module only opens files for reading.

What a replay can and cannot say
--------------------------------
* It verifies *arithmetic reproducibility*: the processed correlators, standard errors,
  intervals, fractions and ideal values follow from the stored counts and circuits.
* It does not re-run any job, does not validate the hardware, and a match says nothing
  about gravity. A mismatch is reported as a finding, never silently patched.
* The raw directory is checked against its ``EVIDENCE_MANIFEST.json`` SHA-256 digests so an
  altered raw file is detected before its numbers are trusted.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

REPLAY_SCHEMA = "cqhecs.qg.replay.v1"
Z95 = 1.96
FLOAT_TOL = 1e-12


# -- small helpers (read-only) ----------------------------------------------------
def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


_TEXT_SUFFIXES = {".csv", ".md"}
CRLF = bytes([13, 10])
LF = bytes([10])


def _manifest_digest(path: Path, expected: str) -> str:
    """Digest to compare against a manifest entry.

    The evidence manifests were produced from CRLF working-tree copies of the text files, while Git
    stores (and a Linux checkout materialises) them with LF. For ``.csv``/``.md`` only, a digest of the
    CRLF-canonical form is accepted as an equivalent of the raw bytes; every content change still
    changes both digests. Binary and JSON files keep the strict raw-byte digest.
    """
    raw = _sha256(path)
    if raw == expected or path.suffix.lower() not in _TEXT_SUFFIXES:
        return raw
    lf = path.read_bytes().replace(CRLF, LF)
    canonical = lf.replace(LF, CRLF)
    alt = hashlib.sha256(canonical).hexdigest()
    return alt if alt == expected else raw


def parity_correlator(counts: Dict[str, int]) -> float:
    """``(n_even - n_odd) / N`` where parity is that of the two measured bits (bit-order independent)."""
    shots = sum(counts.values())
    if shots <= 0:
        raise ValueError("counts are empty")
    signed = sum(v if k.count("1") % 2 == 0 else -v for k, v in counts.items())
    return signed / shots


def correlator_std_err(correlator: float, shots: int) -> float:
    return math.sqrt(max(0.0, 1.0 - correlator ** 2) / shots)


def probability_std_err(p: float, shots: int) -> float:
    return math.sqrt(max(0.0, p * (1.0 - p)) / shots)


def _ideal_probabilities(qasm_path: Path) -> Dict[str, float]:
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    circuit = QuantumCircuit.from_qasm_str(qasm_path.read_text(encoding="utf-8"))
    circuit.remove_final_measurements()
    return {k: float(v) for k, v in Statevector(circuit).probabilities_dict().items()}


def _ideal_parity(qasm_path: Path) -> float:
    return sum(
        (p if k.count("1") % 2 == 0 else -p) for k, p in _ideal_probabilities(qasm_path).items()
    )


class _Report:
    def __init__(self) -> None:
        self.checks: List[Dict[str, Any]] = []
        self.findings: List[Dict[str, Any]] = []

    def numeric(self, check_id: str, processed: Optional[float], recomputed: float, tol: float = FLOAT_TOL) -> None:
        ok = processed is not None and abs(float(processed) - float(recomputed)) <= tol
        self.checks.append(
            {
                "id": check_id,
                "kind": "numeric",
                "processed": processed,
                "recomputed": recomputed,
                "abs_diff": None if processed is None else abs(float(processed) - float(recomputed)),
                "ok": bool(ok),
            }
        )

    def exact(self, check_id: str, processed: Any, recomputed: Any) -> None:
        self.checks.append(
            {"id": check_id, "kind": "exact", "processed": processed, "recomputed": recomputed,
             "ok": processed == recomputed}
        )

    def finding(self, finding_id: str, text: str) -> None:
        self.findings.append({"id": finding_id, "text": text})


class Replay:
    """Locate evidence under ``root`` (the repository root) and recompute processed numbers."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.base = self.root / "research" / "qg_2026"
        self.raw = self.base / "raw"
        self.processed = self.base / "processed"
        self.qasm = self.base / "qasm"
        self.report = _Report()

    # -- raw access --------------------------------------------------------------
    def raw_counts(self, circuit_id: str) -> Dict[str, int]:
        matches = sorted(self.raw.glob(f"*/{circuit_id}/result.json"))
        if len(matches) != 1:
            raise FileNotFoundError(f"expected one raw result for {circuit_id}, found {len(matches)}")
        return {str(k): int(v) for k, v in _load(matches[0]).items()}

    def qasm_path(self, circuit_id: str) -> Path:
        matches = sorted(self.qasm.glob(f"*/{circuit_id}.qasm"))
        if len(matches) != 1:
            raise FileNotFoundError(f"expected one QASM for {circuit_id}, found {len(matches)}")
        return matches[0]

    # -- checks ------------------------------------------------------------------
    def verify_raw_manifests(self) -> None:
        for manifest_path in sorted(self.raw.glob("*/EVIDENCE_MANIFEST.json")):
            manifest = _load(manifest_path)
            for entry in manifest["files"]:
                relative = entry["path"].replace("\\", "/")
                target = manifest_path.parent / relative
                key = f"manifest:{manifest_path.parent.name}/{relative}"
                if not target.is_file():
                    self.report.checks.append({"id": key, "kind": "manifest", "ok": False, "reason": "missing"})
                    continue
                self.report.exact(key, entry["sha256"], _manifest_digest(target, entry["sha256"]))

    def replay_bmv_qpu(self) -> None:
        data = _load(self.processed / "bmv_qpu_analysis.json")
        for circ in data["circuits"]:
            cid = circ["circuit_id"]
            counts = self.raw_counts(cid)
            shots = sum(counts.values())
            corr = parity_correlator(counts)
            se = correlator_std_err(corr, shots)
            self.report.exact(f"bmv_qpu:{cid}:counts", circ["counts"], counts)
            self.report.exact(f"bmv_qpu:{cid}:shots", circ["shots"], shots)
            self.report.numeric(f"bmv_qpu:{cid}:correlator", circ["correlator"], corr)
            self.report.numeric(f"bmv_qpu:{cid}:std_err", circ["std_err"], se)
            self.report.numeric(f"bmv_qpu:{cid}:ci95_lo", circ["ci95"][0], corr - Z95 * se)
            self.report.numeric(f"bmv_qpu:{cid}:ci95_hi", circ["ci95"][1], corr + Z95 * se)
            ideal = _ideal_parity(self.qasm_path(cid))
            self.report.numeric(f"bmv_qpu:{cid}:expected_from_qasm", circ["expected"], ideal, 1e-9)
            self.report.numeric(f"bmv_qpu:{cid}:deviation", circ["deviation"], corr - circ["expected"])

    def replay_phase_scan(self) -> None:
        data = _load(self.processed / "bmv_phase_scan.json")
        for pt in data["points"]:
            cid = pt["circuit_id"]
            counts = self.raw_counts(cid)
            shots = sum(counts.values())
            corr = parity_correlator(counts)
            self.report.numeric(f"phase_scan:{cid}:correlator", pt["correlator"], corr)
            self.report.numeric(f"phase_scan:{cid}:std_err", pt["std_err"], correlator_std_err(corr, shots))
            self.report.exact(f"phase_scan:{cid}:shots", pt["shots"], shots)
            ideal = _ideal_parity(self.qasm_path(cid))
            if pt["basis"] == "XX" and abs(pt["expected_sin"] - abs(ideal)) > 1e-6:
                self.report.finding(
                    f"R-PHASESCAN-XX:{cid}",
                    f"processed expected_sin={pt['expected_sin']:.6f} for an XX point, but the frozen circuit's "
                    f"ideal XX correlator is {ideal:.6f} (ZZ commutes with XX, so XX carries no theta "
                    "dependence); the stored 'ratio' for XX points is not a phase-recovery ratio",
                )
            else:
                self.report.numeric(f"phase_scan:{cid}:ideal_vs_expected_sin", pt["expected_sin"], abs(ideal), 1e-9)
                if pt["ratio"] is not None:
                    self.report.numeric(f"phase_scan:{cid}:ratio", pt["ratio"], corr / pt["expected_sin"])

    def replay_xx_trend(self) -> None:
        data = _load(self.processed / "bmv_xx_trend.json")
        xx_ids = [p.name for p in self.raw.glob("*/*XX") if p.is_dir()]
        by_counts = {json.dumps(self.raw_counts(cid), sort_keys=True): cid for cid in xx_ids}
        for pt in data["points"]:
            key = json.dumps({k: int(v) for k, v in pt["counts"].items()}, sort_keys=True)
            cid = by_counts.get(key)
            if cid is None:
                self.report.checks.append({"id": f"xx_trend:theta={pt['theta']:.4f}", "kind": "source",
                                           "ok": False, "reason": "no raw XX circuit has these counts"})
                continue
            counts = self.raw_counts(cid)
            shots = sum(counts.values())
            corr = parity_correlator(counts)
            se = correlator_std_err(corr, shots)
            self.report.numeric(f"xx_trend:{cid}:xx", pt["xx"], corr)
            self.report.numeric(f"xx_trend:{cid}:ci95_lo", pt["ci95"][0], corr - Z95 * se)
            self.report.numeric(f"xx_trend:{cid}:ci95_hi", pt["ci95"][1], corr + Z95 * se)

    def replay_drift(self) -> None:
        data = _load(self.processed / "final_analysis.json")
        for row in data["sections"].get("bmv_drift", []):
            basis = row["basis"]
            cid = f"bmv-drift-t2-{basis}"
            counts = self.raw_counts(cid)
            corr = parity_correlator(counts)
            original = parity_correlator(self.raw_counts(f"bmv-t2-{basis}"))
            self.report.exact(f"drift:{cid}:counts", row["counts"], counts)
            self.report.numeric(f"drift:{cid}:correlator", row["correlator"], corr)
            self.report.numeric(f"drift:{cid}:original", row["original_correlator"], original)
            self.report.numeric(f"drift:{cid}:delta", row["delta_vs_original"], corr - original)

    def replay_syk(self) -> None:
        import numpy as np

        from cqhecs.quantum_gravity.hamiltonians import build_syk
        from cqhecs.quantum_gravity.references import evolve_state, trotter_first_order

        syk = build_syk(3, seed=20260101, scale=0.4)
        psi = np.zeros(8, dtype=complex)
        psi[0] = 1.0
        p_exact = float(abs(evolve_state(syk.matrix(), 1.0, psi)[0]) ** 2)
        p_trot = float(abs(trotter_first_order(syk.hermitian_terms(), 1.0, 1, psi)[0]) ** 2)
        for name, folder, version in (("syk_qpu_analysis.json", "syk_qpu", "v1"), ("syk_qpu_v3_analysis.json", "syk_qpu_v3", "v3")):
            data = _load(self.processed / name)
            for circ in data["circuits"]:
                cid = circ["circuit_id"]
                counts = self.raw_counts(cid)
                shots = sum(counts.values())
                p = counts.get("000", 0) / shots
                se = probability_std_err(p, shots)
                self.report.exact(f"syk_{version}:{cid}:counts", circ["counts"], counts)
                self.report.numeric(f"syk_{version}:{cid}:p000", circ["p000"], p)
                self.report.numeric(f"syk_{version}:{cid}:std_err", circ["std_err"], se)
                self.report.numeric(f"syk_{version}:{cid}:ci95_lo", circ["ci95"][0], p - Z95 * se)
                self.report.numeric(f"syk_{version}:{cid}:ci95_hi", circ["ci95"][1], p + Z95 * se)
                qasm_ideal = _ideal_probabilities(self.qasm_path(cid)).get("000", 0.0)
                forward = "forward" in cid
                if version == "v3":
                    self.report.numeric(f"syk_v3:{cid}:ideal_from_qasm", circ["ideal_p000"], qasm_ideal, 1e-9)
                    if forward:
                        self.report.numeric(f"syk_v3:{cid}:ideal_is_trotter_r1", circ["ideal_p000"], p_trot, 1e-9)
                else:
                    # v1 stored the exact-exponential ideal while the hardware ran the Trotter circuit.
                    stored = circ["ideal_p000"]
                    if forward:
                        self.report.numeric(f"syk_v1:{cid}:stored_ideal_is_exact_expm", stored, p_exact, 1e-9)
                    else:
                        self.report.numeric(f"syk_v1:{cid}:stored_ideal_is_return_to_zero", stored, 1.0, 1e-12)
                    if abs(stored - qasm_ideal) > 1e-3:
                        self.report.finding(
                            f"R-SYK-V1-IDEAL:{cid}",
                            f"stored ideal_p000={stored:.6f} does not describe the submitted circuit "
                            f"(its own statevector gives {qasm_ideal:.6f}); consistent with the recorded "
                            "correction F-09 (v1 INVALID as a test of the stated model)",
                        )

    def replay_smoke(self) -> None:
        data = _load(self.processed / "qpu_smoke_analysis.json")
        for cid, row in data["circuits"].items():
            counts = self.raw_counts(cid)
            shots = sum(counts.values())
            support = sorted(k for k, v in _ideal_probabilities(self.qasm_path(cid)).items() if v > 1e-9)
            in_support = sum(v for k, v in counts.items() if k in support)
            dominant = max(counts.items(), key=lambda kv: kv[1])
            self.report.exact(f"smoke:{cid}:counts", row["counts"], counts)
            self.report.exact(f"smoke:{cid}:ideal_support", sorted(row["ideal_support"]), support)
            self.report.exact(f"smoke:{cid}:in_support_count", row["in_support_count"], in_support)
            self.report.numeric(f"smoke:{cid}:in_support_fraction", row["in_support_fraction"], in_support / shots)
            self.report.exact(f"smoke:{cid}:dominant_outcome", row["dominant_outcome"], dominant[0])
            self.report.numeric(f"smoke:{cid}:dominant_fraction", row["dominant_fraction"], dominant[1] / shots)

    # -- driver ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        self.verify_raw_manifests()
        self.replay_bmv_qpu()
        self.replay_phase_scan()
        self.replay_xx_trend()
        self.replay_drift()
        self.replay_syk()
        self.replay_smoke()
        failed = [c for c in self.report.checks if not c["ok"]]
        return {
            "schema": REPLAY_SCHEMA,
            "root": str(self.root),
            "read_only": True,
            "provider_calls": 0,
            "credentials_read": False,
            "num_checks": len(self.report.checks),
            "num_failed": len(failed),
            "all_ok": not failed,
            "failed": failed,
            "findings": self.report.findings,
            "checks": self.report.checks,
            "limitations": [
                "replay verifies arithmetic reproducibility only; it does not re-run or validate any job",
                "no statement about gravity follows from a matching replay",
            ],
        }


def replay_all(root: Path | str) -> Dict[str, Any]:
    """Convenience wrapper: replay every processed file against the raw evidence under ``root``."""
    return Replay(root).run()
