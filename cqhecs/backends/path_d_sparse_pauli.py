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
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

from cqhecs.circuit_parsing import parse_circuit
from cqhecs.result import SimulationResult, hoeffding_total_variation_bound


_OBSERVABLE_TOKEN = re.compile(r"\s*Z\s*\[\s*([0-9]+)\s*\]\s*")


def _parse_observable_request(
    observables: Union[Dict[str, int], Sequence[str]],
    num_qubits: int,
) -> Dict[str, int]:
    """
    Parses a user observable request into a mapping of name -> z_mask.

    Accepted forms
    --------------
    * ``{"<Z[0]>": mask}`` with a non-negative integer mask that fits in
      ``num_qubits`` bits,
    * ``["Z[0]", "Z[0]Z[1]"]``: one or more ``Z[i]`` factors, optionally
      separated by whitespace, and nothing else.

    Grammar is strict. A string such as ``"Z[0]garbage"`` is rejected instead
    of having its valid-looking prefix silently extracted. Repeated factors
    cancel because ``Z[i] Z[i] = I``; an observable that cancels completely is
    reported as the identity ``I`` with mask 0 (expectation value 1).
    """
    if isinstance(observables, dict):
        parsed: Dict[str, int] = {}
        for name, mask in observables.items():
            if not isinstance(name, str):
                raise TypeError(
                    f"Observable name must be a string, got "
                    f"{type(name).__name__}"
                )
            if isinstance(mask, bool) or not isinstance(mask, int):
                raise ValueError(
                    f"Observable mask for {name!r} must be an integer, got "
                    f"{mask!r}"
                )
            if mask < 0:
                raise ValueError(
                    f"Observable mask for {name!r} must be non-negative, got "
                    f"{mask}"
                )
            if mask.bit_length() > num_qubits:
                raise ValueError(
                    f"Observable mask for {name!r} uses bit {mask.bit_length() - 1}, "
                    f"beyond the {num_qubits}-qubit system"
                )
            parsed[name] = mask
        return parsed

    result: Dict[str, int] = {}
    for obs_str in observables:
        if not isinstance(obs_str, str):
            raise TypeError(
                f"Observable descriptor must be str, got "
                f"{type(obs_str).__name__}"
            )
        position = 0
        parity: Dict[int, int] = {}
        factors: List[int] = []
        text = obs_str.strip()
        if not text:
            raise ValueError(
                "Empty observable descriptor; expected e.g. 'Z[0]' or "
                "'Z[0]Z[1]'."
            )
        while position < len(text):
            match = _OBSERVABLE_TOKEN.match(text, position)
            if match is None:
                raise ValueError(
                    f"Invalid observable {obs_str!r} at position {position}: "
                    "expected only 'Z[<integer>]' factors (e.g. 'Z[0]Z[1]')."
                )
            qubit = int(match.group(1))
            if not (0 <= qubit < num_qubits):
                raise ValueError(
                    f"Qubit index {qubit} in observable {obs_str!r} is out of "
                    f"range for {num_qubits} qubits."
                )
            parity[qubit] = parity.get(qubit, 0) ^ 1
            if parity[qubit]:
                factors.append(qubit)
            else:
                factors.remove(qubit)
            position = match.end()
            # Skip optional whitespace between factors (already consumed by
            # the token pattern, but a trailing space must not fail the loop).
            while position < len(text) and text[position].isspace():
                position += 1
            if position < len(text) and not text.startswith("Z", position):
                raise ValueError(
                    f"Invalid observable {obs_str!r} at position {position}: "
                    "trailing characters are not allowed."
                )

        mask = 0
        for qubit in sorted(factors):
            mask |= 1 << qubit
        clean_name = "".join(f"Z[{q}]" for q in sorted(factors)) or "I"
        result[clean_name] = mask
    return result

# Pauli basis used for single-qubit conjugation, in (x_mask, z_mask) order.
#   I = (0,0), X = (1,0), Y = (1,1), Z = (0,1)
PAULI_BASIS: Tuple[Tuple[int, int], ...] = ((0, 0), (1, 0), (1, 1), (0, 1))

#: Direct lookup from the packed (x_bit, z_bit) pair to the basis index, so the
#: innermost loop avoids a linear search over PAULI_BASIS.
_PAULI_INDEX_FLAT: Dict[int, int] = {
    (x << 1) | z: index for index, (x, z) in enumerate(PAULI_BASIS)
}


def _pauli_matrices() -> List[np.ndarray]:
    """
    Conventional Pauli matrices {I, X, Y, Z}.

    Used only where a phase convention is explicitly wanted. Path D's term
    storage uses ``X^x Z^z`` instead, so conjugation code must use
    :func:`_basis_matrices`; see that function for why the two differ.
    """
    return [
        np.eye(2, dtype=np.complex128),
        np.array([[0, 1], [1, 0]], dtype=np.complex128),
        np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
        np.array([[1, 0], [0, -1]], dtype=np.complex128),
    ]


def conjugation_matrix(unitary: np.ndarray) -> np.ndarray:
    """
    Builds M such that ``U^dag P_j U = sum_k M[k, j] P_k`` in the Pauli basis.

    The basis must match how terms are *stored*: a term is ``c * X^x Z^z``, so
    the four basis operators are ``I``, ``X``, ``XZ`` and ``Z`` - not
    ``I, X, Y, Z``. ``XZ = -iY``, so using the conventional ``Y`` here while
    the term dict keys mean ``XZ`` silently mis-scales every Y-containing term.

    Coefficients come from the Hilbert-Schmidt inner product
    ``M[k, j] = Tr(P_k^dag U^dag P_j U) / 2``, exact for this 2x2 space.
    """
    paulis = _basis_matrices()
    u_dag = np.conjugate(unitary.T)
    m = np.zeros((4, 4), dtype=np.complex128)
    for j, pj in enumerate(paulis):
        conj = u_dag @ pj @ unitary
        for k, pk in enumerate(paulis):
            m[k, j] = 0.5 * np.trace(pk.conj().T @ conj)
    return m


def _basis_matrices() -> List[np.ndarray]:
    """
    The four basis operators as they are *stored*: X^x Z^z.

    Order matches :data:`PAULI_BASIS`, i.e. I, X, XZ, Z.
    """
    identity = np.eye(2, dtype=np.complex128)
    xm = np.array([[0, 1], [1, 0]], dtype=np.complex128)
    zm = np.array([[1, 0], [0, -1]], dtype=np.complex128)
    return [identity, xm, xm @ zm, zm]


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
        """
        Applies a single-qubit conjugation M to every term.

        This is the innermost loop of Path D, so it avoids anything with
        per-term Python overhead: the Pauli basis index is a direct table
        lookup (not a linear search), and only the non-zero entries of each
        column of M are visited.
        """
        new_terms: Dict[Tuple[int, int], complex] = {}
        xbit = 1 << q
        clear = ~xbit

        # Columns of M, pre-filtered to the entries that actually contribute.
        columns = []
        for j in range(4):
            entries = []
            for k in range(4):
                c = m[k, j]
                if c.real == 0.0 and c.imag == 0.0:
                    continue
                kx, kz = PAULI_BASIS[k]
                entries.append((kx, kz, c))
            columns.append(entries)

        for (x_mask, z_mask), coeff in terms.items():
            xq = (x_mask >> q) & 1
            zq = (z_mask >> q) & 1
            # Basis index j corresponds to X^{xq} Z^{zq}.
            j = _PAULI_INDEX_FLAT[(xq << 1) | zq]
            for kx, kz, c in columns[j]:
                new_x = (x_mask & clear) | (kx << q)
                new_z = (z_mask & clear) | (kz << q)
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

        Verified against explicit 2x2/4x4 matrices for every two-qubit Pauli
        (see tests/test_correctness_contracts.py::TestTwoQubitConjugationRules).

        CX:  X_c -> X_c X_t,  Z_t -> Z_c Z_t, others unchanged.
        CZ:  X_c -> X_c Z_t,  X_t -> Z_c X_t, Z unchanged. When *both* qubits
             carry an X the two rules compose to -X_c X_t Z_c Z_t, so a
             relative sign appears; the Z mask also gains factors on any third
             qubit carrying an X.
        SWAP: X/Z factors simply exchange between the two qubits.
        """
        new_terms: Dict[Tuple[int, int], complex] = {}
        pair_mask = (1 << a) | (1 << b)

        for (x_mask, z_mask), coeff in terms.items():
            factor = coeff
            if name in ("cx", "cnot"):
                xc = (x_mask >> a) & 1
                zt = (z_mask >> b) & 1
                new_x = x_mask ^ (xc << b)
                new_z = z_mask ^ (zt << a)
            elif name == "cz":
                # CZ is diagonal: it commutes with every Z, and conjugates
                #     CZ^dag X_a CZ = X_a Z_b
                #     CZ^dag X_b CZ = Z_a X_b
                # The X mask is unchanged; the Z mask gains Z_b when a carries
                # an X and Z_a when b carries an X. When both carry an X the
                # two images commute, but their product picks up a relative
                # minus sign: CZ^dag X_a X_b CZ = -X_a X_b Z_a Z_b.
                xa = (x_mask >> a) & 1
                xb = (x_mask >> b) & 1
                new_x = x_mask
                new_z = z_mask ^ (xa << b) ^ (xb << a)
                if xa and xb:
                    factor = -coeff
            else:  # swap
                xa = (x_mask >> a) & 1
                za = (z_mask >> a) & 1
                xb = (x_mask >> b) & 1
                zb = (z_mask >> b) & 1
                new_x = (x_mask & ~pair_mask) | (xa << b) | (xb << a)
                new_z = (z_mask & ~pair_mask) | (za << b) | (zb << a)

            new_terms[(new_x, new_z)] = new_terms.get((new_x, new_z), 0.0) + factor

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
        observables: Optional[Dict[str, int]] = None,
    ) -> Tuple[Dict[str, float], float, bool]:
        """
        Computes certified single-qubit and parity expectation values.

        All observables are propagated **in a single backward pass** rather than
        one pass each. The naive version re-walked the circuit for every
        observable, which is O(n^2) observables x O(circuit) and took minutes on
        a 30-qubit deep circuit. Sharing the walk makes it one pass.

        The per-observable error bound is not lost by batching: truncation is
        applied per observable at each step, exactly as before, and each
        observable accumulates its own discarded mass. Because the bound for a
        single observable is the sum of *its own* discarded coefficients, the
        total reported is still the sum over observables, which is what the
        triangle inequality requires.

        Single-qubit marginals alone cannot distinguish entangled states, so
        <Z_q Z_r> pairs are included by default: they are the observables that
        actually carry the Bell/GHZ correlation structure.

        Args:
            instructions: Circuit instructions.
            include_pairs: If True and observables is None, includes all pair parities.
            observables: Explicit dict of name -> z_mask. If provided, overrides include_pairs.

        Returns:
            (expectation_values, accumulated_error_bound, is_unresolved)

            The reported bound is the *total* accumulated bound over every
            observable evaluated, so it bounds every returned value.
        """
        if observables is not None:
            obs_map = dict(observables)
        else:
            obs_map = {}
            for q in range(self.num_qubits):
                obs_map[f"Z[{q}]"] = 1 << q
            if include_pairs:
                for q in range(self.num_qubits):
                    for r in range(q + 1, self.num_qubits):
                        obs_map[f"Z[{q}]Z[{r}]"] = (1 << q) | (1 << r)

        # One backward walk carrying every observable independently.
        states = {name: {(0, mask): complex(1.0, 0.0)}
                  for name, mask in obs_map.items()}
        bounds = dict.fromkeys(states, 0.0)

        # The truncation bound only grows. Once the *combined* bound already
        # exceeds what any of these observables could contribute
        # (each |<Z...>| <= 1), the result is unresolved by construction, so
        # continuing the walk would burn minutes of CPU to produce a value the
        # caller will discard. Bail out as soon as that is provable.
        # For n qubits there are at most `len(states)` terms, each bounded
        # by 1 in absolute value.
        budget_cap = float(len(states))
        running_bound = 0.0

        exhausted = False
        for name, qubits, params in reversed(instructions):
            if name in self.IGNORED_GATES:
                continue
            if exhausted:
                break
            for key, terms in states.items():
                evolved = self._apply_gate_backward(terms, name, qubits, params)
                # Truncate each observable independently so its bound stays
                # its own; the discarded mass is returned, not accumulated
                # into shared state.
                evolved, discarded = self._truncate_terms(evolved)
                bounds[key] += discarded
                running_bound += discarded
                states[key] = evolved
                if running_bound > budget_cap:
                    exhausted = True
                    break

        values: Dict[str, float] = {}
        total_bound = 0.0
        for key, terms in states.items():
            exp_val = 0.0
            for (x_mask, _z_mask), coeff in terms.items():
                if x_mask == 0:
                    exp_val += coeff.real
            values[key] = max(-1.0, min(1.0, exp_val))
            total_bound += bounds[key]

        any_unresolved = total_bound > self.error_tolerance
        if any_unresolved:
            # No value is meaningful once the bound has blown past the
            # tolerance, so report nothing rather than something misleading.
            return {}, float(total_bound), True
        return values, float(total_bound), any_unresolved

    def _truncate_terms(self, terms: Dict[Tuple[int, int], complex]):
        """
        Applies the certified truncation budget to one observable.

        Returns ``(truncated_terms, discarded_mass)`` without touching shared
        state, so several observables can be propagated in one pass with their
        bounds kept separate.
        """
        # Fast path: when nothing was pruned and the budget is not exceeded,
        # the term dict passes through untouched. Sorting on every step was a
        # significant share of Path D's runtime.
        threshold = self.prune_threshold
        budget = self.max_pauli_terms
        if len(terms) <= budget:
            discarded_weight = 0.0
            for coeff in terms.values():
                mag = abs(coeff)
                if mag < threshold:
                    discarded_weight += mag
            if discarded_weight == 0.0:
                return terms, 0.0

        filtered: List[Tuple[Tuple[int, int], complex]] = []
        discarded_weight = 0.0

        for term, coeff in terms.items():
            mag = abs(coeff)
            if mag < threshold:
                discarded_weight += mag
            else:
                filtered.append((term, coeff))

        if len(filtered) > budget:
            filtered.sort(key=lambda item: abs(item[1]), reverse=True)
            kept = filtered[:budget]
            for _, coeff in filtered[budget:]:
                discarded_weight += abs(coeff)
            filtered = kept

        return dict(filtered), discarded_weight

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

    #: Observable construction is O(n) for singles and O(n^2) for pairs, so a
    #: legal million-qubit QASM register must be refused before that loop.
    MAX_QUBITS = 4096
    MAX_SHOTS = 10_000_000

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
        observables: Optional[Union[Dict[str, int], Sequence[str]]] = None,
        include_pairs: Optional[bool] = None,
    ) -> SimulationResult:
        t0 = time.perf_counter()

        if shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots}")
        if shots > self.MAX_SHOTS:
            raise ValueError(
                f"shots must not exceed {self.MAX_SHOTS}, got {shots}"
            )

        tol = error_tolerance if error_tolerance is not None else self.error_tolerance
        instructions, n_q = parse_circuit(circuit)
        if n_q > self.MAX_QUBITS:
            raise ValueError(
                f"Path D supports at most {self.MAX_QUBITS} qubits "
                f"(circuit has {n_q}); refusing before building observables."
            )

        sim = SparsePauliDynamicsSimulator(
            num_qubits=n_q,
            max_pauli_terms=self.max_pauli_terms,
            prune_threshold=self.prune_threshold,
            error_tolerance=tol,
        )

        obs_map: Optional[Dict[str, int]] = None
        if observables is not None:
            obs_map = _parse_observable_request(observables, n_q)
            inc_pairs = False
        else:
            inc_pairs = (n_q <= 30) if include_pairs is None else bool(include_pairs)

        values, error_bound, unresolved = sim.evaluate_expectation_values(
            instructions,
            include_pairs=inc_pairs,
            observables=obs_map,
        )

        counts: Dict[str, int] = {}
        sampling_bound: Optional[float] = None
        counts_supported = False

        if self.allow_uncertified_joint_counts and not unresolved:
            counts, _, _ = sim.sample_marginals(instructions, shots=shots, seed=seed)
            # Support size for the opt-in marginal sampling: one bit per qubit.
            sampling_bound = hoeffding_total_variation_bound(
                shots, support_size=1 << n_q
            )
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
