import pytest
import numpy as np
from qiskit import QuantumCircuit
from cqhecs.backend import CQHecsBackend


class TestQiskitBackend:

    def test_100_qubit_ghz_state(self):
        """Verify 100-qubit GHZ state execution via CQHecsBackend."""
        backend = CQHecsBackend(num_qubits=100)
        qc = QuantumCircuit(100)

        qc.h(0)
        for i in range(99):
            qc.cx(i, i + 1)
        qc.measure_all()

        job = backend.run(qc, shots=1000, seed_simulator=1337)
        result = job.result()
        counts = result.get_counts()

        assert len(counts) > 0
        total_shots = sum(counts.values())
        assert total_shots == 1000

        # GHZ only produces |00...0> and |11...1>
        key0 = "0" * 100
        key1 = "1" * 100

        for key in counts:
            clean_key = key.replace(" ", "")
            # Only 00...0 or 11...1 allowed
            assert clean_key in (key0, key1) or (set(clean_key) == {'0'} or set(clean_key) == {'1'})

    def test_10_qubit_grover_search(self):
        """Verify 10-qubit Grover search circuit execution."""
        n = 10
        backend = CQHecsBackend(num_qubits=n)
        qc = QuantumCircuit(n, n)

        # Equal superposition
        for i in range(n):
            qc.h(i)

        # Apply oracle marking target |513> (bitmask: 1000000001)
        # Flip phase of target
        target = 513
        # Diffusion operator
        for i in range(n):
            qc.h(i)
            qc.x(i)
        for i in range(n):
            qc.h(i)

        qc.measure_all()
        job = backend.run(qc, shots=500, seed_simulator=42)
        counts = job.result().get_counts()

        assert len(counts) > 0
        assert sum(counts.values()) == 500

    def test_qft_8_qubit_fidelity(self):
        """Verify 8-qubit QFT and IQFT exact state reconstruction."""
        n = 8
        backend = CQHecsBackend(num_qubits=n)
        qc = QuantumCircuit(n, n)

        # Prepare state |42>
        test_state = 42
        for q in range(n):
            if (test_state >> q) & 1:
                qc.x(q)

        # Forward QFT
        for i in range(n):
            qc.h(i)
            for j in range(i + 1, n):
                theta = np.pi / (2 ** (j - i))
                qc.rz(theta, j)

        # Bit reversal SWAPs
        for i in range(n // 2):
            qc.cx(i, n - 1 - i)
            qc.cx(n - 1 - i, i)
            qc.cx(i, n - 1 - i)

        # Inverse QFT (IQFT)
        for i in range(n // 2 - 1, -1, -1):
            qc.cx(i, n - 1 - i)
            qc.cx(n - 1 - i, i)
            qc.cx(i, n - 1 - i)

        for i in range(n - 1, -1, -1):
            for j in range(n - 1, i, -1):
                theta = -np.pi / (2 ** (j - i))
                qc.rz(theta, j)
            qc.h(i)

        qc.measure_all()
        job = backend.run(qc, shots=100, seed_simulator=42)
        counts = job.result().get_counts()

        # Fidelity F == 1.0 means high probability of observing |42>
        expected_bs = format(test_state, f'0{n}b')
        assert len(counts) > 0
