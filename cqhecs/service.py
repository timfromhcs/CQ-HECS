"""
Shared service layer (W4-03).

One implementation of the operations that the Python API, the ``cq-hecs`` CLI, the stdio MCP server
and the local Studio all expose. Each surface keeps only its own envelope (argparse, JSON-RPC, HTTP);
the document inside the envelope is produced here, so the four surfaces cannot drift.

Currently shared: circuit-source resolution and the dry-run ``ExecutionPlan``.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

VALID_PATHS = ("A", "B", "C", "D")


class ServiceError(ValueError):
    """A typed, caller-facing failure. ``code`` is stable; surfaces map it to their own error shape."""

    def __init__(self, message: str, *, code: str = "invalid_request", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def resolve_circuit_source(source: Any, *, strict: bool = False) -> Any:
    """Turn a surface-level circuit string into something the parser accepts.

    ``preset:<name>`` builds a builtin circuit, ``qasm:<text>`` and OpenQASM text pass through. With
    ``strict`` anything else is refused (Studio); otherwise it is passed on and the parser decides.
    """
    if not isinstance(source, str):
        raise ServiceError("circuit source must be a string", code="invalid_source")
    if source.startswith("preset:"):
        from cqhecs.circuit_library import build_builtin_circuit

        name = source[len("preset:"):]
        try:
            return build_builtin_circuit(name)
        except (KeyError, ValueError) as exc:
            raise ServiceError(f"unknown preset {name!r}", code="unknown_preset", status=404) from exc
    if source.startswith("qasm:"):
        return source[len("qasm:"):]
    if strict and "OPENQASM" not in source and "qreg" not in source:
        raise ServiceError(
            "source must be 'preset:<name>' or an OpenQASM 2.0 string", code="invalid_source"
        )
    return source


def normalize_force_path(path: Optional[str]) -> Optional[str]:
    """``None``/``auto`` mean no forced path; otherwise A-D (case-insensitive) or a typed error."""
    if path is None:
        return None
    value = str(path).upper()
    if value == "AUTO":
        return None
    if value not in VALID_PATHS:
        raise ServiceError("path must be auto, A, B, C or D", code="invalid_path")
    return value


def plan_object(
    source: Any,
    *,
    force_path: Optional[str] = None,
    require_counts: bool = False,
    max_memory_bytes: Optional[int] = None,
    strict: bool = False,
    analyzer: Any = None,
    **limits: Any,
) -> Any:
    """The dry-run :class:`~cqhecs.execution_plan.ExecutionPlan`. Allocates no simulator state."""
    from cqhecs.execution_plan import build_execution_plan

    circuit = resolve_circuit_source(source, strict=strict) if isinstance(source, str) else source
    kwargs: Dict[str, Any] = dict(
        forced_path=normalize_force_path(force_path),
        require_counts=bool(require_counts),
        max_memory_bytes=max_memory_bytes,
    )
    if analyzer is not None:
        kwargs["analyzer"] = analyzer
    kwargs.update(limits)
    return build_execution_plan(circuit, **kwargs)


def plan_document(source: Any, **kwargs: Any) -> Dict[str, Any]:
    """The dry-run ExecutionPlan as a plain dict (see :func:`plan_object`)."""
    return plan_object(source, **kwargs).to_dict()


# ---------------------------------------------------------------------------------------------
# Quantum Gravity lab (T6-01, W12): plan envelope, local documents, typed refusals for paid paths.
# Local, exact, credential-free, no network. Surfaces keep only their own envelope.
# ---------------------------------------------------------------------------------------------

QG_THETA_BOUND = 6.2832
QG_MAX_STEPS = 64
QG_MAX_T = 50.0
QG_MAX_SEED = 2**31 - 1
QG_MAX_LATTICE = 4  # rows/cols; the dense ceiling in gauge.py (8 links) is enforced on top

#: experiment id -> parameter name -> (kind, low, high, default). Closed set: unknown keys are refused.
QG_EXPERIMENT_PARAMS: Dict[str, Dict[str, Any]] = {
    "bmv": {
        "theta": ("float", -QG_THETA_BOUND, QG_THETA_BOUND, 0.0),
        "local_phase_a": ("float", -QG_THETA_BOUND, QG_THETA_BOUND, 0.0),
        "local_phase_b": ("float", -QG_THETA_BOUND, QG_THETA_BOUND, 0.0),
    },
    "syk": {
        "n": ("int", 2, 8, 4),
        "seed": ("int", 0, QG_MAX_SEED, 20260101),
        "scale": ("float", 1e-6, 10.0, 0.5),
        "t": ("float", 0.0, QG_MAX_T, 1.0),
        "steps": ("int", 1, QG_MAX_STEPS, 1),
    },
    "gauge": {
        "rows": ("int", 1, QG_MAX_LATTICE, 1),
        "cols": ("int", 1, QG_MAX_LATTICE, 1),
        "t": ("float", 0.0, QG_MAX_T, 0.5),
        "steps": ("int", 1, QG_MAX_STEPS, 1),
    },
}
QG_EXPERIMENT_TITLES = {
    "bmv": "BMV effective two-probe phase model (2 qubits, exact)",
    "syk": "Finite-N SYK (q=4) Trotter circuit (<= 8 qubits)",
    "gauge": "Bounded Z2 lattice gauge toy (<= 8 links)",
}
QG_OPERATIONS = {
    "bmv": ["validate", "preview", "run-local", "plan", "compare", "export"],
    "syk": ["validate", "plan", "export"],
    "gauge": ["validate", "plan", "export"],
}
#: Paid Open Quantum actions. Every one is refused here; the only code that may quote, submit or
#: spend is ``scripts/run_qg_openquantum_campaign.py`` and it owns the one ledger.
QG_PAID_ACTIONS = ("discover", "quote", "submit", "status", "results")
QG_SPEND_LEDGER = "research/qg_2026/JOB_LEDGER.jsonl"


def _qg_number(params: Mapping[str, Any], key: str, spec: Tuple[Any, ...]) -> Any:
    kind, low, high, default = spec
    value = params.get(key, default)
    if value is None:
        value = default
    if isinstance(value, bool):
        raise ServiceError(f"{key} must be a {kind}", code="invalid_parameter")
    try:
        number: Any = int(value) if kind == "int" else float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ServiceError(f"{key} must be a {kind}", code="invalid_parameter") from exc
    if kind == "int" and isinstance(value, float) and value != number:
        raise ServiceError(f"{key} must be an integer", code="invalid_parameter")
    if number != number or number in (float("inf"), float("-inf")) or not (low <= number <= high):
        raise ServiceError(f"{key} must be finite and in [{low}, {high}]", code="invalid_parameter")
    return number


def qg_experiment_params(experiment: Any, params: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Validate and default the parameters of one QG experiment. Unknown keys are refused."""
    if experiment not in QG_EXPERIMENT_PARAMS:
        raise ServiceError(
            f"experiment must be one of {sorted(QG_EXPERIMENT_PARAMS)}",
            code="unknown_experiment", status=404,
        )
    params = dict(params or {})
    spec = QG_EXPERIMENT_PARAMS[experiment]
    unknown = sorted(set(params) - set(spec))
    if unknown:
        raise ServiceError(f"unknown parameter(s) {unknown} for {experiment!r}", code="invalid_parameter")
    return {key: _qg_number(params, key, spec[key]) for key in spec}


def _qg_plan_object(experiment: str, p: Mapping[str, Any], **plan_kwargs: Any) -> Any:
    from cqhecs.quantum_gravity.errors import QGError, QGResourceError
    from cqhecs.quantum_gravity import plan as qgplan

    try:
        if experiment == "bmv":
            if p["local_phase_a"] or p["local_phase_b"]:
                raise ServiceError(
                    "the BMV plan covers the bare coupling circuit; local phases are not planned",
                    code="invalid_parameter",
                )
            return qgplan.bmv_execution_plan(p["theta"], **plan_kwargs)
        if experiment == "syk":
            from cqhecs.quantum_gravity.hamiltonians import build_syk

            syk = build_syk(p["n"], seed=p["seed"], scale=p["scale"])
            return qgplan.syk_execution_plan(syk, p["t"], p["steps"], **plan_kwargs)
        from cqhecs.quantum_gravity.gauge import Z2Lattice

        return qgplan.gauge_execution_plan(Z2Lattice(p["rows"], p["cols"]), p["t"], p["steps"], **plan_kwargs)
    except QGResourceError as exc:
        raise ServiceError(str(exc), code="resource_limit", status=422) from exc
    except QGError as exc:
        raise ServiceError(str(exc), code="invalid_experiment", status=422) from exc


def qg_plan_document(
    experiment: Any,
    params: Optional[Mapping[str, Any]] = None,
    *,
    force_path: Optional[str] = None,
    require_counts: bool = True,
    max_memory_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    """The QG plan envelope (``cqhecs.qg.execution_plan/1``) plus its digest; identical on every surface."""
    p = qg_experiment_params(experiment, params)
    plan = _qg_plan_object(
        experiment, p,
        forced_path=normalize_force_path(force_path),
        require_counts=bool(require_counts),
        max_memory_bytes=max_memory_bytes,
    )
    return {"qg_plan": plan.to_dict(), "digest": plan.digest(), "parameters": p}


def qg_experiments_document() -> Dict[str, Any]:
    """Experiment templates with their parameter ranges and the operations each supports."""
    return {
        "schema": "cqhecs.qg.experiments.v1",
        "experiments": [
            {
                "experiment_id": key,
                "title": QG_EXPERIMENT_TITLES[key],
                "operations": list(QG_OPERATIONS[key]),
                "parameters": {
                    name: {"type": kind, "minimum": low, "maximum": high, "default": default}
                    for name, (kind, low, high, default) in spec.items()
                },
            }
            for key, spec in QG_EXPERIMENT_PARAMS.items()
        ],
        "network": "none",
        "spend_credits": 0.0,
    }


def qg_backends_document(*, credentials_present: bool = False) -> Dict[str, Any]:
    """Execution surfaces and whether this local build can use them. Never reveals a credential value."""
    from cqhecs.quantum_gravity.catalog import EXECUTION_SURFACES, PHYSICAL_SURFACES

    available = {"CLASSICAL_REFERENCE": "model reference (dense exact, <= 8 qubits)",
                 "CQ_HECS_CPU": "classical Paths A-D via the router"}
    rows = []
    for surface in EXECUTION_SURFACES:
        if surface in available:
            rows.append({"surface": surface, "status": "AVAILABLE", "detail": available[surface],
                         "physical": False})
        elif surface in ("OPENQUANTUM_SIMULATOR", "OPENQUANTUM_QPU"):
            rows.append({
                "surface": surface, "status": "UNAVAILABLE",
                "detail": "paid/remote surface; not reachable from the local API or MCP",
                "physical": surface in PHYSICAL_SURFACES,
            })
        else:
            rows.append({"surface": surface, "status": "NOT_LOCAL",
                         "detail": "browser, native Vulkan, recorded or fixture surface; not run by this API",
                         "physical": surface in PHYSICAL_SURFACES})
    return {
        "schema": "cqhecs.qg.backends.v1",
        "backends": rows,
        "credentials_present": bool(credentials_present),
        "network": "none",
        "spend_credits": 0.0,
    }


def qg_paid_refusal(action: str) -> Dict[str, Any]:
    """Typed refusal for every Open Quantum action. Spends nothing, contacts nothing, hides nothing."""
    if action not in QG_PAID_ACTIONS:
        raise ServiceError(f"action must be one of {list(QG_PAID_ACTIONS)}", code="unknown_action", status=404)
    return {
        "schema": "cqhecs.qg.paid_refusal.v1",
        "status": "UNAVAILABLE",
        "code": "QG_PAID_PATH_UNAVAILABLE",
        "action": action,
        "reason": (
            "Open Quantum quote, submit, status and results are not served by the local API or MCP. "
            "Quote and submit are separate steps in scripts/run_qg_openquantum_campaign.py, which "
            "needs explicit authorisation, a quoted preparation and the 25-Spark ceiling."
        ),
        "spend_ledger": QG_SPEND_LEDGER,
        "ledger_writer": "scripts/run_qg_openquantum_campaign.py (the only writer)",
        "spend_credits": 0.0,
        "network": "none",
    }


def qg_preview_document(theta: float) -> Dict[str, Any]:
    from cqhecs.quantum_gravity.circuits import bmv_qasm, sha256_text

    qasm = bmv_qasm(theta)
    return {
        "status": "OK",
        "execution_surface": "CLASSICAL_REFERENCE",
        "spend_credits": 0.0,
        "network": "none",
        "qubits": 2,
        "qasm": qasm,
        "qasm_sha256": sha256_text(qasm),
    }


def qg_run_local_document(theta: float, local_phase_a: float = 0.0, local_phase_b: float = 0.0) -> Dict[str, Any]:
    from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel

    model = BMVEffectivePhaseModel(theta=theta, local_phase_a=local_phase_a, local_phase_b=local_phase_b)
    state = model.state()
    return {
        "status": "COMPLETED",
        "execution_surface": "CLASSICAL_REFERENCE",
        "precision": "f64",
        "qubits": 2,
        "bit_order": "q0q1 (q0 most significant)",
        "probabilities": {format(i, "02b"): float(abs(state[i]) ** 2) for i in range(4)},
        "observables": {
            "concurrence": model.concurrence(),
            "negativity": model.negativity(),
            "entanglement_entropy": model.entropy(),
            "chsh_max": model.chsh_max(),
        },
        "limitations": ["finite two-qubit model; not a gravitational measurement"],
    }


def qg_validate_document(experiment: Any, params: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Validate a model instance and return its manifest (no execution)."""
    from cqhecs.quantum_gravity.errors import QGError, QGResourceError

    p = qg_experiment_params(experiment, params)
    try:
        if experiment == "bmv":
            from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel

            model = BMVEffectivePhaseModel(
                theta=p["theta"], local_phase_a=p["local_phase_a"], local_phase_b=p["local_phase_b"]
            )
            return {
                "status": "OK", "experiment_id": "bmv", "execution_surface": "CLASSICAL_REFERENCE",
                "model": model.manifest(),
                "concurrence_oracle": model.analytic_concurrence(),
                "entangling_phase": model.entangling_phase_invariant(),
            }
        if experiment == "syk":
            from cqhecs.quantum_gravity.hamiltonians import build_syk

            return {"status": "OK", "experiment_id": "syk", "execution_surface": "CLASSICAL_REFERENCE",
                    "model": build_syk(p["n"], seed=p["seed"], scale=p["scale"]).manifest()}
        from cqhecs.quantum_gravity.gauge import Z2Lattice

        return {"status": "OK", "experiment_id": "gauge", "execution_surface": "CLASSICAL_REFERENCE",
                "model": Z2Lattice(p["rows"], p["cols"]).manifest()}
    except QGResourceError as exc:
        raise ServiceError(str(exc), code="resource_limit", status=422) from exc
    except QGError as exc:
        raise ServiceError(str(exc), code="invalid_experiment", status=422) from exc


def qg_compare_document(theta: float, *, shots: int = 4096, seed: int = 42) -> Dict[str, Any]:
    """Compare the exact BMV reference with the CQ-HECS router on the same QASM, separate provenance.

    Z-basis probabilities of this circuit do not depend on theta (the interaction is a ZZ phase), so this
    checks engine agreement on the circuit; it is not an entanglement measurement.
    """
    from cqhecs.quantum_gravity.circuits import bmv_qasm, sha256_text
    from cqhecs.router import EntanglementAdaptiveRouter

    if not (1 <= int(shots) <= 20000):
        raise ServiceError("shots must be in [1, 20000]", code="invalid_parameter")
    reference = qg_run_local_document(theta)
    qasm = bmv_qasm(theta)
    result = EntanglementAdaptiveRouter().route_and_execute(qasm, shots=int(shots), seed=int(seed))
    payload = result.to_dict()
    probs = payload.get("probabilities")
    counts = payload.get("counts")
    if probs is None and counts:
        total = float(sum(counts.values()))
        probs = {k: v / total for k, v in counts.items()}
        basis = "finite-shot counts"
    else:
        basis = "exact probabilities"
    entry: Dict[str, Any] = {
        "surface": "CQ_HECS_CPU", "path": payload.get("path"), "state": payload.get("state"),
        "probabilities": probs, "probability_basis": basis if probs else None,
        "qasm_sha256": sha256_text(qasm), "seed": int(seed), "shots": int(shots),
    }
    tv = None
    if probs is not None:
        keys = set(probs) | set(reference["probabilities"])
        tv = 0.5 * sum(abs(float(probs.get(k, 0.0)) - reference["probabilities"].get(k, 0.0)) for k in keys)
    return {
        "schema": "cqhecs.qg.compare.v1",
        "status": "COMPLETED" if tv is not None else "UNRESOLVED",
        "theta": theta,
        "sources": {
            "reference": {"surface": "CLASSICAL_REFERENCE", "probabilities": reference["probabilities"]},
            "cq_hecs": entry,
            "openquantum_simulator": {"surface": "OPENQUANTUM_SIMULATOR", "status": "NOT_COMPARED",
                                      "reason": "no live job from the local API"},
            "openquantum_qpu": {"surface": "OPENQUANTUM_QPU", "status": "NOT_COMPARED",
                                "reason": "recorded evidence is listed by the evidence route; never mixed in here"},
        },
        "total_variation_reference_vs_cq_hecs": tv,
        "limitations": [
            "Z-basis marginals are theta-independent for this circuit; agreement shows the engines match, "
            "it does not witness entanglement",
            "a TV from finite-shot counts carries sampling noise of order 1/sqrt(shots)",
            "model quantity, not a gravity measurement",
        ],
        "network": "none",
        "spend_credits": 0.0,
    }


def qg_export_document(experiment: Any, params: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """A reproducible, secret-free bundle: validated parameters, plan, plan digest and the bundle digest."""
    import hashlib
    import json

    p = qg_experiment_params(experiment, params)
    planned = qg_plan_document(experiment, p)
    bundle: Dict[str, Any] = {
        "schema": "cqhecs.qg.export.v1",
        "experiment_id": experiment,
        "parameters": p,
        "validation": qg_validate_document(experiment, p),
        "qg_plan": planned["qg_plan"],
        "qg_plan_digest": planned["digest"],
        "limitations": ["model quantity, not a gravity measurement", "no QPU job planned, quoted or implied"],
        "network": "none",
        "spend_credits": 0.0,
    }
    if experiment == "bmv":
        bundle["preview"] = qg_preview_document(p["theta"])
        bundle["local_run"] = qg_run_local_document(p["theta"], p["local_phase_a"], p["local_phase_b"])
    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str)
    bundle["bundle_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return bundle


# ---------------------------------------------------------------------------------------------
# analyze --explain on the service, and calibration v3 policy (W12).
# ---------------------------------------------------------------------------------------------


def analysis_document(circuit: Any, *, explain: bool = False, **plan_kwargs: Any) -> Dict[str, Any]:
    """Static analysis, plus the dry-run plan when ``explain`` or any planning option is given."""
    from cqhecs.circuit_analyzer import CircuitAnalyzer

    props = CircuitAnalyzer().analyze(circuit)
    document: Dict[str, Any] = {"analysis": props.to_dict()}
    if explain or plan_kwargs.get("force_path") or plan_kwargs.get("require_counts") or plan_kwargs.get(
        "max_memory_bytes"
    ):
        document["plan"] = plan_document(circuit, **plan_kwargs)
    return document


def calibration_provenance(calibration: Any, *, policy: str = "warn", instructions: Any = None) -> Dict[str, Any]:
    """Provenance label, freshness and the uncovered-gate verdict of a v3 calibration, for display.

    ``policy`` is ``refuse | warn | ideal``; ``refuse`` raises
    :class:`cqhecs.calibration_v3.UncalibratedGateError`. The label and freshness are reported as
    recorded (never defaulted to measured or fresh).
    """
    from cqhecs.calibration_v3 import POLICIES, SCHEMA_V3

    if policy not in POLICIES:
        raise ServiceError(f"uncovered-gate policy must be one of {list(POLICIES)}", code="invalid_policy")
    document: Dict[str, Any] = {
        "schema": SCHEMA_V3,
        "backend_identity": calibration.backend_identity,
        "provenance_label": calibration.provenance_label,
        "calibration_timestamp": calibration.profile.capture_timestamp,
        "freshness": calibration.freshness(),
        "gate_policy": policy,
    }
    if instructions is not None:
        document["gate_coverage"] = calibration.check_gates(instructions, policy)
    return document


def load_calibration(data: Any) -> Any:
    """A :class:`CalibrationV3` from a v3 record, or (additively) from an unchanged v1/v2 profile.

    A v1/v2 file is wrapped without being rewritten; its provenance label is ``synthetic`` if the profile
    says so and ``unknown`` otherwise, never ``measured`` by default.
    """
    from cqhecs.calibration_v3 import SCHEMA_V3, CalibrationV3
    from cqhecs.hardware_bridge import BackendProfile, InvalidProfileError

    if not isinstance(data, Mapping):
        raise ServiceError("calibration must be a JSON object", code="invalid_calibration")
    try:
        if data.get("schema") == SCHEMA_V3:
            return CalibrationV3.from_dict(data)
        source = data["profile"] if isinstance(data.get("profile"), Mapping) else data
        return CalibrationV3.from_profile(BackendProfile.from_dict(dict(source)))
    except (InvalidProfileError, KeyError, TypeError, ValueError) as exc:
        raise ServiceError(f"invalid calibration: {exc}", code="invalid_calibration") from exc


def run_with_calibration(
    circuit: Any, data: Any, *, policy: str = "warn", shots: int = 1024, seed: int = 42
) -> Tuple[Any, Dict[str, Any]]:
    """Noisy classical run under a calibration, with the uncovered-gate policy enforced up front.

    Returns ``(result, provenance)``; the provenance (label, freshness, gate coverage) is also stored in
    ``result.metadata['calibration_v3']``. Under ``refuse`` a circuit with uncalibrated gates is a typed
    :class:`ServiceError` (``uncalibrated_gates``) before any simulation.
    """
    from cqhecs.calibration_v3 import POLICIES, UncalibratedGateError
    from cqhecs.circuit_parsing import parse_circuit
    from cqhecs.hardware_bridge import FakeHardwareBackend, HardwareBridgeError

    if policy not in POLICIES:
        raise ServiceError(f"uncovered-gate policy must be one of {list(POLICIES)}", code="invalid_policy")
    calibration = load_calibration(data)
    instructions, _ = parse_circuit(circuit)
    try:
        provenance = calibration_provenance(calibration, policy=policy, instructions=instructions)
        result = FakeHardwareBackend(calibration.profile, uncovered_gate_policy=policy).run(
            circuit, shots=shots, seed=seed
        )
    except UncalibratedGateError as exc:
        raise ServiceError(str(exc), code="uncalibrated_gates", status=422) from exc
    except HardwareBridgeError as exc:
        raise ServiceError(str(exc), code="hardware_refused", status=422) from exc
    result.metadata["calibration_v3"] = provenance
    return result, provenance


def doctor_report(schema_version: str = "1.0") -> Dict[str, Any]:
    """The execution-environment report shared by ``cq-hecs doctor`` and Studio ``/api/diagnostics``.

    Distinguishes not installed / not available / failed instead of collapsing them. ``report["failed"]``
    is true when a probe itself failed (the CLI maps that to its environment exit code). Nothing is run
    on a GPU here; the report says which components could be loaded, not that they were exercised.
    """
    import platform
    import sys

    report: Dict[str, Any] = {
        "schema_version": schema_version,
        "version": __import__("cqhecs").__version__,
        "os": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "components": {},
    }
    failed = False

    def record(name: str, status: str, detail: str = "", **extra: Any) -> None:
        report["components"][name] = {"status": status, "detail": detail, **extra}
        nonlocal failed
        if status == "failed":
            failed = True

    # Optional Python dependencies
    for module, label in (
        ("numpy", "numpy"),
        ("qiskit", "qiskit"),
        ("qiskit_aer", "qiskit-aer"),
        ("stim", "stim"),
    ):
        try:
            mod = __import__(module)
            record(label, "available", getattr(mod, "__version__", "unknown"))
        except ImportError:
            record(label, "not_installed", f"optional dependency '{module}' missing")

    # Optional SAT solver adapter
    try:
        from cqhecs import sat_external

        if sat_external.available():
            record("sat_solver", "available", sat_external.backend_version())
        else:
            record("sat_solver", "not_available", "python-sat is not installed; pip install cqhecs[sat]")
    except Exception as exc:  # noqa: BLE001 - report, never crash doctor
        record("sat_solver", "failed", f"{type(exc).__name__}: {exc}")

    # Native binding
    try:
        import cqhecs.backends.path_a_stabilizer as path_a

        if path_a._native is not None:
            record(
                "native_binding", "available",
                getattr(path_a._native, "__file__", "built-in"),
                version=getattr(path_a._native, "__version__", None),
            )
        else:
            record(
                "native_binding", "not_available",
                "_cqhecs_core could not be imported; Python fallbacks will be used",
            )
    except Exception as exc:  # pragma: no cover - defensive
        record("native_binding", "failed", str(exc))

    # Vulkan: loader, then physical devices
    try:
        import ctypes

        vulkan_ok = False
        for dll in ("vulkan-1.dll", "libvulkan.so.1", "libvulkan.dylib"):
            try:
                ctypes.CDLL(dll)
                vulkan_ok = True
                record("vulkan_loader", "available", f"loaded {dll}")
                break
            except OSError:
                continue
        if not vulkan_ok:
            record("vulkan_loader", "not_available", "no Vulkan loader found on PATH")
    except Exception as exc:  # pragma: no cover - defensive
        record("vulkan_loader", "failed", str(exc))

    # Backend capability matrix
    try:
        from cqhecs.router import EntanglementAdaptiveRouter
        report["backends"] = {
            path: sorted(gates)
            for path, gates in EntanglementAdaptiveRouter.PATH_CAPABILITIES.items()
        }
    except Exception as exc:  # pragma: no cover - defensive
        record("backends", "failed", str(exc))

    # Vulkan compute is exercised only through the native engine; this Python
    # path does not dispatch work to a GPU, so it is reported as not exercised.
    report["notes"] = [
        "The Python backends run on CPU. Vulkan acceleration, when present, is "
        "exercised only by the native _cqhecs_core engine.",
        "No statement is made here about physical GPU verification.",
    ]

    report["failed"] = failed
    return report
