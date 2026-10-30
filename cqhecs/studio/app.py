"""
CQ-HECS Studio: a local, dependency-free experiment server.

The server binds to ``127.0.0.1`` by default, serves only bundled static files,
and never reads credentials. Every number it shows comes from a real simulation
or from the committed measured dataset; missing data is reported as missing.
"""

from __future__ import annotations

import json
import os
import re
import threading
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

from cqhecs import __version__
from cqhecs.circuit_library import build_builtin_circuit
from cqhecs.circuit_parsing import parse_circuit
from cqhecs.hardware_bridge import NoiseModel, TwoQubitDepolarizingChannel
from cqhecs.openquantum_suite import SUITE_ID, SuiteCircuit, build_suite, fit_model, simulate
from cqhecs.reference import counts_vector, total_variation
from cqhecs.result import SimulationState
from cqhecs.router import EntanglementAdaptiveRouter, UnsupportedCircuitError
from cqhecs.sat import CNFFormatError, CNF, parse_dimacs, random_3sat, solve, sweep

FIT2_MODEL_ID = "M-FIT-2"

MAX_BODY = 1_000_000
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DATA_ROOT = Path(__file__).resolve().parent / "data"
DATASET_RELATIVE = Path("research/v3/evidence/openquantum/rigetti_cepheus-1-108q")
FIT_RELATIVE = Path("research/v4/evidence/r-io-7")
EVALUATION_RELATIVE = Path("research/v3/evidence/openquantum/rigetti_cepheus-1-108q/h_v3_8_evaluation.json")

_STATIC_FILES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "logo.svg": "image/svg+xml",
}

_ONE_QUBIT = ("h", "x", "s", "sdg", "t", "tdg", "sx", "rx", "ry", "rz")


class StudioError(Exception):
    """A request error with an HTTP status and a stable code."""

    def __init__(self, message: str, status: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.status = status
        self.code = code


def _int(value: Any, name: str, low: int, high: int, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise StudioError(f"{name} must be an integer", code="invalid_argument") from exc
    if parsed < low or parsed > high:
        raise StudioError(f"{name} must be in [{low}, {high}]", code="invalid_argument")
    return parsed


def _float(value: Any, name: str, low: float, high: float, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise StudioError(f"{name} must be a number", code="invalid_argument") from exc
    if not (low <= parsed <= high):
        raise StudioError(f"{name} must be in [{low}, {high}]", code="invalid_argument")
    return parsed


def _measured(circuit: Any) -> Any:
    """Return a Qiskit circuit with terminal measurements, without mutating input."""
    from qiskit import QuantumCircuit

    if isinstance(circuit, str):
        if re.search(r"^\s*measure\b", circuit, re.MULTILINE):
            return circuit
        match = re.search(r"qreg\s+(\w+)\[(\d+)\]", circuit)
        if not match:
            raise StudioError(
                "QASM has no qreg; the studio cannot infer a width",
                code="invalid_qasm",
            )
        register, n = match.group(1), int(match.group(2))
        creg = re.search(r"creg\s+(\w+)\[", circuit)
        classical = creg.group(1) if creg else "c"
        suffix = []
        if not creg:
            suffix.append(f"creg {classical}[{n}];")
        suffix.extend(f"measure {register}[{q}] -> {classical}[{q}];" for q in range(n))
        return circuit.rstrip() + "\n" + "\n".join(suffix) + "\n"
    if isinstance(circuit, QuantumCircuit):
        if circuit.num_clbits == 0:
            measured = circuit.copy()
            measured.measure_all()
            return measured
    return circuit


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


@dataclass
class DatasetView:
    available: bool
    source: str
    dataset_id: str
    backend: str
    dataset_sha256: Optional[str]
    counts: Dict[str, Dict[str, int]]
    files: Dict[str, str]
    provider_job_ids: Dict[str, str]
    evaluation: Optional[Dict[str, Any]]
    fit2: Optional[Dict[str, Any]]
    fit2_evaluation: Optional[Dict[str, Any]]
    note: str
    evaluation_dataset_sha256: Optional[str] = None
    digest_note: Optional[str] = None


class StudioState:
    """State and operations behind the HTTP surface. No global mutable state."""

    def __init__(self, root: Optional[Path | str] = None):
        self.root = Path(root or os.getcwd()).resolve()
        self.jobs: Tuple[SuiteCircuit, ...] = tuple(build_suite())
        self.by_id = {job.job_id: job for job in self.jobs}
        self.dataset = self._load_dataset()
        self._router = EntanglementAdaptiveRouter()

    # -- loading --------------------------------------------------------
    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return None

    def _load_dataset(self) -> DatasetView:
        repo_dir = self.root / DATASET_RELATIVE
        packaged = DATA_ROOT / "dataset.json"
        payload: Optional[Dict[str, Any]] = None
        source = "unavailable"
        note = (
            "No measured r-io-7 folder was found. The simulation labs still work; "
            "the noise and evidence labs need the committed dataset."
        )
        if repo_dir.is_dir():
            try:
                from cqhecs.openquantum_suite import load_suite_run

                run = load_suite_run(repo_dir)
                evaluation = self._load_json(self.root / EVALUATION_RELATIVE)
                fit2_dir = self.root / FIT_RELATIVE
                payload = {
                    "source": str(repo_dir),
                    "dataset_id": SUITE_ID,
                    "backend": run.backend,
                    "dataset_sha256": run.dataset_sha256,
                    "counts": run.counts,
                    "files": run.files,
                    "provider_job_ids": run.provider_job_ids,
                    "evaluation": evaluation,
                    "fit2": self._load_json(fit2_dir / "mfit2.json"),
                    "fit2_evaluation": self._load_json(fit2_dir / "mfit2_evaluation.json"),
                }
                source = str(repo_dir)
                note = "Measured counts loaded from the repository evidence folder."
            except Exception as exc:  # noqa: BLE001 - report, never invent
                note = f"Repository dataset could not be loaded: {type(exc).__name__}: {exc}"
        if payload is None and packaged.is_file():
            payload = self._load_json(packaged)
            if payload:
                source = f"packaged:{packaged.name}"
                note = "Measured counts loaded from the packaged r-io-7 snapshot."
        if not payload:
            return DatasetView(
                available=False,
                source="unavailable",
                dataset_id=SUITE_ID,
                backend="unknown",
                dataset_sha256=None,
                counts={},
                files={},
                provider_job_ids={},
                evaluation=None,
                fit2=None,
                fit2_evaluation=None,
                note=note,
            )
        return DatasetView(
            available=True,
            source=source,
            dataset_id=str(payload.get("dataset_id", SUITE_ID)),
            backend=str(payload.get("backend", "unknown")),
            dataset_sha256=payload.get("dataset_sha256"),
            counts={str(k): {str(s): int(v) for s, v in counts.items()} for k, counts in payload.get("counts", {}).items()},
            files={str(k): str(v) for k, v in payload.get("files", {}).items()},
            provider_job_ids={str(k): str(v) for k, v in payload.get("provider_job_ids", {}).items()},
            evaluation=payload.get("evaluation"),
            fit2=payload.get("fit2"),
            fit2_evaluation=payload.get("fit2_evaluation"),
            note=note,
            evaluation_dataset_sha256=payload.get("evaluation_dataset_sha256"),
            digest_note=payload.get("digest_note"),
        )

    def reload(self) -> None:
        self.dataset = self._load_dataset()

    # -- views ----------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "name": "CQ-HECS Studio",
            "version": __version__,
            "dataset": {
                "available": self.dataset.available,
                "id": self.dataset.dataset_id,
                "backend": self.dataset.backend,
                "source": self.dataset.source,
                "note": self.dataset.note,
                "jobs": len(self.dataset.counts),
                "sha256": self.dataset.dataset_sha256,
            },
            "model": {
                "id": FIT2_MODEL_ID if self.dataset.fit2 else None,
                "status": "post-hoc exploratory" if self.dataset.fit2 else "unavailable",
            },
            "paths": {
                "A": "stabilizer tableau (exact Clifford)",
                "B": "stabilizer rank (exact, T-count cost)",
                "C": "untruncated MPS (exact up to memory)",
                "D": "sparse Pauli (certified bound, may refuse)",
            },
            "presets": sorted(
                [
                    "bell",
                    "clifford6",
                    "ghz8",
                    "ghz16",
                    "low_t_rank4",
                    "mps6",
                    "sparse_pauli4",
                    "toffoli_adder",
                    "qft4",
                    "ising6",
                ]
            ),
            "non_claims": [
                "Classical simulation, not quantum hardware.",
                "No P = NP claim; no ETH proof.",
                "No noise-cleaning claim beyond the stated readout assumption.",
            ],
        }

    def suite(self) -> Dict[str, Any]:
        evaluation_by_job = {}
        if self.dataset.evaluation:
            evaluation_by_job = {
                row["job_id"]: row for row in self.dataset.evaluation.get("circuits", [])
            }
        fit2_by_job = {}
        if self.dataset.fit2_evaluation:
            fit2_by_job = {
                row["job_id"]: row for row in self.dataset.fit2_evaluation.get("circuits", [])
            }
        jobs = []
        for job in self.jobs:
            row = evaluation_by_job.get(job.job_id, {})
            row2 = fit2_by_job.get(job.job_id, {})
            counts = self.dataset.counts.get(job.job_id)
            jobs.append(
                {
                    "job_id": job.job_id,
                    "name": job.name,
                    "split": job.split,
                    "family": job.family,
                    "num_qubits": job.num_qubits,
                    "cx_count": job.cx_count,
                    "shots": job.shots,
                    "purpose": job.purpose,
                    "qasm_sha256": job.sha256,
                    "provider_job_id": self.dataset.provider_job_ids.get(job.job_id),
                    "has_counts": counts is not None,
                    "counts": counts,
                    "tv_ideal": row.get("tv_ideal"),
                    "tv_mfit": row.get("tv_noisy"),
                    "tv_mfit2": row2.get("tv_mfit2"),
                    "delta_mfit": row.get("delta_tv"),
                    "delta_mfit2": row2.get("delta_mfit2"),
                }
            )
        return {
            "schema_version": "1.0",
            "dataset": {
                "id": self.dataset.dataset_id,
                "backend": self.dataset.backend,
                "available": self.dataset.available,
                "source": self.dataset.source,
                "sha256": self.dataset.dataset_sha256,
                "note": self.dataset.note,
                "digest_note": self.dataset.digest_note,
            },
            "jobs": jobs,
            "evaluation": self.dataset.evaluation,
            "fit2_evaluation": self.dataset.fit2_evaluation,
        }

    def noise(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "available": self.dataset.fit2 is not None,
            "dataset": {
                "id": self.dataset.dataset_id,
                "backend": self.dataset.backend,
                "sha256": self.dataset.dataset_sha256,
            },
            "model": self.dataset.fit2,
            "evaluation": self.dataset.fit2_evaluation,
            "mfit": (self.dataset.evaluation or {}).get("model"),
            "note": (
                "M-FIT-2 is post-hoc and exploratory. M-FIT is the frozen, "
                "preregistered model; its SUPPORTED verdict is unchanged."
            ),
        }

    # -- simulation -----------------------------------------------------
    def preset(self, name: str) -> Dict[str, Any]:
        try:
            circuit = build_builtin_circuit(name)
        except (KeyError, ValueError) as exc:
            raise StudioError(f"unknown preset {name!r}", status=404, code="unknown_preset") from exc
        circuit = _measured(circuit)
        from qiskit import qasm2

        return {
            "name": name,
            "qasm": qasm2.dumps(circuit),
            "num_qubits": int(circuit.num_qubits),
            "measured": True,
        }

    def simulate(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        source = str(request.get("source", "preset:bell"))
        if source.startswith("preset:"):
            name = source[len("preset:") :]
            try:
                circuit = build_builtin_circuit(name)
            except (KeyError, ValueError) as exc:
                raise StudioError(f"unknown preset {name!r}", status=404, code="unknown_preset") from exc
        elif source.startswith("qasm:"):
            circuit = source[len("qasm:") :]
        elif "OPENQASM" in source or "qreg" in source:
            circuit = source
        else:
            raise StudioError(
                "source must be 'preset:<name>' or an OpenQASM 2.0 string",
                code="invalid_source",
            )
        circuit = _measured(circuit)
        shots = _int(request.get("shots"), "shots", 1, 20000, 1024)
        seed = _int(request.get("seed"), "seed", 0, 2**31 - 1, 42)
        path = str(request.get("path", "auto")).upper()
        if path != "AUTO" and path not in ("A", "B", "C", "D"):
            raise StudioError("path must be auto, A, B, C or D", code="invalid_path")
        noise = str(request.get("noise", "ideal"))
        if noise not in ("ideal", "mfit", "mfit2", "custom"):
            raise StudioError("noise must be ideal, mfit, mfit2 or custom", code="invalid_noise")

        instructions, num_qubits = parse_circuit(circuit)
        if noise == "ideal":
            result = self._router.route_and_execute(
                circuit,
                shots=shots,
                seed=seed,
                preferred_path=None if path == "AUTO" else path,
            )
            model_label = "ideal (no noise model)"
        else:
            if num_qubits > 10:
                raise StudioError(
                    f"the exact density-matrix noise path supports up to 10 qubits; "
                    f"this circuit has {num_qubits}",
                    status=422,
                    code="noise_width_limit",
                )
            model = self._build_noise_model(instructions, num_qubits, noise, request.get("overrides") or {})
            from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend

            result = NoisyDensityMatrixBackend(max_qubits=10).simulate(
                instructions, noise_model=model, shots=shots, seed=seed
            )
            model_label = model.name

        payload = result.to_dict()
        outcomes = self._outcomes(payload, num_qubits)
        notes = []
        if payload.get("probabilities") is None:
            notes.append(
                "This path reports finite-shot counts, not an exact probability vector. "
                "The histogram is normalised counts."
            )
        if result.state == SimulationState.UNRESOLVED:
            notes.append(str(result.metadata.get("reason", "path refused the circuit")))
        return {
            "schema_version": "1.0",
            "result": payload,
            "analysis": payload.get("metadata", {}).get("analysis"),
            "outcomes": outcomes,
            "num_qubits": num_qubits,
            "noise": {"mode": noise, "model": model_label},
            "notes": notes,
        }

    def _outcomes(self, payload: Mapping[str, Any], num_qubits: int) -> List[Dict[str, Any]]:
        counts = payload.get("counts") or {}
        probabilities = payload.get("probabilities") or {}
        total = sum(counts.values()) or 1
        rows = []
        keys = set(counts) | set(probabilities)
        for key in keys:
            count = int(counts.get(key, 0))
            probability = probabilities.get(key)
            rows.append(
                {
                    "state": key,
                    "count": count,
                    "frequency": count / total,
                    "probability": float(probability) if probability is not None else None,
                }
            )
        rows.sort(key=lambda row: (-row["count"], -float(row["probability"] or 0), row["state"]))
        return rows[:64]

    def _build_noise_model(
        self,
        instructions: Sequence[Any],
        num_qubits: int,
        noise: str,
        overrides: Mapping[str, Any],
    ) -> NoiseModel:
        from cqhecs.hardware_bridge import BitFlipChannel

        pairs = sorted({tuple(ins[1]) for ins in instructions if ins[0] == "cx"})
        if noise == "mfit":
            model_data = (self.dataset.evaluation or {}).get("model") or {}
            if not model_data:
                raise StudioError("M-FIT parameters are not available", status=409, code="model_unavailable")
            p01 = [float(model_data["p01_mean"])] * num_qubits
            p10 = [float(model_data["p10_mean"])] * num_qubits
            cx = float(model_data["cx_depolarizing"])
            x_flip = [0.0] * num_qubits
            label = "M-FIT (frozen, mean readout)"
        else:
            fit = self.dataset.fit2
            if not fit:
                raise StudioError("M-FIT-2 parameters are not available", status=409, code="model_unavailable")
            p01 = [float(v) for v in fit["readout"]["p01"]][:num_qubits]
            p10 = [float(v) for v in fit["readout"]["p10"]][:num_qubits]
            cx = float(fit["cx_depolarizing"])
            x_flip = [float(v) for v in fit["x_bitflip"]][:num_qubits]
            label = "M-FIT-2 (post-hoc)"
            if len(p01) < num_qubits:
                raise StudioError(
                    "the fitted model covers fewer qubits than this circuit",
                    status=422,
                    code="model_width_limit",
                )

        if overrides:
            if "p10" in overrides:
                values = list(overrides["p10"])
                if len(values) != num_qubits:
                    raise StudioError("overrides.p10 must have one value per qubit", code="invalid_override")
                p10 = [_float(v, "p10", 0.0, 1.0, 0.0) for v in values]
            if "p01" in overrides:
                values = list(overrides["p01"])
                if len(values) != num_qubits:
                    raise StudioError("overrides.p01 must have one value per qubit", code="invalid_override")
                p01 = [_float(v, "p01", 0.0, 1.0, 0.0) for v in values]
            if "x_bitflip" in overrides:
                values = list(overrides["x_bitflip"])
                if len(values) != num_qubits:
                    raise StudioError("overrides.x_bitflip must have one value per qubit", code="invalid_override")
                x_flip = [_float(v, "x_bitflip", 0.0, 1.0, 0.0) for v in values]
            if "cx_depolarizing" in overrides:
                cx = _float(overrides["cx_depolarizing"], "cx_depolarizing", 0.0, 1.0, 0.0)
            label += " + overrides"

        model = NoiseModel(name=label)
        for qubit in range(num_qubits):
            model.set_readout_error(qubit, p01[qubit], p10[qubit])
            if x_flip[qubit] > 0.0:
                model.add_1q_channel("x", qubit, BitFlipChannel(x_flip[qubit]))
        if cx > 0.0:
            for pair in pairs:
                model.add_2q_channel("cx", pair, TwoQubitDepolarizingChannel(cx))
        model.validate()
        return model

    # -- noise comparison ----------------------------------------------
    def compare_noise(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        job_id = str(request.get("job_id", ""))
        job = self.by_id.get(job_id)
        if job is None:
            raise StudioError(f"unknown job_id {job_id!r}", status=404, code="unknown_job")
        if job_id not in self.dataset.counts:
            raise StudioError(f"{job_id} has no measured counts", status=409, code="no_counts")
        real = counts_vector(self.dataset.counts[job_id], job.num_qubits)
        ideal = simulate(job, None)
        models: Dict[str, Any] = {}
        rows: List[Dict[str, Any]] = []
        frozen = fit_model({j.job_id: j for j in self.jobs}, self.dataset.counts)
        candidates = {
            "M-FIT": frozen.noise_model(job),
            "M-FIT-2": self._fit_model_from_dict(job, self.dataset.fit2) if self.dataset.fit2 else None,
        }
        if "overrides" in request and self.dataset.fit2:
            candidates["custom"] = self._build_noise_model(
                job.instructions(), job.num_qubits, "custom", request["overrides"]
            )
        for name, model in candidates.items():
            if model is None:
                continue
            predicted = simulate(job, model)
            models[name] = {
                "tv": total_variation(real, predicted),
                "outcomes": self._outcomes(
                    {"counts": {}, "probabilities": {
                        format(i, f"0{job.num_qubits}b"): float(p)
                        for i, p in enumerate(predicted)
                        if p > 1e-12
                    }},
                    job.num_qubits,
                ),
            }
        models["ideal"] = {
            "tv": total_variation(real, ideal),
            "outcomes": self._outcomes(
                {"counts": {}, "probabilities": {
                    format(i, f"0{job.num_qubits}b"): float(p)
                    for i, p in enumerate(ideal)
                    if p > 1e-12
                }},
                job.num_qubits,
            ),
        }
        models["measured"] = {
            "tv": 0.0,
            "outcomes": self._outcomes({"counts": self.dataset.counts[job_id]}, job.num_qubits),
        }
        for outcome, count in self.dataset.counts[job_id].items():
            rows.append({"state": outcome, "count": count})
        rows.sort(key=lambda row: -row["count"])
        return {
            "schema_version": "1.0",
            "job": {
                "job_id": job.job_id,
                "name": job.name,
                "family": job.family,
                "num_qubits": job.num_qubits,
                "cx_count": job.cx_count,
                "shots": sum(self.dataset.counts[job_id].values()),
            },
            "models": models,
            "measured_top": rows[:32],
            "note": (
                "TV is total variation to the measured counts. A lower TV is a better "
                "prediction on this job; it is not a proof of the physical noise model."
            ),
        }

    def _fit_model_from_dict(self, job: SuiteCircuit, data: Mapping[str, Any]) -> NoiseModel:
        from cqhecs.hardware_bridge import BitFlipChannel

        p01 = [float(v) for v in data["readout"]["p01"]]
        p10 = [float(v) for v in data["readout"]["p10"]]
        x_flip = [float(v) for v in data["x_bitflip"]]
        cx = float(data["cx_depolarizing"])
        model = NoiseModel(name="M-FIT-2")
        for qubit in range(job.num_qubits):
            model.set_readout_error(qubit, p01[qubit], p10[qubit])
            if x_flip[qubit] > 0.0:
                model.add_1q_channel("x", qubit, BitFlipChannel(x_flip[qubit]))
        if cx > 0.0:
            for pair in sorted({tuple(q) for name, q, _ in job.gates if name == "cx"}):
                model.add_2q_channel("cx", pair, TwoQubitDepolarizingChannel(cx))
        model.validate()
        return model

    # -- SAT ------------------------------------------------------------
    def sat_solve(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        timeout = _float(request.get("timeout"), "timeout", 0.01, 30.0, 5.0)
        if "cnf" in request:
            text = str(request["cnf"])
            if len(text) > 200_000:
                raise StudioError("CNF text is larger than 200 kB", code="cnf_too_large")
            formula = parse_dimacs(text)
        elif "random" in request:
            spec = request["random"] or {}
            n = _int(spec.get("num_vars"), "random.num_vars", 3, 120, 20)
            ratio = _float(spec.get("ratio"), "random.ratio", 0.0, 20.0, 4.26)
            seed = _int(spec.get("seed"), "random.seed", 0, 2**31 - 1, 20261030)
            formula = random_3sat(n, int(round(ratio * n)), seed=seed)
        elif "num_vars" in request and "clauses" in request:
            n = _int(request.get("num_vars"), "num_vars", 1, 200, 10)
            clauses = []
            for clause in request["clauses"]:
                cleaned = tuple(int(lit) for lit in clause if int(lit) != 0)
                if cleaned:
                    clauses.append(cleaned)
            formula = CNF(num_vars=n, clauses=tuple(clauses), source="request")
        else:
            raise StudioError(
                "provide 'cnf', 'random' or 'num_vars' + 'clauses'",
                code="invalid_formula",
            )
        budget_value = request.get("node_budget")
        node_budget = (
            _int(budget_value, "node_budget", 1, 10_000_000, 1)
            if budget_value not in (None, 0, "0", "")
            else None
        )
        result = solve(formula, timeout_seconds=timeout, node_budget=node_budget)
        return {
            "schema_version": "1.0",
            "formula": {
                "num_vars": formula.num_vars,
                "num_clauses": formula.num_clauses,
                "sha256": formula.sha256,
                "source": formula.source,
                "clause_widths": _width_histogram(formula),
            },
            "result": result.to_dict(),
            "non_claim": (
                "SAT/UNSAT refers to this formula only. UNKNOWN is a timeout, not a "
                "negative answer; UNSAT has no proof object."
            ),
        }

    def sat_sweep(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        sizes = [int(v) for v in request.get("sizes", [10, 15, 20])]
        ratios = [float(v) for v in request.get("ratios", [3.0, 3.5, 4.0, 4.26, 4.5, 5.0])]
        trials = _int(request.get("trials"), "trials", 1, 20, 3)
        timeout = _float(request.get("timeout"), "timeout", 0.01, 5.0, 1.0)
        if len(sizes) > 8 or len(ratios) > 10:
            raise StudioError("at most 8 sizes and 10 ratios per sweep", code="sweep_too_large")
        if any(n < 3 or n > 60 for n in sizes):
            raise StudioError("sizes must be in [3, 60]", code="invalid_argument")
        if any(r < 0 or r > 12 for r in ratios):
            raise StudioError("ratios must be in [0, 12]", code="invalid_argument")
        if len(sizes) * len(ratios) * trials > 240:
            raise StudioError("at most 240 solver runs per sweep", code="sweep_too_large")
        return sweep(sizes=sizes, ratios=ratios, trials=trials, timeout_seconds=timeout)

    # -- research -------------------------------------------------------
    def research(self) -> Dict[str, Any]:
        return _research_payload()

    def reference(self) -> Dict[str, Any]:
        return self.suite()


def _width_histogram(formula: CNF) -> Dict[str, int]:
    histogram: Dict[str, int] = {}
    for clause in formula.clauses:
        key = str(len(clause))
        histogram[key] = histogram.get(key, 0) + 1
    return histogram


def _research_payload() -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "updated": "2026-10-30",
        "headline": "P versus NP is open. ETH is a hypothesis. A simulator is not a proof.",
        "sections": [
            {
                "id": "pnp",
                "title": "P versus NP",
                "status": "open",
                "body": (
                    "P is the class of decision problems solvable in polynomial time; NP is "
                    "the class whose yes-instances have polynomial-size certificates that can "
                    "be checked in polynomial time. Cook (1971) and Karp (1972) established "
                    "NP-completeness; SAT is the canonical complete problem. No proof of "
                    "P = NP or P != NP is accepted. A finite benchmark, a simulator, or an "
                    "AI-generated manuscript cannot settle it."
                ),
                "what_this_repo_does": (
                    "It solves finite CNF instances soundly and measures their runtime. "
                    "That is evidence about this solver on these instances, nothing more."
                ),
            },
            {
                "id": "eth",
                "title": "Exponential Time Hypothesis",
                "status": "hypothesis",
                "body": (
                    "ETH (Impagliazzo and Paturi, 2001) conjectures that 3-SAT needs "
                    "2^(Omega(n)) time in the worst case. SETH strengthens it. ETH implies "
                    "P != NP, so a proof of ETH would settle P versus NP; the converse is "
                    "not true. Conditional lower bounds (for example for Weisfeiler-Leman "
                    "refinement) often assume ETH or SETH rather than prove them."
                ),
                "what_this_repo_does": (
                    "The SAT lab plots median decisions and wall time against clause ratio. "
                    "An exponential-looking curve is consistent with ETH; it is not a proof."
                ),
            },
            {
                "id": "openai_math",
                "title": "The OpenAI math corpus",
                "status": "evidence, not authority",
                "body": (
                    "The openai/math release (October 2026) contains hundreds of manuscripts "
                    "across mathematics and theoretical computer science, with Lean "
                    "formalizations for a minority of them. The repository's own audit "
                    "(research/v2_4) classifies which results are formalized, which are "
                    "conditional, and which do not transfer to this project. A manuscript is "
                    "not a peer-reviewed theorem, and a Lean file is only as good as its "
                    "statement."
                ),
                "what_this_repo_does": (
                    "It reuses formalization patterns and a small number of complexity "
                    "statements as literature, never as an oracle. It does not import an "
                    "unverified claim into a test."
                ),
            },
            {
                "id": "quantum",
                "title": "What the quantum emulator can and cannot say",
                "status": "classical simulation",
                "body": (
                    "The four paths exploit structure: stabilizer circuits, low T-count, "
                    "low entanglement, and sparse Pauli observables. They do not simulate "
                    "arbitrary circuits in polynomial time. The measured r-io-7 counts are "
                    "used to fit a noise model; the noiseless QuantumRings runs are an "
                    "independent cross-check of the exact paths."
                ),
                "what_this_repo_does": (
                    "It reports EXACT, CERTIFIED, UNRESOLVED or FAILED, and refuses when no "
                    "path has a valid contract. It never fills a gap with a plausible number."
                ),
            },
        ],
        "citations": [
            "Cook, S. A. (1971). The complexity of theorem-proving procedures.",
            "Karp, R. M. (1972). Reducibility among combinatorial problems.",
            "Impagliazzo, R., Paturi, R. (2001). On the complexity of k-SAT.",
            "Impagliazzo, R., Paturi, R., Zane, F. (2001). Which problems have strongly exponential complexity?",
            "Williams, R. (2011). Non-uniform ACC circuit lower bounds.",
            "OpenAI (2026). Sharing AI progress in mathematics. https://openai.com/index/sharing-ai-progress-in-mathematics",
            "CQ-HECS research/v2_4: audit of the openai/math corpus.",
        ],
    }


class StudioHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: Tuple[str, int], state: StudioState):
        self.state = state
        super().__init__(address, StudioHandler)

    def handle_error(self, request: Any, client_address: Any) -> None:
        # A browser closing a keep-alive connection is not an engine error.
        import sys

        error = sys.exc_info()[1]
        if isinstance(error, (ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


class StudioHandler(BaseHTTPRequestHandler):
    server: StudioHTTPServer
    server_version = f"CQ-HECS-Studio/{__version__}"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    # -- plumbing -------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str, extra: Optional[Dict[str, str]] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(_jsonable(payload), indent=2, sort_keys=True).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: int, code: str, message: str) -> None:
        self._json(status, {"error": {"code": code, "message": message}})

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise StudioError("request body is larger than 1 MB", status=413, code="body_too_large")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise StudioError("request body is not valid JSON", code="invalid_json") from exc
        if not isinstance(payload, dict):
            raise StudioError("request body must be a JSON object", code="invalid_json")
        return payload

    # -- routes ---------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/":
                return self._static("index.html")
            if path.startswith("/static/"):
                return self._static(path[len("/static/") :])
            if path == "/api/health":
                return self._json(HTTPStatus.OK, self.server.state.health())
            if path == "/api/suite":
                return self._json(HTTPStatus.OK, self.server.state.suite())
            if path == "/api/noise":
                return self._json(HTTPStatus.OK, self.server.state.noise())
            if path == "/api/research":
                return self._json(HTTPStatus.OK, self.server.state.research())
            if path == "/api/reference":
                return self._json(HTTPStatus.OK, self.server.state.reference())
            if path == "/api/preset":
                query = parse_qs(urlparse(self.path).query)
                name = (query.get("name") or ["bell"])[0]
                return self._json(HTTPStatus.OK, self.server.state.preset(name))
            return self._error(HTTPStatus.NOT_FOUND, "not_found", f"no route for {path}")
        except StudioError as exc:
            return self._error(exc.status, exc.code, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._error(500, "internal_error", f"{type(exc).__name__}: {exc}")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/simulate":
                return self._json(HTTPStatus.OK, self.server.state.simulate(body))
            if path == "/api/noise/compare":
                return self._json(HTTPStatus.OK, self.server.state.compare_noise(body))
            if path == "/api/sat/solve":
                return self._json(HTTPStatus.OK, self.server.state.sat_solve(body))
            if path == "/api/sat/sweep":
                return self._json(HTTPStatus.OK, self.server.state.sat_sweep(body))
            if path == "/api/reload":
                self.server.state.reload()
                return self._json(HTTPStatus.OK, self.server.state.health())
            return self._error(HTTPStatus.NOT_FOUND, "not_found", f"no route for {path}")
        except (StudioError, CNFFormatError) as exc:
            status = getattr(exc, "status", 400)
            code = getattr(exc, "code", "invalid_formula")
            return self._error(status, code, str(exc))
        except (ValueError, TypeError, UnsupportedCircuitError) as exc:
            return self._error(422, "refused", f"{type(exc).__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            return self._error(500, "internal_error", f"{type(exc).__name__}: {exc}")

    def _static(self, name: str) -> None:
        if name not in _STATIC_FILES:
            return self._error(HTTPStatus.NOT_FOUND, "not_found", f"no static file {name!r}")
        path = STATIC_ROOT / name
        try:
            body = path.read_bytes()
        except OSError:
            return self._error(HTTPStatus.NOT_FOUND, "not_found", f"missing bundled file {name!r}")
        return self._send(HTTPStatus.OK, body, _STATIC_FILES[name])


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    root: Optional[Path | str] = None,
) -> StudioHTTPServer:
    state = StudioState(root)
    return StudioHTTPServer((host, port), state)


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    root: Optional[Path | str] = None,
    open_browser: bool = True,
) -> None:
    server = create_server(host, port, root)
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"CQ-HECS Studio {__version__} on {url}")
    print("Local only. Press Ctrl+C to stop.")
    print(server.state.dataset.note)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.shutdown()
        server.server_close()
