"""Opt-in smoke test for the standalone executable (set ``CQ_HECS_EXE``)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from cqhecs import __version__

ROOT = Path(__file__).resolve().parent.parent
EXE = os.environ.get("CQ_HECS_EXE")

pytestmark = pytest.mark.skipif(not EXE, reason="CQ_HECS_EXE not set")


def _run(*args, cwd=None):
    return subprocess.run(
        [EXE, *args], cwd=cwd, capture_output=True, text=True, timeout=300, check=True
    )


def test_exe_version(tmp_path):
    first_line = _run("version", cwd=tmp_path).stdout.splitlines()[0]
    assert first_line == f"cq-hecs {__version__}"


def test_exe_sat_unsat(tmp_path):
    cnf = ROOT / "benchmarks" / "sat" / "pigeonhole_6_5.cnf"
    assert "UNSAT" in _run("sat", "solve", str(cnf), cwd=tmp_path).stdout


def test_exe_runs_bell(tmp_path):
    payload = json.loads(_run("--format", "json", "run", "name:bell", "--shots", "64", cwd=tmp_path).stdout)
    assert sum(payload["result"]["counts"].values()) == 64


def test_exe_device_profiles(tmp_path):
    payload = json.loads(_run("--format", "json", "devices", cwd=tmp_path).stdout)
    assert {"iqm_garnet", "ibm_kingston", "rigetti_cepheus"} <= {d["id"] for d in payload["devices"]}
    run = json.loads(_run("--format", "json", "run", "name:bell", "--device", "iqm_garnet", "--shots", "500", cwd=tmp_path).stdout)
    assert sum(run["result"]["counts"].values()) == 500


def test_exe_plan_and_qg_plan_share_the_service_documents(tmp_path):
    plan = json.loads(_run("--format", "json", "plan", "name:bell", cwd=tmp_path).stdout)["plan"]
    analyzed = json.loads(_run("--format", "json", "analyze", "name:bell", "--explain", cwd=tmp_path).stdout)["plan"]
    assert plan == analyzed
    qg = json.loads(_run("--format", "json", "qg", "plan", "--experiment", "bmv", "--theta", "0.7", cwd=tmp_path).stdout)
    assert qg["qg_plan"]["physical_execution"] is False and len(qg["digest"]) == 64


def test_exe_doctor_reports_components(tmp_path):
    report = json.loads(_run("--format", "json", "doctor", cwd=tmp_path).stdout)
    assert "vulkan_loader" in report["components"] and set(report["backends"]) == {"A", "B", "C", "D"}
