from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from cqhecs.backend import CQHecsBackend
from cqhecs.hardware_bridge import (
    FakeHardwareBackend,
    FakeHardwareProvider,
    RealHardwareBackend,
    RealHardwareProvider,
    create_fake_manila_profile,
    create_linear_profile,
)


class CQHecsProvider:
    """
    CQ-HECS Quantum Provider for Qiskit and Classical Emulation.
    Offers bit-exact emulation in Z[1/sqrt(2), i], hybrid stabilizer-MPS,
    and Hardware-Aware Quantum Bridge backends.
    """

    def __init__(self):
        self._backends: Dict[str, Union[CQHecsBackend, FakeHardwareBackend]] = {
            "cq_hecs_backend": CQHecsBackend(num_qubits=300),
            "cq_hecs_100q": CQHecsBackend(num_qubits=100),
            "cq_hecs_300q": CQHecsBackend(num_qubits=300),
            "cq_hecs_10k_clifford": CQHecsBackend(num_qubits=10000),
            "fake_manila": FakeHardwareBackend(create_fake_manila_profile()),
            "linear_5q": FakeHardwareBackend(create_linear_profile(5, name="linear_5q")),
        }
        self._fake_provider = FakeHardwareProvider()
        self._real_provider = RealHardwareProvider()

    def backends(self, name: Optional[str] = None) -> List[Any]:
        if name:
            return [self._backends[name]] if name in self._backends else []
        return list(self._backends.values())

    def get_backend(self, name: str = "cq_hecs_backend") -> Any:
        if name in self._backends:
            return self._backends[name]
        return CQHecsBackend(num_qubits=300, name=name)

    @property
    def fake_hardware(self) -> FakeHardwareProvider:
        """Access deterministic offline hardware testbeds."""
        return self._fake_provider

    @property
    def real_hardware(self) -> RealHardwareProvider:
        """Access real hardware provider boundary (requires explicit authorization)."""
        return self._real_provider


__all__ = [
    "CQHecsProvider",
    "FakeHardwareProvider",
    "FakeHardwareBackend",
    "RealHardwareProvider",
    "RealHardwareBackend",
]
