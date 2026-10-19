"""
Four-Path Classical Router for CQ-HECS.
Orchestrates transparent, certified classical quantum circuit emulation:
A: Stabilizer-Tableau (exact for Clifford circuits)
B: Stabilizer-Rank-Decomposition (exact, scales with T-Count)
C: MPS without cutoff + NVMe-Offload (no truncation, exact up to memory ceiling)
D: Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound

Routing rules
-------------
* ``auto`` mode only selects a path that explicitly supports the circuit.
* A user-forced path never silently reroutes. If the forced path cannot run
  the circuit, the failure is raised with a clear diagnostic.
* Only specific, expected capability failures are treated as "this path cannot
  run this circuit". Programming errors are never swallowed.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from cqhecs.circuit_analyzer import (
    CircuitAnalyzer,
    CircuitProperties,
    UnsupportedCircuitInput,
)
from cqhecs.result import SimulationResult
from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.backends.path_b_stabilizer_rank import (
    PathBStabilizerRankBackend,
    StabilizerRankError,
)
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
from cqhecs.backends.path_d_sparse_pauli import (
    PathDSparsePauliBackend,
    UnsupportedPathDOperation,
)

VALID_PATHS = ("A", "B", "C", "D")


class UnsupportedCircuitError(ValueError):
    """Raised when a forced path cannot execute the requested circuit."""


class EntanglementAdaptiveRouter:
    """
    Entanglement-adaptive classical router enforcing the Four-Path architecture:
    - Path A: Stabilizer (CPU) - exact polynomial Gottesman-Knill
    - Path B: Stabilizer Rank - exact Bravyi-Smith-Smolin scaling with T-count
    - Path C: MPS without cutoff - exact tensor contraction for Area-Law states
    - Path D: Certified Sparse-Pauli-Dynamics with proven error bounds
    """

    #: Gates each path can execute, used for pre-flight capability checks.
    PATH_CAPABILITIES: Dict[str, frozenset] = {
        "A": frozenset({
            "h", "x", "y", "z", "s", "sdg", "cx", "cnot", "cz", "swap",
            "id", "barrier", "measure", "reset", "rz", "p", "u1",
        }),
        "B": frozenset({
            "h", "x", "y", "z", "s", "sdg", "cx", "cnot", "cz", "swap",
            "t", "tdg", "rz", "p", "u1", "rx", "ry",
            "id", "barrier",
        }),
        "C": frozenset({
            "h", "x", "y", "z", "s", "sdg", "cx", "cnot", "cz", "swap",
            "t", "tdg", "rz", "p", "u1", "rx", "ry",
            "id", "barrier", "measure",
        }),
        "D": frozenset({
            "h", "x", "y", "z", "s", "sdg", "t", "tdg",
            "rz", "p", "u1", "rx", "ry",
            "cx", "cnot", "cz", "swap",
            "id", "barrier",
        }),
    }

    def __init__(
        self,
        t_rank_threshold: int = 14,
        mps_entanglement_threshold: int = 32,
        max_storage_mb: float = 5120.0,
        error_tolerance: float = 0.05,
        max_pauli_terms: int = 1024
    ):
        if t_rank_threshold < 0:
            raise ValueError(f"t_rank_threshold must be >= 0, got {t_rank_threshold}")
        if mps_entanglement_threshold < 0:
            raise ValueError(
                f"mps_entanglement_threshold must be >= 0, got {mps_entanglement_threshold}"
            )
        if max_storage_mb <= 0:
            raise ValueError(f"max_storage_mb must be > 0, got {max_storage_mb}")
        if error_tolerance <= 0:
            raise ValueError(f"error_tolerance must be > 0, got {error_tolerance}")
        if max_pauli_terms <= 0:
            raise ValueError(f"max_pauli_terms must be > 0, got {max_pauli_terms}")

        self.analyzer = CircuitAnalyzer(
            t_rank_threshold=t_rank_threshold,
            mps_entanglement_threshold=mps_entanglement_threshold
        )
        self.backend_a = PathAStabilizerBackend()
        self.backend_b = PathBStabilizerRankBackend()
        self.backend_c = PathCMPSExactBackend(max_storage_mb=max_storage_mb)
        self.backend_d = PathDSparsePauliBackend(
            max_pauli_terms=max_pauli_terms,
            error_tolerance=error_tolerance
        )
        self.error_tolerance = error_tolerance

    # -- validation ----------------------------------------------------
    @staticmethod
    def _validate_run_arguments(
        shots: int,
        seed: Optional[int],
        error_tolerance: Optional[float],
    ) -> None:
        if not isinstance(shots, int) or isinstance(shots, bool):
            raise ValueError(f"shots must be an int, got {type(shots).__name__}")
        if shots <= 0:
            raise ValueError(f"shots must be > 0, got {shots}")
        if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
            raise ValueError(f"seed must be an int or None, got {type(seed).__name__}")
        if error_tolerance is not None and error_tolerance <= 0:
            raise ValueError(f"error_tolerance must be > 0, got {error_tolerance}")

    def _unsupported_gates(
        self, props: CircuitProperties, path: str
    ) -> list:
        """Returns the gate names present in the circuit but unsupported by `path`."""
        supported = self.PATH_CAPABILITIES[path]
        return sorted(n for n in props.gate_counts if n not in supported)

    # -- routing -------------------------------------------------------
    def route_and_execute(
        self,
        circuit: Any,
        shots: int = 1024,
        seed: int = 42,
        preferred_path: Optional[str] = None,
        error_tolerance: Optional[float] = None
    ) -> SimulationResult:
        """
        Analyzes `circuit` and routes execution to the optimal classical path.

        Args:
            circuit: A Qiskit QuantumCircuit, an OpenQASM 2.0 string, or a list
                of instruction tuples.
            shots: Number of measurement samples; must be > 0.
            seed: RNG seed.
            preferred_path: Force a specific path ("A"/"B"/"C"/"D"). When set,
                the circuit is NOT silently rerouted: an unsupported circuit
                raises UnsupportedCircuitError.
            error_tolerance: Overrides the router's default tolerance.

        Returns:
            SimulationResult with metadata['analysis'] populated.

        Raises:
            UnsupportedCircuitInput: If the circuit input form is unrecognised.
            UnsupportedCircuitError: If a forced path cannot run the circuit.
            ValueError: On invalid run arguments.
        """
        self._validate_run_arguments(shots, seed, error_tolerance)

        props = self.analyzer.analyze(circuit)
        tol = error_tolerance if error_tolerance is not None else self.error_tolerance
        forced = preferred_path is not None

        if forced:
            selected = preferred_path.upper()
            if selected not in VALID_PATHS:
                raise ValueError(
                    f"Unknown path: {preferred_path!r}. Valid paths are {list(VALID_PATHS)}."
                )
            # A forced path must genuinely support this circuit.
            unsupported = self._unsupported_gates(props, selected)
            if unsupported:
                raise UnsupportedCircuitError(
                    f"Path {selected} was forced but does not support the "
                    f"following gate(s) present in the circuit: {unsupported}. "
                    f"Path {selected} supports: "
                    f"{sorted(self.PATH_CAPABILITIES[selected])}. "
                    "Refusing to silently reroute; pass preferred_path=None to "
                    "let the router choose."
                )
            if selected == "A" and not props.is_clifford:
                raise UnsupportedCircuitError(
                    "Path A was forced but the circuit is not Clifford "
                    f"(T-count={props.t_count}). The Gottesman-Knill tableau "
                    "cannot represent it. Refusing to silently reroute."
                )
        else:
            selected = props.recommended_path

        if selected == "A":
            res = self.backend_a.execute(circuit, shots=shots, seed=seed)
            res.metadata["analysis"] = props.to_dict()
            return res

        if selected == "B":
            try:
                res = self.backend_b.execute(circuit, shots=shots, seed=seed)
            except StabilizerRankError as exc:
                # An expected capability limit (rank budget, qubit width).
                if forced:
                    raise UnsupportedCircuitError(
                        f"Path B cannot execute this circuit: {exc}"
                    ) from exc
                selected = (
                    "C"
                    if props.entanglement_estimate <= self.analyzer.mps_entanglement_threshold
                    else "D"
                )
            else:
                res.metadata["analysis"] = props.to_dict()
                return res

        if selected == "C":
            res = self.backend_c.execute(circuit, shots=shots, seed=seed)
            if res.unresolved and not forced:
                # Memory exceeded without truncation: escalate to Path D.
                res_d = self.backend_d.execute(
                    circuit, shots=shots, seed=seed, error_tolerance=tol
                )
                res_d.metadata["escalation_from"] = "C"
                res_d.metadata["analysis"] = props.to_dict()
                return res_d
            res.metadata["analysis"] = props.to_dict()
            return res

        if selected == "D":
            res = self.backend_d.execute(
                circuit, shots=shots, seed=seed, error_tolerance=tol
            )
            res.metadata["analysis"] = props.to_dict()
            return res

        raise ValueError(
            f"Unknown path: {selected}. Valid paths are {list(VALID_PATHS)}."
        )


# Alias for backwards compatibility
FourPathRouter = EntanglementAdaptiveRouter