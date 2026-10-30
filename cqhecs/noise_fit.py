"""
Fit a measured noise profile from the preregistered ``r-io-7`` counts.

Why this module exists
----------------------
The frozen ``M-FIT`` model uses one device-mean readout error for every qubit.
The build plan ``research/v3/EMULATOR_BUILD_PLAN.md`` proposed a per-qubit
``M-FIT-2``. While implementing it, the probe data showed a second problem:

``OQ-02`` (``X`` on all five qubits) reports 53.1 % zeros on qubit 0, but
``OQ-03`` (``X`` on qubit 0 only) reports the same ~50 % flip and ``OQ-09``
(GHZ-5, no ``X``) reports a healthy 48.6 % ones. A readout matrix cannot do
that. The defect follows the ``X`` gate on qubit 0, so installing 0.531 as
readout error over-corrects every GHZ circuit.

``M-FIT-2`` therefore:

* takes ``p01`` from ``OQ-01`` (``X`` twice, so no ``X`` error contributes);
* takes ``p10`` from ``OQ-02`` for ordinary qubits;
* fits ``p10`` for anomalous qubits on the padded GHZ jobs instead;
* fits one global CX depolarizing parameter on ``OQ-04``/``OQ-05``;
* solves an ``X`` bit-flip probability from ``OQ-02``/``OQ-03``.

Every departure from a direct readout interpretation is written into
``identifiability``. The model is **post-hoc and exploratory**: it was written
after the 25 jobs existed, so its held-out score is a mechanism check, not a
preregistered confirmation. A fresh backend is needed for confirmation.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

from cqhecs.hardware_bridge import (
    BackendProfile,
    BitFlipChannel,
    NoiseModel,
    TwoQubitDepolarizingChannel,
)
from cqhecs.openquantum_suite import (
    DEFAULT_SHOTS,
    SUITE_ID,
    SuiteCircuit,
    build_suite,
    fit_model,
    load_suite_run,
    simulate,
)
from cqhecs.reference import (
    _bootstrap_median_delta,
    counts_vector,
    total_variation,
)

MODEL_ID = "M-FIT-2"
SCHEMA_VERSION = "1.0"
DEFAULT_SEED = 20261030


def _marginal(counts: Mapping[str, int], num_qubits: int, qubit: int) -> float:
    """P(bit ``qubit`` is 1), with qubit 0 rightmost (Qiskit order)."""
    total = sum(counts.values())
    if total <= 0:
        raise ValueError("counts are empty")
    position = num_qubits - 1 - qubit
    return sum(value for bits, value in counts.items() if bits[position] == "1") / total


def _p01(counts: Mapping[str, int], num_qubits: int, qubit: int) -> float:
    return _marginal(counts, num_qubits, qubit)


def _p10(counts: Mapping[str, int], num_qubits: int, qubit: int) -> float:
    return 1.0 - _marginal(counts, num_qubits, qubit)


@dataclass(frozen=True)
class NoiseFit:
    """A deterministic, provenance-carrying per-qubit noise fit."""

    dataset_id: str
    backend: str
    dataset_sha256: str
    num_qubits: int
    p01: Tuple[float, ...]
    p10: Tuple[float, ...]
    x_bitflip: Tuple[float, ...]
    cx_depolarizing: float
    fit_tv: float
    mfit_tv: float
    fit_jobs: Tuple[str, ...]
    probe_jobs: Tuple[str, ...]
    anomalous_qubits: Tuple[int, ...]
    p10_observed: Tuple[float, ...]
    warnings: Tuple[str, ...]
    fit_objective: str = "mean total variation on the padded GHZ FIT jobs"

    # -- serialisation --------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "model_id": MODEL_ID,
            "dataset_id": self.dataset_id,
            "backend": self.backend,
            "dataset_sha256": self.dataset_sha256,
            "num_qubits": self.num_qubits,
            "readout": {
                "p01": [round(float(x), 12) for x in self.p01],
                "p10": [round(float(x), 12) for x in self.p10],
                "p10_observed_from_OQ02": [round(float(x), 12) for x in self.p10_observed],
            },
            "x_bitflip": [round(float(x), 12) for x in self.x_bitflip],
            "cx_depolarizing": round(float(self.cx_depolarizing), 12),
            "fit": {
                "objective": self.fit_objective,
                "fit_tv": round(float(self.fit_tv), 12),
                "mfit_fit_tv": round(float(self.mfit_tv), 12),
                "fit_jobs": list(self.fit_jobs),
                "probe_jobs": list(self.probe_jobs),
            },
            "identifiability": {
                "anomalous_qubits": list(self.anomalous_qubits),
                "statement": (
                    "OQ-02's marginal on an anomalous qubit is not a readout "
                    "probability: OQ-03 reproduces the flip with a single X and "
                    "OQ-09 (no X) does not. p10 for those qubits is fitted on the "
                    "GHZ ladder; the X bit-flip is solved from OQ-02/OQ-03."
                ),
                "assumption": (
                    "Qubits without an anomaly are assumed to have no X-gate error; "
                    "the X bit-flip is therefore a lower bound there."
                ),
                "one_qubit_gate_error": (
                    "not fitted: on the padded GHZ jobs a uniform 1q depolarizing "
                    "term is collinear with the CX term, so the fit keeps it at 0 "
                    "and reports this rather than inventing a split."
                ),
            },
            "provenance": {
                "shots_per_job": DEFAULT_SHOTS,
                "measurement_date": "2026-10-30",
                "source": f"research/v3/evidence/openquantum/{self.backend.replace(':', '_')}",
                "preregistered_model": "M-FIT (H-V3-8), unchanged",
                "status": "post-hoc exploratory model; not preregistered",
            },
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def to_profile(self) -> BackendProfile:
        """Emit the same numbers in the validated ``BackendProfile`` schema."""
        profile = BackendProfile(
            name=f"{MODEL_ID}[{self.dataset_id}/{self.backend}]",
            num_qubits=self.num_qubits,
            schema_version="2.0",
            provider_name="CQ-HECS (fit from measured counts)",
            capture_timestamp="2026-10-30",
            provenance_uri=f"dataset:{self.dataset_id}@{self.dataset_sha256}",
            is_synthetic=False,
            basis_gates=["cx", "h", "s", "sdg", "t", "tdg", "x", "sx", "rx", "ry", "rz", "measure"],
            coupling_map=[(q, q + 1) for q in range(self.num_qubits - 1)],
            gate_errors={
                "cx": {
                    (q, q + 1): 0.75 * float(self.cx_depolarizing)
                    for q in range(self.num_qubits - 1)
                }
            }
            if self.cx_depolarizing > 0.0
            else {},
            readout_errors={
                q: (float(self.p01[q]), float(self.p10[q])) for q in range(self.num_qubits)
            },
            calibration_flags={
                "not_modelled": [
                    {
                        "gate": "x",
                        "qubits": [q],
                        "reason": f"bit-flip probability {self.x_bitflip[q]:.6g}",
                    }
                    for q in range(self.num_qubits)
                    if self.x_bitflip[q] > 0.0
                ]
            },
            source_sha256=self.dataset_sha256,
        )
        return profile

    # -- execution ------------------------------------------------------
    def noise_model(self, job: SuiteCircuit) -> NoiseModel:
        model = NoiseModel(
            name=(
                f"{MODEL_ID}[cx={self.cx_depolarizing:.6g};"
                f"p10max={max(self.p10):.6g};xmax={max(self.x_bitflip):.6g}]"
            )
        )
        model.metadata = {
            "model_id": MODEL_ID,
            "dataset_id": self.dataset_id,
            "dataset_sha256": self.dataset_sha256,
            "cx_depolarizing": self.cx_depolarizing,
            "p01": list(self.p01),
            "p10": list(self.p10),
            "x_bitflip": list(self.x_bitflip),
            "status": "post-hoc exploratory",
        }
        for qubit in range(job.num_qubits):
            model.set_readout_error(qubit, float(self.p01[qubit]), float(self.p10[qubit]))
            if self.x_bitflip[qubit] > 0.0:
                model.add_1q_channel("x", qubit, BitFlipChannel(float(self.x_bitflip[qubit])))
        if self.cx_depolarizing > 0.0:
            pairs = {tuple(q) for name, q, _ in job.gates if name == "cx"}
            for pair in sorted(pairs):
                model.add_2q_channel(
                    "cx", pair, TwoQubitDepolarizingChannel(float(self.cx_depolarizing))
                )
        model.validate()
        return model


def fit_noise(
    root: Path | str,
    *,
    dataset_id: str = SUITE_ID,
    seed: int = DEFAULT_SEED,
) -> NoiseFit:
    """Fit ``M-FIT-2`` from a measured suite folder. Deterministic."""
    root = Path(root)
    run = load_suite_run(root, seed)
    jobs = {job.job_id: job for job in build_suite(seed)}
    by_name = {job.name: job for job in jobs.values()}
    counts = run.counts

    for needed in ("readout_zero_5", "readout_one_5", "bitorder_q0_5", "ghz5_pad2", "ghz5_pad4"):
        job = by_name[needed]
        if job.job_id not in counts:
            raise ValueError(f"FIT job {job.job_id} ({needed}) has no counts")

    zero = by_name["readout_zero_5"]
    one = by_name["readout_one_5"]
    order = by_name["bitorder_q0_5"]
    n = zero.num_qubits
    p01 = tuple(_p01(counts[zero.job_id], n, q) for q in range(n))
    p10_observed = tuple(_p10(counts[one.job_id], n, q) for q in range(n))

    finite = [value for value in p10_observed if math.isfinite(value)]
    median = float(np.median(finite))
    anomalies = tuple(
        q for q, value in enumerate(p10_observed) if abs(value - median) > 0.25
    )
    p10 = list(p10_observed)
    for q in anomalies:
        p10[q] = median

    padded = [by_name["ghz5_pad2"], by_name["ghz5_pad4"]]
    real = [counts_vector(counts[job.job_id], job.num_qubits) for job in padded]

    def score(p10_values: Sequence[float], cx: float, x_flip: Sequence[float]) -> float:
        candidate = _make_fit(
            dataset_id=dataset_id,
            backend=run.backend,
            dataset_sha256=run.dataset_sha256,
            num_qubits=n,
            p01=p01,
            p10=tuple(p10_values),
            x_bitflip=tuple(x_flip),
            cx_depolarizing=float(cx),
            fit_tv=0.0,
            mfit_tv=0.0,
            fit_jobs=tuple(sorted(job.job_id for job in padded)),
            probe_jobs=tuple(sorted(job.job_id for job in (zero, one, order))),
            anomalous_qubits=anomalies,
            p10_observed=p10_observed,
            warnings=(),
        )
        return float(
            np.mean(
                [
                    total_variation(result, simulate(job, candidate.noise_model(job)))
                    for job, result in zip(padded, real)
                ]
            )
        )

    # Coordinate descent on the anomalies and the CX term. Fixed grids keep the
    # fit byte-reproducible; no random initialisation is involved.
    cx = 0.0
    for _ in range(3):
        for q in anomalies:
            best_value, best_tv = p10[q], score(p10, cx, [0.0] * n)
            for candidate in np.linspace(0.0, 0.3, 61):
                trial = list(p10)
                trial[q] = float(candidate)
                tv = score(trial, cx, [0.0] * n)
                if tv < best_tv - 1e-12:
                    best_value, best_tv = float(candidate), tv
            p10[q] = best_value
        best_cx, best_tv = cx, score(p10, cx, [0.0] * n)
        for candidate in np.linspace(0.0, 0.03, 61):
            tv = score(p10, float(candidate), [0.0] * n)
            if tv < best_tv - 1e-12:
                best_cx, best_tv = float(candidate), tv
        cx = best_cx

    # Solve the X bit-flip on every qubit from OQ-02 and OQ-03. For ordinary
    # qubits this is zero by construction; for an anomalous qubit it is the
    # probability that explains the observed marginal given the fitted readout.
    x_flip: List[float] = []
    for q in range(n):
        estimates: List[float] = []
        for job, expected in ((order, 1 if q == 0 else 0), (one, 1)):
            if expected != 1:
                continue
            observed = _marginal(counts[job.job_id], n, q)
            denominator = p01[q] - (1.0 - p10[q])
            if abs(denominator) < 1e-12:
                continue
            estimate = (observed - (1.0 - p10[q])) / denominator
            estimates.append(float(np.clip(estimate, 0.0, 1.0)))
        x_flip.append(float(np.mean(estimates)) if estimates else 0.0)

    fit_tv = score(p10, cx, x_flip)
    frozen = fit_model(jobs, counts)
    mfit_tv = float(
        np.mean(
            [
                total_variation(result, simulate(job, frozen.noise_model(job)))
                for job, result in zip(padded, real)
            ]
        )
    )

    warnings: List[str] = [
        "M-FIT-2 is post-hoc: it was written after the 25 jobs existed, so the "
        "EVAL score is exploratory, not a preregistered confirmation.",
        "One backend, one day, 1000 shots per job. No drift or T1/T2 claim.",
        "Readout inversion is an assumption, not a measurement of the true state.",
    ]
    if anomalies:
        warnings.append(
            "Qubit(s) "
            + ", ".join(str(q) for q in anomalies)
            + " show a circuit-dependent flip that is attributed to the X gate, "
            "not to readout. See identifiability."
        )

    return _make_fit(
        dataset_id=dataset_id,
        backend=run.backend,
        dataset_sha256=run.dataset_sha256,
        num_qubits=n,
        p01=p01,
        p10=tuple(p10),
        x_bitflip=tuple(x_flip),
        cx_depolarizing=cx,
        fit_tv=fit_tv,
        mfit_tv=mfit_tv,
        fit_jobs=tuple(sorted(job.job_id for job in padded)),
        probe_jobs=tuple(sorted(job.job_id for job in (zero, one, order))),
        anomalous_qubits=anomalies,
        p10_observed=p10_observed,
        warnings=tuple(warnings),
    )


def _make_fit(**kwargs: Any) -> NoiseFit:
    return NoiseFit(**kwargs)


def evaluate_fit(
    fit: NoiseFit,
    root: Path | str,
    *,
    bootstrap_samples: int = 5000,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Score ``M-FIT`` and ``M-FIT-2`` on the held-out EVAL split."""
    root = Path(root)
    run = load_suite_run(root, seed)
    jobs = {job.job_id: job for job in build_suite(seed)}
    frozen = fit_model(jobs, run.counts)
    rows: List[Dict[str, Any]] = []
    for job_id, job in jobs.items():
        if job.split != "EVAL" or job_id not in run.counts:
            continue
        real = counts_vector(run.counts[job_id], job.num_qubits)
        ideal = simulate(job, None)
        mfit = simulate(job, frozen.noise_model(job))
        mfit2 = simulate(job, fit.noise_model(job))
        rows.append(
            {
                "job_id": job_id,
                "name": job.name,
                "family": job.family,
                "num_qubits": job.num_qubits,
                "cx_count": job.cx_count,
                "tv_ideal": total_variation(real, ideal),
                "tv_mfit": total_variation(real, mfit),
                "tv_mfit2": total_variation(real, mfit2),
                "delta_mfit": total_variation(real, mfit) - total_variation(real, ideal),
                "delta_mfit2": total_variation(real, mfit2) - total_variation(real, ideal),
            }
        )
    if not rows:
        raise ValueError("no EVAL job has counts")

    rng = np.random.default_rng(seed)
    median_mfit, low_mfit, high_mfit = _bootstrap_median_delta(
        [row["delta_mfit"] for row in rows], samples=bootstrap_samples, rng=rng
    )
    rng = np.random.default_rng(seed)
    median_mfit2, low_mfit2, high_mfit2 = _bootstrap_median_delta(
        [row["delta_mfit2"] for row in rows], samples=bootstrap_samples, rng=rng
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": fit.dataset_id,
        "backend": fit.backend,
        "dataset_sha256": run.dataset_sha256,
        "status": "exploratory_post_hoc",
        "models": {
            "M-FIT": {
                "fit_tv": round(float(fit.mfit_tv), 12),
                "median_delta_tv": median_mfit,
                "ci95_low": low_mfit,
                "ci95_high": high_mfit,
                "n_noisy_better": sum(1 for row in rows if row["delta_mfit"] < 0),
            },
            "M-FIT-2": {
                "fit_tv": round(float(fit.fit_tv), 12),
                "median_delta_tv": median_mfit2,
                "ci95_low": low_mfit2,
                "ci95_high": high_mfit2,
                "n_noisy_better": sum(1 for row in rows if row["delta_mfit2"] < 0),
            },
        },
        "n_eval": len(rows),
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": seed,
        "circuits": rows,
        "non_claim": (
            "Post-hoc comparison on the same 25 jobs that motivated the model. "
            "Confirmation requires a fresh backend and a preregistered split."
        ),
    }


def write_fit(
    root: Path | str,
    out_dir: Path | str,
    *,
    dataset_id: str = SUITE_ID,
    seed: int = DEFAULT_SEED,
    bootstrap_samples: int = 5000,
) -> Dict[str, Path]:
    """Fit, evaluate and write ``mfit2.json``, ``profile.json``, ``evaluation.json``."""
    fit = fit_noise(root, dataset_id=dataset_id, seed=seed)
    evaluation = evaluate_fit(fit, root, bootstrap_samples=bootstrap_samples, seed=seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "model": out / "mfit2.json",
        "profile": out / "profile.json",
        "evaluation": out / "mfit2_evaluation.json",
    }
    paths["model"].write_text(fit.to_json(), "utf-8")
    paths["profile"].write_text(
        json.dumps(fit.to_profile().to_dict(), indent=2, sort_keys=True) + "\n", "utf-8"
    )
    paths["evaluation"].write_text(
        json.dumps(evaluation, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    return paths
