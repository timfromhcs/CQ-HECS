"""
Four-Path Classical Router for CQ-HECS.
Orchestrates transparent, certified classical quantum circuit emulation across Paths A, B, C, and D:
A: Stabilizer-Tableau (exact, Clifford)
B: Stabilizer-Rank-Decomposition (exact, scales with T-Count)
C: MPS without Cutoff + NVMe-Offload (exact up to memory ceiling)
D: Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from cqhecs.circuit_analyzer import CircuitAnalyzer, CircuitProperties
from cqhecs.result import SimulationResult
from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend


class EntanglementAdaptiveRouter:
    """
    Entanglement-adaptive classical router enforcing the Four-Path architecture:
    - Path A: Stabilizer (CPU) - exact polynomial Aaronson-Gottesman
    - Path B: Stabilizer Rank - exact Bravyi-Smith-Smolin scaling with T-count
    - Path C: Vulkan-MPS - exact tensor contraction for Area-Law states
    - Path D: Certified Sparse-Pauli-Dynamics with proven error bounds
    """

    def __init__(
        self,
        t_rank_threshold: int = 14,
        mps_entanglement_threshold: int = 32,
        max_storage_mb: float = 5120.0,
        error_tolerance: float = 0.05,
        max_pauli_terms: int = 1024
    ):
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

    def route_and_execute(
        self,
        circuit: Any,
        shots: int = 1024,
        seed: int = 42,
        preferred_path: Optional[str] = None,
        error_tolerance: Optional[float] = None
    ) -> SimulationResult:
        """
        Analyzes circuit and routes execution to the optimal verified classical path.
        """
        props = self.analyzer.analyze(circuit)
        selected_path = preferred_path.upper() if preferred_path else props.recommended_path
        tol = error_tolerance if error_tolerance is not None else self.error_tolerance

        # Route to selected backend
        if selected_path == "A":
            if not props.is_clifford and preferred_path is None:
                # Safety escalation if non-Clifford
                selected_path = "B"
            else:
                res = self.backend_a.execute(circuit, shots=shots, seed=seed)
                res.metadata["analysis"] = props.to_dict()
                return res

        if selected_path == "B":
            try:
                res = self.backend_b.execute(circuit, shots=shots, seed=seed)
                res.metadata["analysis"] = props.to_dict()
                return res
            except Exception as e:
                if preferred_path:
                    raise
                # Escalate to Path C or D
                selected_path = "C" if props.entanglement_estimate <= self.analyzer.mps_entanglement_threshold else "D"

        if selected_path == "C":
            res = self.backend_c.execute(circuit, shots=shots, seed=seed)
            if res.unresolved and preferred_path is None:
                # Memory exceeded without silent truncation: escalate to Path D
                res_d = self.backend_d.execute(circuit, shots=shots, seed=seed, error_tolerance=tol)
                res_d.metadata["escalation_from"] = "C"
                res_d.metadata["analysis"] = props.to_dict()
                return res_d
            res.metadata["analysis"] = props.to_dict()
            return res

        if selected_path == "D":
            res = self.backend_d.execute(circuit, shots=shots, seed=seed, error_tolerance=tol)
            res.metadata["analysis"] = props.to_dict()
            return res

        raise ValueError(f"Unknown path: {selected_path}. Valid paths are 'A', 'B', 'C', 'D'.")
 
 
# Alias for backwards compatibility
FourPathRouter = EntanglementAdaptiveRouter
