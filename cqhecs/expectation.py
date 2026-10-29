"""
Pauli expectation values across the four-path stack.

``expectation_values(circuit, observables)`` evaluates ``<psi|P|psi>`` for
general Pauli strings (``X``, ``Y``, ``Z``) and weighted sums of them on the
state prepared by a circuit from ``|0...0>``.

Engines (``method``)
--------------------
``stabilizer``  Exact for Clifford circuits at any supported width. The state is
                a stabilizer tableau; ``<P>`` is ``0`` or ``+-1`` and is read
                from the tableau without sampling.
``dense``       Exact float64 statevector (:mod:`cqhecs.backends.dense_reference`)
                up to ``DENSE_MAX_QUBITS`` qubits. No deliberate approximation.
``sparse_pauli``  Path D Heisenberg propagation with a certified truncation
                bound, for wide non-Clifford circuits. ``X``/``Y`` letters are
                rotated into ``Z`` by appending basis changes, one Path D run
                per distinct rotation pattern. A value whose bound exceeds the
                tolerance is *not* returned (``None`` and ``unresolved``).
``auto``        ``stabilizer`` if the circuit is Clifford, else ``dense`` if it
                fits, else ``sparse_pauli``.

Contract
--------
Values are exact expectation values of the ideal circuit, not sampled counts.
``error_bound`` is the deliberate-approximation bound on every returned value
(``0.0`` for the exact engines; a sum of ``|coefficient| * bound`` for Path D).
Float64 roundoff of the dense engine is not quantified and is not included.
Mid-circuit measurement, reset and classical control are refused.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from cqhecs.backends.dense_reference import (
    MAX_DENSE_QUBITS,
    DenseReferenceError,
    simulate,
)
from cqhecs.circuit_parsing import parse_circuit

#: Default ceiling for the dense engine (2**22 amplitudes = 64 MiB).
DENSE_MAX_QUBITS = 22

#: Stabilizer width limit, matching Path A.
STABILIZER_MAX_QUBITS = 4096

METHODS = ("auto", "stabilizer", "dense", "sparse_pauli")

_SPARSE_TOKEN = re.compile(r"\s*([IXYZixyz])\s*\[?\s*([0-9]+)\s*\]?")


class ExpectationError(ValueError):
    """Raised for invalid observables, circuits or method requests."""


# --------------------------------------------------------------------------
# Pauli strings
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PauliString:
    """A tensor product of single-qubit Paulis; identity factors are omitted."""

    ops: Tuple[Tuple[int, str], ...]

    @property
    def label(self) -> str:
        return "".join(f"{letter}[{q}]" for q, letter in self.ops) or "I"

    @property
    def weight(self) -> int:
        return len(self.ops)


def parse_pauli(text: str, num_qubits: int) -> PauliString:
    """
    Parses a Pauli string.

    Accepted forms:
      * dense Qiskit label of length ``num_qubits`` with the **rightmost**
        character acting on qubit 0, e.g. ``"IZXY"``;
      * sparse list of ``<letter><qubit>`` factors, e.g. ``"X0 Z2"`` or
        ``"X[0]Z[2]"``.

    Every qubit may appear at most once and must be in range.
    """
    if not isinstance(text, str):
        raise ExpectationError(f"Pauli string must be str, got {type(text).__name__}")
    raw = text.strip()
    if not raw:
        raise ExpectationError("empty Pauli string")
    upper = raw.upper()
    if re.fullmatch(r"[IXYZ]+", upper):
        if len(upper) != num_qubits:
            raise ExpectationError(
                f"dense Pauli label {text!r} has {len(upper)} letters but the circuit "
                f"has {num_qubits} qubits; use the sparse form (e.g. 'X0 Z2') for "
                "partial strings"
            )
        ops = [
            (num_qubits - 1 - i, letter)
            for i, letter in enumerate(upper)
            if letter != "I"
        ]
        return PauliString(tuple(sorted(ops)))

    pos = 0
    seen: Dict[int, str] = {}
    while pos < len(raw):
        match = _SPARSE_TOKEN.match(raw, pos)
        if match is None:
            raise ExpectationError(
                f"invalid Pauli string {text!r} at position {pos}: expected "
                "'<I|X|Y|Z><qubit>' factors such as 'X0 Z2' or 'X[0]Z[2]'"
            )
        letter, qubit = match.group(1).upper(), int(match.group(2))
        if not 0 <= qubit < num_qubits:
            raise ExpectationError(
                f"qubit {qubit} in {text!r} is out of range for {num_qubits} qubits"
            )
        if qubit in seen:
            raise ExpectationError(
                f"qubit {qubit} appears twice in {text!r}; products of Paulis on "
                "one qubit are not accepted"
            )
        seen[qubit] = letter
        pos = match.end()
    ops = sorted((q, letter) for q, letter in seen.items() if letter != "I")
    return PauliString(tuple(ops))


Terms = List[Tuple[float, PauliString]]


def _normalize_observables(
    observables: Union[Sequence[str], Mapping[str, Any]],
    num_qubits: int,
) -> Dict[str, Terms]:
    out: Dict[str, Terms] = {}
    if isinstance(observables, str):
        raise ExpectationError(
            "observables must be a list of Pauli strings or a mapping, not a bare string"
        )
    if isinstance(observables, Mapping):
        items = list(observables.items())
    else:
        items = [(o, o) for o in observables]
    if not items:
        raise ExpectationError("no observables requested")
    for name, spec in items:
        if not isinstance(name, str) or not name:
            raise ExpectationError(f"observable name must be a non-empty str, got {name!r}")
        if name in out:
            raise ExpectationError(f"duplicate observable name {name!r}")
        if isinstance(spec, str):
            terms: Terms = [(1.0, parse_pauli(spec, num_qubits))]
        else:
            terms = []
            for entry in spec:
                try:
                    coeff, label = entry
                except (TypeError, ValueError) as exc:
                    raise ExpectationError(
                        f"weighted term {entry!r} of {name!r} must be (coefficient, string)"
                    ) from exc
                if isinstance(coeff, bool) or not isinstance(coeff, (int, float)):
                    raise ExpectationError(
                        f"coefficient {coeff!r} in {name!r} must be a real number"
                    )
                if not math.isfinite(coeff):
                    raise ExpectationError(f"coefficient {coeff!r} in {name!r} is not finite")
                terms.append((float(coeff), parse_pauli(label, num_qubits)))
            if not terms:
                raise ExpectationError(f"observable {name!r} has no terms")
        out[name] = terms
    return out


# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------
@dataclass
class ExpectationResult:
    """Outcome of :func:`expectation_values`."""

    values: Dict[str, Optional[float]]
    method: str
    exact: bool
    error_bound: float
    unresolved: bool
    num_qubits: int
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "values": self.values,
            "method": self.method,
            "exact": self.exact,
            "error_bound": self.error_bound,
            "error_bound_covers": "expectation_values",
            "unresolved": self.unresolved,
            "num_qubits": self.num_qubits,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


# --------------------------------------------------------------------------
# Engines
# --------------------------------------------------------------------------
def _strip_terminal_measurements(instructions: Sequence[Any]) -> List[Any]:
    first = next((i for i, inst in enumerate(instructions) if inst[0] == "measure"), None)
    if first is None:
        return list(instructions)
    if any(inst[0] != "measure" for inst in instructions[first:]):
        raise ExpectationError(
            "mid-circuit measurement is not supported for expectation values"
        )
    return list(instructions[:first])


def _stabilizer_state(instructions: Sequence[Any], num_qubits: int):
    from cqhecs.backends.path_a_stabilizer import (
        PathAStabilizerBackend,
        StabilizerTableauSimulator,
        UnsupportedPathAOperation,
    )

    backend = PathAStabilizerBackend()
    try:
        backend._validate(list(instructions))
    except UnsupportedPathAOperation as exc:
        raise ExpectationError(f"circuit is not a Clifford circuit: {exc}") from exc
    sim = StabilizerTableauSimulator(num_qubits)
    backend._apply_instructions(sim, list(instructions))
    return sim


def _stabilizer_expectation(sim: Any, ops: Sequence[Tuple[int, str]]) -> int:
    """Exact ``<P>`` in ``{-1, 0, +1}`` from an Aaronson-Gottesman tableau."""
    n = sim.n
    px = np.zeros(n, dtype=np.int64)
    pz = np.zeros(n, dtype=np.int64)
    for q, letter in ops:
        if letter in ("X", "Y"):
            px[q] = 1
        if letter in ("Z", "Y"):
            pz[q] = 1
    tab = sim.tableau
    x_part = tab[:2 * n, :n].astype(np.int64)
    z_part = tab[:2 * n, n:2 * n].astype(np.int64)
    anticommutes = (x_part @ pz + z_part @ px) % 2
    if anticommutes[n:].any():
        return 0  # P anticommutes with a stabilizer generator
    tab[2 * n, :] = 0
    for j in np.nonzero(anticommutes[:n])[0]:
        sim._row_sum(2 * n, n + int(j))
    if not (np.array_equal(tab[2 * n, :n], px) and np.array_equal(tab[2 * n, n:2 * n], pz)):
        raise RuntimeError("stabilizer decomposition did not reproduce the Pauli string")
    return 1 - 2 * int(tab[2 * n, 2 * n])


def _rotation_signature(ops: Sequence[Tuple[int, str]]) -> Tuple[Tuple[int, str], ...]:
    return tuple((q, letter) for q, letter in ops if letter in ("X", "Y"))


def _basis_rotation(signature: Sequence[Tuple[int, str]]) -> List[Any]:
    gates: List[Any] = []
    for q, letter in signature:
        if letter == "Y":
            gates.append(("sdg", [q], []))
        gates.append(("h", [q], []))
    return gates


def _evaluate_terms(
    instructions: List[Any],
    num_qubits: int,
    method: str,
    terms: Dict[Tuple[Tuple[int, str], ...], Optional[float]],
    error_tolerance: float,
    max_pauli_terms: int,
    meta: Dict[str, Any],
) -> Tuple[Dict[Tuple[Tuple[int, str], ...], Optional[float]], Dict[Any, float], bool]:
    """Fills `terms` in place. Returns (terms, per-term error bound, unresolved)."""
    bounds: Dict[Any, float] = {key: 0.0 for key in terms}
    unresolved = False

    if method == "stabilizer":
        sim = _stabilizer_state(instructions, num_qubits)
        for key in terms:
            terms[key] = float(_stabilizer_expectation(sim, key))
        meta["numerical_mode"] = "exact-tableau"
        return terms, bounds, unresolved

    if method == "dense":
        try:
            state = simulate(instructions, num_qubits)
        except DenseReferenceError as exc:
            raise ExpectationError(str(exc)) from exc
        for key in terms:
            terms[key] = state.pauli_expectation(key)
        meta["numerical_mode"] = "float64-dense-statevector"
        return terms, bounds, unresolved

    # sparse_pauli: one Path D run per distinct basis-rotation pattern.
    from cqhecs.backends.path_d_sparse_pauli import (
        PathDSparsePauliBackend,
        UnsupportedPathDOperation,
    )

    groups: Dict[Tuple[Tuple[int, str], ...], List[Any]] = {}
    for key in terms:
        if not key:
            terms[key] = 1.0
            continue
        groups.setdefault(_rotation_signature(key), []).append(key)

    runs = 0
    for signature, keys in groups.items():
        # An idle top qubit would otherwise shrink the width Path D infers
        # from the instruction list and invalidate observables on it.
        rotated = (
            instructions
            + _basis_rotation(signature)
            + [("id", [num_qubits - 1], [])]
        )
        requests = {}
        for idx, key in enumerate(keys):
            mask = 0
            for q, _letter in key:
                mask |= 1 << q
            requests[f"t{idx}"] = mask
        backend = PathDSparsePauliBackend(
            max_pauli_terms=max_pauli_terms, error_tolerance=error_tolerance
        )
        try:
            res = backend.execute(
                rotated, shots=1, error_tolerance=error_tolerance, observables=requests
            )
        except UnsupportedPathDOperation as exc:
            raise ExpectationError(
                f"the sparse_pauli engine cannot evolve this circuit ({exc}); "
                "use method='dense' (up to the dense width limit) or method='stabilizer' "
                "(Clifford circuits)"
            ) from exc
        runs += 1
        if res.unresolved or res.expectation_values is None:
            unresolved = True
            for key in keys:
                terms[key] = None
                bounds[key] = float(res.error_bound)
            continue
        for idx, key in enumerate(keys):
            terms[key] = float(res.expectation_values[f"t{idx}"])
            bounds[key] = float(res.error_bound)
    meta["numerical_mode"] = "float64-heisenberg-certified"
    meta["sparse_pauli_runs"] = runs
    return terms, bounds, unresolved


def _is_clifford(instructions: List[Any], num_qubits: int) -> bool:
    try:
        _stabilizer_state(instructions, num_qubits)
    except ExpectationError:
        return False
    return True


def expectation_values(
    circuit: Any,
    observables: Union[Sequence[str], Mapping[str, Any]],
    *,
    method: str = "auto",
    error_tolerance: float = 0.05,
    max_pauli_terms: int = 1024,
    dense_max_qubits: int = DENSE_MAX_QUBITS,
) -> ExpectationResult:
    """
    Evaluates Pauli expectation values on the state prepared by `circuit`.

    Args:
        circuit: Qiskit circuit, OpenQASM string or instruction list. Composite
            gates are lowered exactly; terminal measurements are ignored.
        observables: list of Pauli strings (see :func:`parse_pauli`), or a
            mapping ``name -> string`` / ``name -> [(coefficient, string), ...]``.
        method: one of :data:`METHODS`.
        error_tolerance: Path D acceptance tolerance on the total bound.
        max_pauli_terms: Path D term budget.
        dense_max_qubits: width limit for the dense engine.

    Raises:
        ExpectationError: invalid observables, non-Clifford circuit with
            ``method="stabilizer"``, or a register too wide for ``dense``.
    """
    t0 = time.perf_counter()
    if method not in METHODS:
        raise ExpectationError(f"method must be one of {METHODS}, got {method!r}")
    if not (isinstance(error_tolerance, (int, float)) and 0.0 < error_tolerance <= 1.0):
        raise ExpectationError(f"error_tolerance must lie in (0, 1], got {error_tolerance!r}")
    if not (isinstance(dense_max_qubits, int) and 1 <= dense_max_qubits <= MAX_DENSE_QUBITS):
        raise ExpectationError(
            f"dense_max_qubits must be an integer in [1, {MAX_DENSE_QUBITS}]"
        )

    instructions, num_qubits = parse_circuit(circuit)
    instructions = _strip_terminal_measurements(instructions)
    if num_qubits < 1:
        raise ExpectationError("circuit has no qubits")
    if num_qubits > STABILIZER_MAX_QUBITS:
        raise ExpectationError(
            f"circuits wider than {STABILIZER_MAX_QUBITS} qubits are not supported"
        )
    for name, _q, _p in instructions:
        if name == "reset":
            raise ExpectationError("reset is not supported for expectation values")

    parsed = _normalize_observables(observables, num_qubits)

    chosen = method
    if method == "auto":
        if _is_clifford(instructions, num_qubits):
            chosen = "stabilizer"
        elif num_qubits <= dense_max_qubits:
            chosen = "dense"
        else:
            chosen = "sparse_pauli"
    elif method == "dense" and num_qubits > dense_max_qubits:
        raise ExpectationError(
            f"dense method needs 2^{num_qubits} amplitudes; limit is "
            f"{dense_max_qubits} qubits"
        )

    unique: Dict[Tuple[Tuple[int, str], ...], Optional[float]] = {}
    for terms in parsed.values():
        for _coeff, pauli in terms:
            unique[pauli.ops] = None

    meta: Dict[str, Any] = {
        "requested_method": method,
        "hardware_access": False,
        "classical_only": True,
        "distinct_pauli_strings": len(unique),
    }
    values_by_term, bounds, term_unresolved = _evaluate_terms(
        instructions, num_qubits, chosen, unique, error_tolerance, max_pauli_terms, meta,
    )

    results: Dict[str, Optional[float]] = {}
    total_bound = 0.0
    unresolved = False
    for name, terms in parsed.items():
        parts = [values_by_term[pauli.ops] for _c, pauli in terms]
        if any(v is None for v in parts):
            results[name] = None
            unresolved = True
        else:
            results[name] = float(sum(c * v for (c, _p), v in zip(terms, parts)))
        total_bound = max(
            total_bound,
            sum(abs(c) * bounds[pauli.ops] for c, pauli in terms),
        )

    exact = chosen in ("stabilizer", "dense")
    if chosen == "sparse_pauli" and unresolved:
        meta["reason"] = (
            "Path D could not certify every requested value within the tolerance; "
            "unresolved observables are reported as None, never guessed."
        )
    return ExpectationResult(
        values=results,
        method=chosen,
        exact=exact,
        error_bound=0.0 if exact else float(total_bound),
        unresolved=unresolved or term_unresolved,
        num_qubits=num_qubits,
        execution_time_ms=(time.perf_counter() - t0) * 1000.0,
        metadata=meta,
    )
