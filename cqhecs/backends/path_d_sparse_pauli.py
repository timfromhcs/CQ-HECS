"""
Path D: Certified Classical Approximation Backend (Sparse-Pauli-Dynamics).
Heisenberg-picture operator dynamics with certified Pauli weight truncation.

Supported output
----------------
The triangle-inequality truncation bound used here is

    |<O_exact> - <O_approx>| <= sum_{P discarded} |c_P|

which certifies **Pauli expectation values**, not sampled bitstring
distributions. Path D therefore reports `expectation_values` as its primary
result:

* single-qubit observables ``<Z_q>``
* parity/correlation observables ``<Z_q Z_r>`` (these are what capture
  multi-qubit correlations such as Bell and GHZ structure)

Joint `counts` are **not** emitted by default. Reconstructing a bitstring
distribution from independent one-qubit marginals destroys multi-qubit
correlations -- a Bell state would come out uniform -- and the truncation
bound does not certify such a distribution. Callers that genuinely need counts
must opt in via `allow_uncertified_joint_counts=True`, which returns marginal
samples explicitly labelled as *not* a joint distribution and does not attach
the certified bound to them.

If the accumulated bound exceeds the caller's tolerance the result is
`unresolved=True` with no expectation values, never a guess.
"""

from __future__ import annotations
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np

from cqhecs.circuit_parsing import parse_circuit
from cqhecs.result import SimulationResult, hoeffding_total_variation_bound

# Pauli basis used for single-qubit conjugation, in (x_mask, z_mask) order.
#   I = (0,0), X = (1,0), Y = (1,1), Z = (0,1)
PAULI_BASIS: Tuple[Tuple[int, int], ...] = ((0, 0), (1, 0), (1, 1), (0, 1))


def _pauli_matrices() -> List[np.ndarray]:
    return [
        np.eye(2, dtype=np.complex128),
        np.array([[0, 1], [1, 0]], dtype=np.complex128),
        np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
        np.array([[1, 0], [0, -1]], dtype=np.complex128),
    ]


def conjugation_matrix(unitary: np.ndarray) -> np.ndarray:
    """
    Builds M such that ``U^dag P_j U = sum_k M[k, j] P_k`` in the Pauli basis.

    The coefficients come from the Hilbert-Schmidt inner product
    ``M[k, j] = Tr(P_k^dag U^dag P_j U) / 2``, which is exact for the
    four-dimensional 2x2 matrix space. Using the numeric gate matrix instead of
    hand-derived bit algebra keeps phase bookkeeping correct.
    """
    paulis = _pauli_matrices()
    u_dag = np.conjugate(unitary.T)
    m = np.zeros((4, 4), dtype=np.complex128)
    for j, pj in enumerate(paulis):
        conj = u_dag @ pj @ unitary
        for k, pk in enumerate(paulis):
            m[k, j] = 0.5 * np.trace(pk.conj().T @ conj)
    return m


# Single-qubit gate matrices, keyed by the names Path D understands.
def _single_qubit_gate_matrices() -> Dict[str, np.ndarray]:
    mats: Dict[str, np.ndarray] = {
        "i": np.eye(2, dtype=np.complex128),
        "id": np.eye(2, dtype=np.complex128),
        "h": np.array([[1, 1], [1, -1]], dtype=np.complex128) / math.sqrt(2.0),
        "x": np.array([[0, 1], [1, 0]], dtype=np.complex128),
        "y": np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
        "z": np.array([[1, 0], [0, -1]], dtype=np.complex128),
        "s": np.array([[1, 0], [0, 1j]], dtype=np.complex128),
        "sdg": np.array([[1, 0], [0, -1j]], dtype=np.complex128),
        "t": np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=np.complex128),
        "tdg": np.array([[1, 0], [0, np.exp(-1j * math.pi / 4)]], dtype=np.complex128),
    }
    return mats


@dataclass(frozen=True)
class PauliTerm:
    """
    Representation of an n-qubit Pauli operator with phase:
    P = c * (X^{x_mask} Z^{z_mask})
    """
    x_mask: int
    z_mask: int

    def weight(self) -> int:
        """Hamming weight of active non-identity Pauli qubits."""
        return bin(self.x_mask | self.z_mask).count("1")


class UnsupportedPathDOperation(ValueError):
    """Raised when a circuit uses an operation Path D cannot evolve faithfully."""


class SparsePauliDynamicsSimulator:
    """
    Simulates quantum expectation values in the Heisenberg picture:
    O(t) = U^dag O U = sum_P c_P P.
    Applies certified truncation whenever the term budget is exceeded.
    """

    #: Instructions with no effect on the state.
    IGNORED_GATES = frozenset({"barrier", "id", "i"})

    #: Two-qubit gates handled by explicit Clifford conjugation rules.
    TWO_QUBIT_GATES = frozenset({"cx", "cnot", "cz", "swap"})

    #: Rotation gates that take an angle parameter.
    ANGLE_GATES = frozenset({"rz", "p", "u1", "rx", "ry"})

    def __init__(
        self,
        num_qubits: int,
        max_pauli_terms: int = 1024,
        prune_threshold: float = 1e-6,
        error_tolerance: float = 0.05
    ):
        self.num_qubits = num_qubits
        self.max_pauli_terms = max_pauli_terms
        self.prune_threshold = prune_threshold
        self.error_tolerance = error_tolerance
        self.accumulated_error_bound = 0.0
        self._static_mats = _single_qubit_gate_matrices()
        self._conj_cache: Dict[str, np.ndarray] = {
            name: conjugation_matrix(m) for name, m in self._static_mats.items()
        }

    # -- conjugation ---------------------------------------------------
    def _conjugation_for(self, name: str, params: Sequence[float]) -> np.ndarray:
        """Returns M with U^dag P_j U = sum_k M[k, j] P_k for gate `name`."""
        if name in self._conj_cache:
            return self._conj_cache[name]

        if not params:
            raise UnsupportedPathDOperation(
                f"Rotation gate '{name}' requires an angle parameter."
            )
        theta = float(params[0])
        key = f"{name}:{theta!r}"
        cached = self._conj_cache.get(key)
        if cached is not None:
            return cached

        if name in ("rz", "p", "u1"):
            u = np.array(
                [[np.exp(-1j * theta / 2.0), 0.0], [0.0, np.exp(1j * theta / 2.0)]],
                dtype=np.complex128,
            )
        elif name == "rx":
            c, s = math.cos(theta / 2.0), math.sin(theta / 2.0)
            u = np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)
        elif name == "ry":
            c, s = math.cos(theta / 2.0), math.sin(theta / 2.0)
            u = np.array([[c, -s], [s, c]], dtype=np.complex128)
        else:
            raise UnsupportedPathDOperation(
                f"Path D does not support single-qubit gate '{name}'."
            )

        m = conjugation_matrix(u)
        self._conj_cache[key] = m
        return m

    def _apply_gate_backward(
        self,
        terms: Dict[Tuple[int, int], complex],
        name: str,
        qubits: List[int],
        params: List[float]
    ) -> Dict[Tuple[int, int], complex]:
        """
        Computes G^dag P G for all Pauli terms in the current expansion.

        Raises:
            UnsupportedPathDOperation: On any gate that cannot be conjugated
                exactly. Unknown gates are never treated as identity, because
                doing so silently changes the simulated state.
        """
        if name in self.IGNORED_GATES:
            return dict(terms)

        if name in self.TWO_QUBIT_GATES:
            if len(qubits) != 2:
                raise UnsupportedPathDOperation(
                    f"Gate '{name}' expects 2 qubits, got {len(qubits)}."
                )
            return self._apply_two_qubit_backward(terms, name, qubits[0], qubits[1])

        if name in self._static_mats or name in self.ANGLE_GATES:
            if len(qubits) != 1:
                raise UnsupportedPathDOperation(
                    f"Gate '{name}' expects 1 qubit, got {len(qubits)}."
                )
            m = self._conjugation_for(name, params)
            return self._apply_single_qubit_backward(terms, qubits[0], m)

        raise UnsupportedPathDOperation(
            f"Path D does not support gate '{name}'. Refusing to treat an "
            "unrecognised gate as identity, which would corrupt the result."
        )

    def _apply_single_qubit_backward(
        self,
        terms: Dict[Tuple[int, int], complex],
        q: int,
        m: np.ndarray,
    ) -> Dict[Tuple[int, int], complex]:
        """Applies a single-qubit conjugation M to every term."""
        new_terms: Dict[Tuple[int, int], complex] = {}
        xbit, zbit = 1 << q, 1 << q

        for (x_mask, z_mask), coeff in terms.items():
            xq = (x_mask >> q) & 1
            zq = (z_mask >> q) & 1
            # Basis index j corresponds to X^{xq} Z^{zq}.
            j = PAULI_BASIS.index((xq, zq))
            for k, (kx, kz) in enumerate(PAULI_BASIS):
                c = m[k, j]
                if abs(c) < 1e-15:
                    continue
                new_x = (x_mask & ~xbit) | (kx << q)
                new_z = (z_mask & ~zbit) | (kz << q)
                new_terms[(new_x, new_z)] = new_terms.get((new_x, new_z), 0.0) + coeff * c

        return new_terms

    def _apply_two_qubit_backward(
        self,
        terms: Dict[Tuple[int, int], complex],
        name: str,
        a: int,
        b: int,
    ) -> Dict[Tuple[int, int], complex]:
        """
        Exact Clifford conjugation for CX, CZ and SWAP.

        CX:  X_c -> X_c X_t,  Z_t -> Z_c Z_t, others unchanged.
        CZ:  X_c -> X_c Z_t,  X_t -> Z_c X_t, Z unchanged.
        SWAP: X/Z factors simply exchange between the two qubits.
        """
        new_terms: Dict[Tuple[int, int], complex] = {}

        for (x_mask, z_mask), coeff in terms.items():
            if name in ("cx", "cnot"):
                xc = (x_mask >> a) & 1
                zt = (z_mask >> b) & 1
                new_x = x_mask ^ (xc << b)
                new_z = z_mask ^ (zt << a)
            elif name == "cz":
                xa = (x_mask >> a) & 1
                xb = (x_mask >> b) & 1
                new_x = x_mask
                new_z = z_mask ^ (xb << a) ^ (xa << b)
            else:  # swap
                xa = (x_mask >> a) & 1
                za = (z_mask >> a) & 1
                xb = (x_mask >> b) & 1
                zb = (z_mask >> b) & 1
                new_x = (x_mask & ~((1 << a) | (1 << b))) | (xa << b) | (xb << a)
                new_z = (z_mask & ~((1 << a) | (1 << b))) | (za << b) | (zb << a)

            new_terms[(new_x, new_z)] = new_terms.get((new_x, new_z), 0.0) + coeff

        return new_terms

    # -- evaluation ----------------------------------------------------
    def evaluate_observable(
        self,
        instructions: List[Tuple[str, List[int], List[float]]],
        observable_terms: Dict[Tuple[int, int], complex]
    ) -> Tuple[float, float, bool]:
        """
        Evolves observable backwards through circuit gates: O_prev = G^dag O G.

        Args:
            instructions: Parsed circuit as (gate_name, qubits, params).
            observable_terms: Map from (x_mask, z_mask) to complex coefficient.

        Returns:
            (expectation_value, total_error_bound, is_unresolved)
        """
        self.accumulated_error_bound = 0.0
        current_terms = {
            k: v for k, v in observable_terms.items() if abs(v) > 0.0
        }

        # Reverse circuit iteration (Heisenberg picture: O_out = U^dag O U)
        for name, qubits, params in reversed(instructions):
            if name in self.IGNORED_GATES:
                continue
            current_terms = self._apply_gate_backward(current_terms, name, qubits, params)
            current_terms = self._truncate_if_needed(current_terms)

        # <0| P |0> for P = X^x Z^z: Z^z|0> = |0>, but any X component gives 0.
        exp_val = 0.0
        for (x_mask, z_mask), coeff in current_terms.items():
            if x_mask == 0:
                exp_val += coeff.real

        unresolved = (self.accumulated_error_bound > self.error_tolerance)
        return exp_val, float(self.accumulated_error_bound), unresolved

    def evaluate_expectation_values(
        self,
        instructions: List[Tuple[str, List[int], List[float]]],
        include_pairs: bool = True,
    ) -> Tuple[Dict[str, float], float, bool]:
        """
        Computes certified single-qubit and parity expectation values.

        Single-qubit marginals alone cannot distinguish entangled states, so
        <Z_q Z_r> pairs are included by default: they are the observables that
        actually carry the Bell/GHZ correlation structure.

        Returns:
            (expectation_values, accumulated_error_bound, is_unresolved)

            The reported bound is the *total* accumulated bound over every
            observable evaluated, so it bounds every returned value.
        """
        singles: Dict[str, float] = {}
        total_bound = 0.0
        any_unresolved = False

        for q in range(self.num_qubits):
            obs = {(0, 1 << q): complex(1.0, 0.0)}
            val, bound, unres = self.evaluate_observable(instructions, obs)
            singles[f"Z[{q}]"] = max(-1.0, min(1.0, val))
            total_bound += bound
            any_unresolved = any_unresolved or unres

        pairs: Dict[str, float] = {}
        if include_pairs:
            for q in range(self.num_qubits):
                for r in range(q + 1, self.num_qubits):
                    obs = {(0, (1 << q) | (1 << r)): complex(1.0, 0.0)}
                    val, bound, unres = self.evaluate_observable(
                        instructions, obs
                    )
                    pairs[f"Z[{q}]Z[{r}]"] = max(-1.0, min(1.0, val))
                    total_bound += bound
                    any_unresolved = any_unresolved or unres

        values = {**singles, **pairs}
        return values, float(total_bound), any_unresolved

    def sample_marginals(
        self,
        instructions: List[Tuple[str, List[int], List[float]]],
        shots: int = 1024,
        seed: int = 42,
    ) -> Tuple[Dict[str, int], float, bool]:
        """
        Samples each qubit independently from its own <Z_q> marginal.

        This is explicitly NOT a joint measurement distribution. The bits are
        statistically independent, so multi-qubit correlations are destroyed
        (a Bell state comes out uniform). Callers that accept this must opt in
        explicitly and must not treat the result as the circuit's measurement
        distribution.

        Returns:
            (counts, total_marginal_error_bound, any_unresolved)
        """
        if shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots}")

        rng = np.random.default_rng(seed)
        z_expectations: List[float] = []
        total_bound = 0.0
        any_unresolved = False

        for q in range(self.num_qubits):
            obs = {(0, 1 << q): complex(1.0, 0.0)}
            exp_z, bound, unres = self.evaluate_observable(instructions, obs)
            exp_z = max(-1.0, min(1.0, exp_z))
            z_expectations.append(exp_z)
            total_bound += bound
            any_unresolved = any_unresolved or unres

        p1_list = [(1.0 - z) / 2.0 for z in z_expectations]

        counts: Dict[str, int] = {}
        for _ in range(shots):
            bits = "".join("1" if rng.random() < p1 else "0" for p1 in p1_list)
            counts[bits] = counts.get(bits, 0) + 1

        return counts, float(total_bound), any_unresolved

    def _truncate_if_needed(self, terms: Dict[Tuple[int, int], complex]) -> Dict[Tuple[int, int], complex]:
        """
        Certified Pauli 1-norm truncation.
        Discards terms with |c_P| < threshold or beyond max_pauli_terms budget.
        Theorem: |<O_exact> - <O_approx>| <= sum_{P in discarded} |c_P|.
        """
        filtered: List[Tuple[Tuple[int, int], complex]] = []
        discarded_weight = 0.0

        for term, coeff in terms.items():
            mag = abs(coeff)
            if mag < self.prune_threshold:
                discarded_weight += mag
            else:
                filtered.append((term, coeff))

        if len(filtered) > self.max_pauli_terms:
            filtered.sort(key=lambda item: abs(item[1]), reverse=True)
            kept = filtered[:self.max_pauli_terms]
            dropped = filtered[self.max_pauli_terms:]
            for _, coeff in dropped:
                discarded_weight += abs(coeff)
            filtered = kept

        self.accumulated_error_bound += discarded_weight
        return dict(filtered)


class PathDSparsePauliBackend:
    """
    Path D Classical Backend: Certified Sparse-Pauli-Dynamics.

    Reports certified expectation values. Joint counts are opt-in and are never
    certified by the Pauli truncation bound.
    """

    def __init__(
        self,
        max_pauli_terms: int = 1024,
        prune_threshold: float = 1e-5,
        error_tolerance: float = 0.05,
        allow_uncertified_joint_counts: bool = False,
    ):
        self.max_pauli_terms = max_pauli_terms
        self.prune_threshold = prune_threshold
        self.error_tolerance = error_tolerance
        self.allow_uncertified_joint_counts = allow_uncertified_joint_counts

    def execute(
        self,
        circuit: Any,
        shots: int = 1024,
        seed: int = 42,
        error_tolerance: Optional[float] = None,
    ) -> SimulationResult:
        t0 = time.perf_counter()

        if shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots}")

        tol = error_tolerance if error_tolerance is not None else self.error_tolerance
        instructions, n_q = parse_circuit(circuit)

        sim = SparsePauliDynamicsSimulator(
            num_qubits=n_q,
            max_pauli_terms=self.max_pauli_terms,
            prune_threshold=self.prune_threshold,
            error_tolerance=tol,
        )

        values, error_bound, unresolved = sim.evaluate_expectation_values(instructions)

        counts: Dict[str, int] = {}
        sampling_bound: Optional[float] = None
        counts_supported = False

        if self.allow_uncertified_joint_counts and not unresolved:
            counts, _, _ = sim.sample_marginals(instructions, shots=shots, seed=seed)
            sampling_bound = hoeffding_total_variation_bound(shots)
            counts_supported = True

        t1 = time.perf_counter()

        return SimulationResult(
            path="D",
            exact=False,
            error_bound=error_bound,
            unresolved=unresolved,
            counts=counts,
            expectation_values=None if unresolved else values,
            sampling_error_bound=sampling_bound,
            execution_time_ms=(t1 - t0) * 1000.0,
            metadata={
                "backend": "SparsePauliDynamicsSimulator",
                "qubit_count": n_q,
                "error_tolerance": tol,
                "certified_error_bound": error_bound,
                "unresolved": unresolved,
                "max_pauli_terms": self.max_pauli_terms,
                "method": "Heisenberg Sparse-Pauli Certified Approximation",
                "hardware_access": False,
                "classical_only": True,
                "certified_observables": sorted(values.keys()),
                "counts_supported": counts_supported,
                "counts_are_joint_distribution": False,
                "error_bound_covers": "expectation_values",
                "error_bound_excludes": (
                    "sampled_counts" if counts_supported else "counts (not produced)"
                ),
                "numerical_mode": "float64-heisenberg-certified",
                **(
                    {
                        "reason": (
                            "Counts were produced by sampling each qubit "
                            "independently from its own marginal. This is NOT "
                            "the circuit's joint measurement distribution: "
                            "multi-qubit correlations are not preserved."
                        )
                    }
                    if counts_supported
                    else {
                        "reason": (
                            "Path D certifies Pauli expectation values. Joint "
                            "bitstring counts are not produced because the "
                            "Pauli truncation bound does not certify a sampled "
                            "distribution, and independent marginals would "
                            "destroy multi-qubit correlations. Use Path A, B or "
                            "C for exact counts."
                        )
                    }
                ),
            },
        )
