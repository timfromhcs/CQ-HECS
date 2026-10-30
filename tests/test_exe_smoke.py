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
    assert _run("version", cwd=tmp_path).stdout.strip().endswith(__version__)


def test_exe_sat_unsat(tmp_path):
    cnf = ROOT / "benchmarks" / "sat" / "pigeonhole_6_5.cnf"
    assert "UNSAT" in _run("sat", "solve", str(cnf), cwd=tmp_path).stdout


def test_exe_runs_bell(tmp_path):
    payload = json.loads(_run("--format", "json", "run", "name:bell", "--shots", "64", cwd=tmp_path).stdout)
    assert sum(payload["result"]["counts"].values()) == 64
