"""W12: calibration v3 policy (refuse | warn | ideal) and provenance on the noisy-run path.

CLI ``run --calibration``, MCP ``cqhecs_run`` and Studio ``/api/simulate`` all go through
``service.run_with_calibration``. v1/v2 profile files are accepted unchanged and never rewritten.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cqhecs import service
from cqhecs.calibration_v3 import CalibrationV3
from cqhecs.cli import main as cli_main
from cqhecs.hardware_bridge import FakeHardwareBackend, create_fake_manila_profile
from cqhecs.mcp_server import handle
from cqhecs.studio import StudioState
from cqhecs.studio.app import StudioError

ROOT = Path(__file__).resolve().parent.parent

COVERED = (
    'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
    "rz(0.3) q[0];\nx q[0];\ncx q[0],q[1];\nmeasure q -> c;\n"
)
UNCOVERED = COVERED.replace("x q[0];", "h q[0];")  # fake_manila has no calibrated h channel


def _v3(max_age_hours=24, label=None):
    return CalibrationV3.from_profile(
        create_fake_manila_profile(), provenance_label=label, max_age_hours=max_age_hours
    ).to_dict()


def test_covered_circuit_reports_label_and_freshness_never_assumed_fresh():
    result, info = service.run_with_calibration(COVERED, _v3(), policy="refuse", shots=64)
    assert info["provenance_label"] == "synthetic"
    assert info["freshness"]["status"] == "unknown"  # no capture timestamp: never defaulted to fresh
    assert info["gate_coverage"]["uncovered_gates"] == []
    assert result.metadata["calibration_v3"] == info
    assert result.execution_mode.value == "NOISY_CLASSICAL" and result.is_real_hardware is False


def test_refuse_policy_is_a_typed_error_before_any_simulation(monkeypatch):
    import cqhecs.hardware_bridge as hb

    def boom(*a, **k):  # pragma: no cover - must not be reached
        raise AssertionError("simulated despite refuse policy")

    monkeypatch.setattr(hb.FakeHardwareBackend, "run", boom)
    with pytest.raises(service.ServiceError) as err:
        service.run_with_calibration(UNCOVERED, _v3(), policy="refuse")
    assert err.value.code == "uncalibrated_gates" and err.value.status == 422


@pytest.mark.parametrize("policy", ["warn", "ideal"])
def test_warn_and_ideal_run_noiseless_for_uncovered_gates_and_say_so(policy):
    result, info = service.run_with_calibration(UNCOVERED, _v3(), policy=policy, shots=64)
    coverage = info["gate_coverage"]
    assert "h" in coverage["uncovered_gates"] and coverage["noiseless_gates_accepted"] is True
    assert (len(coverage["warnings"]) == 1) == (policy == "warn")
    assert result.uncovered_gates == coverage["uncovered_gates"]
    assert result.metadata["uncovered_gate_policy"] == policy


def test_invalid_policy_is_typed():
    with pytest.raises(service.ServiceError) as err:
        service.run_with_calibration(COVERED, _v3(), policy="whatever")
    assert err.value.code == "invalid_policy"


def test_v2_profile_files_are_accepted_unchanged_and_match_the_direct_run():
    profile = create_fake_manila_profile()
    bare = profile.to_dict()
    snapshot = json.dumps(bare, sort_keys=True)
    result, info = service.run_with_calibration(COVERED, bare, policy="warn", shots=128, seed=7)
    assert json.dumps(bare, sort_keys=True) == snapshot  # input untouched
    assert info["provenance_label"] == "synthetic"
    direct = FakeHardwareBackend(profile).run(COVERED, shots=128, seed=7)
    assert result.counts == direct.counts


def test_measured_label_without_a_source_is_refused():
    record = _v3()
    record["provenance_label"] = "measured"
    with pytest.raises(service.ServiceError) as err:
        service.run_with_calibration(COVERED, record)
    assert err.value.code == "invalid_calibration"


def test_garbage_calibration_is_typed():
    for bad in ("nope", {"schema": "cqhecs.calibration/3.0"}, {"profile": 3}):
        with pytest.raises(service.ServiceError) as err:
            service.load_calibration(bad)
        assert err.value.code == "invalid_calibration"


# --- surfaces -----------------------------------------------------------------------------------

def _write(tmp_path, record):
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(record), "utf-8")
    return str(path)


def test_cli_text_shows_label_freshness_and_policy(tmp_path, capsys):
    qasm = tmp_path / "c.qasm"
    qasm.write_text(UNCOVERED, "utf-8")
    code = cli_main(["run", str(qasm), "--calibration", _write(tmp_path, _v3()), "--shots", "32"])
    out = capsys.readouterr().out
    assert code == 0
    assert "label=synthetic" in out and "freshness=unknown" in out
    assert "Gate policy : warn" in out and "uncovered=['h'" in out


def test_cli_json_carries_calibration_metadata(tmp_path, capsys):
    qasm = tmp_path / "c.qasm"
    qasm.write_text(COVERED, "utf-8")
    assert cli_main(["--format", "json", "run", str(qasm), "--calibration", _write(tmp_path, _v3()),
                     "--uncovered-gates", "refuse", "--shots", "32"]) == 0
    meta = json.loads(capsys.readouterr().out)["result"]["metadata"]
    assert meta["calibration_v3"]["provenance_label"] == "synthetic"


def test_cli_refuse_exits_nonzero_with_a_message_not_a_traceback(tmp_path, capsys, caplog):
    qasm = tmp_path / "c.qasm"
    qasm.write_text(UNCOVERED, "utf-8")
    code = cli_main(["run", str(qasm), "--calibration", _write(tmp_path, _v3()), "--uncovered-gates", "refuse"])
    captured = capsys.readouterr()
    assert code != 0 and captured.out == "" and "Traceback" not in captured.err
    assert "uncalibrated_gates" in caplog.text


def test_cli_missing_calibration_file_is_an_error_not_a_crash(tmp_path, capsys):
    qasm = tmp_path / "c.qasm"
    qasm.write_text(COVERED, "utf-8")
    assert cli_main(["run", str(qasm), "--calibration", str(tmp_path / "nope.json")]) != 0


def test_studio_returns_provenance_and_notes():
    out = StudioState(ROOT).simulate({
        "source": COVERED, "shots": 64, "noise": "calibration_v3", "calibration": _v3(),
        "uncovered_gates": "warn",
    })
    assert out["calibration"]["provenance_label"] == "synthetic"
    assert out["calibration"]["freshness"]["status"] == "unknown"
    assert "calibration_v3" in out["noise"]["model"] and "unknown" in out["noise"]["model"]
    assert any("freshness" in note for note in out["notes"])


def test_studio_refuse_and_missing_calibration_are_typed():
    state = StudioState(ROOT)
    with pytest.raises(StudioError) as err:
        state.simulate({"source": UNCOVERED, "noise": "calibration_v3", "calibration": _v3(),
                        "uncovered_gates": "refuse"})
    assert err.value.code == "uncalibrated_gates"
    with pytest.raises(StudioError) as err:
        state.simulate({"source": COVERED, "noise": "calibration_v3"})
    assert err.value.code == "invalid_calibration"


def test_mcp_run_accepts_a_calibration_and_returns_the_same_provenance():
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "cqhecs_run",
        "arguments": {"circuit": COVERED, "shots": 32, "noise": "calibration_v3", "calibration": _v3(),
                      "uncovered_gates": "refuse"},
    }})
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["calibration"]["provenance_label"] == "synthetic"
    assert payload["calibration"]["gate_policy"] == "refuse"


def test_non_calibration_runs_are_unchanged():
    out = StudioState(ROOT).simulate({"source": COVERED, "shots": 32, "noise": "ideal"})
    assert "calibration" not in out
