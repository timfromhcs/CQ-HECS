"""W10 noise governance: calibration v3, gate policy, channel checks, FIT/EVAL separation.

Offline only; reads the committed r-io-7 counts and never contacts a provider.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

import cqhecs.noise_fit as noise_fit
from cqhecs.calibration_v3 import (
    CalibrationV3,
    UncalibratedGateError,
    check_channel,
    check_noise_model,
)
from cqhecs.hardware_bridge import (
    AmplitudeDampingChannel,
    BackendProfile,
    DepolarizingChannel,
    InvalidProfileError,
    NoiseChannel,
    NoiseModel,
    ReadoutErrorChannel,
    ThermalRelaxationChannel,
    TwoQubitDepolarizingChannel,
    create_fake_manila_profile,
    create_linear_profile,
)
from cqhecs.openquantum_suite import SUITE_SEED, build_suite

ROOT = Path(__file__).resolve().parents[1]
RIGETTI = ROOT / "research" / "v3" / "evidence" / "openquantum" / "rigetti_cepheus-1-108q"


def _measured_profile() -> BackendProfile:
    return BackendProfile(
        name="dev", num_qubits=2, is_synthetic=False,
        capture_timestamp="2026-01-01T00:00:00+00:00", provenance_uri="file://snapshot.json",
        gate_errors={"cx": {(0, 1): 0.01}},
    )


# ---------------------------------------------------------------- labels

def test_synthetic_profile_defaults_to_synthetic_label():
    cal = CalibrationV3.from_profile(create_linear_profile(3))
    assert cal.provenance_label == "synthetic"
    d = cal.to_dict()
    assert d["schema"] == "cqhecs.calibration/3.0"
    assert d["gate_basis"] == list(cal.profile.basis_gates)
    assert d["units"]["t1"] == "us"


def test_real_profile_without_declaration_is_unknown_not_measured():
    assert CalibrationV3.from_profile(_measured_profile()).provenance_label == "unknown"


def test_synthetic_profile_cannot_be_labelled_measured():
    with pytest.raises(InvalidProfileError):
        CalibrationV3.from_profile(create_fake_manila_profile(), provenance_label="measured")


def test_measured_needs_timestamp_and_source():
    p = BackendProfile(name="d", num_qubits=1, is_synthetic=False,
                       capture_timestamp="2026-01-01T00:00:00+00:00", provenance_uri="x")
    assert CalibrationV3.from_profile(p, provenance_label="measured").provenance_label == "measured"
    with pytest.raises(InvalidProfileError):
        CalibrationV3.from_profile(_measured_profile(), provenance_label="synthetic")


def test_unknown_label_rejected():
    with pytest.raises(InvalidProfileError):
        CalibrationV3.from_profile(create_linear_profile(2), provenance_label="trusted")


def test_layout_must_be_injective_and_in_range():
    p = create_linear_profile(3)
    with pytest.raises(InvalidProfileError):
        CalibrationV3.from_profile(p, layout=[0, 0])
    with pytest.raises(InvalidProfileError):
        CalibrationV3.from_profile(p, layout=[0, 7])
    assert CalibrationV3.from_profile(p, layout=[2, 0]).layout == (2, 0)


def test_roundtrip():
    cal = CalibrationV3.from_profile(_measured_profile(), provenance_label="derived",
                                     layout=[1, 0], max_age_hours=24)
    again = CalibrationV3.from_dict(json.loads(json.dumps(cal.to_dict())))
    assert again.to_dict() == cal.to_dict()
    bad = cal.to_dict()
    bad["schema"] = "cqhecs.calibration/2.0"
    with pytest.raises(InvalidProfileError):
        CalibrationV3.from_dict(bad)


# ---------------------------------------------------------------- freshness

def test_freshness_is_never_assumed():
    cal = CalibrationV3.from_profile(_measured_profile())
    assert cal.freshness()["status"] == "unknown"
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cal = CalibrationV3.from_profile(_measured_profile(), max_age_hours=24)
    assert cal.freshness(ts + timedelta(hours=1))["status"] == "fresh"
    assert cal.freshness(ts + timedelta(hours=25))["status"] == "stale"
    assert cal.freshness(ts - timedelta(hours=1))["status"] == "stale"  # future stamp is not fresh
    assert CalibrationV3.from_profile(create_linear_profile(2), max_age_hours=1).freshness()["status"] == "unknown"


# ---------------------------------------------------------------- gate policy

def test_uncalibrated_gate_policy():
    cal = CalibrationV3.from_profile(create_linear_profile(2))
    ins = [("h", (0,), ()), ("t", (0,), ())]
    assert "t" in cal.profile.uncovered_gates(ins)
    with pytest.raises(UncalibratedGateError):
        cal.check_gates(ins, "refuse")
    warn = cal.check_gates(ins, "warn")
    assert warn["warnings"] and warn["noiseless_gates_accepted"]
    ideal = cal.check_gates(ins, "ideal")
    assert ideal["uncovered_gates"] == warn["uncovered_gates"] and not ideal["warnings"]
    assert not cal.check_gates([("x", (0,), ())], "refuse")["uncovered_gates"]
    with pytest.raises(ValueError):
        cal.check_gates(ins, "silent")


# ---------------------------------------------------------------- channel checks

def test_shipped_channels_pass():
    for ch in (DepolarizingChannel(0.1), AmplitudeDampingChannel(0.2),
               TwoQubitDepolarizingChannel(0.05), ThermalRelaxationChannel(50.0, 40.0, 0.3)):
        r = check_channel(ch)
        assert r["ok"], r


class _Bad(NoiseChannel):
    def __init__(self, kraus):
        self._k = kraus

    name = "bad"

    @property
    def kraus_operators(self):
        return self._k

    def to_dict(self):
        return {}


def test_incomplete_channel_flagged():
    r = check_channel(_Bad([0.9 * np.eye(2, dtype=complex)]))
    assert not r["ok"] and r["completeness_residual"] > 0.1


def test_choi_psd_is_exact_for_kraus_form():
    # Any Kraus form has PSD Choi by construction; the check must report ~0 Hermiticity residual.
    rng = np.random.default_rng(3)
    ks = [rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2)) for _ in range(3)]
    s = sum(k.conj().T @ k for k in ks)
    w, v = np.linalg.eigh(s)
    inv = v @ np.diag(w ** -0.5) @ v.conj().T
    r = check_channel(_Bad([k @ inv for k in ks]))
    assert r["ok"], r


def test_noise_model_report_and_readout_stochasticity():
    m = NoiseModel()
    m.add_1q_channel("x", 0, DepolarizingChannel(0.1))
    m.set_readout_error(0, 0.02, 0.05)
    assert check_noise_model(m)["ok"]
    m.readout_errors[0].matrix = np.array([[0.9, 0.1], [0.2, 0.9]])  # tampered: column 2 sums 1.0? no, 1.1
    rep = check_noise_model(m)
    assert not rep["ok"] and not rep["readout"][0]["ok"]
    m.readout_errors[0].matrix = np.array([[1.1, 0.0], [-0.1, 1.0]])  # sums ok, negative entry
    assert not check_noise_model(m)["ok"]
    with pytest.raises(Exception):
        ReadoutErrorChannel(1.2, 0.0)


# ---------------------------------------------------------------- FIT/EVAL split

@pytest.mark.skipif(not RIGETTI.is_dir(), reason="committed r-io-7 evidence absent")
def test_fit_reads_only_fit_split_counts(monkeypatch):
    splits = {j.job_id: j.split for j in build_suite(SUITE_SEED)}
    real_load = noise_fit.load_suite_run
    touched = set()

    class Recording(dict):
        def __getitem__(self, k):
            touched.add(k)
            return super().__getitem__(k)

        def get(self, k, d=None):
            touched.add(k)
            return super().get(k, d)

        def items(self):
            touched.update(self)
            return super().items()

        def values(self):
            touched.update(self)
            return super().values()

        def __iter__(self):
            touched.update(self.keys())
            return super().__iter__()

    def spy(root, seed=SUITE_SEED):
        run = real_load(root, seed)
        run.counts = Recording(run.counts)
        return run

    monkeypatch.setattr(noise_fit, "load_suite_run", spy)
    noise_fit.fit_profile(RIGETTI)
    assert touched, "recorder saw nothing; test is vacuous"
    assert {splits[j] for j in touched} == {"FIT"}


@pytest.mark.skipif(not RIGETTI.is_dir(), reason="committed r-io-7 evidence absent")
def test_corrupting_eval_counts_does_not_change_the_fit(tmp_path):
    copy = tmp_path / "run"
    shutil.copytree(RIGETTI, copy)
    def fitted(doc):
        # dataset_sha256 digests every job file (provenance of the whole dataset,
        # including EVAL); it is not a fitted quantity, so it is excluded.
        doc = json.loads(noise_fit.dump_profile(doc))
        assert doc["provenance"].pop("dataset_sha256")
        return doc

    base = fitted(noise_fit.fit_profile(copy)[1])
    eval_jobs = [j for j in build_suite(SUITE_SEED) if j.split == "EVAL"]
    changed = 0
    for job in eval_jobs:
        f = copy / job.job_id / "result.json"
        if not f.is_file():
            continue
        text = f.read_text("utf-8")
        payload = json.loads(text)
        counts_holder = payload
        stack, hit = [payload], False
        while stack and not hit:
            o = stack.pop()
            if isinstance(o, dict):
                if o and all(isinstance(k, str) and k.strip() and set(k.replace(" ", "")) <= {"0", "1"}
                             and isinstance(v, int) and not isinstance(v, bool) for k, v in o.items()):
                    k = next(iter(o))
                    o[k] = o[k] + 12345
                    hit = True
                stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
        if hit:
            f.write_text(json.dumps(counts_holder), "utf-8")
            changed += 1
    assert changed > 0, "no EVAL counts tampered; test is vacuous"
    assert fitted(noise_fit.fit_profile(copy)[1]) == base
