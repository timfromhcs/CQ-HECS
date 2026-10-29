"""
Independent Mathematical and Differential Tests for NoisyDensityMatrixBackend.

Covers:
- Trace preservation (|Tr(rho) - 1| <= 1e-12)
- Hermiticity (max |rho - rho^dag| <= 1e-12)
- Complete positivity (eigenvalues >= -1e-12)
- Independent closed-form algebraic oracles for Depolarizing, Amplitude Damping, and Phase Damping
- Differential parity against Qiskit Aer
- Fail-closed memory ceiling for > 10 qubits
"""

import unittest

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel as AerNoiseModel, depolarizing_error, ReadoutError as AerReadoutError

from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.hardware_bridge import (
    NoiseModel,
    DepolarizingChannel,
    AmplitudeDampingChannel,
    PhaseDampingChannel,
    TwoQubitDepolarizingChannel,
    ReadoutErrorChannel,
)
from cqhecs.result import ExecutionMode, SimulationState


class TestNoisyDensityMatrix(unittest.TestCase):

    def setUp(self):
        self.backend = NoisyDensityMatrixBackend(max_qubits=10)

    def test_ideal_bell_density_matrix(self):
        """Ideal Bell circuit produces exact (0.5, 0, 0, 0.5) probabilities."""
        circuit = [("h", [0], []), ("cx", [0, 1], [])]
        res = self.backend.simulate(circuit, noise_model=None, shots=1000, seed=42)

        self.assertEqual(res.execution_mode, ExecutionMode.IDEAL_CLASSICAL)
        self.assertEqual(res.state, SimulationState.EXACT)
        self.assertTrue(res.exact)
        self.assertEqual(res.error_bound, 0.0)

        # Probabilities
        self.assertAlmostEqual(res.probabilities.get("00", 0.0), 0.5, places=10)
        self.assertAlmostEqual(res.probabilities.get("11", 0.0), 0.5, places=10)
        self.assertNotIn("01", res.probabilities)
        self.assertNotIn("10", res.probabilities)

        # Invariants in metadata
        self.assertLess(res.metadata["trace_error"], 1e-12)
        self.assertLess(res.metadata["hermitian_error"], 1e-12)
        self.assertGreaterEqual(res.metadata["min_eigenvalue"], -1e-12)

    def test_depolarizing_channel_independent_formula(self):
        """
        Independent algebraic oracle for single-qubit depolarizing channel:
            rho_0 = |0><0|
            E(rho_0) = (1 - p)|0><0| + p (I / 2)
                     = (1 - p/2)|0><0| + (p/2)|1><1|
        """
        for p in [0.03, 0.1, 0.25]:
            noise = NoiseModel(name="test_depol")
            noise.add_1q_channel("id", 0, DepolarizingChannel(p))

            circuit = [("id", [0], [])]
            res = self.backend.simulate(circuit, noise_model=noise, shots=5000, seed=123)

            expected_p0 = 1.0 - (p / 2.0)
            expected_p1 = p / 2.0

            actual_p0 = res.probabilities.get("0", 0.0)
            actual_p1 = res.probabilities.get("1", 0.0)

            self.assertAlmostEqual(actual_p0, expected_p0, places=10)
            self.assertAlmostEqual(actual_p1, expected_p1, places=10)

    def test_amplitude_damping_independent_formula(self):
        """
        Independent algebraic oracle for amplitude damping on excited state |1>:
            rho = |1><1|
            E(|1><1|) = gamma |0><0| + (1 - gamma)|1><1|
        """
        for gamma in [0.05, 0.2, 0.6]:
            noise = NoiseModel(name="test_amp_damp")
            # Apply after X gate
            noise.add_1q_channel("x", 0, AmplitudeDampingChannel(gamma))

            circuit = [("x", [0], [])]
            res = self.backend.simulate(circuit, noise_model=noise, shots=5000, seed=123)

            expected_p0 = gamma
            expected_p1 = 1.0 - gamma

            self.assertAlmostEqual(res.probabilities.get("0", 0.0), expected_p0, places=10)
            self.assertAlmostEqual(res.probabilities.get("1", 0.0), expected_p1, places=10)

    def test_phase_damping_independent_formula(self):
        """
        Independent algebraic oracle for phase damping on superposition state |+>:
            P(0) = 0.5, P(1) = 0.5 (diagonal probabilities remain unchanged)
            while trace and Hermiticity are strictly preserved.
        """
        for lambd in [0.05, 0.25, 0.7]:
            noise = NoiseModel(name="test_phase_damp")
            noise.add_1q_channel("h", 0, PhaseDampingChannel(lambd))

            circuit = [("h", [0], [])]
            res = self.backend.simulate(circuit, noise_model=noise, shots=2000, seed=42)

            self.assertAlmostEqual(res.probabilities.get("0", 0.0), 0.5, places=10)
            self.assertAlmostEqual(res.probabilities.get("1", 0.0), 0.5, places=10)
            self.assertLess(res.metadata["trace_error"], 1e-12)
            self.assertLess(res.metadata["hermitian_error"], 1e-12)

    def test_readout_error_independent_formula(self):
        """
        Readout error transforms ideal probabilities:
            p_noisy = M @ p_ideal
        """
        ro_channel = ReadoutErrorChannel(p01=0.04, p10=0.08)
        self.assertEqual(ro_channel.matrix.shape, (2, 2))

        noise = NoiseModel(name="test_readout")
        noise.set_readout_error(0, p01=0.04, p10=0.08)

        # Circuit prepares |0>
        circuit = [("id", [0], [])]
        res = self.backend.simulate(circuit, noise_model=noise, shots=1000, seed=42)

        expected_p0 = 1.0 - 0.04
        expected_p1 = 0.04
        self.assertAlmostEqual(res.probabilities.get("0", 0.0), expected_p0, places=10)
        self.assertAlmostEqual(res.probabilities.get("1", 0.0), expected_p1, places=10)

    def test_differential_parity_with_qiskit_aer(self):
        """
        Differential parity test: compare NoisyDensityMatrixBackend with Qiskit Aer
        under identical depolarizing and readout noise models on a 2-qubit Bell circuit.
        """
        p_depol = 0.02
        p01, p10 = 0.015, 0.025

        # 1. CQ-HECS NoiseModel with 2Q depolarizing channel on CX
        cq_noise = NoiseModel(name="diff_test")
        cq_noise.add_2q_channel("cx", (0, 1), TwoQubitDepolarizingChannel(p_depol))
        cq_noise.set_readout_error(0, p01=p01, p10=p10)
        cq_noise.set_readout_error(1, p01=p01, p10=p10)

        cq_circuit = [("h", [0], []), ("cx", [0, 1], [])]
        cq_res = self.backend.simulate(cq_circuit, noise_model=cq_noise, shots=50000, seed=42)

        # 2. Qiskit Aer simulation under identical channels
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure_all()

        aer_noise = AerNoiseModel()
        error_2q = depolarizing_error(p_depol, 2)
        aer_noise.add_quantum_error(error_2q, ["cx"], [0, 1])
        r0 = AerReadoutError([[1 - p01, p01], [p10, 1 - p10]])
        r1 = AerReadoutError([[1 - p01, p01], [p10, 1 - p10]])
        aer_noise.add_readout_error(r0, [0])
        aer_noise.add_readout_error(r1, [1])

        sim = AerSimulator(noise_model=aer_noise)
        aer_job = sim.run(qc, shots=50000, seed_simulator=42)
        aer_counts = aer_job.result().get_counts()

        # Differential parity: TV distance between exact CQ-HECS and Aer <= 0.02
        tv_dist = 0.5 * sum(
            abs(cq_res.probabilities.get(bs, 0.0) - (aer_counts.get(bs, 0) / 50000.0))
            for bs in ["00", "01", "10", "11"]
        )
        self.assertLess(tv_dist, 0.02)

        # Verify CQ-HECS physical invariants and distribution shape
        self.assertGreater(cq_res.probabilities["00"], 0.45)
        self.assertGreater(cq_res.probabilities["11"], 0.45)
        self.assertGreater(cq_res.probabilities["01"], 0.01)
        self.assertGreater(cq_res.probabilities["10"], 0.01)
        self.assertAlmostEqual(sum(cq_res.probabilities.values()), 1.0, places=10)
        self.assertEqual(sum(cq_res.counts.values()), 50000)

    def test_memory_ceiling_fails_closed(self):
        """Circuits wider than max_qubits (10) must fail closed with UNRESOLVED status."""
        circuit = [("x", [11], [])]
        res = self.backend.simulate(circuit)
        self.assertTrue(res.unresolved)
        self.assertEqual(res.state, SimulationState.UNRESOLVED)
        self.assertIn("exceeds maximum allocation ceiling", res.metadata.get("unresolved_reason", ""))


if __name__ == "__main__":
    unittest.main()
