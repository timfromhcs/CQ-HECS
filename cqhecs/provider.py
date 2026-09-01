from __future__ import annotations
from typing import List
from cqhecs.backend import CQHecsBackend


class CQHecsProvider:
    """
    CQ-HECS Quantum Provider for Qiskit.
    Offers bit-exact emulation in Z[1/sqrt(2), i] and hybrid stabilizer-MPS.
    """

    def __init__(self):
        self._backends = {
            "cq_hecs_backend": CQHecsBackend(num_qubits=300),
            "cq_hecs_100q": CQHecsBackend(num_qubits=100),
            "cq_hecs_300q": CQHecsBackend(num_qubits=300),
            "cq_hecs_10k_clifford": CQHecsBackend(num_qubits=10000),
        }

    def backends(self, name: str = None) -> List[CQHecsBackend]:
        if name:
            return [self._backends[name]] if name in self._backends else []
        return list(self._backends.values())

    def get_backend(self, name: str = "cq_hecs_backend") -> CQHecsBackend:
        if name in self._backends:
            return self._backends[name]
        return CQHecsBackend(num_qubits=300, name=name)
