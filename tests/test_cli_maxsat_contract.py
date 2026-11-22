"""CLI `sat maxsat` uses the typed contract: a size limit is UNKNOWN, never an optimum."""
import json
import subprocess
import sys


def _run(*args):
    fmt = []
    if "--format" in args:
        i = args.index("--format")
        fmt = ["--format", args[i + 1]]
        args = args[:i] + args[i + 2:]
    return subprocess.run(
        [sys.executable, "-m", "cqhecs.cli", *fmt, "sat", "maxsat", *args],
        capture_output=True, text=True, timeout=120,
    )


def test_small_formula_is_optimal_json():
    p = _run("--cnf", "p cnf 2 3\n1 2 0\n-1 0\n-2 0\n", "--format", "json")
    data = json.loads(p.stdout)
    assert data["status"] == "OPTIMAL"
    assert data["optimality_certificate"] is None
    assert data["assignment"] is not None


def test_over_limit_is_unknown_without_optimum():
    p = _run("--random", "30", "--seed", "1", "--format", "json")
    data = json.loads(p.stdout)
    assert data["status"] == "UNKNOWN"
    assert data["limit_reached"] is True
    assert data["assignment"] is None and data["satisfied_weight"] is None


def test_over_limit_text_does_not_crash():
    p = _run("--random", "30", "--seed", "1")
    assert p.returncode == 0
    assert "no optimum claimed" in p.stdout
