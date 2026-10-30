"""Tests for the real-reference dataset harness (v3 W4)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cqhecs.reference import (
    DATASETS,
    DatasetNotAvailableError,
    IntegrityError,
    build_device_mean_noise_model,
    counts_vector,
    dataset,
    device_means,
    evaluate,
    fetch_dataset,
    load_quantum_noise_transfer,
    resolve_file,
    total_variation,
    verify_dataset,
)

ROOT = Path(__file__).resolve().parent / "data" / "quantum_noise_transfer"


class TestRegistry(unittest.TestCase):
    def test_registered_ids_are_stable(self):
        self.assertIn("r-io-5", DATASETS)
        self.assertIn("r-io-6", DATASETS)
        self.assertFalse(DATASETS["r-io-5"].complete_circuits)
        self.assertTrue(DATASETS["r-io-6"].complete_circuits)

    def test_unknown_dataset_is_typed_error(self):
        with self.assertRaises(DatasetNotAvailableError):
            dataset("does-not-exist")

    def test_every_file_is_pinned(self):
        for record in DATASETS.values():
            with self.subTest(dataset=record.dataset_id):
                self.assertTrue(record.files)
                for entry in record.files:
                    self.assertEqual(len(entry.sha256), 64)
                    self.assertGreater(entry.size, 0)
                    int(entry.sha256, 16)


class TestIntegrity(unittest.TestCase):
    def test_vendored_files_verify(self):
        verified = verify_dataset(dataset("r-io-5"), ROOT)
        self.assertEqual(len(verified), 5)

    def test_corruption_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            for entry in dataset("r-io-5").files:
                shutil.copy(ROOT / Path(entry.path).name, target / Path(entry.path).name)
            victim = target / "noisy_A.json"
            payload = bytearray(victim.read_bytes())
            payload[10] ^= 0x01
            victim.write_bytes(payload)
            with self.assertRaises(IntegrityError):
                verify_dataset(dataset("r-io-5"), target)

    def test_missing_file_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(IntegrityError):
                verify_dataset(dataset("r-io-5"), Path(temporary))

    def test_resolve_flat_layout(self):
        path = resolve_file(dataset("r-io-5"), ROOT, "data/raw/circuit_meta.json")
        self.assertEqual(path.name, "circuit_meta.json")
        self.assertTrue(path.is_file())

    def test_fetch_unknown_dataset_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(DatasetNotAvailableError):
                fetch_dataset("not-registered", Path(temporary))


class TestCircuits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_quantum_noise_transfer(ROOT)

    def test_unique_reconstruction_counts(self):
        circuits = self.data.circuits("A")
        self.assertEqual(len(circuits), 7)
        families = sorted(circuit.family for circuit in circuits)
        self.assertEqual(families, ["bell"] + ["ghz"] * 3 + ["qft"] * 3)
        by_family = {circuit.family: circuit for circuit in circuits}
        self.assertEqual(by_family["bell"].executions, 15)
        self.assertEqual(by_family["bell"].shots, 15360)

    def test_repeated_executions_can_be_kept_separate(self):
        circuits = self.data.circuits("A", unique=False)
        self.assertEqual(len(circuits), 45)
        self.assertTrue(all(circuit.executions == 1 for circuit in circuits))

    def test_random_circuits_are_excluded_by_default(self):
        circuits = self.data.circuits("A")
        self.assertNotIn("random", {circuit.family for circuit in circuits})

    def test_bell_gate_counts_match_published_metadata(self):
        bell = [c for c in self.data.circuits("A") if c.family == "bell"][0]
        meta = self.data.metadata[bell.circuit_id]
        gates = [name for name, _qubits, _params in bell.instructions]
        self.assertEqual(gates.count("h"), meta["gate_counts"]["h"])
        self.assertEqual(gates.count("cx"), meta["gate_counts"]["cx"])
        self.assertEqual(gates.count("measure"), meta["gate_counts"]["measure"])

    def test_ghz_gate_counts_match_published_metadata(self):
        for circuit in [c for c in self.data.circuits("A") if c.family == "ghz"]:
            meta = self.data.metadata[circuit.circuit_id]
            gates = [name for name, _qubits, _params in circuit.instructions]
            self.assertEqual(gates.count("h"), 1)
            self.assertEqual(gates.count("cx"), circuit.num_qubits - 1)
            self.assertEqual(meta["gate_counts"]["cx"], circuit.num_qubits - 1)

    def test_qft_is_marked_as_reconstruction_not_exact(self):
        for circuit in [c for c in self.data.circuits("A") if c.family == "qft"]:
            self.assertFalse(circuit.exact_gate_sequence)
            self.assertIn("not verified", circuit.reconstruction_note)


class TestDeviceModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_quantum_noise_transfer(ROOT)

    def test_means_are_plausible_and_pinned_to_the_snapshot(self):
        means = device_means(self.data.calibrations["A"])
        self.assertEqual(means.backend, "ibm_fez")
        self.assertGreater(means.num_operational_edges, 100)
        self.assertGreater(means.cx_error_median, 0.0)
        self.assertLess(means.cx_error_median, 0.75)
        self.assertGreater(means.readout_error_median, 0.0)
        self.assertLess(means.readout_error_median, 0.5)
        self.assertGreater(means.two_qubit_depolarizing_parameter, 0.0)

    def test_noise_model_changes_a_bell_circuit(self):
        from cqhecs.reference import _simulate

        circuit = [c for c in self.data.circuits("A") if c.family == "bell"][0]
        means = device_means(self.data.calibrations["A"])
        ideal = _simulate(circuit, None)
        noisy = _simulate(circuit, build_device_mean_noise_model(circuit, means))
        self.assertGreater(total_variation(ideal, noisy), 0.01)
        self.assertAlmostEqual(float(noisy.sum()), 1.0, places=12)

    def test_qft_is_invariant_under_unital_noise(self):
        from cqhecs.reference import _simulate

        circuit = [c for c in self.data.circuits("A") if c.family == "qft"][0]
        means = device_means(self.data.calibrations["A"])
        ideal = _simulate(circuit, None)
        noisy = _simulate(circuit, build_device_mean_noise_model(circuit, means))
        self.assertLess(total_variation(ideal, noisy), 1e-12)


class TestMetrics(unittest.TestCase):
    def test_counts_vector_bit_order(self):
        vector = counts_vector({"00": 3, "11": 1}, 2)
        np.testing.assert_allclose(vector, [0.75, 0.0, 0.0, 0.25])

    def test_counts_vector_rejects_wrong_width(self):
        with self.assertRaises(ValueError):
            counts_vector({"000": 1}, 2)

    def test_total_variation(self):
        self.assertAlmostEqual(total_variation(np.array([1.0, 0.0]), np.array([0.0, 1.0])), 1.0)
        self.assertAlmostEqual(total_variation(np.array([0.5, 0.5]), np.array([0.5, 0.5])), 0.0)


class TestEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = evaluate(ROOT, bootstrap_samples=200, seed=7)

    def test_contract_and_verdict(self):
        payload = self.result.to_dict()
        self.assertEqual(payload["dataset_id"], "r-io-5")
        self.assertEqual(len(payload["dataset_sha256"]), 64)
        self.assertEqual(payload["aggregate"]["n_circuits"], 14)
        self.assertIn(payload["aggregate"]["verdict"], {"SUPPORTED", "REJECTED", "INCONCLUSIVE"})
        self.assertLessEqual(payload["aggregate"]["ci95_low"], payload["aggregate"]["ci95_high"])

    def test_all_evaluations_are_finite_and_normalised(self):
        for circuit in self.result.circuits:
            self.assertTrue(np.isfinite(circuit.tv_ideal))
            self.assertTrue(np.isfinite(circuit.tv_noisy))
            self.assertGreaterEqual(circuit.tv_ideal, 0.0)
            self.assertGreaterEqual(circuit.tv_noisy, 0.0)
            self.assertGreater(circuit.shots, 0)

    def test_identifiable_subset_is_exploratory_only(self):
        aggregate = self.result.aggregate
        self.assertEqual(aggregate["exploratory_identifiable"]["n"], 8)
        self.assertIn("not preregistered", aggregate["exploratory_identifiable"]["note"])
        self.assertEqual(aggregate["by_family"]["qft"]["median_delta_tv"], 0.0)

    def test_reproducible_with_the_same_seed(self):
        again = evaluate(ROOT, bootstrap_samples=200, seed=7)
        self.assertEqual(
            again.aggregate["ci95_low"],
            self.result.aggregate["ci95_low"],
        )


if __name__ == "__main__":
    unittest.main()
