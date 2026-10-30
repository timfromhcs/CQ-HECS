"""
Import of real device calibration snapshots into :class:`BackendProfile`.

Supported source: IBM Quantum ``BackendProperties`` / ``BackendConfiguration``
JSON as shipped in ``qiskit_ibm_runtime/fake_provider/backends/<name>/``
(``props_<name>.json`` and ``conf_<name>.json``). These are real calibration
exports with a ``last_update_date``; they describe the device at that time,
not today.

Nothing in the source is clipped, guessed or silently dropped:

* a gate error the noise model cannot represent (IBM reports ``1.0`` for
  non-operational gates) is listed in ``calibration_flags["non_operational"]``;
* missing or physically inconsistent T1/T2 (``T2 > 2 T1`` occurs in real fits)
  is listed in ``calibration_flags["relaxation_excluded"]`` and the raw values
  are kept there;
* reported operations without a noise channel here (``measure``, ``reset``,
  vendor-specific names) are listed in ``calibration_flags["not_modelled"]``;
* an unknown unit or a non-finite number refuses the whole import.

The fake backend then refuses circuits that touch flagged qubits or pairs.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cqhecs.gate_manifest import get_gate
from cqhecs.hardware_bridge import BackendProfile, InvalidProfileError

#: Readout conventions. ``asymmetric`` uses ``prob_meas1_prep0`` and
#: ``prob_meas0_prep1`` (what was measured); ``symmetric`` uses
#: ``readout_error`` for both, which is what Qiskit Aer's
#: ``NoiseModel.from_backend`` does for a BackendV2 target.
READOUT_MODELS = ("asymmetric", "symmetric")

_TIME_TO_US = {"us": 1.0, "µs": 1.0, "ns": 1e-3, "ms": 1e3, "s": 1e6}
_TIME_TO_NS = {"ns": 1.0, "us": 1e3, "µs": 1e3, "ms": 1e6, "s": 1e9}


def _number(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InvalidProfileError(f"{what} must be a finite number, got {value!r}")
    return float(value)


def _convert(value: Any, unit: str, table: Dict[str, float], what: str) -> float:
    if unit not in table:
        raise InvalidProfileError(f"{what} has unsupported unit {unit!r}")
    return _number(value, what) * table[unit]


def profile_from_ibm_properties(
    props: Dict[str, Any],
    conf: Dict[str, Any],
    *,
    provenance_uri: str,
    source_sha256: Optional[str] = None,
    readout: str = "asymmetric",
) -> BackendProfile:
    """
    Builds a non-synthetic schema-2.0 profile from IBM properties/configuration.

    Args:
        props: parsed ``props_<name>.json``.
        conf: parsed ``conf_<name>.json`` (coupling map, basis gates, width).
        provenance_uri: where the data came from (required for real data).
        source_sha256: SHA-256 of the properties file, if known.
        readout: one of :data:`READOUT_MODELS`.

    Raises:
        InvalidProfileError: For missing fields, unknown units, non-finite
            values or a backend-name mismatch between the two files.
    """
    if readout not in READOUT_MODELS:
        raise InvalidProfileError(f"readout must be one of {READOUT_MODELS}, got {readout!r}")
    for key in ("backend_name", "last_update_date", "qubits", "gates"):
        if key not in props:
            raise InvalidProfileError(f"properties lack {key!r}")
    for key in ("backend_name", "n_qubits", "coupling_map", "basis_gates"):
        if key not in conf:
            raise InvalidProfileError(f"configuration lacks {key!r}")
    if props["backend_name"] != conf["backend_name"]:
        raise InvalidProfileError(
            f"properties are for {props['backend_name']!r}, configuration for {conf['backend_name']!r}"
        )
    num_qubits = conf["n_qubits"]
    if len(props["qubits"]) != num_qubits:
        raise InvalidProfileError(
            f"properties list {len(props['qubits'])} qubits, configuration {num_qubits}"
        )

    t1_us: Dict[int, float] = {}
    t2_us: Dict[int, float] = {}
    readout_errors: Dict[int, Tuple[float, float]] = {}
    relaxation_excluded: Dict[int, Any] = {}
    for q, entries in enumerate(props["qubits"]):
        values: Dict[str, float] = {}
        for entry in entries:
            name = entry.get("name")
            unit = entry.get("unit", "")
            if name in ("T1", "T2"):
                values[name] = _convert(entry.get("value"), unit, _TIME_TO_US, f"{name} of qubit {q}")
            elif name in ("readout_error", "prob_meas1_prep0", "prob_meas0_prep1"):
                values[name] = _number(entry.get("value"), f"{name} of qubit {q}")
        t1, t2 = values.get("T1"), values.get("T2")
        if t1 is None or t2 is None:
            relaxation_excluded[q] = {"reason": "T1 or T2 not reported", "T1_us": t1, "T2_us": t2}
        elif t1 <= 0.0 or t2 <= 0.0 or t2 > 2.0 * t1:
            relaxation_excluded[q] = {"reason": "T2 > 2*T1 or non-positive", "T1_us": t1, "T2_us": t2}
        else:
            t1_us[q], t2_us[q] = t1, t2
        if readout == "asymmetric" and "prob_meas1_prep0" in values and "prob_meas0_prep1" in values:
            readout_errors[q] = (values["prob_meas1_prep0"], values["prob_meas0_prep1"])
        elif "readout_error" in values:
            readout_errors[q] = (values["readout_error"], values["readout_error"])

    gate_errors: Dict[str, Dict[Tuple[int, ...], float]] = {}
    durations: Dict[str, Dict[Tuple[int, ...], float]] = {}
    non_operational: List[Dict[str, Any]] = []
    not_modelled: List[Dict[str, Any]] = []
    for gate_entry in props["gates"]:
        gate = str(gate_entry.get("gate", "")).lower()
        qubits = tuple(int(q) for q in gate_entry.get("qubits", []))
        params = {p.get("name"): p for p in gate_entry.get("parameters", [])}
        spec = get_gate(gate)
        if spec is None or spec.measurement or spec.reset or spec.barrier or spec.arity != len(qubits) \
                or len(qubits) not in (1, 2):
            not_modelled.append({"gate": gate, "qubits": list(qubits)})
            continue
        if "gate_error" not in params:
            not_modelled.append({"gate": gate, "qubits": list(qubits)})
            continue
        error = _number(params["gate_error"].get("value"), f"gate_error of {gate}{list(qubits)}")
        d = 1 << len(qubits)
        if not (0.0 <= error <= (d - 1) / d):
            non_operational.append({"gate": gate, "qubits": list(qubits), "gate_error": error})
            continue
        gate_errors.setdefault(gate, {})[qubits] = error
        if "gate_length" in params:
            length = params["gate_length"]
            durations.setdefault(gate, {})[qubits] = _convert(
                length.get("value"), length.get("unit", ""), _TIME_TO_NS, f"gate_length of {gate}{list(qubits)}"
            )

    flags: Dict[str, Any] = {}
    if non_operational:
        flags["non_operational"] = non_operational
    if relaxation_excluded:
        flags["relaxation_excluded"] = relaxation_excluded
    if not_modelled:
        flags["not_modelled"] = not_modelled

    return BackendProfile(
        name=str(props["backend_name"]),
        num_qubits=int(num_qubits),
        schema_version="2.0",
        provider_name="IBM Quantum (calibration snapshot)",
        capture_timestamp=str(props["last_update_date"]),
        provenance_uri=provenance_uri,
        is_synthetic=False,
        basis_gates=[str(g) for g in conf["basis_gates"]] + ["measure"],
        # A single-qubit device reports ``coupling_map: null``.
        coupling_map=[(int(a), int(b)) for a, b in (conf["coupling_map"] or [])],
        gate_errors=gate_errors,
        gate_durations_ns=durations,
        readout_errors=readout_errors,
        t1_us=t1_us,
        t2_us=t2_us,
        dynamic_circuit_features={},
        calibration_flags=flags,
        source_sha256=source_sha256,
    )


def load_ibm_snapshot_files(props_path: Path, conf_path: Path, *, provenance_uri: str,
                            readout: str = "asymmetric") -> BackendProfile:
    """Reads the two JSON files, hashes the properties file and imports them."""
    raw = Path(props_path).read_bytes()
    return profile_from_ibm_properties(
        json.loads(raw),
        json.loads(Path(conf_path).read_text(encoding="utf-8")),
        provenance_uri=provenance_uri,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        readout=readout,
    )


def load_qiskit_ibm_runtime_snapshot(name: str, readout: str = "asymmetric") -> BackendProfile:
    """
    Imports ``props_<name>.json`` from an installed ``qiskit-ibm-runtime``.

    ``qiskit-ibm-runtime`` is optional and only read as a data source.

    Raises:
        ImportError: If the package is not installed.
        FileNotFoundError: If it ships no snapshot of that name.
    """
    import importlib.metadata
    import importlib.util

    spec = importlib.util.find_spec("qiskit_ibm_runtime")
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("qiskit-ibm-runtime is not installed")
    root = Path(list(spec.submodule_search_locations)[0])
    folder = root / "fake_provider" / "backends" / name
    props = folder / f"props_{name}.json"
    conf = folder / f"conf_{name}.json"
    if not props.is_file() or not conf.is_file():
        raise FileNotFoundError(f"qiskit-ibm-runtime has no calibration snapshot {name!r}")
    version = importlib.metadata.version("qiskit-ibm-runtime")
    uri = f"pypi:qiskit-ibm-runtime=={version}#qiskit_ibm_runtime/fake_provider/backends/{name}/props_{name}.json"
    return load_ibm_snapshot_files(props, conf, provenance_uri=uri, readout=readout)


def available_qiskit_ibm_runtime_snapshots() -> List[str]:
    """Names of the snapshots shipped by the installed qiskit-ibm-runtime."""
    import importlib.util

    spec = importlib.util.find_spec("qiskit_ibm_runtime")
    if spec is None or not spec.submodule_search_locations:
        return []
    folder = Path(list(spec.submodule_search_locations)[0]) / "fake_provider" / "backends"
    return sorted(p.parent.name for p in folder.glob("*/props_*.json") if p.name == f"props_{p.parent.name}.json")
