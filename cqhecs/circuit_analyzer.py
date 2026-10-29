"""
Circuit Analyzer for CQ-HECS Classical Four-Path Architecture.

Performs deterministic static circuit analysis:

- T-count tracking (non-Clifford resource estimation),
- Clifford verification (stabilizer-tableau compatibility),
- entanglement estimation (1D cut connectivity),
- capability-first Four-Path recommendation (A -> B -> C -> D).

The gate table lives in :mod:`cqhecs.gate_manifest`; the analyzer, the router
and the backends all read the same data, so "the analyzer says path X supports
this" cannot drift from what path X actually executes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Sequence, Set, Tuple

from cqhecs.circuit_parsing import (
    Instruction,
    UnsupportedCircuitInputError,
    parse_circuit,
)
from cqhecs.gate_manifest import (
    NON_UNITARY,
    clifford_rotation_kind,
    get_gate,
    path_gate_names,
)

#: Retained for backwards compatibility with callers that imported the old
#: hand-written sets. Both now derive from the shared manifest.
CLIFFORD_GATES: FrozenSet[str] = path_gate_names("A")
NON_CLIFFORD_T_GATES: FrozenSet[str] = frozenset({
    "t", "tdg", "ccx", "toffoli", "ch", "cs", "csdg",
})
ROTATION_GATES: FrozenSet[str] = frozenset({
    "rz", "rx", "ry", "p", "u1", "u2", "u3", "u", "cp", "crz",
    "crx", "cry", "cu1",
})

#: Highest qubit count Path B can represent with its statevector branch model.
PATH_B_MAX_QUBITS = 22


#: Raised when a circuit cannot be recognised or parsed. There is exactly one
#: rejection type on purpose: a caller that catches malformed OpenQASM must
#: catch an unrecognised Python object too, and vice versa. ``parse_circuit``
#: raises this class (or its ``QASMParseError`` subclass); the alias below
#: keeps the historical analyzer-facing name without introducing a second,
#: non-overlapping exception hierarchy.
#:
#: This is deliberately a hard failure. Defaulting an unrecognised input to a
#: path recommendation would route a circuit nobody has inspected to a
#: simulator that will silently mis-handle it.
UnsupportedCircuitInput = UnsupportedCircuitInputError


@dataclass
class CircuitProperties:
    """Static properties extracted from a quantum circuit."""

    num_qubits: int
    total_gates: int
    gate_counts: Dict[str, int] = field(default_factory=dict)
    t_count: int = 0
    non_clifford_rotations: int = 0
    is_clifford: bool = True
    entanglement_estimate: int = 0
    max_cut_width: int = 0
    recommended_path: str = "A"
    reason: str = ""
    #: Raw normalised instructions, so callers do not have to re-parse (and
    #: possibly parse differently) before checking capabilities.
    gate_sequence: List[Instruction] = field(default_factory=list, repr=False)
    #: Every path whose validated gate table covers the whole circuit.
    supported_paths: Tuple[str, ...] = ()
    #: Operations no backend implements; execution must be refused.
    unsupported_gates: Tuple[str, ...] = ()
    has_measurement: bool = False
    has_mid_circuit_measurement: bool = False
    has_reset: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_qubits": self.num_qubits,
            "total_gates": self.total_gates,
            "gate_counts": self.gate_counts,
            "t_count": self.t_count,
            "non_clifford_rotations": self.non_clifford_rotations,
            "is_clifford": self.is_clifford,
            "entanglement_estimate": self.entanglement_estimate,
            "max_cut_width": self.max_cut_width,
            "recommended_path": self.recommended_path,
            "reason": self.reason,
            "supported_paths": list(self.supported_paths),
            "unsupported_gates": list(self.unsupported_gates),
            "has_measurement": self.has_measurement,
            "has_mid_circuit_measurement": self.has_mid_circuit_measurement,
            "has_reset": self.has_reset,
        }


def _is_clifford_instruction(name: str, params: Sequence[float]) -> bool:
    """True when the stabilizer tableau can apply this operation exactly."""
    spec = get_gate(name)
    if spec is None or not spec.clifford or "A" not in spec.paths:
        return False
    if spec.parameterised:
        if len(params) != spec.max_params:
            return False
        return all(clifford_rotation_kind(float(p)) is not None for p in params)
    return True


def _t_resource(name: str, params: Sequence[float]) -> int:
    """Non-Clifford resource count used for the Path B rank threshold."""
    if name in NON_UNITARY:
        return 0
    if name in ("t", "tdg"):
        return 1
    if name in ("ccx", "toffoli"):
        return 7
    spec = get_gate(name)
    if spec is None:
        return 1
    if spec.parameterised:
        return 0 if _is_clifford_instruction(name, params) else 1
    if spec.clifford and "A" in spec.paths:
        return 0
    if spec.barrier or name == "id":
        return 0
    return 1


def supporting_paths(
    instructions: Sequence[Instruction],
    num_qubits: int,
    *,
    has_measurement: bool = False,
    has_mid_circuit_measurement: bool = False,
    has_reset: bool = False,
) -> FrozenSet[str]:
    """
    Capability-first decision: which paths can execute this exact operation
    list faithfully?

    A path is included only when *every* operation is in that path's manifest
    entry, arity and parameter count match, and the circuit's non-unitary
    structure is representable (terminal measurement only for A/C; no
    measurement for B/D; no reset anywhere).
    """
    names = {name for name, _q, _p in instructions}
    paths: Set[str] = set()

    if has_reset or has_mid_circuit_measurement:
        return frozenset()

    for path in ("A", "B", "C", "D"):
        supported = path_gate_names(path)
        if not names <= supported:
            continue
        if path in ("B", "D") and has_measurement:
            continue
        # Arity and parameter-count check against the shared manifest.
        valid = True
        for name, qubits, params in instructions:
            spec = get_gate(name)
            if spec is None:
                valid = False
                break
            if spec.barrier:
                continue
            if len(qubits) != spec.arity:
                valid = False
                break
            if not (spec.min_params <= len(params) <= spec.max_params):
                valid = False
                break
        if not valid:
            continue
        if path == "A":
            # The tableau only accepts parameterised gates at Clifford angles.
            # Measurement and barrier are not unitary gates and are handled by
            # the path-specific measurement rules above.
            for name, _q, params in instructions:
                spec = get_gate(name)
                if spec is not None and (spec.measurement or spec.barrier):
                    continue
                if not _is_clifford_instruction(name, params):
                    valid = False
                    break
            if not valid:
                continue
        if path == "B" and num_qubits > PATH_B_MAX_QUBITS:
            continue
        paths.add(path)

    return frozenset(paths)


class CircuitAnalyzer:
    """
    Deterministic static circuit analysis and Four-Path routing engine.
    """

    def __init__(
        self,
        t_rank_threshold: int = 14,
        mps_entanglement_threshold: int = 32,
        max_mps_qubits: int = 500,
    ):
        if t_rank_threshold < 0:
            raise ValueError(f"t_rank_threshold must be >= 0, got {t_rank_threshold}")
        if mps_entanglement_threshold < 0:
            raise ValueError(
                f"mps_entanglement_threshold must be >= 0, got "
                f"{mps_entanglement_threshold}"
            )
        if max_mps_qubits <= 0:
            raise ValueError(f"max_mps_qubits must be > 0, got {max_mps_qubits}")
        self.t_rank_threshold = t_rank_threshold
        self.mps_entanglement_threshold = mps_entanglement_threshold
        # Aligned with ExactMPSTensorChain.MAX_SAMPLING_QUBITS (500). This is a
        # routing ceiling, not an exactness guarantee: actual feasibility still
        # depends on entanglement, memory and numeric rank growth.
        self.max_mps_qubits = max_mps_qubits

    def analyze(self, circuit: Any) -> CircuitProperties:
        """
        Analyzes a Qiskit QuantumCircuit, OpenQASM string, or instruction list.

        Raises:
            UnsupportedCircuitInput: If `circuit` is not one of the supported
                input forms. The analyzer fails closed: an unrecognised input
                is never defaulted to a path recommendation.
            UnsupportedCircuitInputError: If the QASM/instruction input is
                malformed. A syntactically invalid circuit is never partially
                analysed.
        """
        if not isinstance(circuit, (str, list, tuple)) and not (
            hasattr(circuit, "data") and hasattr(circuit, "num_qubits")
        ):
            raise UnsupportedCircuitInput(
                f"Unsupported circuit input type {type(circuit).__name__!r}. "
                "Expected a Qiskit QuantumCircuit, an OpenQASM 2.0 string, or a "
                "list of instruction tuples (name, qubits, params). "
                "Refusing to guess a path for an unrecognised circuit."
            )
        instructions, num_qubits = parse_circuit(circuit)
        return self.analyze_instructions(instructions, num_qubits)

    def analyze_instructions(
        self, instructions: Sequence[Instruction], num_qubits: int
    ) -> CircuitProperties:
        """Analyses an already-parsed instruction list."""
        gate_counts: Dict[str, int] = {}
        t_count = 0
        non_clifford_rotations = 0
        is_clifford = True
        two_qubit_gates: List[Tuple[int, int]] = []
        unsupported: Set[str] = set()
        has_measurement = False
        has_reset = False
        last_unitary_index = -1

        for index, (name, qubits, params) in enumerate(instructions):
            gate_counts[name] = gate_counts.get(name, 0) + 1
            spec = get_gate(name)
            if spec is None:
                unsupported.add(name)
            elif not spec.paths:
                unsupported.add(name)

            if name == "measure":
                has_measurement = True
                continue
            if name == "reset":
                has_reset = True
                is_clifford = False
                continue
            # Barrier and identity have no state effect, so they do not make a
            # preceding measurement "mid-circuit".
            if spec is not None and (spec.barrier or name == "id"):
                continue
            last_unitary_index = index

            if len(qubits) == 2:
                two_qubit_gates.append((qubits[0], qubits[1]))

            resource = _t_resource(name, params)
            if resource:
                t_count += resource
                if name not in NON_CLIFFORD_T_GATES:
                    non_clifford_rotations += 1
                is_clifford = False
            elif not _is_clifford_instruction(name, params):
                is_clifford = False

        has_mid_circuit_measurement = any(
            name == "measure" and index < last_unitary_index
            for index, (name, _q, _p) in enumerate(instructions)
        )
        if has_mid_circuit_measurement:
            is_clifford = False

        supported = supporting_paths(
            instructions,
            num_qubits,
            has_measurement=has_measurement,
            has_mid_circuit_measurement=has_mid_circuit_measurement,
            has_reset=has_reset,
        )

        entanglement_estimate, max_cut = self._estimate_entanglement(
            num_qubits, two_qubit_gates
        )
        recommended_path, reason = self._determine_path(
            num_qubits=num_qubits,
            is_clifford=is_clifford,
            t_count=t_count,
            entanglement_estimate=entanglement_estimate,
            max_cut_width=max_cut,
            supported=supported,
            unsupported=sorted(unsupported),
            has_measurement=has_measurement,
            has_mid_circuit_measurement=has_mid_circuit_measurement,
            has_reset=has_reset,
        )

        return CircuitProperties(
            num_qubits=num_qubits,
            total_gates=len(instructions),
            gate_counts=gate_counts,
            t_count=t_count,
            non_clifford_rotations=non_clifford_rotations,
            is_clifford=is_clifford,
            entanglement_estimate=entanglement_estimate,
            max_cut_width=max_cut,
            recommended_path=recommended_path,
            reason=reason,
            gate_sequence=list(instructions),
            supported_paths=tuple(sorted(supported)),
            unsupported_gates=tuple(sorted(unsupported)),
            has_measurement=has_measurement,
            has_mid_circuit_measurement=has_mid_circuit_measurement,
            has_reset=has_reset,
        )

    def _estimate_entanglement(
        self, num_qubits: int, two_qubit_gates: List[Tuple[int, int]]
    ) -> Tuple[int, int]:
        """
        Estimates entanglement via bipartite cut analysis across a 1D chain.

        Returns:
            (entanglement_score, max_cut_width)
        """
        if num_qubits <= 1 or not two_qubit_gates:
            return 0, 0

        cuts = [0] * (num_qubits - 1)
        for (q1, q2) in two_qubit_gates:
            lo, hi = min(q1, q2), max(q1, q2)
            for c in range(lo, min(hi, num_qubits - 1)):
                cuts[c] += 1

        max_cut = max(cuts) if cuts else 0
        total_crossing = sum(cuts)
        return total_crossing, max_cut

    def _determine_path(
        self,
        *,
        num_qubits: int,
        is_clifford: bool,
        t_count: int,
        entanglement_estimate: int,
        max_cut_width: int,
        supported: FrozenSet[str],
        unsupported: List[str],
        has_measurement: bool,
        has_mid_circuit_measurement: bool,
        has_reset: bool,
    ) -> Tuple[str, str]:
        """
        Enforces the four-path selection order A -> B -> C -> D, but never
        recommends a path whose validated capabilities do not cover the
        circuit.
        """
        if has_reset:
            return "", (
                "reset is non-unitary and no path implements its semantics; "
                "execution will be refused."
            )
        if has_mid_circuit_measurement:
            return "", (
                "mid-circuit measurement changes the subsequent state; no path "
                "currently implements dynamic measurement semantics, so the "
                "circuit must be rejected rather than reordered."
            )
        if unsupported:
            return "", (
                "No backend implements the following operation(s): "
                f"{unsupported}. Execution will be refused."
            )

        if "A" in supported and is_clifford:
            return "A", (
                f"Circuit is 100% Clifford and executable by the stabilizer "
                f"tableau (T-Count=0, {num_qubits} qubits). Exact polynomial "
                "Gottesman-Knill simulation."
            )

        if "B" in supported and t_count <= self.t_rank_threshold:
            return "B", (
                f"Low T-Count (T={t_count} <= {self.t_rank_threshold}) and "
                f"{num_qubits} <= {PATH_B_MAX_QUBITS} qubits. Exact stabilizer "
                "rank decomposition scales as O(2^(alpha*T))."
            )

        if (
            "C" in supported
            and num_qubits <= self.max_mps_qubits
            and (
                max_cut_width <= self.mps_entanglement_threshold
                or num_qubits <= 20
            )
        ):
            return "C", (
                f"Moderate entanglement (Max cut={max_cut_width}, T={t_count}). "
                f"Untruncated MPS (numerical rank only) with "
                f"{num_qubits} <= {self.max_mps_qubits} qubits. Exact up to "
                "float64 roundoff and the memory ceiling."
            )

        if "D" in supported:
            return "D", (
                f"High T-Count (T={t_count}) and high entanglement "
                f"(Cut={max_cut_width}). Routed to the certified sparse-Pauli "
                "approximation, which reports expectation values with a "
                "triangle-inequality bound; it does not produce joint counts."
            )

        return "", (
            "No path supports this circuit within its documented limits "
            f"(qubits={num_qubits}, T={t_count}, cut={max_cut_width})."
        )
