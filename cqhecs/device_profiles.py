"""
Measured device noise profiles (M-FIT-2) for arbitrary circuits.

The profiles live in ``cqhecs/studio/data/device_profiles.json``, written by
``scripts/export_device_profiles.py`` from the committed QPU evidence. A
profile becomes a :class:`~cqhecs.hardware_bridge.NoiseModel` for any circuit:

* readout: per-qubit asymmetric ``p01`` (read 1 on |0>) and ``p10`` (read 0 on
  |1>). Qubits beyond the measured ones reuse the mean measured value, which is
  an extrapolation and is reported as such;
* ``x`` gates: a bit-flip channel on qubits with a fitted X anomaly;
* every ``cx`` pair: two-qubit depolarizing with the readout-corrected rate.

For the measured qubits on the suite circuits, this is exactly the M-FIT-2
model that the evaluation scored.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from statistics import fmean
from typing import Any, Dict, List, Sequence

from cqhecs.hardware_bridge import BitFlipChannel, NoiseModel, TwoQubitDepolarizingChannel

PROFILE_FILE = "device_profiles.json"


class UnknownDeviceProfileError(KeyError):
    """Raised for a profile id that is not in the bundled file."""


@lru_cache(maxsize=1)
def _document() -> Dict[str, Any]:
    text = resources.files("cqhecs.studio").joinpath("data", PROFILE_FILE).read_text("utf-8")
    return json.loads(text)


def list_profiles() -> List[Dict[str, Any]]:
    """All bundled profiles, in file order."""
    return list(_document()["profiles"])


def get_profile(profile_id: str) -> Dict[str, Any]:
    for profile in _document()["profiles"]:
        if profile["id"] == profile_id:
            return profile
    known = ", ".join(p["id"] for p in _document()["profiles"])
    raise UnknownDeviceProfileError(f"unknown device profile '{profile_id}'; known: {known}")


def readout_for(profile: Dict[str, Any], num_qubits: int) -> Dict[str, List[float]]:
    """Per-qubit readout and X-flip for ``num_qubits``; extrapolated qubits use the mean."""
    p01, p10, xf = list(profile["p01"]), list(profile["p10"]), list(profile["x_bitflip"])
    mean01, mean10 = fmean(p01), fmean(p10)
    extra = max(0, num_qubits - len(p01))
    return {
        "p01": (p01 + [mean01] * extra)[:num_qubits],
        "p10": (p10 + [mean10] * extra)[:num_qubits],
        # An X anomaly is a property of a specific physical qubit; it is not extrapolated.
        "x_bitflip": (xf + [0.0] * extra)[:num_qubits],
        "extrapolated_qubits": list(range(len(profile["p01"]), num_qubits)),
    }


def noise_model(profile_id: str, instructions: Sequence[Any], num_qubits: int) -> NoiseModel:
    """Build the M-FIT-2 noise model of ``profile_id`` for one circuit."""
    profile = get_profile(profile_id)
    ro = readout_for(profile, num_qubits)
    model = NoiseModel(name=f"device:{profile_id} (M-FIT-2)")
    model.metadata = {
        "profile": profile_id,
        "backend": profile["backend"],
        "extrapolated_qubits": ro["extrapolated_qubits"],
        "evidence": profile["evidence"],
    }
    cx = float(profile["cx_depolarizing"])
    if cx > 0.0:
        for pair in sorted({tuple(ins[1]) for ins in instructions if ins[0] == "cx"}):
            model.add_2q_channel("cx", pair, TwoQubitDepolarizingChannel(cx))
    for qubit in range(num_qubits):
        model.set_readout_error(qubit, ro["p01"][qubit], ro["p10"][qubit])
        if ro["x_bitflip"][qubit] > 0.0:
            model.add_1q_channel("x", qubit, BitFlipChannel(ro["x_bitflip"][qubit]))
    model.validate()
    return model


def summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Compact, display-oriented view used by the CLI, Studio and MCP."""
    v = profile["validation"]
    return {
        "id": profile["id"],
        "vendor": profile["vendor"],
        "label": profile["label"],
        "measured_qubits": profile["measured_qubits"],
        "shots_per_circuit": profile["shots_per_circuit"],
        "cx_depolarizing": profile["cx_depolarizing"],
        "mean_p01": fmean(profile["p01"]),
        "mean_p10": fmean(profile["p10"]),
        "x_anomaly_qubits": [q for q, f in enumerate(profile["x_bitflip"]) if f > 0.0],
        "h_v3_8": v["h_v3_8"],
        "m_fit_2_vs_ideal_median": v["m_fit_2_vs_ideal_median"],
    }
