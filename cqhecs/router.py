"""
Four-Path Classical Router for CQ-HECS.

A: Stabilizer-Tableau (exact for Clifford circuits)
B: Stabilizer-Rank-Decomposition (exact, scales with T-Count)
C: Untruncated MPS (exact up to float64 roundoff and the memory ceiling)
D: Certified Classical Approximation (Sparse-Pauli-Dynamics) with a derived
   triangle-inequality bound on expectation values

Routing rules
-------------
* Capabilities come from :mod:`cqhecs.gate_manifest`, shared with the
  backends. A path is selected only if its manifest entry covers every
  concrete operation in the circuit (including the parameter count and the
  measurement structure).
* ``auto`` mode follows A -> B -> C -> D and never selects a path that cannot
  run the circuit. Unsupported circuits are refused *before* execution.
* A user-forced path never silently reroutes. If the forced path cannot run
  the circuit, the failure is raised with a clear diagnostic.
* Only specific, expected capability failures are treated as "this path cannot
  run this circuit". Programming errors are never swallowed.
* Mid-circuit measurement, reset and classically controlled operations are
  non-unitary semantics. They are refused instead of being reordered to the
  end of the circuit.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from cqhecs.circuit_analyzer import (
    CircuitAnalyzer,
    CircuitProperties,
)
from cqhecs.circuit_parsing import parse_circuit
from cqhecs.gate_manifest import path_gate_names
from cqhecs.result import SimulationResult
from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.backends.path_b_stabilizer_rank import (
    PathBStabilizerRankBackend,
    StabilizerRankError,
)
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend

VALID_PATHS = ("A", "B", "C", "D")


class UnsupportedCircuitError(ValueError):
    """Raised when a forced path cannot execute the requested circuit."""


class EntanglementAdaptiveRouter:
    """
    Entanglement-adaptive classical router enforcing the Four-Path architecture.
    """

    #: Gate names each path can execute, derived from the shared manifest.
    #: Kept as a class attribute for diagnostics and backwards compatibility.
    PATH_CAPABILITIES: Dict[str, frozenset] = {
        path: frozenset(path_gate_names(path)) for path in VALID_PATHS
    }

    def __init__(
        self,
        t_rank_threshold: int = 14,
        mps_entanglement_threshold: int = 32,
        max_storage_mb: float = 5120.0,
        error_tolerance: float = 0.05,
        max_pauli_terms: int = 1024,
    ):
        if t_rank_threshold < 0:
            raise ValueError(f"t_rank_threshold must be >= 0, got {t_rank_threshold}")
        if mps_entanglement_threshold < 0:
            raise ValueError(
                f"mps_entanglement_threshold must be >= 0, got "
                f"{mps_entanglement_threshold}"
            )
        if max_storage_mb <= 0:
            raise ValueError(f"max_storage_mb must be > 0, got {max_storage_mb}")
        if error_tolerance <= 0:
            raise ValueError(f"error_tolerance must be > 0, got {error_tolerance}")
        if max_pauli_terms <= 0:
            raise ValueError(f"max_pauli_terms must be > 0, got {max_pauli_terms}")

        self.analyzer = CircuitAnalyzer(
            t_rank_threshold=t_rank_threshold,
            mps_entanglement_threshold=mps_entanglement_threshold,
        )
        self.backend_a = PathAStabilizerBackend()
        self.backend_b = PathBStabilizerRankBackend()
        self.backend_c = PathCMPSExactBackend(max_storage_mb=max_storage_mb)
        self.backend_d = PathDSparsePauliBackend(
            max_pauli_terms=max_pauli_terms,
            error_tolerance=error_tolerance,
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
        if error_tolerance is not None:
            if not isinstance(error_tolerance, (int, float)) or isinstance(
                error_tolerance, bool
            ):
                raise ValueError(
                    "error_tolerance must be a number or None, got "
                    f"{type(error_tolerance).__name__}"
                )
            if error_tolerance <= 0:
                raise ValueError(
                    f"error_tolerance must be > 0, got {error_tolerance}"
                )

    def _unsupported_gates(
        self, props: CircuitProperties, path: str
    ) -> list:
        """Gate names present in the circuit but unsupported by `path`."""
        supported = self.PATH_CAPABILITIES[path]
        return sorted(n for n in props.gate_counts if n not in supported)

    @staticmethod
    def _dynamic_refusal(props: CircuitProperties) -> Optional[str]:
        if props.has_reset:
            return (
                "reset is non-unitary and is not implemented by any path. "
                "Refusing to simulate a circuit whose state depends on it."
            )
        if props.has_mid_circuit_measurement:
            return (
                "mid-circuit measurement is not implemented by any path. "
                "Moving it to the end would silently change the result, so the "
                "circuit is refused."
            )
        return None

    # -- routing -------------------------------------------------------
    def route_and_execute(
        self,
        circuit: Any,
        shots: int = 1024,
        seed: int = 42,
        preferred_path: Optional[str] = None,
        error_tolerance: Optional[float] = None,
        require_counts: bool = False,
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
            require_counts: When True, refuse a path that only reports
                expectation values. ``CQHecsBackend.run`` uses this because a
                Qiskit result without counts would look like an empty
                distribution instead of an explicit capability refusal.

        Returns:
            SimulationResult with metadata['analysis'] populated.

        Raises:
            UnsupportedCircuitInput: If the circuit input form is unrecognised.
            QASMParseError: If a QASM source violates the strict contract.
            UnsupportedCircuitError: If no path (or the forced path) can run it.
            ValueError: On invalid run arguments.
        """
        self._validate_run_arguments(shots, seed, error_tolerance)

        instructions, num_qubits = parse_circuit(circuit)
        props = self.analyzer.analyze_instructions(instructions, num_qubits)

        refusal = self._dynamic_refusal(props)
        if refusal is not None:
            raise UnsupportedCircuitError(refusal)
        if props.unsupported_gates:
            raise UnsupportedCircuitError(
                "No backend implements the following operation(s): "
                f"{list(props.unsupported_gates)}. Refusing to run a circuit "
                "that would be silently reduced."
            )

        tol = error_tolerance if error_tolerance is not None else self.error_tolerance
        forced = preferred_path is not None

        if forced:
            selected = preferred_path.upper()
            if selected not in VALID_PATHS:
                raise ValueError(
                    f"Unknown path: {preferred_path!r}. Valid paths are "
                    f"{list(VALID_PATHS)}."
                )
            if selected not in props.supported_paths:
                unsupported = self._unsupported_gates(props, selected)
                detail = (
                    f"the following gate(s) present in the circuit: {unsupported}"
                    if unsupported
                    else "the circuit's measurement structure or qubit count"
                )
                raise UnsupportedCircuitError(
                    f"Path {selected} was forced but does not support {detail}. "
                    f"Path {selected} supports: "
                    f"{sorted(self.PATH_CAPABILITIES[selected])}. "
                    "Refusing to silently reroute; pass preferred_path=None to "
                    "let the router choose."
                )
        else:
            selected = props.recommended_path
            if not selected:
                raise UnsupportedCircuitError(
                    props.reason or "No path supports this circuit."
                )

        if require_counts and selected == "D":
            raise UnsupportedCircuitError(
                "Path D is a certified expectation-value backend and does not "
                "produce joint bitstring counts. This call requires counts, so "
                "it is refused instead of returning an empty distribution. "
                "Use the Path D backend directly for expectation values, or a "
                "circuit that Path A/B/C can execute."
            )

        if selected == "A":
            res = self.backend_a.execute(circuit, shots=shots, seed=seed)
            res.metadata["analysis"] = props.to_dict()
            return res

        if selected == "B":
            try:
                res = self.backend_b.execute(circuit, shots=shots, seed=seed)
            except StabilizerRankError as exc:
                # An expected capability limit (rank budget, branch width).
                if forced:
                    raise UnsupportedCircuitError(
                        f"Path B cannot execute this circuit: {exc}"
                    ) from exc
                fallback = self._fallback_after_b(props)
                if fallback is None:
                    raise UnsupportedCircuitError(
                        f"Path B cannot execute this circuit ({exc}) and no "
                        "other path supports it."
                    ) from exc
                selected = fallback
            else:
                res.metadata["analysis"] = props.to_dict()
                return res

        if selected == "C":
            res = self.backend_c.execute(circuit, shots=shots, seed=seed)
            if res.unresolved and not forced:
                if "D" not in props.supported_paths:
                    raise UnsupportedCircuitError(
                        "Path C exceeded its memory ceiling and Path D cannot "
                        "run this circuit. Refusing to return a partial state."
                    )
                if require_counts:
                    raise UnsupportedCircuitError(
                        "Path C exceeded its memory ceiling and the only "
                        "fallback (Path D) cannot produce bitstring counts."
                    )
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

    def _fallback_after_b(self, props: CircuitProperties) -> Optional[str]:
        """Chooses a genuinely capable fallback when Path B hits a rank limit."""
        if "C" in props.supported_paths:
            return "C"
        if "D" in props.supported_paths:
            return "D"
        return None


# Alias for backwards compatibility
FourPathRouter = EntanglementAdaptiveRouter
