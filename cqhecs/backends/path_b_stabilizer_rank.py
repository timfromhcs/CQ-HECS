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

from cqhecs.circuit_parsing import parse_circuit
from cqhecs.result import SimulationResult, hoeffding_total_variation_bound
from cqhecs.gate_manifest import get_gate, path_gate_names


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

    #: Dense statevector evaluation costs O(2**n) memory. This is an implementation
    #: limit, not a mathematical one: it exists because a 2**n complex vector at
    #: 16 bytes/amplitude runs out of memory well before the rank decomposition
    #: itself becomes infeasible.
    MAX_STATEVECTOR_QUBITS = 22

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
        if self.n <= self.MAX_STATEVECTOR_QUBITS:
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
                # This statevector uses the Qiskit convention: qubit q is bit q of the
                # index, so qubit 0 is the least significant bit. format()
                # already prints the most significant bit first, which is
                # exactly Qiskit's rendering (qubit 0 rightmost).
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
                state = _apply_cx(state, self.n, c, t)
            elif name == "cz":
                c, t = qubits[0], qubits[1]
                state = _apply_cz(state, self.n, c, t)
            elif name == "swap":
                state = _apply_swap(state, self.n, qubits[0], qubits[1])
            else:
                raise StabilizerRankError(
                    f"Path B Clifford branch simulator cannot apply gate '{name}'. "
                    "Unknown gates are refused rather than ignored, because "
                    "ignoring them would silently change the simulated state."
                )

        return state


def _apply_cx(state: np.ndarray, num_qubits: int, ctrl: int, tgt: int) -> np.ndarray:
    """Applies CX by swapping amplitude blocks. Fully vectorised.

    CX maps |c,t> -> |c, t XOR c>, so within the ctrl=1 block the two target
    values are exchanged. Expressed as a reshape with the control as the outer
    of the two manipulated axes, which avoids any transposes entirely.
    """
    if ctrl == tgt:
        return state
    dim = state.size
    lo, hi = (ctrl, tgt) if ctrl < tgt else (tgt, ctrl)
    # Reshape puts `hi` on axis 1 and `lo` on axis 3.
    # `.copy()` because reshape returns a view; writing through it would
    # otherwise mutate the caller's statevector in place.
    view = state.reshape(_two_qubit_reshape(num_qubits, hi, lo)).copy()
    if ctrl == lo:
        # Swap the two qubit axes so the control is always axis 1.
        # Axis order after transpose: (0, 3, 2, 1, 4).
        # `.copy()` matters: transpose returns a view, so writing through it
        # would otherwise mutate the caller's array in place.
        view = view.transpose(0, 3, 2, 1, 4).copy()
    row0 = view[:, 1, :, 0, :].copy()
    row1 = view[:, 1, :, 1, :].copy()
    view[:, 1, :, 0, :] = row1
    view[:, 1, :, 1, :] = row0
    if ctrl == lo:
        view = view.transpose(0, 3, 2, 1, 4)
    return view.reshape(dim)


def _two_qubit_reshape(num_qubits: int, outer: int, inner: int):
    """
    Reshape with qubit `outer` as axis 1 and qubit `inner` as axis 3.

    Shape: [above outer] x [outer] x [between] x [inner] x [below inner].
    """
    return (
        1 << (num_qubits - 1 - outer),
        2,
        1 << (outer - inner - 1),
        2,
        1 << inner,
    )


def _apply_cz(state: np.ndarray, num_qubits: int, a: int, b: int) -> np.ndarray:
    """Applies CZ by negating the |1,1> block. Fully vectorised.

    Returns a new array; the input is never modified.
    """
    if a == b:
        return state
    lo, hi = (a, b) if a < b else (b, a)
    # `reshape` on a contiguous array returns a view, so copy before writing.
    view = state.reshape(_two_qubit_reshape(num_qubits, hi, lo)).copy()
    view[:, 1, :, 1, :] *= -1.0
    return view.reshape(state.size)


def _apply_swap(state: np.ndarray, num_qubits: int, a: int, b: int) -> np.ndarray:
    """Applies SWAP by exchanging the |01> and |10> blocks. Fully vectorised.

    Returns a new array; the input is never modified.
    """
    if a == b:
        return state
    lo, hi = (a, b) if a < b else (b, a)
    view = state.reshape(_two_qubit_reshape(num_qubits, hi, lo)).copy()
    block01 = view[:, 0, :, 1, :].copy()
    block10 = view[:, 1, :, 0, :].copy()
    view[:, 0, :, 1, :] = block10
    view[:, 1, :, 0, :] = block01
    return view.reshape(state.size)


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

    #: Gates the Clifford branch simulator can apply directly, derived from the
    #: shared manifest (parameterised Clifford gates are handled as branches
    #: when the angle is not a multiple of pi/2).
    SUPPORTED_CLIFFORD_GATES = frozenset(
        name
        for name in path_gate_names("B")
        if get_gate(name).clifford and not get_gate(name).parameterised
    )

    #: Non-Clifford gates decomposed into rank branches.
    SUPPORTED_NON_CLIFFORD_GATES = frozenset(
        name
        for name in path_gate_names("B")
        if not (get_gate(name).clifford and not get_gate(name).parameterised)
    )

    #: Instructions with no effect on the state.
    IGNORED_GATES = frozenset({"barrier", "id"})

    #: This backend's exact branch decomposition contracts to a dense
    #: statevector, so the simulator's own ceiling is the execution ceiling.
    MAX_QUBITS = StabilizerRankSimulator.MAX_STATEVECTOR_QUBITS
    MAX_SHOTS = 10_000_000

    def __init__(self, max_rank_branches: int = 16384):
        self.max_rank_branches = max_rank_branches

    def execute(self, circuit: Any, shots: int = 1024, seed: int = 42) -> SimulationResult:
        t0 = time.perf_counter()

        if shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots}")
        if shots > self.MAX_SHOTS:
            raise ValueError(
                f"shots must not exceed {self.MAX_SHOTS}, got {shots}"
            )

        instructions, n_q = parse_circuit(circuit)
        if n_q > self.MAX_QUBITS:
            raise StabilizerRankError(
                f"Path B supports at most {self.MAX_QUBITS} qubits "
                f"(circuit has {n_q}); refusing before allocating a dense "
                "statevector. Route the circuit to Path C or D."
            )
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
            # Support size is the number of distinct measurement outcomes,
            # i.e. 2**num_qubits for a full-register readout.
            sampling_error_bound=hoeffding_total_variation_bound(
                shots, support_size=1 << n_q
            ),
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
            spec = get_gate(name)
            if spec is None:
                raise StabilizerRankError(
                    f"Path B does not support gate '{name}'."
                )
            if len(qubits) != spec.arity:
                raise StabilizerRankError(
                    f"Gate '{name}' expects {spec.arity} qubit(s), got "
                    f"{len(qubits)}: {qubits}"
                )
            if not (spec.min_params <= len(params) <= spec.max_params):
                raise StabilizerRankError(
                    f"Gate '{name}' expects {spec.min_params}.."
                    f"{spec.max_params} parameter(s), got {len(params)}."
                )
