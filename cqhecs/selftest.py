"""
Metamorphic and property-based self-test for a CQ-HECS installation.

The suite is deliberately independent of the production router: it drives the
dense reference, the exact MPS chain and the noise channels directly, and checks
relations that must hold for *any* correct implementation:

* normalization and non-negativity of probabilities;
* ``C† C = I`` (inverse identity) on random circuits;
* qubit-permutation equivariance (including the documented MPS endianness);
* ``p(θ)`` and ``rz(θ)`` differ only by a global phase;
* exact MPS contraction equals the dense reference up to a global phase;
* finite-shot sampling is within a Hoeffding total-variation bound, with a
  Bonferroni-corrected failure budget across checks;
* Kraus channels preserve trace/Hermiticity/positivity, depolarizing noise is
  unital, and the readout assignment matrix is column-stochastic;
* the dense expectation engine agrees with the statevector oracle.

This is a test oracle, not a proof of correctness. It can miss bugs that all
implementations share (for example a wrong but consistent gate matrix). The
dense reference and Qiskit differential tests remain the independent oracles.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence, Tuple

import numpy as np

from cqhecs.backends.dense_reference import (
    DenseStatevector,
    _single_qubit_matrix,
    _two_qubit_tensor,
)
from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.backends.path_c_mps_exact import ExactMPSTensorChain
from cqhecs.hardware_bridge import (
    AmplitudeDampingChannel,
    ComposedChannel,
    DepolarizingChannel,
    NoiseModel,
    ReadoutErrorChannel,
    TwoQubitDepolarizingChannel,
)
from cqhecs.result import hoeffding_total_variation_bound

SELFTEST_SCHEMA_VERSION = "1.0"

_ONE_QUBIT = ("h", "x", "y", "z", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "p")
_TWO_QUBIT = ("cx", "cz", "swap", "cp", "crx", "cry", "crz")
_ANGLE = frozenset({"rx", "ry", "rz", "p", "cp", "crx", "cry", "crz"})
_SELF_INVERSE = frozenset({"h", "x", "y", "z", "cx", "cz", "swap"})
_DAGGER = {"s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}


@dataclass
class SelftestCheck:
    name: str
    passed: bool
    detail: str
    duration_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "duration_ms": self.duration_ms,
        }


@dataclass
class SelftestReport:
    checks: List[SelftestCheck]
    seed: int
    cases: int
    schema_version: str = SELFTEST_SCHEMA_VERSION

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "seed": self.seed,
            "cases": self.cases,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
        }


def _random_circuit(rng: random.Random, num_qubits: int, depth: int) -> List[Tuple[str, List[int], List[float]]]:
    circuit: List[Tuple[str, List[int], List[float]]] = []
    for _ in range(depth):
        if rng.random() < 0.45:
            name = rng.choice(_TWO_QUBIT)
            qubits = rng.sample(range(num_qubits), 2)
            params = [rng.uniform(-math.pi, math.pi)] if name in _ANGLE else []
            circuit.append((name, qubits, params))
        else:
            name = rng.choice(_ONE_QUBIT)
            qubits = [rng.randrange(num_qubits)]
            params = [rng.uniform(-math.pi, math.pi)] if name in _ANGLE else []
            circuit.append((name, qubits, params))
    # Force the inferred width to be exactly num_qubits.
    circuit.extend(("id", [q], []) for q in range(num_qubits))
    return circuit


def _inverse(circuit: Sequence[Tuple[str, List[int], List[float]]]) -> List[Tuple[str, List[int], List[float]]]:
    inverted: List[Tuple[str, List[int], List[float]]] = []
    for name, qubits, params in reversed(circuit):
        if name in ("id", "barrier"):
            continue
        if name in _SELF_INVERSE:
            inverted.append((name, list(qubits), list(params)))
        elif name in _DAGGER:
            inverted.append((_DAGGER[name], list(qubits), list(params)))
        elif name in _ANGLE:
            inverted.append((name, list(qubits), [-float(p) for p in params]))
        else:
            raise ValueError(f"no inverse rule for {name!r}")
    return inverted


def _dense_statevector(circuit: Sequence[Tuple[str, List[int], List[float]]], num_qubits: int) -> np.ndarray:
    simulator = DenseStatevector(num_qubits)
    simulator.run(circuit)
    return simulator.statevector()


def _mps_statevector(circuit: Sequence[Tuple[str, List[int], List[float]]], num_qubits: int) -> np.ndarray:
    chain = ExactMPSTensorChain(num_qubits)
    try:
        for name, qubits, params in circuit:
            if name in ("id", "barrier"):
                continue
            if len(qubits) == 1:
                chain.apply_single_qubit_gate(qubits[0], _single_qubit_matrix(name, params))
            elif len(qubits) == 2:
                chain.apply_two_qubit_gate(qubits[0], qubits[1], _two_qubit_tensor(name, params))
            else:
                raise ValueError(f"unsupported arity {len(qubits)} for {name!r}")
        # to_statevector() is chain order (q0 outermost); reverse to Qiskit order.
        raw = chain.to_statevector().reshape((2,) * num_qubits)
        return raw.transpose(tuple(range(num_qubits - 1, -1, -1))).reshape(-1)
    finally:
        chain.cleanup()


def _fidelity(a: np.ndarray, b: np.ndarray) -> float:
    return float(abs(np.vdot(a, b)) ** 2 / (np.vdot(a, a).real * np.vdot(b, b).real))


def _probabilities(state: np.ndarray) -> np.ndarray:
    return np.abs(state) ** 2


def _check_normalization(cases: int, seed: int) -> str:
    for case in range(cases):
        rng = random.Random(seed + case)
        n = rng.randint(2, 5)
        circuit = _random_circuit(rng, n, rng.randint(3, 10))
        probs = _probabilities(_dense_statevector(circuit, n))
        if abs(float(probs.sum()) - 1.0) > 1e-12:
            raise AssertionError(f"case {case}: probabilities sum to {probs.sum()!r}")
        if float(probs.min()) < -1e-15:
            raise AssertionError(f"case {case}: negative probability {probs.min()!r}")
    return f"{cases} random circuits, sum-to-one and non-negative"


def _check_inverse_identity(cases: int, seed: int) -> str:
    for case in range(cases):
        rng = random.Random(seed + 1000 + case)
        n = rng.randint(2, 5)
        circuit = _random_circuit(rng, n, rng.randint(3, 10))
        combined = list(circuit) + _inverse(circuit)
        dense = _dense_statevector(combined, n)
        mps = _mps_statevector(combined, n)
        for label, state in (("dense", dense), ("mps", mps)):
            overlap = float(abs(state[0]) ** 2)
            if abs(overlap - 1.0) > 1e-9:
                raise AssertionError(
                    f"case {case} ({label}): C†C|0> has |<0|psi>|^2={overlap!r}"
                )
    return f"{cases} random circuits, dense and MPS return |0...0> up to phase"


def _check_permutation(cases: int, seed: int) -> str:
    for case in range(cases):
        rng = random.Random(seed + 2000 + case)
        n = rng.randint(2, 5)
        circuit = _random_circuit(rng, n, rng.randint(3, 10))
        permutation = list(range(n))
        rng.shuffle(permutation)
        permuted = [
            (name, [permutation[q] for q in qubits], params)
            for name, qubits, params in circuit
        ]
        original = _probabilities(_mps_statevector(circuit, n))
        moved = _probabilities(_mps_statevector(permuted, n))
        remapped = np.zeros_like(moved)
        for index, value in enumerate(moved):
            target = 0
            for old_q in range(n):
                if (index >> permutation[old_q]) & 1:
                    target |= 1 << old_q
            remapped[target] = value
        distance = 0.5 * float(np.abs(remapped - original).sum())
        if distance > 1e-12:
            raise AssertionError(f"case {case}: permutation TV={distance!r}")
    return f"{cases} random circuits, MPS is permutation-equivariant"


def _check_global_phase(cases: int, seed: int) -> str:
    for case in range(cases):
        rng = random.Random(seed + 3000 + case)
        n = rng.randint(2, 4)
        circuit = _random_circuit(rng, n, rng.randint(3, 8))
        indices = [i for i, (name, _q, _p) in enumerate(circuit) if name in ("rz", "p")]
        if not indices:
            circuit = list(circuit) + [("rz", [0], [0.37])]
            indices = [len(circuit) - 1]
        index = rng.choice(indices)
        alternate = list(circuit)
        name, qubits, params = alternate[index]
        alternate[index] = ("p" if name == "rz" else "rz", list(qubits), list(params))
        left = _probabilities(_mps_statevector(circuit, n))
        right = _probabilities(_mps_statevector(alternate, n))
        distance = 0.5 * float(np.abs(left - right).sum())
        if distance > 1e-12:
            raise AssertionError(f"case {case}: p/rz global-phase TV={distance!r}")
    return f"{cases} random circuits, p(theta) equals rz(theta) up to global phase"


def _check_mps_dense_parity(cases: int, seed: int) -> str:
    for case in range(cases):
        rng = random.Random(seed + 4000 + case)
        n = rng.randint(2, 6)
        circuit = _random_circuit(rng, n, rng.randint(3, 12))
        dense = _dense_statevector(circuit, n)
        mps = _mps_statevector(circuit, n)
        fidelity = _fidelity(dense, mps)
        if 1.0 - fidelity > 1e-10:
            raise AssertionError(f"case {case}: MPS/dense infidelity={1.0 - fidelity!r}")
    return f"{cases} random circuits, exact MPS equals dense up to phase"


def _check_sampling(cases: int, seed: int) -> str:
    shots = 20000
    delta = 0.01
    for case in range(cases):
        rng = random.Random(seed + 5000 + case)
        n = rng.randint(3, 5)
        circuit = _random_circuit(rng, n, rng.randint(3, 8))
        chain = ExactMPSTensorChain(n)
        try:
            for name, qubits, params in circuit:
                if name in ("id", "barrier"):
                    continue
                if len(qubits) == 1:
                    chain.apply_single_qubit_gate(qubits[0], _single_qubit_matrix(name, params))
                else:
                    chain.apply_two_qubit_gate(qubits[0], qubits[1], _two_qubit_tensor(name, params))
            exact = _probabilities(_mps_statevector(circuit, n))
            counts, supported = chain.sample(shots=shots, seed=seed + case, measured_qubits=list(range(n)))
        finally:
            chain.cleanup()
        if not supported:
            raise AssertionError(f"case {case}: MPS refused to sample")
        empirical = np.zeros(1 << n, dtype=float)
        for bitstring, count in counts.items():
            empirical[int(bitstring, 2)] += count
        empirical /= shots
        distance = 0.5 * float(np.abs(empirical - exact).sum())
        bound = hoeffding_total_variation_bound(
            shots, support_size=1 << n, delta=delta / max(cases, 1)
        )
        if distance > bound:
            raise AssertionError(
                f"case {case}: sampling TV={distance!r} exceeds Hoeffding bound {bound!r}"
            )
    return f"{cases} circuits x {shots} shots, TV within a Bonferroni-corrected Hoeffding bound"


def _check_noise_invariants(cases: int, seed: int) -> str:  # noqa: ARG001 - signature parity
    rng = np.random.default_rng(seed)
    for p in (0.0, 0.1, 0.5, 1.0):
        channel = DepolarizingChannel(p)
        matrix = rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2))
        rho = matrix @ matrix.conj().T
        rho /= np.trace(rho)
        out = sum(k @ rho @ k.conj().T for k in channel.kraus_operators)
        if abs(np.trace(out) - 1.0) > 1e-10:
            raise AssertionError(f"depolarizing p={p}: trace={np.trace(out)!r}")
        if np.max(np.abs(out - out.conj().T)) > 1e-10:
            raise AssertionError(f"depolarizing p={p}: not Hermitian")
        if float(np.min(np.linalg.eigvalsh(out))) < -1e-10:
            raise AssertionError(f"depolarizing p={p}: negative eigenvalue")
        fixed = sum(k @ (np.eye(2) / 2) @ k.conj().T for k in channel.kraus_operators)
        if not np.allclose(fixed, np.eye(2) / 2, atol=1e-12):
            raise AssertionError(f"depolarizing p={p}: not unital")
    damping = AmplitudeDampingChannel(0.25)
    matrix = rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2))
    rho = matrix @ matrix.conj().T
    rho /= np.trace(rho)
    out = sum(k @ rho @ k.conj().T for k in damping.kraus_operators)
    if abs(np.trace(out) - 1.0) > 1e-10 or float(np.min(np.linalg.eigvalsh(out))) < -1e-10:
        raise AssertionError("amplitude damping: non-physical output state")
    readout = ReadoutErrorChannel(0.02, 0.05)
    if not np.allclose(readout.matrix.sum(axis=0), [1.0, 1.0], atol=1e-12):
        raise AssertionError("readout assignment matrix is not column-stochastic")
    return "Kraus trace/Hermiticity/positivity, depolarizing unitality, readout column sums"


def _check_expectation(cases: int, seed: int) -> str:
    from cqhecs.expectation import expectation_values

    for case in range(cases):
        rng = random.Random(seed + 6000 + case)
        n = rng.randint(2, 5)
        circuit = _random_circuit(rng, n, rng.randint(3, 8))
        label = "".join(rng.choice("IXYZ") for _ in range(n))
        ops = [(q, letter) for q, letter in enumerate(reversed(label)) if letter != "I"]
        oracle = DenseStatevector(n)
        oracle.run(circuit)
        want = oracle.pauli_expectation(ops)
        result = expectation_values(circuit, [label], method="dense")
        got = result.values[label]
        if got is None or abs(got - want) > 1e-9:
            raise AssertionError(f"case {case}: expectation {got!r} != oracle {want!r}")
    return f"{cases} random circuits, dense expectation matches the statevector oracle"


def _apply_channel(channel: Any, rho: np.ndarray) -> np.ndarray:
    return sum(
        k @ rho @ k.conj().T for k in channel.kraus_operators
    )


def _random_noise_model(circuit, num_qubits: int, rng: random.Random) -> NoiseModel:
    model = NoiseModel("selftest_random")
    seen_1q = set()
    seen_2q = set()
    for name, qubits, _params in circuit:
        if len(qubits) == 1 and (name, qubits[0]) not in seen_1q:
            seen_1q.add((name, qubits[0]))
            model.add_1q_channel(name, qubits[0], DepolarizingChannel(rng.uniform(0.0, 0.2)))
        elif len(qubits) == 2 and (name, tuple(qubits)) not in seen_2q:
            seen_2q.add((name, tuple(qubits)))
            model.add_2q_channel(
                name,
                (qubits[0], qubits[1]),
                TwoQubitDepolarizingChannel(rng.uniform(0.0, 0.2)),
            )
    for qubit in range(num_qubits):
        model.set_readout_error(qubit, rng.uniform(0.0, 0.1), rng.uniform(0.0, 0.1))
    model.validate()
    return model


def _permute_model(model: NoiseModel, permutation: Sequence[int]) -> NoiseModel:
    moved = NoiseModel("selftest_permuted")
    for gate, by_qubit in model.channels_1q.items():
        for qubit, channels in by_qubit.items():
            for channel in channels:
                moved.add_1q_channel(gate, permutation[qubit], channel)
    for gate, by_pair in model.channels_2q.items():
        for (left, right), channels in by_pair.items():
            for channel in channels:
                moved.add_2q_channel(
                    gate, (permutation[left], permutation[right]), channel
                )
    for qubit, channel in model.readout_errors.items():
        moved.readout_errors[permutation[qubit]] = channel
    moved.validate()
    return moved


def _noisy_probabilities(circuit, model: NoiseModel, num_qubits: int) -> np.ndarray:
    result = NoisyDensityMatrixBackend(max_qubits=10).simulate(
        circuit, noise_model=model, shots=4, seed=1
    )
    if not result.probabilities:
        raise AssertionError(f"noisy simulation returned no probabilities: {result.state}")
    return _probabilities_from_dict(result.probabilities, num_qubits)


def _probabilities_from_dict(probabilities: Dict[str, float], num_qubits: int) -> np.ndarray:
    vector = np.zeros(1 << num_qubits, dtype=float)
    for bitstring, value in probabilities.items():
        vector[int(bitstring, 2)] = float(value)
    return vector


def _check_noise_permutation(cases: int, seed: int) -> str:
    for case in range(cases):
        rng = random.Random(seed + 7000 + case)
        n = rng.randint(2, 5)
        circuit = _random_circuit(rng, n, rng.randint(2, 8))
        permutation = list(range(n))
        rng.shuffle(permutation)
        moved = [
            (name, [permutation[q] for q in qubits], params)
            for name, qubits, params in circuit
        ]
        model = _random_noise_model(circuit, n, rng)
        moved_model = _permute_model(model, permutation)
        original = _noisy_probabilities(circuit, model, n)
        permuted = _noisy_probabilities(moved, moved_model, n)
        remapped = np.zeros_like(permuted)
        for index, value in enumerate(permuted):
            target = 0
            for old_q in range(n):
                if (index >> permutation[old_q]) & 1:
                    target |= 1 << old_q
            remapped[target] = value
        distance = 0.5 * float(np.abs(remapped - original).sum())
        if distance > 1e-10:
            raise AssertionError(f"case {case}: noisy permutation TV={distance!r}")
    return f"{cases} random noisy circuits, permutation-equivariant"


def _check_zero_noise(cases: int, seed: int) -> str:
    for case in range(cases):
        rng = random.Random(seed + 8000 + case)
        n = rng.randint(2, 5)
        circuit = _random_circuit(rng, n, rng.randint(2, 8))
        model = NoiseModel("zero")
        seen_1q = set()
        seen_2q = set()
        for name, qubits, _params in circuit:
            if len(qubits) == 1 and (name, qubits[0]) not in seen_1q:
                seen_1q.add((name, qubits[0]))
                model.add_1q_channel(name, qubits[0], DepolarizingChannel(0.0))
            elif len(qubits) == 2 and (name, tuple(qubits)) not in seen_2q:
                seen_2q.add((name, tuple(qubits)))
                model.add_2q_channel(
                    name, (qubits[0], qubits[1]), TwoQubitDepolarizingChannel(0.0)
                )
        for qubit in range(n):
            model.set_readout_error(qubit, 0.0, 0.0)
        model.validate()
        ideal = _probabilities(_dense_statevector(circuit, n))
        zero_noise = _noisy_probabilities(circuit, model, n)
        distance = 0.5 * float(np.abs(zero_noise - ideal).sum())
        if distance > 1e-12:
            raise AssertionError(f"case {case}: zero-noise TV={distance!r}")
    return f"{cases} circuits, zero-error noise model equals the ideal distribution"


def _check_composition_order(cases: int, seed: int) -> str:  # noqa: ARG001
    rng = np.random.default_rng(seed)
    first = AmplitudeDampingChannel(0.2)
    second = DepolarizingChannel(0.25)
    composed = ComposedChannel(first, second)
    for case in range(cases):
        matrix = rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2))
        rho = matrix @ matrix.conj().T
        rho /= np.trace(rho)
        expected = _apply_channel(second, _apply_channel(first, rho))
        got = _apply_channel(composed, rho)
        if np.max(np.abs(got - expected)) > 1e-12:
            raise AssertionError(f"case {case}: ComposedChannel is not second o first")
    return f"{cases} states, ComposedChannel(A,B) equals B after A"


_CHECK_TABLE: Sequence[Tuple[str, Callable[[int, int], str]]] = (
    ("normalization", _check_normalization),
    ("inverse_identity", _check_inverse_identity),
    ("permutation_equivariance", _check_permutation),
    ("global_phase", _check_global_phase),
    ("mps_dense_parity", _check_mps_dense_parity),
    ("sampling", _check_sampling),
    ("noise_invariants", _check_noise_invariants),
    ("noise_permutation_equivariance", _check_noise_permutation),
    ("zero_noise_identity", _check_zero_noise),
    ("channel_composition_order", _check_composition_order),
    ("expectation_oracle", _check_expectation),
)


def run_selftest(cases: int = 8, seed: int = 20261030) -> SelftestReport:
    """Run every metamorphic check and return a structured report."""
    if not isinstance(cases, int) or isinstance(cases, bool) or cases < 1:
        raise ValueError(f"cases must be a positive integer, got {cases!r}")
    checks: List[SelftestCheck] = []
    for name, function in _CHECK_TABLE:
        started = time.perf_counter()
        try:
            detail = function(cases, seed)
            passed = True
        except Exception as exc:  # noqa: BLE001 - the report records the failure
            detail = f"{type(exc).__name__}: {exc}"
            passed = False
        checks.append(
            SelftestCheck(
                name=name,
                passed=passed,
                detail=detail,
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )
        )
    return SelftestReport(checks=checks, seed=seed, cases=cases)
