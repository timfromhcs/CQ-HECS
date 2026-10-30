"""Measured device profiles: extraction, M-FIT-2 equivalence, surfaces."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from cqhecs.device_profiles import (
    UnknownDeviceProfileError,
    get_profile,
    list_profiles,
    noise_model,
    readout_for,
)
from cqhecs.noise_fit import fit_profile
from cqhecs.openquantum_suite import build_suite, simulate

ROOT = Path(__file__).resolve().parent.parent


def test_bundled_file_is_current_and_mirrored_to_the_web():
    result = subprocess.run(
        [sys.executable, "scripts/export_device_profiles.py", "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    packaged = (ROOT / "cqhecs/studio/data/device_profiles.json").read_text("utf-8")
    assert (ROOT / "web/public/device_profiles.json").read_text("utf-8") == packaged


def test_every_profile_is_physical_and_evidenced():
    profiles = list_profiles()
    assert {"rigetti_cepheus", "ibm_fez", "ibm_kingston", "ibm_marrakesh"} <= {p["id"] for p in profiles}
    for p in profiles:
        assert p["measured_qubits"] == len(p["p01"]) == len(p["p10"]) == len(p["x_bitflip"])
        assert all(0.0 <= v <= 0.5 for v in p["p01"] + p["p10"])
        assert 0.0 <= p["cx_depolarizing"] <= 1.0
        assert (ROOT / p["evidence"] / "m_fit_2_profile.json").is_file()
        assert p["validation"]["h_v3_8"] in ("SUPPORTED", "REJECTED", "INCONCLUSIVE")


@pytest.mark.parametrize("profile_id", ["rigetti_cepheus", "ibm_kingston"])
def test_profile_model_reproduces_the_scored_m_fit_2(profile_id):
    # On the suite circuits the profile must give the same distribution as the
    # M-FIT-2 model the evaluation scored (up to the 6-digit rounding in the file).
    profile = get_profile(profile_id)
    fitted, _ = fit_profile(ROOT / profile["evidence"])
    for job in build_suite():
        if job.num_qubits > profile["measured_qubits"] or job.job_id not in ("OQ-06", "OQ-09", "OQ-13", "OQ-21"):
            continue
        ours = simulate(job, noise_model(profile_id, job.instructions(), job.num_qubits))
        theirs = simulate(job, fitted.noise_model(job))
        assert 0.5 * np.abs(ours - theirs).sum() < 1e-4, job.job_id


def test_extrapolation_beyond_measured_qubits_is_explicit():
    profile = get_profile("rigetti_cepheus")
    ro = readout_for(profile, 8)
    assert ro["extrapolated_qubits"] == [5, 6, 7]
    assert ro["p01"][7] == pytest.approx(sum(profile["p01"]) / 5)
    assert ro["x_bitflip"][7] == 0.0  # anomalies are not copied to unmeasured qubits


def test_unknown_profile_is_refused():
    with pytest.raises(UnknownDeviceProfileError):
        get_profile("nope")


def test_cli_devices_and_run_with_device():
    out = subprocess.run(
        [sys.executable, "-m", "cqhecs.cli", "--format", "json", "devices"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    ids = {d["id"] for d in json.loads(out.stdout)["devices"]}
    assert "ibm_fez" in ids
    run = subprocess.run(
        [sys.executable, "-m", "cqhecs.cli", "--format", "json", "run", "name:bell",
         "--device", "rigetti_cepheus", "--shots", "4000"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    counts = json.loads(run.stdout)["result"]["counts"]
    # Rigetti readout makes the "impossible" Bell outcomes clearly visible.
    assert counts.get("01", 0) + counts.get("10", 0) > 100
