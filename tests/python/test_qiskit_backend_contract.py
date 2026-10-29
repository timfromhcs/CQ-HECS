"""
Qiskit BackendV2 contract tests.

The previous tests only asserted that counts were non-empty, which would pass
even for fabricated output. These exercise the actual BackendV2 contract:
transpile against the target, run, retrieve results, read counts, handle
multiple circuits, respect options, and reject unsupported circuits.
"""

from __future__ import annotations
import unittest

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.synthesis.qft import synth_qft_full

from cqhecs.backend import CQHecsBackend


def _clean(key: str) -> str:
    """Strips Qiskit's multi-register separators."""
    return key.replace(" ", "")


class TestBackendV2Contract(unittest.TestCase):
    def setUp(self):
        self.backend = CQHecsBackend(num_qubits=8)

    # -- transpilation -------------------------------------------------
    def test_transpiles_against_target(self):
        qc = QuantumCircuit(8)
        qc.h(0)
        for i in range(7):
            qc.cx(i, i + 1)
        qc.measure_all()
        compiled = transpile(qc, self.backend)
        self.assertEqual(compiled.num_qubits, 8)
        self.assertGreater(self.backend.target.num_qubits, 0)

    def test_run_accepts_transpiled_circuit(self):
        qc = QuantumCircuit(4, 4)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc.cx(2, 3)
        qc.measure_all()
        compiled = transpile(qc, self.backend)
        counts = self.backend.run(compiled, shots=500).result().get_counts()
        total = sum(counts.values())
        self.assertEqual(total, 500)

    # -- correctness ---------------------------------------------------
    def test_ghz_gives_only_all_zero_or_all_one(self):
        n = 8
        backend = CQHecsBackend(num_qubits=n)
        qc = QuantumCircuit(n)
        qc.h(0)
        for i in range(n - 1):
            qc.cx(i, i + 1)
        qc.measure_all()
        counts = backend.run(qc, shots=2000, seed_simulator=7).result().get_counts()
        for key in counts:
            self.assertIn(_clean(key), ("0" * n, "1" * n))
        # Roughly balanced.
        total = sum(counts.values())
        for key, value in counts.items():
            self.assertGreater(value / total, 0.3)

    def test_bell_state_bit_ordering(self):
        """X on qubit 0 must render with qubit 0 rightmost."""
        qc = QuantumCircuit(3, 3)
        qc.x(0)
        qc.measure_all()
        counts = self.backend.run(qc, shots=200).result().get_counts()
        # measure_all() maps qubit q -> clbit q+3, so qubit 0 is the 6th column.
        self.assertIn("001000", {_clean(k) for k in counts})

    def test_x_on_top_qubit_bit_ordering(self):
        qc = QuantumCircuit(3, 3)
        qc.x(2)
        qc.measure_all()
        counts = self.backend.run(qc, shots=200).result().get_counts()
        # measure_all() maps qubit q -> clbit q+3, so qubit 2 is the 4th column.
        self.assertIn("100000", {_clean(k) for k in counts})

    def test_matches_exact_probabilities(self):
        """The returned distribution must match the exact Born rule."""
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.rz(0.4, 2)
        qc.measure_all()
        backend = CQHecsBackend(num_qubits=3)
        counts = backend.run(qc, shots=40000, seed_simulator=3).result().get_counts()
        total = sum(counts.values())
        got = np.zeros(8)
        for key, value in counts.items():
            got[int(_clean(key), 2)] = value / total
        # Qubit 2 stays in |0>, so only indices 0-3 carry probability.
        self.assertAlmostEqual(got[4:].sum(), 0.0, delta=0.02)
        # The Bell pair on qubits 0/1 puts equal weight on |00> and |11>.
        self.assertAlmostEqual(got[0], 0.5, delta=0.03)
        self.assertAlmostEqual(got[3], 0.5, delta=0.03)

    def test_distribution_matches_aer(self):
        """Differential check against Qiskit Aer on the same circuit."""
        from qiskit_aer import AerSimulator

        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.rz(0.4, 2)
        qc.measure_all()
        backend = CQHecsBackend(num_qubits=3)
        ours = backend.run(qc, shots=8000, seed_simulator=11).result().get_counts()
        theirs = AerSimulator().run(
            qc, shots=8000, seed_simulator=11
        ).result().get_counts()

        our_dist = {_clean(k): v / sum(ours.values()) for k, v in ours.items()}
        aer_dist = {_clean(k): v / sum(theirs.values()) for k, v in theirs.items()}
        keys = set(our_dist) | set(aer_dist)
        worst = max(abs(our_dist.get(k, 0.0) - aer_dist.get(k, 0.0)) for k in keys)
        self.assertLess(worst, 0.05)

    # -- job / result contract ------------------------------------------
    def test_job_result_interface(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure_all()
        job = self.backend.run(qc, shots=256)
        # BackendV2 job status is RUNNING/DONE/ERROR; it must reach DONE.
        self.assertIn(job.status(), ("DONE", "COMPLETED"))
        result = job.result()
        self.assertTrue(result.success)
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].shots, 256)
        counts = result.get_counts()
        self.assertEqual(sum(counts.values()), 256)

    def test_multiple_circuits(self):
        circuits = []
        for n in (2, 3):
            qc = QuantumCircuit(n)
            qc.h(0)
            for i in range(n - 1):
                qc.cx(i, i + 1)
            qc.measure_all()
            circuits.append(qc)
        backend = CQHecsBackend(num_qubits=3)
        result = backend.run(circuits, shots=128).result()
        self.assertEqual(len(result.results), 2)
        for entry in result.results:
            counts = entry.data.counts
            self.assertEqual(sum(counts.values()), 128)

    def test_result_reports_backend_metadata(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure_all()
        result = self.backend.run(qc, shots=64).result()
        header = result.results[0].header
        for key in ("path", "exact", "error_bound", "unresolved"):
            self.assertIn(key, header)

    def test_seed_is_deterministic(self):
        qc = QuantumCircuit(3, 3)
        qc.h(0)
        qc.cx(0, 1)
        qc.t(1)
        qc.measure_all()
        first = self.backend.run(qc, shots=300, seed_simulator=99).result().get_counts()
        second = self.backend.run(qc, shots=300, seed_simulator=99).result().get_counts()
        self.assertEqual(first, second)

    def test_options_defaults(self):
        self.assertEqual(self.backend.options.shots, 1024)
        self.assertEqual(self.backend.options.seed_simulator, 42)

    def test_target_declares_supported_instructions(self):
        names = set(self.backend.target.operation_names)
        for gate in ("h", "x", "cx", "measure"):
            self.assertIn(gate, names)

    def test_max_circuits(self):
        self.assertGreater(self.backend.max_circuits, 0)

    # -- failure modes --------------------------------------------------
    def test_zero_shots_is_rejected(self):
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.measure_all()
        with self.assertRaises(ValueError):
            self.backend.run(qc, shots=0)

    def test_unsupported_circuit_surfaces_error(self):
        """A circuit the backend cannot run must not silently reroute."""
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.reset(1)  # Reset: non-unitary, implemented by no path
        qc.measure_all()
        backend = CQHecsBackend(num_qubits=3)
        try:
            result = backend.run(qc, shots=64).result()
        except (ValueError, TypeError, IndexError, NotImplementedError):
            return  # raising is the acceptable behaviour
        # If it did not raise, it must not claim a clean success.
        if result.results and result.results[0].header.get("unresolved"):
            return
        raise AssertionError(
            "Backend neither raised nor reported unresolved for an "
            "unsupported circuit"
        )

    def test_qft_circuit_runs(self):
        # Qiskit 2.1 deprecated the ``QFT`` BlueprintCircuit; ``synth_qft_full``
        # is the documented replacement and yields the same h/cp/swap circuit.
        qc = synth_qft_full(4)
        qc.measure_all()
        backend = CQHecsBackend(num_qubits=4)
        counts = backend.run(qc, shots=256, seed_simulator=5).result().get_counts()
        self.assertEqual(sum(counts.values()), 256)


if __name__ == "__main__":
    unittest.main()