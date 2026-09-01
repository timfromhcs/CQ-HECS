"""
CQ-HECS Classical Four-Path Backends.
Path A: Stabilizer Tableau (Gottesman-Knill Theorem, exact, Clifford)
Path B: Stabilizer Rank Decomposition (Bravyi-Smith-Smolin, exact, scales with T-Count)
Path C: MPS without Cutoff + NVMe-Offload (exact up to memory ceiling)
Path D: Certified Classical Approximation (Sparse-Pauli-Dynamics with proven error bound)
"""

from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend, StabilizerTableauSimulator
from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend, StabilizerRankSimulator
from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend, ExactMPSTensorChain
from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend, SparsePauliDynamicsSimulator

__all__ = [
    "PathAStabilizerBackend",
    "StabilizerTableauSimulator",
    "PathBStabilizerRankBackend",
    "StabilizerRankSimulator",
    "PathCMPSExactBackend",
    "ExactMPSTensorChain",
    "PathDSparsePauliBackend",
    "SparsePauliDynamicsSimulator",
]
