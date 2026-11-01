"""Typed SHA research contract: states, integrity digest, tamper detection."""
import pytest

from cqhecs.sha.model import ShaResult, ShaState, ShaTask


def _task(**kw):
    base = dict(
        task_id="t-1", algorithm="SHA-256", rounds=64, iv="standard", input_model="bytes",
        target="digest", endian="big", seed=1, budget={"seconds": 5}, backend="BROWSER_CPU",
    )
    base.update(kw)
    return ShaTask(**base)


def test_states_are_the_documented_set():
    assert {s.value for s in ShaState} == {
        "COMPUTED", "CANDIDATE", "VERIFIED", "UNRESOLVED", "UNSUPPORTED", "FAILED", "SIMULATED",
    }


def test_result_integrity_digest_roundtrip():
    r = ShaResult.create(_task(), ShaState.COMPUTED, payload={"digest": "00"}, software={"cqhecs": "4.0.0"})
    assert r.verify_integrity()
    again = ShaResult.from_dict(r.to_dict())
    assert again.integrity == r.integrity and again.verify_integrity()


def test_tampered_result_detected():
    r = ShaResult.create(_task(), ShaState.COMPUTED, payload={"digest": "00"}, software={})
    d = r.to_dict()
    d["payload"]["digest"] = "01"
    assert not ShaResult.from_dict(d).verify_integrity()


def test_simulated_and_hardware_cannot_be_confused():
    sim = ShaResult.create(_task(backend="DEMO_SIMULATED"), ShaState.SIMULATED, payload={}, software={})
    assert sim.to_dict()["state"] == "SIMULATED"
    with pytest.raises(ValueError):
        ShaResult.create(_task(backend="DEMO_SIMULATED"), ShaState.VERIFIED, payload={}, software={})
    with pytest.raises(ValueError):
        ShaResult.create(_task(backend="ASIC_BM1366"), ShaState.SIMULATED, payload={}, software={})


def test_asic_result_requires_firmware_version():
    with pytest.raises(ValueError):
        ShaResult.create(_task(backend="ASIC_BM1366"), ShaState.CANDIDATE, payload={}, software={})
    ok = ShaResult.create(
        _task(backend="ASIC_BM1366"), ShaState.CANDIDATE, payload={}, software={}, firmware_version="v4.0.2-rc1"
    )
    assert ok.firmware_version == "v4.0.2-rc1"


def test_invalid_task_rejected():
    with pytest.raises(ValueError):
        _task(rounds=65)
    with pytest.raises(ValueError):
        _task(backend="MAGIC")
