"""Google Sycamore gate set (v3 W5, gate V3-C).

The reference matrices below are written from Cirq's published definitions,
independently of ``cqhecs.gate_lowering``:

* ``FSimGate(theta, phi)``: [[1,0,0,0],[0,cos,-i sin,0],[0,-i sin,cos,0],[0,0,0,e^{-i phi}]]
  on basis order |00>,|01>,|10>,|11> (symmetric, so qubit order does not matter);
* ``PhasedXPowGate(t, p) = Z^p X^t Z^-p`` with ``X^t = e^{i pi t/2} RX(pi t)`` and
  ``Z^p = diag(1, e^{i pi p})``; ``X**0.5``, ``Y**0.5`` and ``W**0.5`` likewise.
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.gate_lowering import GLOBAL_PHASE_ONLY, is_lowered_gate, lower_instructions
from cqhecs.gate_manifest import MANIFEST
from cqhecs.router import FourPathRouter

I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)


def fsim(theta, phi):
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[1, 0, 0, 0], [0, c, -1j * s, 0], [0, -1j * s, c, 0], [0, 0, 0, np.exp(-1j * phi)]])


def pow_pauli(pauli, t):
    """Cirq ``P**t`` for a Pauli P: e^{i pi t/2} (cos(pi t/2) I - i sin(pi t/2) P)."""
    return np.exp(1j * math.pi * t / 2) * (math.cos(math.pi * t / 2) * I2 - 1j * math.sin(math.pi * t / 2) * pauli)


def z_pow(p):
    return np.diag([1, np.exp(1j * math.pi * p)])


def phased_x_cirq(t, p):
    return z_pow(p) @ pow_pauli(X, t) @ z_pow(-p)


REFERENCE = {
    "fsim": (lambda th, ph: fsim(th, ph), 2, (0.61, -1.27)),
    "syc": (lambda: fsim(math.pi / 2, math.pi / 6), 2, ()),
    "sqrt_x": (lambda: pow_pauli(X, 0.5), 1, ()),
    "sqrt_y": (lambda: pow_pauli(Y, 0.5), 1, ()),
    "sqrt_w": (lambda: pow_pauli((X + Y) / math.sqrt(2), 0.5), 1, ()),
    # radians in CQ-HECS = pi * Cirq exponent
    "phased_x": (lambda th, ph: phased_x_cirq(th / math.pi, ph / math.pi), 1, (0.9, 0.35)),
}


def embed(matrix, qubits, width):
    """Full operator of ``matrix`` acting on ``qubits`` (qubit 0 least significant)."""
    dim = 1 << width
    full = np.zeros((dim, dim), dtype=complex)
    k = len(qubits)
    for col in range(dim):
        sub_col = sum(((col >> q) & 1) << (k - 1 - i) for i, q in enumerate(qubits))
        for sub_row in range(1 << k):
            amp = matrix[sub_row, sub_col]
            if amp == 0:
                continue
            row = col
            for i, q in enumerate(qubits):
                bit = (sub_row >> (k - 1 - i)) & 1
                row = (row & ~(1 << q)) | (bit << q)
            full[row, col] += amp
    return full


def native_operator(instructions, width):
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Operator

    qc = QuantumCircuit(width)
    for name, qubits, params in instructions:
        getattr(qc, name)(*params, *qubits)
    return Operator(qc).data


def phase_aligned(a, b):
    index = np.unravel_index(np.argmax(np.abs(b)), b.shape)
    return a * (b[index] / a[index])


class SycamoreDefinitionTests(unittest.TestCase):
    def test_manifest_and_rules(self):
        for name in REFERENCE:
            self.assertTrue(is_lowered_gate(name), name)
            self.assertEqual(MANIFEST[name].arity, REFERENCE[name][1])

    def test_rules_match_cirq_definitions(self):
        for name, (factory, arity, params) in REFERENCE.items():
            reference = factory(*params)
            for operands in ([[0]] if arity == 1 else [[0, 1], [1, 0]]):
                with self.subTest(gate=name, operands=operands):
                    lowered = lower_instructions([(name, operands, list(params))])
                    self.assertTrue(all(not is_lowered_gate(n) for n, _q, _p in lowered))
                    got = native_operator(lowered, arity)
                    want = embed(reference, operands, arity)
                    if name in GLOBAL_PHASE_ONLY:
                        self.assertFalse(np.allclose(got, want, atol=1e-9), "phase note is stale")
                        want = phase_aligned(want, got)
                    np.testing.assert_allclose(got, want, atol=1e-12)

    def test_fsim_special_points(self):
        # fsim(pi/2, 0) is iSWAP^dagger in Cirq's convention; fsim(0, pi) is CZ.
        iswap_dag = np.array([[1, 0, 0, 0], [0, 0, -1j, 0], [0, -1j, 0, 0], [0, 0, 0, 1]])
        np.testing.assert_allclose(native_operator(lower_instructions([("fsim", [0, 1], [math.pi / 2, 0.0])]), 2),
                                   iswap_dag, atol=1e-12)
        np.testing.assert_allclose(native_operator(lower_instructions([("fsim", [0, 1], [0.0, math.pi])]), 2),
                                   np.diag([1, 1, 1, -1]), atol=1e-12)


class SycamoreCircuitTests(unittest.TestCase):
    """Random Sycamore-style layers: exact density matrix and the router vs numpy."""

    def _random_layer_circuit(self, width, cycles, seed):
        rng = np.random.default_rng(seed)
        singles = ("sqrt_x", "sqrt_y", "sqrt_w")
        instructions, state = [], np.zeros(1 << width, dtype=complex)
        state[0] = 1
        for cycle in range(cycles):
            for q in range(width):
                gate = singles[int(rng.integers(3))]
                instructions.append((gate, [q], []))
                state = embed(REFERENCE[gate][0](), [q], width) @ state
            for a in range(cycle % 2, width - 1, 2):
                theta, phi = (float(x) for x in rng.uniform(-math.pi, math.pi, 2))
                instructions.append(("fsim", [a, a + 1], [theta, phi]))
                state = embed(fsim(theta, phi), [a, a + 1], width) @ state
        return instructions, np.abs(state) ** 2

    def test_density_matrix_is_exact(self):
        for seed in range(5):
            instructions, expected = self._random_layer_circuit(4, 6, seed)
            measured = instructions + [("measure", [q], []) for q in range(4)]
            result = NoisyDensityMatrixBackend(max_qubits=10).simulate(measured, shots=1, seed=0)
            got = np.zeros(16)
            for bits, p in result.probabilities.items():
                got[int(bits, 2)] = p
            np.testing.assert_allclose(got, expected, atol=1e-10, err_msg=f"seed {seed}")

    def test_router_samples_match(self):
        instructions, expected = self._random_layer_circuit(4, 5, seed=11)
        measured = instructions + [("measure", [q], []) for q in range(4)]
        result = FourPathRouter().route_and_execute(measured, shots=20000, seed=3)
        self.assertFalse(result.is_unresolved, result.metadata)
        probs = np.zeros(16)
        total = sum(result.counts.values())
        for bits, count in result.counts.items():
            probs[int(bits.replace(" ", ""), 2)] += count / total
        self.assertLess(0.5 * np.abs(probs - expected).sum(), 0.03, result.path)


if __name__ == "__main__":
    unittest.main()
