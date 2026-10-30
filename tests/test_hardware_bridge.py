"""
Tests for the CQ-HECS Hardware-Aware Quantum Bridge.

Covers:
- ExecutionMode enums and immutability
- BackendProfile schema validation, serialization, and topology consistency
- NoiseChannel and Kraus completeness verification
- FakeHardwareBackend topology enforcement and deterministic emulation
- RealHardwareProvider authorization boundaries and fail-closed security
"""

import unittest
import numpy as np

from cqhecs.hardware_bridge import (
    ExecutionMode,
    BackendProfile,
    NoiseModel,
    DepolarizingChannel,
    AmplitudeDampingChannel,
    PhaseDampingChannel,
    TwoQubitDepolarizingChannel,
    ReadoutErrorChannel,
    FakeHardwareBackend,
    FakeHardwareProvider,
    RealHardwareBackend,
    RealHardwareProvider,
    HardwareBridgeError,
    HardwareAuthorizationRequiredError,
    HardwareAuthenticationError,
    InvalidProfileError,
    InvalidNoiseModelError,
    InvalidTopologyError,
    create_fake_manila_profile,
    create_linear_profile,
)
from cqhecs.provider import CQHecsProvider


class TestHardwareBridge(unittest.TestCase):

    def test_execution_modes(self):
        """Execution modes must be distinct and well-defined strings."""
        self.assertEqual(ExecutionMode.IDEAL_CLASSICAL, "IDEAL_CLASSICAL")
        self.assertEqual(ExecutionMode.NOISY_CLASSICAL, "NOISY_CLASSICAL")
        self.assertEqual(ExecutionMode.REAL_HARDWARE, "REAL_HARDWARE")
        modes = {m.value for m in ExecutionMode}
        self.assertEqual(len(modes), 3)

    def test_backend_profile_valid(self):
        """Valid profile constructs and validates cleanly."""
        profile = create_fake_manila_profile()
        self.assertEqual(profile.name, "fake_manila")
        self.assertEqual(profile.num_qubits, 5)
        # The numbers are illustrative, not a provider calibration export, so
        # the profile must not claim real provenance (CQ-V251-03).
        self.assertTrue(profile.is_synthetic)
        self.assertIsNone(profile.provenance_uri)
        self.assertIsNone(profile.capture_timestamp)
        self.assertEqual(len(profile.coupling_map), 8)
        self.assertIn((0, 1), profile.coupling_map)
        profile.validate()

    def test_backend_profile_invalid_schema_version(self):
        """Unsupported schema version must be rejected."""
        with self.assertRaises(InvalidProfileError):
            BackendProfile(name="test", num_qubits=2, schema_version="3.0")

    def test_backend_profile_invalid_num_qubits(self):
        """Non-positive qubit count must be rejected."""
        with self.assertRaises(InvalidProfileError):
            BackendProfile(name="test", num_qubits=0)
        with self.assertRaises(InvalidProfileError):
            BackendProfile(name="test", num_qubits=-3)

    def test_backend_profile_invalid_coupling(self):
        """Out-of-range edges or self-loops must be rejected."""
        with self.assertRaises(InvalidProfileError):
            BackendProfile(name="test", num_qubits=3, coupling_map=[(0, 3)])
        with self.assertRaises(InvalidProfileError):
            BackendProfile(name="test", num_qubits=3, coupling_map=[(1, 1)])

    def test_backend_profile_invalid_error_rates(self):
        """Negative or >1.0 error rates must be rejected."""
        with self.assertRaises(InvalidProfileError):
            BackendProfile(
                name="test", num_qubits=2,
                gate_errors={"cx": {(0, 1): 1.5}},
            )
        with self.assertRaises(InvalidProfileError):
            BackendProfile(
                name="test", num_qubits=2,
                readout_errors={0: (-0.1, 0.05)},
            )

    def test_backend_profile_serialization(self):
        """Profile to_dict and from_dict must round-trip exactly."""
        p1 = create_fake_manila_profile()
        d = p1.to_dict()
        p2 = BackendProfile.from_dict(d)
        self.assertEqual(p1.name, p2.name)
        self.assertEqual(p1.num_qubits, p2.num_qubits)
        self.assertEqual(p1.coupling_map, p2.coupling_map)
        self.assertEqual(p1.gate_errors, p2.gate_errors)
        self.assertEqual(p1.readout_errors, p2.readout_errors)
        self.assertEqual(p1.is_synthetic, p2.is_synthetic)

    def test_kraus_completeness_depolarizing_1q(self):
        """1-qubit depolarizing channel must satisfy sum K^dag K = I."""
        for p in [0.0, 0.001, 0.05, 0.1, 0.5, 1.0]:
            ch = DepolarizingChannel(p)
            self.assertTrue(ch.validate_kraus_completeness())
            sum_k = sum(k.conj().T @ k for k in ch.kraus_operators)
            np.testing.assert_allclose(sum_k, np.eye(2), atol=1e-12)

    def test_kraus_completeness_amplitude_damping(self):
        """Amplitude damping channel must satisfy sum K^dag K = I."""
        for gamma in [0.0, 0.01, 0.2, 0.8, 1.0]:
            ch = AmplitudeDampingChannel(gamma)
            self.assertTrue(ch.validate_kraus_completeness())
            sum_k = sum(k.conj().T @ k for k in ch.kraus_operators)
            np.testing.assert_allclose(sum_k, np.eye(2), atol=1e-12)

    def test_kraus_completeness_phase_damping(self):
        """Phase damping channel must satisfy sum K^dag K = I."""
        for lambd in [0.0, 0.05, 0.3, 0.9, 1.0]:
            ch = PhaseDampingChannel(lambd)
            self.assertTrue(ch.validate_kraus_completeness())
            sum_k = sum(k.conj().T @ k for k in ch.kraus_operators)
            np.testing.assert_allclose(sum_k, np.eye(2), atol=1e-12)

    def test_kraus_completeness_depolarizing_2q(self):
        """2-qubit depolarizing channel must satisfy sum K^dag K = I_4."""
        for p in [0.0, 0.01, 0.05, 0.2]:
            ch = TwoQubitDepolarizingChannel(p)
            self.assertTrue(ch.validate_kraus_completeness())
            sum_k = sum(k.conj().T @ k for k in ch.kraus_operators)
            np.testing.assert_allclose(sum_k, np.eye(4), atol=1e-12)

    def test_invalid_noise_parameters(self):
        """Negative, >1, or NaN noise parameters must raise InvalidNoiseModelError."""
        with self.assertRaises(InvalidNoiseModelError):
            DepolarizingChannel(-0.01)
        with self.assertRaises(InvalidNoiseModelError):
            DepolarizingChannel(1.05)
        with self.assertRaises(InvalidNoiseModelError):
            AmplitudeDampingChannel(float("nan"))
        with self.assertRaises(InvalidNoiseModelError):
            ReadoutErrorChannel(-0.1, 0.05)

    def test_fake_hardware_provider(self):
        """FakeHardwareProvider exposes registered fake backends."""
        provider = FakeHardwareProvider()
        backends = provider.backends()
        self.assertGreaterEqual(len(backends), 2)
        backend = provider.get_backend("fake_manila")
        self.assertEqual(backend.name, "fake_manila")
        self.assertEqual(backend.profile.num_qubits, 5)

    def test_fake_hardware_backend_execution(self):
        """FakeHardwareBackend executes a 2-qubit circuit with hardware metadata."""
        provider = FakeHardwareProvider()
        backend = provider.get_backend("fake_manila")

        # Linear coupling (0, 1) is valid in Manila
        circuit = [("h", [0], []), ("cx", [0, 1], [])]
        res = backend.run(circuit, shots=500, seed=123)

        self.assertEqual(res.execution_mode, ExecutionMode.NOISY_CLASSICAL)
        self.assertFalse(res.is_real_hardware)
        self.assertTrue(res.metadata.get("simulated_hardware"))
        self.assertEqual(res.backend_profile_id, "fake_manila")
        self.assertEqual(res.noise_model_id, "fake_manila_noise_model")
        self.assertEqual(sum(res.counts.values()), 500)
        self.assertIn("00", res.counts)
        self.assertIn("11", res.counts)

    def test_fake_hardware_topology_enforcement(self):
        """Attempting a 2-qubit gate on disconnected qubits must raise InvalidTopologyError."""
        provider = FakeHardwareProvider()
        backend = provider.get_backend("fake_manila")

        # (0, 3) is NOT in Manila's linear coupling map
        circuit = [("h", [0], []), ("cx", [0, 3], [])]
        with self.assertRaises(InvalidTopologyError) as ctx:
            backend.run(circuit)
        self.assertIn("violates backend topology", str(ctx.exception))

    def test_fake_hardware_width_overflow(self):
        """Circuit wider than backend qubit count must raise InvalidTopologyError."""
        provider = FakeHardwareProvider()
        backend = provider.get_backend("fake_manila")

        # 6-qubit circuit on a 5-qubit backend
        circuit = [("x", [5], [])]
        with self.assertRaises(InvalidTopologyError):
            backend.run(circuit)

    def test_real_hardware_provider_fails_closed(self):
        """Real hardware execution without authorization must fail closed immediately."""
        provider = RealHardwareProvider()
        backend = provider.get_backend("ibm_brisbane")
        self.assertTrue(backend.is_real_hardware)

        # 1. unauthorized execution must raise HardwareAuthorizationRequiredError
        with self.assertRaises(HardwareAuthorizationRequiredError):
            backend.run([("h", [0], [])], authorized=False)

        # 2. authorized but missing token must raise HardwareAuthenticationError
        with self.assertRaises(HardwareAuthenticationError):
            backend.run([("h", [0], [])], authorized=True, api_token=None)

    def test_linear_profile_and_custom_noise_model(self):
        """Synthetic linear profile and custom noise model construct and validate."""
        profile = create_linear_profile(4, name="linear_4q")
        self.assertEqual(profile.num_qubits, 4)
        self.assertTrue(profile.is_synthetic)
        self.assertEqual(len(profile.coupling_map), 6)

        nm = NoiseModel(name="custom")
        backend = FakeHardwareBackend(profile, noise_model=nm)
        self.assertEqual(backend.name, "linear_4q")
        self.assertEqual(backend.profile.num_qubits, 4)

    def test_real_hardware_backend_direct(self):
        """Direct instantiation of RealHardwareBackend fails closed with HardwareBridgeError base."""
        real_backend = RealHardwareBackend("ibm_kyoto")
        self.assertTrue(real_backend.is_real_hardware)
        with self.assertRaises(HardwareBridgeError):
            real_backend.run([("h", [0], [])], authorized=False)

    def test_cqhecs_provider_bridge_integration(self):
        """CQHecsProvider exposes fake and real hardware provider accessors and backends."""
        prov = CQHecsProvider()
        fake_prov = prov.fake_hardware
        self.assertIsInstance(fake_prov, FakeHardwareProvider)
        real_prov = prov.real_hardware
        self.assertIsInstance(real_prov, RealHardwareProvider)
        backend_names = [b.name for b in prov.backends()]
        self.assertIn("fake_manila", backend_names)
        self.assertIn("linear_5q", backend_names)


if __name__ == "__main__":
    unittest.main()
