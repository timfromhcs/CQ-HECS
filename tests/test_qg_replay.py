"""Offline replay of the historical QG QPU evidence: reproduces processed numbers, read-only."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from cqhecs.quantum_gravity import replay as replay_mod
from cqhecs.quantum_gravity.replay import (
    REPLAY_SCHEMA,
    Replay,
    correlator_std_err,
    parity_correlator,
    probability_std_err,
    replay_all,
)

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "research" / "qg_2026"


@pytest.fixture(scope="module")
def report():
    return replay_all(ROOT)


def _tree_digest(*dirs: Path) -> str:
    digest = hashlib.sha256()
    for directory in dirs:
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def test_every_processed_number_is_reproduced_from_raw_counts(report):
    assert report["schema"] == REPLAY_SCHEMA
    assert report["num_failed"] == 0, report["failed"][:5]
    assert report["all_ok"] is True
    assert report["num_checks"] > 300


def test_replay_covers_every_processed_family(report):
    ids = [c["id"] for c in report["checks"]]
    for prefix in ("manifest:", "bmv_qpu:", "phase_scan:", "xx_trend:", "drift:", "syk_v1:", "syk_v3:", "smoke:"):
        assert any(i.startswith(prefix) for i in ids), prefix


def test_replay_is_read_only_and_makes_no_provider_calls():
    before = _tree_digest(BASE / "raw", BASE / "processed", BASE / "qasm")
    report = replay_all(ROOT)
    after = _tree_digest(BASE / "raw", BASE / "processed", BASE / "qasm")
    assert before == after
    assert report["read_only"] is True and report["provider_calls"] == 0
    assert report["credentials_read"] is False
    source = Path(replay_mod.__file__).read_text(encoding="utf-8")
    for banned in ("openquantum", "requests", "urllib", "socket", "os.environ", "JOB_LEDGER", "open(\"w"):
        assert banned not in source, banned
    assert "write_text" not in source and "write_bytes" not in source


def test_replay_surfaces_documented_historical_findings(report):
    ids = {f["id"] for f in report["findings"]}
    # v1 SYK ideals described the exact exponential, not the submitted Trotter circuit (F-09)
    assert "R-SYK-V1-IDEAL:syk-forward" in ids and "R-SYK-V1-IDEAL:syk-mirror" in ids
    # processed XX points compare against sin(theta) although ZZ commutes with XX (ideal XX = 1)
    assert any(i.startswith("R-PHASESCAN-XX:") for i in ids)


def test_v3_forward_ideal_is_the_trotter_value_and_v1_ideal_is_exact_expm(report):
    by_id = {c["id"]: c for c in report["checks"]}
    assert by_id["syk_v3:syk-forward-v3:ideal_is_trotter_r1"]["ok"]
    assert by_id["syk_v1:syk-forward:stored_ideal_is_exact_expm"]["ok"]
    assert by_id["syk_v1:syk-forward:stored_ideal_is_exact_expm"]["recomputed"] == pytest.approx(0.4280170238029712, abs=1e-9)
    assert by_id["syk_v3:syk-forward-v3:ideal_is_trotter_r1"]["recomputed"] == pytest.approx(0.23258429030050012, abs=1e-9)


def test_estimator_helpers_against_hand_values():
    assert parity_correlator({"00": 750, "11": 159, "01": 50, "10": 41}) == pytest.approx(0.818)
    assert parity_correlator({"00": 1}) == 1.0
    assert parity_correlator({"01": 3, "10": 1}) == -1.0
    assert correlator_std_err(0.0, 100) == pytest.approx(0.1)
    assert probability_std_err(0.5, 100) == pytest.approx(0.05)
    with pytest.raises(ValueError):
        parity_correlator({})


def _mini_tree(tmp_path: Path) -> Path:
    """A copy of processed/qasm and each raw result.json + manifest (calibration blobs skipped)."""
    dest = tmp_path / "research" / "qg_2026"
    shutil.copytree(BASE / "processed", dest / "processed")
    shutil.copytree(BASE / "qasm", dest / "qasm")
    for src in (BASE / "raw").glob("*/*/result.json"):
        target = dest / "raw" / src.relative_to(BASE / "raw")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    for src in (BASE / "raw").glob("*/EVIDENCE_MANIFEST.json"):
        shutil.copy2(src, dest / "raw" / src.relative_to(BASE / "raw"))
    return tmp_path


def test_altered_raw_counts_are_detected(tmp_path):
    root = _mini_tree(tmp_path)
    target = root / "research" / "qg_2026" / "raw" / "bmv_qpu" / "bmv-t1-YZ" / "result.json"
    counts = json.loads(target.read_text(encoding="utf-8"))
    first = sorted(counts)[0]
    counts[first] += 1
    target.write_text(json.dumps(counts), encoding="utf-8")
    report = replay_all(root)
    failed = {c["id"] for c in report["failed"]}
    assert "bmv_qpu:bmv-t1-YZ:counts" in failed
    assert "bmv_qpu:bmv-t1-YZ:correlator" in failed
    assert report["all_ok"] is False


def test_altered_processed_number_is_detected(tmp_path):
    root = _mini_tree(tmp_path)
    path = root / "research" / "qg_2026" / "processed" / "syk_qpu_v3_analysis.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["circuits"][1]["p000"] = 0.5
    path.write_text(json.dumps(data), encoding="utf-8")
    failed = {c["id"] for c in replay_all(root)["failed"]}
    assert "syk_v3:syk-mirror-v3:p000" in failed


def test_manifest_digest_mismatch_is_detected(tmp_path):
    root = _mini_tree(tmp_path)
    path = root / "research" / "qg_2026" / "raw" / "bmv_qpu" / "bmv-t0-XX" / "result.json"
    path.write_text(path.read_text(encoding="utf-8").replace("976", "975"), encoding="utf-8")
    failed = {c["id"] for c in replay_all(root)["failed"]}
    assert any(i.startswith("manifest:bmv_qpu/bmv-t0-XX") and i.endswith("result.json") for i in failed)


def test_missing_raw_circuit_raises_instead_of_passing(tmp_path):
    root = _mini_tree(tmp_path)
    shutil.rmtree(root / "research" / "qg_2026" / "raw" / "bmv_qpu" / "bmv-t2-XX")
    with pytest.raises(FileNotFoundError):
        Replay(root).replay_bmv_qpu()


def test_report_limitations_forbid_gravity_inference(report):
    text = " ".join(report["limitations"]).lower()
    assert "does not re-run" in text and "no statement about gravity" in text


def _copy_tree(tmp_path: Path) -> Path:
    shutil.copytree(BASE, tmp_path / "research" / "qg_2026")
    return tmp_path


def test_manifest_digests_are_line_ending_independent_for_csv_and_md(tmp_path):
    """A Linux checkout materialises the CSV/MD evidence with LF; the manifests hash the CRLF form."""
    root = _copy_tree(tmp_path)
    for path in (root / "research" / "qg_2026").rglob("*"):
        if path.suffix in {".csv", ".md"} and path.is_file():
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    assert replay_all(root)["num_failed"] == 0


def test_manifest_still_detects_a_changed_csv_regardless_of_line_endings(tmp_path):
    root = _copy_tree(tmp_path)
    target = next((root / "research" / "qg_2026" / "raw").rglob("counts.csv"))
    target.write_bytes(target.read_bytes().replace(b"\r\n", b"\n") + b"tampered\n")
    failed = replay_all(root)["failed"]
    assert any(c["id"].startswith("manifest:") and c["id"].endswith("counts.csv") for c in failed)
