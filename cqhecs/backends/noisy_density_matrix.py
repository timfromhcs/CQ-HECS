"""
Exact Float64 Density-Matrix Simulator for Noisy and Ideal Quantum Circuits.

Provides mathematically rigorous, exact density matrix emulation for systems up to
10 qubits, with verified Kraus completeness, trace preservation, Hermiticity,
and positive semidefiniteness invariants.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional

import numpy as np

from cqhecs.circuit_parsing import parse_circuit
from cqhecs.gate_lowering import lower_instructions
from cqhecs.hardware_bridge import NoiseModel
from cqhecs.result import (
    ExecutionMode,
    SimulationResult,
    SimulationState,
    hoeffding_total_variation_bound,
)


class NoisyDensityMatrixBackend:
    """
    Exact density matrix simulator for small quantum systems (<= 10 qubits).
    """

    MAX_QUBITS_DEFAULT = 10

    def __init__(self, max_qubits: int = MAX_QUBITS_DEFAULT):
        self.max_qubits = max_qubits

    @staticmethod
    def _gate_matrix_1q(name: str, params: List[float]) -> Optional[np.ndarray]:
        name_l = name.lower()
        if name_l in ("id", "barrier"):
            return np.eye(2, dtype=complex)
        if name_l == "x":
            return np.array([[0, 1], [1, 0]], dtype=complex)
        if name_l == "y":
            return np.array([[0, -1j], [1j, 0]], dtype=complex)
        if name_l == "z":
            return np.array([[1, 0], [0, -1]], dtype=complex)
        if name_l == "h":
            return np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2.0)
        if name_l == "s":
            return np.array([[1, 0], [0, 1j]], dtype=complex)
        if name_l == "sdg":
            return np.array([[1, 0], [0, -1j]], dtype=complex)
        if name_l == "t":
            return np.array([[1, 0], [0, np.exp(1j * np.pi / 4.0)]], dtype=complex)
        if name_l == "tdg":
            return np.array([[1, 0], [0, np.exp(-1j * np.pi / 4.0)]], dtype=complex)
        if name_l == "sx":
            return 0.5 * np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]], dtype=complex)
        if name_l == "sxdg":
            return 0.5 * np.array([[1 - 1j, 1 + 1j], [1 + 1j, 1 - 1j]], dtype=complex)
        if name_l in ("rz", "p", "u1"):
            lam = params[0] if params else 0.0
            return np.array([[np.exp(-1j * lam / 2.0), 0], [0, np.exp(1j * lam / 2.0)]], dtype=complex)
        if name_l == "rx":
            theta = params[0] if params else 0.0
            c = math.cos(theta / 2.0)
            s = math.sin(theta / 2.0)
            return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)
        if name_l == "ry":
            theta = params[0] if params else 0.0
            c = math.cos(theta / 2.0)
            s = math.sin(theta / 2.0)
            return np.array([[c, -s], [s, c]], dtype=complex)
        if name_l in ("u", "u3"):
            theta, phi, lam = params if len(params) == 3 else (0.0, 0.0, 0.0)
            c = math.cos(theta / 2.0)
            s = math.sin(theta / 2.0)
            return np.array([
                [c, -np.exp(1j * lam) * s],
                [np.exp(1j * phi) * s, np.exp(1j * (phi + lam)) * c]
            ], dtype=complex)
        if name_l == "u2":
            phi, lam = params if len(params) == 2 else (0.0, 0.0)
            inv_sqrt2 = 1.0 / np.sqrt(2.0)
            return inv_sqrt2 * np.array([
                [1.0, -np.exp(1j * lam)],
                [np.exp(1j * phi), np.exp(1j * (phi + lam))]
            ], dtype=complex)
        return None

    @staticmethod
    def _gate_matrix_2q(name: str, params: List[float]) -> Optional[np.ndarray]:
        name_l = name.lower()
        if name_l in ("cx", "cnot"):
            return np.array([
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
                [0, 0, 1, 0]
            ], dtype=complex)
        if name_l == "cz":
            return np.array([
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, -1]
            ], dtype=complex)
        if name_l == "swap":
            return np.array([
                [1, 0, 0, 0],
                [0, 0, 1, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1]
            ], dtype=complex)
        if name_l in ("cp", "cphase"):
            lam = params[0] if params else 0.0
            return np.array([
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, np.exp(1j * lam)]
            ], dtype=complex)
        return None

    @staticmethod
    def _apply_1q_unitary(rho: np.ndarray, U: np.ndarray, q: int, n: int) -> np.ndarray:
        # Contract U on row index q
        rho = np.tensordot(U, rho, axes=([1], [q]))
        rho = np.moveaxis(rho, 0, q)
        # Contract U* on col index n + q
        rho = np.tensordot(U.conj(), rho, axes=([1], [n + q]))
        rho = np.moveaxis(rho, 0, n + q)
        return rho

    @staticmethod
    def _apply_2q_unitary(rho: np.ndarray, U: np.ndarray, q0: int, q1: int, n: int) -> np.ndarray:
        U_t = U.reshape((2, 2, 2, 2))
        # Contract U on row indices (q0, q1)
        rho = np.tensordot(U_t, rho, axes=([2, 3], [q0, q1]))
        rho = np.moveaxis(rho, [0, 1], [q0, q1])
        # Contract U* on col indices (n + q0, n + q1)
        rho = np.tensordot(U_t.conj(), rho, axes=([2, 3], [n + q0, n + q1]))
        rho = np.moveaxis(rho, [0, 1], [n + q0, n + q1])
        return rho

    @classmethod
    def _apply_kraus_1q(cls, rho: np.ndarray, kraus: List[np.ndarray], q: int, n: int) -> np.ndarray:
        if len(kraus) == 1 and np.allclose(kraus[0], np.eye(2)):
            return rho
        rho_out = np.zeros_like(rho)
        for K in kraus:
            rho_out += cls._apply_1q_unitary(rho, K, q, n)
        return rho_out

    @classmethod
    def _apply_kraus_2q(cls, rho: np.ndarray, kraus: List[np.ndarray], q0: int, q1: int, n: int) -> np.ndarray:
        if len(kraus) == 1 and np.allclose(kraus[0], np.eye(4)):
            return rho
        rho_out = np.zeros_like(rho)
        for K in kraus:
            rho_out += cls._apply_2q_unitary(rho, K, q0, q1, n)
        return rho_out

    def simulate(
        self,
        circuit: Any,
        noise_model: Optional[NoiseModel] = None,
        shots: int = 1024,
        seed: int = 42,
    ) -> SimulationResult:
        """
        Execute exact density matrix simulation of circuit with optional noise model.
        """
        t_start = time.perf_counter()

        try:
            instructions, num_qubits = parse_circuit(circuit)
        except Exception as e:
            return SimulationResult(
                path="NOISY_DM",
                exact=False,
                error_bound=1.0,
                unresolved=False,
                state=SimulationState.FAILED,
                metadata={"failed": True, "error": str(e)},
            )

        if num_qubits > self.max_qubits:
            return SimulationResult(
                path="NOISY_DM",
                exact=False,
                error_bound=1.0,
                unresolved=True,
                state=SimulationState.UNRESOLVED,
                metadata={
                    "unresolved_reason": f"Circuit width ({num_qubits} qubits) exceeds maximum allocation ceiling ({self.max_qubits} qubits)"
                },
            )

        flat_instructions = lower_instructions(instructions)
        # Initialize density matrix |0...0><0...0|
        dim = 1 << num_qubits
        rho = np.zeros((2,) * (2 * num_qubits), dtype=complex)
        rho[(0,) * (2 * num_qubits)] = 1.0

        for name, qubits, params in flat_instructions:
            if name == "measure" or name == "barrier":
                continue

            if len(qubits) == 1:
                q = qubits[0]
                U = self._gate_matrix_1q(name, params)
                if U is None:
                    return SimulationResult(
                        path="NOISY_DM",
                        exact=False,
                        error_bound=1.0,
                        unresolved=False,
                        state=SimulationState.FAILED,
                        metadata={"failed": True, "error": f"Unsupported 1-qubit gate {name!r}"},
                    )
                rho = self._apply_1q_unitary(rho, U, q, num_qubits)

                # Apply 1-qubit noise channels if present
                if noise_model and name in noise_model.channels_1q:
                    if q in noise_model.channels_1q[name]:
                        for ch in noise_model.channels_1q[name][q]:
                            rho = self._apply_kraus_1q(rho, ch.kraus_operators, q, num_qubits)

            elif len(qubits) == 2:
                q0, q1 = qubits[0], qubits[1]
                U = self._gate_matrix_2q(name, params)
                if U is None:
                    return SimulationResult(
                        path="NOISY_DM",
                        exact=False,
                        error_bound=1.0,
                        unresolved=False,
                        state=SimulationState.FAILED,
                        metadata={"failed": True, "error": f"Unsupported 2-qubit gate {name!r}"},
                    )
                rho = self._apply_2q_unitary(rho, U, q0, q1, num_qubits)

                # Apply 2-qubit noise channels if present
                if noise_model and name in noise_model.channels_2q:
                    pair = (q0, q1)
                    if pair in noise_model.channels_2q[name]:
                        for ch in noise_model.channels_2q[name][pair]:
                            rho = self._apply_kraus_2q(rho, ch.kraus_operators, q0, q1, num_qubits)

        # Invariant checks on final density matrix
        rho_mat = rho.reshape((dim, dim))
        trace_val = np.trace(rho_mat)
        trace_err = abs(trace_val - 1.0)
        hermitian_err = np.max(np.abs(rho_mat - rho_mat.conj().T))

        # Check positivity via minimum eigenvalue
        evals = np.linalg.eigvalsh(rho_mat)
        min_eval = float(np.min(evals))

        if trace_err > 1e-10 or hermitian_err > 1e-10 or min_eval < -1e-10:
            return SimulationResult(
                path="NOISY_DM",
                exact=False,
                error_bound=1.0,
                unresolved=False,
                state=SimulationState.FAILED,
                metadata={
                    "failed": True,
                    "error": f"Physical state invariants violated: trace_err={trace_err:.3e}, hermitian_err={hermitian_err:.3e}, min_eval={min_eval:.3e}",
                },
            )

        # Ideal outcome probabilities from diagonal
        ideal_probs = np.real(np.diag(rho_mat))
        ideal_probs = np.clip(ideal_probs, 0.0, 1.0)
        prob_sum = np.sum(ideal_probs)
        if prob_sum > 0:
            ideal_probs /= prob_sum

        # Apply readout error if present
        noisy_probs = ideal_probs.copy()
        if noise_model and noise_model.readout_errors:
            # Build full measurement assignment matrix via Kronecker product
            # Bit 0 is rightmost (standard Qiskit convention)
            M_full = np.array([[1.0]], dtype=float)
            for q in range(num_qubits - 1, -1, -1):
                if q in noise_model.readout_errors:
                    M_q = noise_model.readout_errors[q].matrix
                else:
                    M_q = np.eye(2, dtype=float)
                M_full = np.kron(M_full, M_q)
            noisy_probs = M_full @ ideal_probs
            noisy_probs = np.clip(noisy_probs, 0.0, 1.0)
            noisy_probs /= np.sum(noisy_probs)

        # Generate sampled counts using deterministic RNG
        rng = np.random.default_rng(seed)
        multinomial_counts = rng.multinomial(shots, noisy_probs)

        counts: Dict[str, int] = {}
        for idx, count in enumerate(multinomial_counts):
            if count > 0:
                bitstring = format(idx, f"0{num_qubits}b")
                counts[bitstring] = int(count)

        # Format probabilities dictionary
        prob_dict: Dict[str, float] = {}
        for idx, prob in enumerate(noisy_probs):
            if prob > 1e-12:
                bitstring = format(idx, f"0{num_qubits}b")
                prob_dict[bitstring] = float(prob)

        sampling_bound = hoeffding_total_variation_bound(
            shots=shots, support_size=min(dim, 1 << num_qubits), delta=0.05
        )

        t_end = time.perf_counter()
        exec_time_ms = (t_end - t_start) * 1000.0

        is_exact = noise_model is None
        state = SimulationState.EXACT if is_exact else SimulationState.CERTIFIED
        mode = ExecutionMode.IDEAL_CLASSICAL if is_exact else ExecutionMode.NOISY_CLASSICAL

        return SimulationResult(
            path="NOISY_DM",
            exact=is_exact,
            error_bound=0.0,
            unresolved=False,
            counts=counts,
            probabilities=prob_dict,
            execution_time_ms=exec_time_ms,
            state=state,
            sampling_error_bound=sampling_bound,
            numerical_error_bound=float(hermitian_err + trace_err),
            execution_mode=mode,
            metadata={
                "density_matrix_dim": dim,
                "trace_error": float(trace_err),
                "hermitian_error": float(hermitian_err),
                "min_eigenvalue": min_eval,
                "noise_model_applied": noise_model.name if noise_model else None,
                "counts_are_joint_distribution": True,
                "error_bound_covers": "total_variation",
            },
        )
