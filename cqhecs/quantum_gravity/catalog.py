"""Capability catalog: execution surfaces and method cards.

Every result in the Quantum Gravity lab must carry one :class:`ExecutionSurface`, so a
reader can never confuse an ideal classical reference with a real hardware measurement.
The categories are exactly the ones mandated by ``QGRAVITY.md`` section 0.2.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple


class ExecutionSurface(str, Enum):
    """The nine irreducible execution categories. Never merge these without new provenance."""

    CLASSICAL_REFERENCE = "CLASSICAL_REFERENCE"
    CQ_HECS_CPU = "CQ_HECS_CPU"
    CQ_HECS_VULKAN = "CQ_HECS_VULKAN"
    WEB_WASM_F64 = "WEB_WASM_F64"
    WEBGPU_F32 = "WEBGPU_F32"
    OPENQUANTUM_SIMULATOR = "OPENQUANTUM_SIMULATOR"
    OPENQUANTUM_QPU = "OPENQUANTUM_QPU"
    MODEL_PREDICTION = "MODEL_PREDICTION"
    SYNTHETIC_OR_FIXTURE = "SYNTHETIC_OR_FIXTURE"


EXECUTION_SURFACES: Tuple[str, ...] = tuple(surface.value for surface in ExecutionSurface)

#: Surfaces that represent a physical measurement (as opposed to a model/classical value).
PHYSICAL_SURFACES = frozenset(
    {ExecutionSurface.OPENQUANTUM_QPU.value}
)

#: Surfaces whose arithmetic is exact by construction (integers / GF(2)), for labelling.
EXACT_ARITHMETIC_SURFACES = frozenset(
    {ExecutionSurface.CLASSICAL_REFERENCE.value}
)


@dataclass(frozen=True)
class MethodCard:
    """A single research method with its assumptions, limits and transfer decision."""

    method_id: str
    title: str
    track: str
    surface: str
    assumptions: Tuple[str, ...]
    observables: Tuple[str, ...]
    established: str  # what a result on this method can establish
    cannot_establish: Tuple[str, ...]
    references: Tuple[str, ...] = ()
    status: str = "PROPOSED"

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ("assumptions", "observables", "cannot_establish", "references"):
            data[key] = list(data[key])
        return data

    def __post_init__(self) -> None:
        if self.surface not in EXECUTION_SURFACES:
            raise ValueError(
                f"surface {self.surface!r} is not one of {EXECUTION_SURFACES}"
            )


_BMV_SYK_CARDS: Tuple[MethodCard, ...] = (
    MethodCard(
        method_id="qg.bmv.zz.v1",
        title="Two-probe gravity-mediated effective interaction (BMV-type)",
        track="A",
        surface=ExecutionSurface.CLASSICAL_REFERENCE.value,
        assumptions=(
            "Two probe degrees of freedom reduced to one qubit each.",
            "Local phase operations are factored out; only the entangling invariant matters.",
            "Interaction is U_ZZ(theta)=exp(-i theta/2 Z(x)Z) on |+>|+>.",
            "theta is a model parameter, not a physical mass-distance value.",
        ),
        observables=("concurrence", "negativity", "entanglement entropy", "CHSH"),
        established=(
            "A reproducible classical value of a declared finite two-qubit model."
        ),
        cannot_establish=(
            "that any gravitational field is quantum",
            "that two physical masses are entangled",
            "a physical mass/separation for theta without a validated dimensional model",
            "that a positive witness is theory-independent (see L-A3, L-A4)",
        ),
        references=("L-A1", "L-A2", "L-A3", "L-A4", "L-A5"),
        status="SUPPORTED_WITHIN_MODEL",
    ),
    MethodCard(
        method_id="qg.syk.q4.v1",
        title="Small-N sparse q=4 Sachdev-Ye-Kitaev model",
        track="B",
        surface=ExecutionSurface.CLASSICAL_REFERENCE.value,
        assumptions=(
            "N Majorana modes (N = 2 * qubits) with a Jordan-Wigner qubit encoding.",
            "Random all-to-all q=4 couplings from a seeded Gaussian distribution.",
            "Optionally sparsified with a preregistered seeded term subset.",
            "Finite-N model; no continuum / holographic limit is taken.",
        ),
        observables=("spectrum", "parity", "Loschmidt amplitude", "OTOC", "entanglement"),
        established="A finite-N model calculation with an explicit encoding and seed.",
        cannot_establish=(
            "a physical wormhole or spacetime geometry",
            "a semiclassical black hole",
            "the continuum SYK/JT correspondence",
        ),
        references=("L-B1", "L-B2"),
        status="PROPOSED",
    ),
    MethodCard(
        method_id="qg.gauge.z2.v1",
        title="Bounded Z2 lattice gauge toy model (bridge, not a gravity claim)",
        track="C",
        surface=ExecutionSurface.CLASSICAL_REFERENCE.value,
        assumptions=(
            "Z2 link variables on a small square lattice (dense <= 8 links).",
            "Gauss generator G_v = prod X over incident links; physical subspace G_v = +1.",
            "H = -sum_p B_p with plaquette operators B_p = prod Z over the four plaquette links.",
        ),
        observables=("gauge-constraint residual", "plaquette spectrum", "physical-subspace leakage"),
        established="A finite constraint model with an explicit encoding and symmetry checks.",
        cannot_establish=(
            "a quantum-gravity result",
            "loop quantum gravity",
            "a continuum gauge theory or a matter-coupled theory",
        ),
        references=("L-C1",),
        status="SUPPORTED_WITHIN_MODEL",
    ),
)


def catalog() -> Dict[str, Any]:
    """Return the full multi-track catalog as plain data (JSON-serialisable)."""
    cards: List[Dict[str, Any]] = [card.to_dict() for card in _BMV_SYK_CARDS]
    return {
        "schema": "cqhecs.qg.catalog.v1",
        "campaign_default": "qg-2026-01",
        "execution_surfaces": list(EXECUTION_SURFACES),
        "physical_surfaces": sorted(PHYSICAL_SURFACES),
        "tracks": [
            {
                "id": "A",
                "title": "Gravity-mediated entanglement / BMV-type interferometry",
                "status": "SUPPORTED_WITHIN_MODEL",
            },
            {
                "id": "B",
                "title": "SYK / JT / holography / traversable-wormhole-inspired circuits",
                "status": "PROPOSED",
            },
            {
                "id": "C",
                "title": "Lattice gauge theory as a bridge (not a gravity claim)",
                "status": "SUPPORTED_WITHIN_MODEL (bounded Z2 toy)",
            },
            {
                "id": "D",
                "title": "Loop quantum gravity / spin networks (longer term)",
                "status": "DEFERRED",
            },
            {
                "id": "E",
                "title": "Entanglement geometry and emergent-space visualisations",
                "status": "DEFERRED",
            },
        ],
        "methods": cards,
        "non_claims": [
            "No result here establishes or disproves quantum gravity.",
            "A processor circuit emulates a model; it does not couple test masses.",
            "WebGPU f32 is never exact; SIMULATOR is never a QPU.",
        ],
    }
