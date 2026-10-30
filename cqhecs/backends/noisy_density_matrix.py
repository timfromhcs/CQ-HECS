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

from cqhecs.circuit_parsing import parse_source_circuit
from cqhecs.gate_lowering import GateLoweringError, lower_instructions
from cqhecs.hardware_bridge import NoiseModel
from cqhecs.result import (
    ExecutionMode,
    SimulationResult,
    SimulationState,
    hoeffding_total_variation_bound,
)


#: Number of angle parameters each supported gate takes. A gate whose
#: parameter list has any other length is refused instead of being evaluated
#: with a default angle (which would silently turn it into the identity).
_PARAM_ARITY: Dict[str, int] = {
    "rz": 1, "p": 1, "u1": 1, "rx": 1, "ry": 1,
    "u": 3, "u3": 3, "u2": 2,
    "cp": 1, "cphase": 1, "cu1": 1, "crx": 1, "cry": 1, "crz": 1,
}

#: Gates this backend evaluates, by operand count (names as produced by
#: ``lower_instructions``; must match ``_gate_matrix_1q``/``_gate_matrix_2q``).
_GATES_1Q = frozenset({
    "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx", "sxdg",
    "rz", "p", "u1", "rx", "ry", "u", "u3", "u2",
})
_GATES_2Q = frozenset({
    "cx", "cnot", "cz", "swap", "cp", "cphase", "cu1", "crx", "cry", "crz",
})

#: Operations without a state effect. They never make a preceding measurement
#: "mid-circuit" (same rule as ``CircuitAnalyzer``).
_NO_STATE_EFFECT = frozenset({"barrier", "id"})


class NoisyDensityMatrixBackend:
    """
    Exact density matrix simulator for small quantum systems (<= 10 qubits).

    Output convention (shared with the four-path router): qubit 0 is the
    least-significant bit and is rendered rightmost. When the circuit contains
    terminal measurements only the measured qubits are reported, otherwise all
    qubits are.
    """

    MAX_QUBITS_DEFAULT = 10

    def __init__(self, max_qubits: int = MAX_QUBITS_DEFAULT):
        if not isinstance(max_qubits, int) or isinstance(max_qubits, bool) or max_qubits < 1:
            raise ValueError(f"max_qubits must be a positive int, got {max_qubits!r}")
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
            lam = params[0]
            return np.array([[np.exp(-1j * lam / 2.0), 0], [0, np.exp(1j * lam / 2.0)]], dtype=complex)
        if name_l == "rx":
            theta = params[0]
            c = math.cos(theta / 2.0)
            s = math.sin(theta / 2.0)
            return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)
        if name_l == "ry":
            theta = params[0]
            c = math.cos(theta / 2.0)
            s = math.sin(theta / 2.0)
            return np.array([[c, -s], [s, c]], dtype=complex)
        if name_l in ("u", "u3"):
            theta, phi, lam = params
            c = math.cos(theta / 2.0)
            s = math.sin(theta / 2.0)
            return np.array([
                [c, -np.exp(1j * lam) * s],
                [np.exp(1j * phi) * s, np.exp(1j * (phi + lam)) * c]
            ], dtype=complex)
        if name_l == "u2":
            phi, lam = params
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
        if name_l in ("cp", "cphase", "cu1"):
            lam = params[0]
            return np.array([
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, np.exp(1j * lam)]
            ], dtype=complex)
        if name_l in ("crx", "cry", "crz"):
            # The first operand is the control and the more significant tensor
            # factor here (as for cx above), so the gate is diag(I, R).
            # rz keeps its exp(-+i lam/2) entries: under a control they are a
            # relative phase, not a global one.
            U = np.eye(4, dtype=complex)
            U[2:, 2:] = NoisyDensityMatrixBackend._gate_matrix_1q(name_l[1:], params)
            return U
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

    @staticmethod
    def _failed(error: str) -> SimulationResult:
        return SimulationResult(
            path="NOISY_DM",
            exact=False,
            error_bound=1.0,
            unresolved=False,
            state=SimulationState.FAILED,
            metadata={"failed": True, "error": error},
        )

    @staticmethod
    def _validate_run_arguments(shots: Any, seed: Any) -> None:
        # Same contract as the four-path router: bool is not an int here, and
        # a float shot count is refused rather than truncated.
        if not isinstance(shots, int) or isinstance(shots, bool):
            raise ValueError(f"shots must be an int, got {type(shots).__name__}")
        if shots <= 0:
            raise ValueError(f"shots must be > 0, got {shots}")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError(f"seed must be an int, got {type(seed).__name__}")
        if seed < 0:
            raise ValueError(f"seed must be >= 0, got {seed}")

    @staticmethod
    def _measured_qubits(instructions: List[Any]) -> Optional[List[int]]:
        """
        Returns the terminally measured qubits in rendering order, or ``None``
        when the circuit has no measurement (all qubits are then reported).

        Raises:
            ValueError: For a mid-circuit measurement. The density matrix is
                not collapsed, so a measurement followed by a state-changing
                operation cannot be represented and is refused, exactly as the
                router refuses it.
        """
        measured: List[int] = []
        seen_unitary_after = False
        for name, qubits, _params in reversed(instructions):
            if name == "measure":
                if seen_unitary_after:
                    raise ValueError(
                        "mid-circuit measurement is not supported by the noisy "
                        "density-matrix backend; refusing instead of moving it "
                        "to the end of the circuit"
                    )
                measured.append(int(qubits[0]))
            elif name not in _NO_STATE_EFFECT:
                seen_unitary_after = True
        if not measured:
            return None
        measured.reverse()
        return measured

    def _prepare(self, circuit: Any):
        """
        Parses, lowers and validates ``circuit`` before any allocation.

        Returns ``(blocks, measured_qubits, num_qubits)``, or a FAILED or
        UNRESOLVED :class:`SimulationResult` explaining the refusal.
        """
        try:
            source_instructions, num_qubits = parse_source_circuit(circuit)
        except Exception as e:
            return self._failed(str(e))

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

        # Lower each source instruction on its own so that noise channels stay
        # attached to the gate as written (e.g. ``sx``), not to the gates it
        # decomposes into. Without this, a channel calibrated on ``sx`` never
        # fired and ``h`` noise was applied twice per ``sx``.
        try:
            blocks = [
                (name, qubits, lower_instructions([(name, qubits, params)]))
                for name, qubits, params in source_instructions
            ]
        except GateLoweringError as e:
            return self._failed(str(e))
        flat_instructions = [op for _name, _qubits, ops in blocks for op in ops]
        try:
            measured_qubits = self._measured_qubits(flat_instructions)
        except ValueError as e:
            return self._failed(str(e))

        # Validate every operation before allocating the density matrix, so a
        # refusal never follows partial evolution.
        for name, qubits, params in flat_instructions:
            if name in ("measure", "barrier"):
                continue
            supported = (len(qubits) == 1 and name in _GATES_1Q) or (
                len(qubits) == 2 and name in _GATES_2Q
            )
            if not supported:
                return self._failed(
                    f"Unsupported {len(qubits)}-qubit operation {name!r}"
                )
            expected = _PARAM_ARITY.get(name, 0)
            if len(params) != expected:
                return self._failed(
                    f"Gate {name!r} expects {expected} parameter(s), got {len(params)}"
                )

        return blocks, measured_qubits, num_qubits

    def _evolve(self, blocks: List[Any], num_qubits: int, noise_model: Optional[NoiseModel]) -> np.ndarray:
        """Evolves |0...0><0...0| through ``blocks``; qubit 0 is the LSB of the result."""
        # Initialize density matrix |0...0><0...0|. Tensor axis k (and n + k)
        # belongs to qubit k.
        dim = 1 << num_qubits
        rho = np.zeros((2,) * (2 * num_qubits), dtype=complex)
        rho[(0,) * (2 * num_qubits)] = 1.0

        for source_name, source_qubits, ops in blocks:
            for name, qubits, params in ops:
                if name == "measure" or name == "barrier":
                    continue
                if len(qubits) == 1:
                    U = self._gate_matrix_1q(name, params)
                    rho = self._apply_1q_unitary(rho, U, qubits[0], num_qubits)
                else:
                    U = self._gate_matrix_2q(name, params)
                    rho = self._apply_2q_unitary(rho, U, qubits[0], qubits[1], num_qubits)

            if noise_model is None:
                continue
            gate = source_name.lower()
            if len(source_qubits) == 1:
                for ch in noise_model.channels_1q.get(gate, {}).get(source_qubits[0], ()):
                    rho = self._apply_kraus_1q(rho, ch.kraus_operators, source_qubits[0], num_qubits)
            elif len(source_qubits) == 2:
                pair = (source_qubits[0], source_qubits[1])
                for ch in noise_model.channels_2q.get(gate, {}).get(pair, ()):
                    rho = self._apply_kraus_2q(rho, ch.kraus_operators, pair[0], pair[1], num_qubits)

        # Reverse the qubit axes before flattening so that qubit 0 becomes the
        # least-significant bit of the basis index (Qiskit convention). Without
        # this, qubit 0 would be the most-significant bit and every bitstring
        # would be mirrored relative to the router and to Qiskit.
        row_axes = list(range(num_qubits - 1, -1, -1))
        col_axes = [num_qubits + k for k in row_axes]
        rho_mat = np.transpose(rho, row_axes + col_axes).reshape((dim, dim))

        return rho_mat

    def density_matrix(self, circuit: Any, noise_model: Optional[NoiseModel] = None) -> np.ndarray:
        """
        Final density matrix of ``circuit`` (terminal measurements ignored).

        The basis index has qubit 0 as its least-significant bit.

        Raises:
            ValueError: If the circuit is refused (unsupported operation,
                mid-circuit measurement) or wider than ``max_qubits``.
        """
        prepared = self._prepare(circuit)
        if isinstance(prepared, SimulationResult):
            raise ValueError(
                prepared.metadata.get("error") or prepared.metadata.get("unresolved_reason")
            )
        blocks, _measured, num_qubits = prepared
        return self._evolve(blocks, num_qubits, noise_model)

    def simulate(
        self,
        circuit: Any,
        noise_model: Optional[NoiseModel] = None,
        shots: int = 1024,
        seed: int = 42,
    ) -> SimulationResult:
        """
        Execute exact density matrix simulation of circuit with optional noise model.

        Raises:
            ValueError: For an invalid ``shots`` or ``seed`` argument (checked
                before any parsing or allocation).
        """
        self._validate_run_arguments(shots, seed)
        t_start = time.perf_counter()

        prepared = self._prepare(circuit)
        if isinstance(prepared, SimulationResult):
            return prepared
        blocks, measured_qubits, num_qubits = prepared
        dim = 1 << num_qubits
        rho_mat = self._evolve(blocks, num_qubits, noise_model)

        # Invariant checks on final density matrix
        trace_val = np.trace(rho_mat)
        trace_err = abs(trace_val - 1.0)
        hermitian_err = np.max(np.abs(rho_mat - rho_mat.conj().T))

        # Check positivity via minimum eigenvalue
        evals = np.linalg.eigvalsh(rho_mat)
        min_eval = float(np.min(evals))

        if trace_err > 1e-10 or hermitian_err > 1e-10 or min_eval < -1e-10:
            return self._failed(
                f"Physical state invariants violated: trace_err={trace_err:.3e}, hermitian_err={hermitian_err:.3e}, min_eval={min_eval:.3e}"
            )

        # Ideal outcome probabilities from diagonal
        ideal_probs = np.real(np.diag(rho_mat))
        ideal_probs = np.clip(ideal_probs, 0.0, 1.0)
        prob_sum = np.sum(ideal_probs)
        if prob_sum > 0:
            ideal_probs /= prob_sum

        # Apply readout error if present. Index bit q is qubit q, so the full
        # assignment matrix is M_{n-1} (x) ... (x) M_0.
        noisy_probs = ideal_probs.copy()
        if noise_model and noise_model.readout_errors:
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

        # Marginalise onto the measured qubits. Readout assignment is a product
        # of column-stochastic per-qubit maps, so applying it before summing
        # out unmeasured qubits gives the same marginal as applying it after.
        if measured_qubits is None:
            out_width = num_qubits
            out_probs = noisy_probs
        else:
            out_width = len(measured_qubits)
            out_probs = np.zeros(1 << out_width, dtype=float)
            for idx, prob in enumerate(noisy_probs):
                out_idx = 0
                for j, q in enumerate(measured_qubits):
                    out_idx |= ((idx >> q) & 1) << j
                out_probs[out_idx] += prob

        # Generate sampled counts using deterministic RNG
        rng = np.random.default_rng(seed)
        multinomial_counts = rng.multinomial(shots, out_probs)

        counts: Dict[str, int] = {}
        for idx, count in enumerate(multinomial_counts):
            if count > 0:
                bitstring = format(idx, f"0{out_width}b")
                counts[bitstring] = int(count)

        # Format probabilities dictionary
        prob_dict: Dict[str, float] = {}
        for idx, prob in enumerate(out_probs):
            if prob > 1e-12:
                bitstring = format(idx, f"0{out_width}b")
                prob_dict[bitstring] = float(prob)

        sampling_bound = hoeffding_total_variation_bound(
            shots=shots, support_size=1 << out_width, delta=0.05
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
                "measured_qubits": measured_qubits,
                "bit_order": "qubit 0 rightmost (little-endian)",
                "counts_are_joint_distribution": True,
                "error_bound_covers": "total_variation",
            },
        )
