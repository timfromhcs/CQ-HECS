from __future__ import annotations
from typing import Any, List, Optional, Dict
from cqhecs.backend import CQHecsBackend


class CQHecsProvider:
    """CQ-HECS Provider for Qiskit ecosystem."""
    def __init__(self):
        self._backends: Dict[str, Any] = {}

    def get_backend(self, name: Optional[str] = None, num_qubits: int = 300, **kwargs) -> CQHecsBackend:
        return CQHecsBackend(num_qubits=num_qubits, **kwargs)

    def backends(self, name: Optional[str] = None, **kwargs) -> List[CQHecsBackend]:
        return [self.get_backend(num_qubits=300)]
