"""
Fit a per-qubit noise profile from measured counts (EMULATOR_BUILD_PLAN W1, W4, W5).

The original v3.0.0 reading of ``OQ-02`` treated its qubit-0 marginal (53.1 %
zeros) as a readout error. The probe circuits contradict that:

* ``OQ-01`` (``X`` twice, identity) gives ``P(1|0) = 0.070``;
* ``OQ-02`` (``X`` on all five) gives ``P(1) = 0.469`` on qubit 0;
* ``OQ-03`` (``X`` on qubit 0 only) gives ``P(1) = 0.507``;
* ``OQ-09`` (GHZ-5, no ``X``) gives ``P(1) = 0.486``.

A readout matrix would depress ``OQ-09`` too. It does not. The defect follows
the ``X`` gate, so installing 0.531 as a readout probability over-corrects every
GHZ circuit.

``M-FIT-2`` therefore:

* takes ``p01`` from ``OQ-01`` (no ``X`` error contributes);
* takes ``p10`` from ``OQ-02`` for ordinary qubits;
* fits ``p10`` for anomalous qubits on the padded GHZ jobs instead;
* fits one CX depolarizing parameter on ``OQ-04``/``OQ-05``;
* solves an ``X`` bit-flip probability from ``OQ-02``/``OQ-03``.

Every departure from a direct readout interpretation is written into the
profile. The model is post-hoc: it was written after the 25 jobs existed, so its
EVAL score is a mechanism check, not a confirmation.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple

import numpy as np

from cqhecs.hardware_bridge import BitFlipChannel, NoiseModel, TwoQubitDepolarizingChannel
from cqhecs.openquantum_suite import (
    SUITE_ID,
    SUITE_SEED,
    SuiteCircuit,
    SuiteRun,
    _marginal_flip_rates,
    build_suite,
    check_bit_order,
    fit_model,
    load_suite_run,
    simulate,
)
from cqhecs.reference import (
    DatasetNotAvailableError,
    IntegrityError,
    _bootstrap_median_delta,
    counts_vector,
    total_variation,
)

PROFILE_SCHEMA = "cqhecs.fitted_noise_profile/2.0"
LAYOUT_ASSUMPTION = (
    "logical qubit q of every job is read with the readout matrix measured on "
    "logical qubit q of the 5-qubit probes; the provider's physical layout is "
    "not published and may differ between jobs"
)


def _grid_minimum(
    score: Callable[[float], float],
    p_max: float = 0.3,
    coarse_points: int = 61,
    fine_points: int = 41,
) -> Tuple[float, float]:
    """Coarse grid, then a fine grid around its minimum; returns (score, p)."""
    best = min((score(float(p)), float(p)) for p in np.linspace(0.0, p_max, coarse_points))
    step = p_max / (coarse_points - 1)
    low, high = max(0.0, best[1] - step), min(p_max, best[1] + step)
    return min([best] + [(score(float(p)), float(p)) for p in np.linspace(low, high, fine_points)])


@dataclass(frozen=True)
class PerQubitModel:
    """``M-FIT-2``: per-qubit readout plus one CX and optional ``X`` error."""

    p01: Tuple[float, ...]
    p10: Tuple[float, ...]
    cx_depolarizing: float
    x_bitflip: Tuple[float, ...] = ()

    def noise_model(self, job: SuiteCircuit) -> NoiseModel:
        if job.num_qubits > len(self.p01):
            raise IntegrityError(
                f"{job.job_id} uses {job.num_qubits} qubits; readout was measured on {len(self.p01)}"
            )
        model = NoiseModel(name=f"M-FIT-2[cx={self.cx_depolarizing:.8g}]")
        model.metadata = {
            "layout_assumption": LAYOUT_ASSUMPTION,
            "x_bitflip": list(self.x_bitflip),
        }
        if self.cx_depolarizing > 0.0:
            for pair in sorted({tuple(q) for name, q, _ in job.gates if name == "cx"}):
                model.add_2q_channel("cx", pair, TwoQubitDepolarizingChannel(self.cx_depolarizing))
        for qubit in range(job.num_qubits):
            model.set_readout_error(qubit, self.p01[qubit], self.p10[qubit])
            if qubit < len(self.x_bitflip) and self.x_bitflip[qubit] > 0.0:
                model.add_1q_channel("x", qubit, BitFlipChannel(self.x_bitflip[qubit]))
        model.validate()
        return model


def _readout_only(n: int) -> PerQubitModel:
    return PerQubitModel((0.0,) * n, (0.0,) * n, 0.0)


def _binomial_se(p: float, shots: int) -> float:
    return math.sqrt(p * (1.0 - p) / shots)


def _jobs_by_name(seed: int) -> Dict[str, SuiteCircuit]:
    return {job.name: job for job in build_suite(seed)}


def _require(run: SuiteRun, jobs: Mapping[str, SuiteCircuit], names: Sequence[str]) -> None:
    for name in names:
        if jobs[name].job_id not in run.counts:
            raise DatasetNotAvailableError(f"FIT job {jobs[name].job_id} ({name}) has no counts")


def _calibration_status(run: SuiteRun) -> Dict[str, Any]:
    """W5: say explicitly whether calibration snapshots exist; never default."""
    if run.calibration_files:
        return {"status": "present", "files": dict(sorted(run.calibration_files.items()))}
    return {"status": "absent", "files": {}}


def _p1(counts: Mapping[str, int], num_qubits: int, qubit: int) -> float:
    total = sum(counts.values())
    if total <= 0:
        raise IntegrityError("empty counts")
    return sum(value for bits, value in counts.items() if bits[num_qubits - 1 - qubit] == "1") / total


def _solve_x_flip(observed_p1: float, p01: float, p10: float) -> float:
    denominator = p01 - (1.0 - p10)
    if abs(denominator) < 1e-12:
        return 0.0
    return float(np.clip((observed_p1 - (1.0 - p10)) / denominator, 0.0, 1.0))


def fit_profile(root: Path, *, seed: int = SUITE_SEED) -> Tuple[PerQubitModel, Dict[str, Any]]:
    """
    Fit ``M-FIT-2`` on the FIT split of a suite run and return it with a
    JSON-serialisable profile document. The document is deterministic: the
    same input gives byte-identical output from :func:`dump_profile`.
    """
    run = load_suite_run(root, seed)
    order = check_bit_order(run, seed)
    if not order["little_endian"]:
        raise IntegrityError(f"bit-order probe returned {order['mode']!r}, expected '00001'")
    jobs = _jobs_by_name(seed)
    _require(
        run,
        jobs,
        ("readout_zero_5", "readout_one_5", "bitorder_q0_5", "ghz5_pad2", "ghz5_pad4"),
    )

    zero, one, probe = jobs["readout_zero_5"], jobs["readout_one_5"], jobs["bitorder_q0_5"]
    zero_shots = sum(run.counts[zero.job_id].values())
    one_shots = sum(run.counts[one.job_id].values())
    p01 = tuple(_marginal_flip_rates(run.counts[zero.job_id], 5, "0"))
    p10_observed = tuple(_marginal_flip_rates(run.counts[one.job_id], 5, "1"))

    median = float(np.median(p10_observed))
    anomalies = tuple(q for q, value in enumerate(p10_observed) if abs(value - median) > 0.25)
    p10 = list(p10_observed)
    for q in anomalies:
        p10[q] = median

    padded = [jobs["ghz5_pad2"], jobs["ghz5_pad4"]]
    real = [counts_vector(run.counts[job.job_id], job.num_qubits) for job in padded]

    def objective(readout: PerQubitModel) -> Callable[[float], float]:
        def score(p: float) -> float:
            model = PerQubitModel(readout.p01, readout.p10, p, readout.x_bitflip)
            return float(np.mean([
                total_variation(r, simulate(job, model.noise_model(job)))
                for job, r in zip(padded, real)
            ]))
        return score

    # Coordinate descent: the anomalous p10 and the CX term are fitted on the
    # two padded GHZ jobs. Fixed grids keep the fit reproducible.
    def score_at(p10_values: Sequence[float], cx_value: float) -> float:
        model = PerQubitModel(p01, tuple(p10_values), float(cx_value))
        return float(np.mean([
            total_variation(r, simulate(job, model.noise_model(job)))
            for job, r in zip(padded, real)
        ]))

    cx = 0.0
    for _ in range(3):
        for q in anomalies:
            best_value, best_tv = p10[q], score_at(p10, cx)
            for candidate in np.linspace(0.0, 0.3, 31):
                trial = list(p10)
                trial[q] = float(candidate)
                tv = score_at(trial, cx)
                if tv < best_tv - 1e-12:
                    best_value, best_tv = float(candidate), tv
            p10[q] = best_value
        best_cx, best_tv = cx, score_at(p10, cx)
        for candidate in np.linspace(0.0, 0.03, 31):
            tv = score_at(p10, float(candidate))
            if tv < best_tv - 1e-12:
                best_cx, best_tv = float(candidate), tv
        cx = best_cx

    uncorrected_tv, uncorrected = _grid_minimum(objective(_readout_only(5)))
    corrected_tv = score_at(p10, cx)
    corrected = cx

    x_flip = [0.0] * 5
    for q in anomalies:
        estimates = []
        if q == 0:
            estimates.append(_solve_x_flip(_p1(run.counts[probe.job_id], 5, q), p01[q], p10[q]))
        estimates.append(_solve_x_flip(_p1(run.counts[one.job_id], 5, q), p01[q], p10[q]))
        x_flip[q] = float(np.mean(estimates)) if estimates else 0.0

    model = PerQubitModel(p01, tuple(p10), corrected, tuple(x_flip))

    fit_jobs = [zero, one, probe, jobs["ghz5_pad2"], jobs["ghz5_pad4"]]
    readout_rows = []
    for q in range(5):
        row = {
            "qubit": q,
            "p01": p01[q],
            "p01_se": _binomial_se(p01[q], zero_shots),
            "p10": p10[q],
            "p10_se": _binomial_se(p10[q], one_shots),
            "p10_observed": p10_observed[q],
            "p10_source": (
                "GHZ ladder (OQ-02 marginal is an X-gate anomaly)"
                if q in anomalies
                else "OQ-02"
            ),
            "x_bitflip": x_flip[q],
        }
        readout_rows.append(row)

    document = {
        "schema": PROFILE_SCHEMA,
        "model": "M-FIT-2",
        "status": "EXPLORATORY_POST_HOC",
        "provenance": {
            "dataset_id": SUITE_ID,
            "dataset_sha256": run.dataset_sha256,
            "backend": run.backend,
            "suite_seed": seed,
            "fit_jobs": [
                {
                    "job_id": job.job_id,
                    "name": job.name,
                    "qasm_sha256": job.sha256,
                    "provider_job_id": run.provider_job_ids.get(job.job_id),
                    "shots": int(sum(run.counts[job.job_id].values())),
                }
                for job in fit_jobs
            ],
            "objective": (
                "mean total variation over OQ-04/OQ-05; anomalous p10 on a "
                "coarse grid over [0, 0.3], CX on a coarse-then-fine grid"
            ),
            "calibration": _calibration_status(run),
            "bit_order": order,
            "layout_assumption": LAYOUT_ASSUMPTION,
        },
        "readout": readout_rows,
        "anomalies": [
            {
                "qubit": q,
                "observed_p10_from_OQ02": p10_observed[q],
                "fitted_p10": p10[q],
                "x_bitflip": x_flip[q],
                "evidence": (
                    "OQ-03 reproduces the flip with a single X on qubit 0; "
                    "OQ-09 (GHZ-5, no X) does not show it"
                )
                if q == 0
                else "OQ-02 marginal is an outlier against the device median",
            }
            for q in anomalies
        ],
        "cx_depolarizing": {
            "readout_corrected": corrected,
            "readout_corrected_fit_tv": corrected_tv,
            "uncorrected": uncorrected,
            "uncorrected_fit_tv": uncorrected_tv,
            "assumption": (
                "the corrected value uses the fitted per-qubit readout matrices; "
                "the uncorrected value fits the gate term with no readout model "
                "and therefore absorbs readout error"
            ),
        },
        "one_qubit_gate_error": (
            "x bit-flip fitted for anomalous qubits; other 1q gates not modelled"
        ),
        "relaxation": "not modelled (no calibration snapshot)",
        "identifiability": {
            "anomalous_qubits": list(anomalies),
            "statement": (
                "OQ-02's marginal on an anomalous qubit is not a readout probability: "
                "OQ-03 reproduces the flip with a single X and OQ-09 (no X) does not."
            ),
            "assumption": (
                "qubits without an anomaly are assumed to have no X-gate error; the "
                "X bit-flip is therefore a lower bound there"
            ),
        },
    }
    return model, document


def dump_profile(document: Mapping[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def evaluate_exploratory(
    root: Path,
    *,
    bootstrap_samples: int = 5000,
    seed: int = SUITE_SEED,
) -> Dict[str, Any]:
    """
    Score ``M-FIT-2`` against the frozen ``M-FIT`` on the same EVAL jobs.

    Same bootstrap (circuits resampled, ``seed``) as H-V3-8. The result is
    labelled post-hoc because ``M-FIT-2`` was designed after the counts were
    known; only a fresh suite can confirm it.
    """
    run = load_suite_run(root, seed)
    model2, profile = fit_profile(root, seed=seed)
    suite = {job.job_id: job for job in build_suite(seed)}
    model1 = fit_model(suite, run.counts)
    rows: List[Dict[str, Any]] = []
    for job_id, job in suite.items():
        if job.split != "EVAL" or job_id not in run.counts:
            continue
        real = counts_vector(run.counts[job_id], job.num_qubits)
        tv_ideal = total_variation(real, simulate(job, None))
        tv_m1 = total_variation(real, simulate(job, model1.noise_model(job)))
        tv_m2 = total_variation(real, simulate(job, model2.noise_model(job)))
        rows.append({
            "job_id": job_id,
            "name": job.name,
            "num_qubits": job.num_qubits,
            "tv_ideal": tv_ideal,
            "tv_m_fit": tv_m1,
            "tv_m_fit_2": tv_m2,
            "delta_m_fit_2_vs_ideal": tv_m2 - tv_ideal,
            "delta_m_fit_2_vs_m_fit": tv_m2 - tv_m1,
        })
    if not rows:
        raise DatasetNotAvailableError("no EVAL job has counts")

    def summary(key: str) -> Dict[str, Any]:
        rng = np.random.default_rng(seed)
        values = [row[key] for row in rows]
        median, low, high = _bootstrap_median_delta(values, samples=bootstrap_samples, rng=rng)
        return {
            "median": median,
            "ci95_low": low,
            "ci95_high": high,
            "n_negative": sum(1 for v in values if v < 0),
            "n": len(values),
            "direction": "M-FIT-2 better" if high < 0 else ("M-FIT-2 worse" if low > 0 else "inconclusive"),
        }

    return {
        "schema_version": "2.0",
        "status": "EXPLORATORY_POST_HOC",
        "note": (
            "M-FIT-2 was written after the r-io-7 counts were known. These numbers check the "
            "mechanism; they do not confirm it. Confirmation needs a fresh suite on another backend."
        ),
        "dataset_id": SUITE_ID,
        "dataset_sha256": run.dataset_sha256,
        "backend": run.backend,
        "calibration": _calibration_status(run),
        "profile": profile,
        "vs_ideal": summary("delta_m_fit_2_vs_ideal"),
        "vs_m_fit": summary("delta_m_fit_2_vs_m_fit"),
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": seed,
        "circuits": rows,
    }
