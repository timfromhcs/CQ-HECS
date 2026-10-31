"""Optional LRAT check with CakeML's cake_lpr.

The proof fixture is committed under ``research/v6/evidence/drat``. The test is
skipped unless ``CQ_CAKE_LPR`` points at a cake_lpr binary. CI or a release audit
can provide a pinned, CakeML-verified checker without making it a runtime
dependency.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CNF = ROOT / "benchmarks" / "sat" / "pigeonhole_6_5.cnf"
LRAT = ROOT / "research" / "v6" / "evidence" / "drat" / "pigeonhole_6_5.cadical.lrat"


@pytest.mark.skipif(not os.environ.get("CQ_CAKE_LPR"), reason="set CQ_CAKE_LPR to a cake_lpr binary")
def test_cakeml_verified_checker_accepts_the_lrat_proof():
    completed = subprocess.run(
        [os.environ["CQ_CAKE_LPR"], str(CNF), str(LRAT)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    assert "VERIFIED UNSAT" in completed.stdout


@pytest.mark.skipif(not os.environ.get("CQ_LRAT_CHECK"), reason="set CQ_LRAT_CHECK to an lrat-check binary")
def test_independent_lrat_checker_accepts_the_lrat_proof():
    completed = subprocess.run(
        [os.environ["CQ_LRAT_CHECK"], str(CNF), str(LRAT)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    assert "VERIFIED" in completed.stdout
