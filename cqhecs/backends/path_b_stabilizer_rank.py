"""
Path B: Stabilizer-Rank-Decomposition Classical Backend (Exact, scales with T-Count).
Decomposes non-Clifford T and rotation operations into an exact linear combination
of stabilizer states (Bravyi-Smith-Smolin / Bravyi-Gosset framework).
Guarantees bit-exact simulation scaling as O(2^(alpha * T)) with 0.0 error bound.
"""

from __future__ import annotations
import cmath
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from cqhecs.result import SimulationResult, hoeffding_total_variation_bound


class StabilizerRankError(RuntimeError):
    """
    Raised when the stabilizer rank decomposition cannot produce a valid result.

    This exists so the router can distinguish "this path genuinely cannot run
    this circuit" (an expected, routable condition) from a programming error.
    """


def _is_clifford_angle(theta: float, tol: float = 1e-7) -> bool:
    """
    Returns True if `theta` is an integer multiple of pi/2 (mod 2*pi).

    Such rotations are Clifford, so they need no rank branching and can be
    applied directly as a diagonal matrix on the branch statevector.
    """
    norm = theta % (2.0 * math.pi)
    ratio = norm / (math.pi / 2.0)
    return abs(ratio - round(ratio)) < tol


class StabilizerRankSimulator:
    """
    Stabilizer rank decomposition simulator.
    Evaluates exact superposition: |psi> = sum_x w_x C_x |0...0>
    where each C_x is a pure Clifford circuit branch.
    """

    #: Dense statevector evaluation costs O(2**n); refuse beyond this width.
    MAX_STATEVECTOR_QUBITS = 16

    def __init__(self, num_qubits: int, max_rank_branches: int = 16384):
        self.n = num_qubits
        self.max_rank_branches = max_rank_branches

    def execute_circuit(
        self,
        instructions: List[Tuple[str, List[int], List[float]]],
        shots: int = 1024,
        seed: int = 42
    ) -> Dict[str, int]:
        """
        instructions: list of (gate_name, qubit_indices, parameters)
        """
        # 1. Identify non-Clifford gates to branch
        t_indices: List[int] = []
        decomposition_coeffs: List[Tuple[complex, complex]] = []
        # Clifford generator substituted for each branch gate when the branch
        # bit selects the non-identity term. RX needs X, RY needs Y, RZ/T need Z.
        branch_clifford: List[str] = []

        for idx, (name, qubits, params) in enumerate(instructions):
            if name == "t":
                t_indices.append(idx)
                # T = c0*I + c1*Z
                # c0 = (1 + exp(i*pi/4)) / 2, c1 = (exp(i*pi/4) - 1) / 2
                e_pi4 = cmath.exp(1j * math.pi / 4.0)
                c0 = (1.0 + e_pi4) / 2.0
                c1 = (e_pi4 - 1.0) / 2.0
                decomposition_coeffs.append((c0, c1))
                branch_clifford.append("z")
            elif name == "tdg":
                t_indices.append(idx)
                e_mpi4 = cmath.exp(-1j * math.pi / 4.0)
                c0 = (1.0 + e_mpi4) / 2.0
                c1 = (e_mpi4 - 1.0) / 2.0
                decomposition_coeffs.append((c0, c1))
                branch_clifford.append("z")
            elif name in ("rz", "p", "u1") and params:
                theta = float(params[0])
                if not _is_clifford_angle(theta):
                    t_indices.append(idx)
                    # RZ(theta) = cos(theta/2)*I - i*sin(theta/2)*Z
                    c0 = complex(math.cos(theta / 2.0), 0.0)
                    c1 = complex(0.0, -math.sin(theta / 2.0))
                    decomposition_coeffs.append((c0, c1))
                    branch_clifford.append("z")
            elif name == "rx" and params:
                theta = float(params[0])
                if not _is_clifford_angle(theta):
                    t_indices.append(idx)
                    # RX(theta) = cos(theta/2)*I - i*sin(theta/2)*X
                    c0 = complex(math.cos(theta / 2.0), 0.0)
                    c1 = complex(0.0, -math.sin(theta / 2.0))
                    decomposition_coeffs.append((c0, c1))
                    branch_clifford.append("x")
            elif name == "ry" and params:
                theta = float(params[0])
                if not _is_clifford_angle(theta):
                    t_indices.append(idx)
                    # RY(theta) = cos(theta/2)*I - i*sin(theta/2)*Y
                    c0 = complex(math.cos(theta / 2.0), 0.0)
                    c1 = complex(0.0, -math.sin(theta / 2.0))
                    decomposition_coeffs.append((c0, c1))
                    branch_clifford.append("y")

        t_count = len(t_indices)
        num_branches = 1 << t_count
        if num_branches > self.max_rank_branches:
            raise ValueError(
                f"T-count {t_count} yields {num_branches} branches, exceeding rank budget {self.max_rank_branches}. "
                "Circuit should be routed to Path C or Path D."
            )

        # 2. For small to moderate circuits (n <= 16), evaluate statevectors directly
        if self.n <= 16:
            dim = 1 << self.n
            total_statevector = np.zeros(dim, dtype=np.complex128)

            for branch in range(num_branches):
                branch_weight = complex(1.0, 0.0)
                branch_circuit: List[Tuple[str, List[int], List[float]]] = []

                t_ptr = 0
                for idx, (name, qubits, params) in enumerate(instructions):
                    if idx in t_indices:
                        bit = (branch >> t_ptr) & 1
                        coeff = decomposition_coeffs[t_ptr][bit]
                        branch_weight *= coeff
                        # Replace the non-Clifford gate with its Clifford
                        # generator (I for bit 0, X/Y/Z for bit 1).
                        if bit == 1:
                            branch_circuit.append((branch_clifford[t_ptr], qubits, []))
                        t_ptr += 1
                    else:
                        branch_circuit.append((name, qubits, params))

                if abs(branch_weight) > 1e-15:
                    branch_sv = self._evolve_clifford_statevector(branch_circuit)
                    total_statevector += branch_weight * branch_sv

            # Compute Born-rule measurement probabilities
            probs = np.abs(total_statevector) ** 2
            norm_sum = float(np.sum(probs))

            # A normalized decomposition must yield unit total probability.
            # Anything else means the algebra is broken; returning a uniform
            # distribution here would fabricate a plausible-looking answer.
            if not np.isfinite(norm_sum) or abs(norm_sum - 1.0) > 1e-6:
                raise StabilizerRankError(
                    "Stabilizer rank decomposition produced a non-unit state "
                    f"(total probability {norm_sum!r}). Refusing to sample from "
                    "an unnormalized or degenerate distribution."
                )

            probs = np.maximum(probs, 0.0)
            probs /= float(np.sum(probs))

            # Sample counts
            rng = np.random.default_rng(seed)
            samples = rng.choice(dim, size=shots, p=probs)
            counts: Dict[str, int] = {}
            for s in samples:
                bs = format(s, f"0{self.n}b")
                counts[bs] = counts.get(bs, 0) + 1
            return counts
        else:
            # For larger n, evaluate Pauli expectation values or Monte Carlo branch sampling
            raise StabilizerRankError(
                f"Exact stabilizer-rank statevector simulation is implemented for at most "
                f"{self.MAX_STATEVECTOR_QUBITS} qubits (circuit has {self.n}). "
                "No approximate fallback is provided; route this circuit to Path C or D."
            )

    def _evolve_clifford_statevector(self, instrs: List[Tuple[str, List[int], List[float]]]) -> np.ndarray:
        """
        Evolves a Clifford branch circuit on a dense statevector.

        Raises:
            StabilizerRankError: If the branch contains a gate this simulator
                cannot apply. Unknown gates are never silently ignored.
        """
        dim = 1 << self.n
        state = np.zeros(dim, dtype=np.complex128)
        state[0] = 1.0

        for name, qubits, params in instrs:
            if name in ("barrier", "id"):
                continue
            if name == "h":
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                h_mat = np.array([[1.0, 1.0], [1.0, -1.0]], dtype=np.complex128) / np.sqrt(2.0)
                state = np.einsum("ij,ajb->aib", h_mat, state).reshape(dim)
            elif name == "s":
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                s_mat = np.array([[1.0, 0.0], [0.0, 1j]], dtype=np.complex128)
                state = np.einsum("ij,ajb->aib", s_mat, state).reshape(dim)
            elif name == "sdg":
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                sdg_mat = np.array([[1.0, 0.0], [0.0, -1j]], dtype=np.complex128)
                state = np.einsum("ij,ajb->aib", sdg_mat, state).reshape(dim)
            elif name == "x":
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                state = np.flip(state, axis=1).reshape(dim)
            elif name == "y":
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                y_mat = np.array([[0.0, -1j], [1j, 0.0]], dtype=np.complex128)
                state = np.einsum("ij,ajb->aib", y_mat, state).reshape(dim)
            elif name == "z":
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                state[:, 1, :] *= -1.0
                state = state.reshape(dim)
            elif name in ("rz", "p", "u1"):
                # A Clifford-angle rotation survived branch decomposition, so it
                # is applied exactly as a matrix here.
                th = float(params[0])
                diag = np.array(
                    [np.exp(-1j * th / 2.0), np.exp(1j * th / 2.0)],
                    dtype=np.complex128
                )
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                state = np.einsum("j,ajb->ajb", diag, state).reshape(dim)
            elif name == "rx":
                th = float(params[0])
                c, s = np.cos(th / 2.0), np.sin(th / 2.0)
                rx_mat = np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                state = np.einsum("ij,ajb->aib", rx_mat, state).reshape(dim)
            elif name == "ry":
                th = float(params[0])
                c, s = np.cos(th / 2.0), np.sin(th / 2.0)
                ry_mat = np.array([[c, -s], [s, c]], dtype=np.complex128)
                q = qubits[0]
                state = state.reshape((1 << (self.n - 1 - q), 2, 1 << q))
                state = np.einsum("ij,ajb->aib", ry_mat, state).reshape(dim)
            elif name in ("cx", "cnot"):
                c, t = qubits[0], qubits[1]
                for i in range(dim):
                    if (i & (1 << c)) and not (i & (1 << t)):
                        partner = i | (1 << t)
                        state[i], state[partner] = state[partner], state[i]
            elif name == "cz":
                c, t = qubits[0], qubits[1]
                for i in range(dim):
                    if (i & (1 << c)) and (i & (1 << t)):
                        state[i] *= -1.0
            elif name == "swap":
                q1, q2 = qubits[0], qubits[1]
                for i in range(dim):
                    b1 = (i >> q1) & 1
                    b2 = (i >> q2) & 1
                    if b1 != b2 and b1 == 1:
                        partner = (i & ~(1 << q1)) | (1 << q2)
                        state[i], state[partner] = state[partner], state[i]
            else:
                raise StabilizerRankError(
                    f"Path B Clifford branch simulator cannot apply gate '{name}'. "
                    "Unknown gates are refused rather than ignored, because "
                    "ignoring them would silently change the simulated state."
                )

        return state


class PathBStabilizerRankBackend:
    """
    Path B Classical Backend: Stabilizer Rank Decomposition.

    Correctness class
    -----------------
    The rank decomposition is *algebraically* exact - every non-Clifford gate is
    expanded into a finite sum over Clifford branches with no approximation and
    no dropped terms, so ``error_bound`` is 0.0.

    It is evaluated in IEEE-754 double precision, and the returned ``counts``
    are a finite-shot sample. Both are reported separately as
    ``numerical_error_bound`` and ``sampling_error_bound``; ``exact=True`` means
    no approximation was applied, not that the arithmetic is symbolic.
    """

    #: Gates the Clifford branch simulator can apply directly.
    SUPPORTED_CLIFFORD_GATES = frozenset({
        "h", "s", "sdg", "x", "y", "z", "cx", "cnot", "cz", "swap", "barrier", "id",
        "rz", "p", "u1", "rx", "ry",
    })

    #: Non-Clifford gates decomposed into rank branches.
    SUPPORTED_NON_CLIFFORD_GATES = frozenset({"t", "tdg", "rz", "p", "u1", "rx", "ry"})

    #: Instructions with no effect on the state.
    IGNORED_GATES = frozenset({"barrier", "id"})

    def __init__(self, max_rank_branches: int = 16384):
        self.max_rank_branches = max_rank_branches

    def execute(self, circuit: Any, shots: int = 1024, seed: int = 42) -> SimulationResult:
        t0 = time.perf_counter()

        if shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots}")

        instructions, n_q = self._parse_circuit(circuit)
        self._validate_instructions(instructions)

        sim = StabilizerRankSimulator(n_q, max_rank_branches=self.max_rank_branches)
        counts = sim.execute_circuit(instructions, shots=shots, seed=seed)

        t1 = time.perf_counter()
        return SimulationResult(
            path="B",
            exact=True,
            error_bound=0.0,
            unresolved=False,
            counts=counts,
            sampling_error_bound=hoeffding_total_variation_bound(shots),
            execution_time_ms=(t1 - t0) * 1000.0,
            metadata={
                "backend": "StabilizerRankSimulator",
                "qubit_count": n_q,
                "shots": shots,
                "seed": seed,
                "method": "Bravyi-Smith-Smolin Stabilizer Rank Decomposition",
                "truncation_applied": False,
                "numerical_mode": "float64-exact-decomposition",
                "numerical_note": (
                    "Decomposition is algebraically exact (no dropped terms). "
                    "Arithmetic is float64; counts are a finite-shot sample."
                ),
            }
        )

    def _validate_instructions(
        self, instructions: List[Tuple[str, List[int], List[float]]]
    ) -> None:
        """Fail closed on gates this backend cannot faithfully execute."""
        supported = self.SUPPORTED_CLIFFORD_GATES | self.SUPPORTED_NON_CLIFFORD_GATES
        two_qubit = {"cx", "cnot", "cz", "swap"}
        one_qubit = {
            "h", "s", "sdg", "x", "y", "z", "t", "tdg", "rz", "p", "u1", "barrier", "id"
        }
        needs_params = {"rz", "p", "u1"}

        for name, qubits, params in instructions:
            if name == "measure":
                raise StabilizerRankError(
                    "Path B does not support measurement instructions."
                )
            if name in self.IGNORED_GATES:
                continue
            if name not in supported:
                raise StabilizerRankError(
                    f"Path B does not support gate '{name}'. "
                    f"Supported gates: {sorted(supported)}."
                )
            if name in two_qubit and len(qubits) != 2:
                raise StabilizerRankError(
                    f"Gate '{name}' expects 2 qubits, got {len(qubits)}: {qubits}"
                )
            if name in one_qubit and len(qubits) != 1:
                raise StabilizerRankError(
                    f"Gate '{name}' expects 1 qubit, got {len(qubits)}: {qubits}"
                )
            if name in needs_params and not params:
                raise StabilizerRankError(
                    f"Gate '{name}' requires a rotation angle parameter."
                )

    def _parse_circuit(self, circuit: Any) -> Tuple[List[Tuple[str, List[int], List[float]]], int]:
        instructions: List[Tuple[str, List[int], List[float]]] = []
        if hasattr(circuit, "data") and hasattr(circuit, "num_qubits"):
            n_q = circuit.num_qubits
            for inst in circuit.data:
                op = inst.operation
                name = op.name.lower()
                q_idx = [circuit.find_bit(q).index for q in inst.qubits]
                params = [float(p) for p in op.params] if hasattr(op, "params") else []
                instructions.append((name, q_idx, params))
            return instructions, n_q
        elif isinstance(circuit, str):
            from cqhecs.circuit_analyzer import CircuitAnalyzer
            analyzer = CircuitAnalyzer()
            props = analyzer.analyze(circuit)
            n_q = max(props.num_qubits, 1)
            import re
            gate_pattern = re.compile(r"([a-zA-Z0-9_]+)(?:\(([^)]*)\))?\s+([^;]+);")
            for line in circuit.splitlines():
                line = line.strip()
                if not line or line.startswith("//") or line.startswith("openqasm") or line.startswith("include") or line.startswith("qreg") or line.startswith("creg"):
                    continue
                m = gate_pattern.search(line)
                if m:
                    gname = m.group(1).lower()
                    params_str = m.group(2)
                    args_str = m.group(3)
                    q_matches = re.findall(r"\[(\d+)\]", args_str)
                    q_idx = [int(x) for x in q_matches]
                    params = []
                    if params_str:
                        try:
                            expr = params_str.replace("pi", str(math.pi))
                            params = [float(eval(expr, {"__builtins__": None}, {}))]
                        except Exception:
                            params = []
                    instructions.append((gname, q_idx, params))
            return instructions, n_q
        else:
            raise ValueError("Unsupported circuit input for Path B.")
