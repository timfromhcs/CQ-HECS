"""CQ-02 / CQ-10: Path C resource contract.

These tests pin the difference between *retained tensor bytes* and the real
working set of a contraction/SVD, and require every refusal to be fail-closed:
no partial state, no fabricated counts and no success flag.
"""

import os
import unittest

import numpy as np

from cqhecs.backends.path_c_mps_exact import (
    MAX_MPS_QUBITS,
    MAX_RAM_BUDGET_MB,
    MAX_SHOTS,
    MAX_STORAGE_BUDGET_MB,
    ExactMPSTensorChain,
    MPSResourceError,
    PathCMPSExactBackend,
)


class TestPathCBudgetValidation(unittest.TestCase):
    def test_invalid_budgets_are_rejected(self):
        for name, maximum in (
            ("ram_budget_mb", MAX_RAM_BUDGET_MB),
            ("max_storage_mb", MAX_STORAGE_BUDGET_MB),
        ):
            for value in (
                0, -1, float("nan"), float("inf"), -float("inf"),
                True, "100", None, maximum * 2,
            ):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        PathCMPSExactBackend(**{name: value})

    def test_valid_budget_types_are_accepted(self):
        # Genuine integral types are legitimate MiB values.
        backend = PathCMPSExactBackend(ram_budget_mb=64, max_storage_mb=128)
        self.assertEqual(backend.ram_budget_mb, 64.0)
        self.assertEqual(backend.max_storage_mb, 128.0)

    def test_invalid_qubit_counts_are_rejected_before_allocation(self):
        for value in (-1, 1.5, True, "4", MAX_MPS_QUBITS + 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ExactMPSTensorChain(num_qubits=value)

    def test_invalid_shots_are_rejected_before_evolution(self):
        backend = PathCMPSExactBackend()
        for value in (0, -1, 1.5, True, "8", MAX_SHOTS + 1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    backend.execute([("h", [0], [])], shots=value)

    def test_shots_times_qubits_batch_ceiling(self):
        chain = ExactMPSTensorChain(num_qubits=64)
        try:
            with self.assertRaises(ValueError) as ctx:
                chain.sample(shots=1_000_000, seed=1)
            self.assertIn("batch ceiling", str(ctx.exception))
        finally:
            chain.cleanup()


class TestPathCPreflight(unittest.TestCase):
    def _cx(self):
        return np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]],
            dtype=np.complex128,
        )

    def test_storage_preflight_refuses_before_contracting(self):
        chain = ExactMPSTensorChain(num_qubits=3, max_storage_mb=1.0)
        try:
            before = chain.to_statevector().copy()
            chain.max_storage_bytes = 100  # below the projected 2-site output
            chain.apply_two_qubit_gate(0, 1, self._cx())
            self.assertTrue(chain.memory_limit_exceeded)
            self.assertEqual(chain.resource_limit_kind, "storage")
            self.assertEqual(chain.num_two_qubit_rewrites, 0)
            self.assertGreater(
                chain.last_preflight["projected_retained_bytes"],
                chain.max_storage_bytes,
            )
            np.testing.assert_allclose(chain.to_statevector(), before, atol=0)
        finally:
            chain.cleanup()

    def test_ram_preflight_refuses_before_contracting(self):
        chain = ExactMPSTensorChain(num_qubits=3, ram_budget_mb=1.0)
        try:
            h = np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)
            chain.apply_single_qubit_gate(0, h)
            before = chain.to_statevector().copy()
            # Leave room for the current sites but not for the contraction/SVD
            # working set.
            chain.ram_budget_bytes = chain.active_ram_bytes + 16
            chain.apply_two_qubit_gate(0, 1, self._cx())
            self.assertTrue(chain.memory_limit_exceeded)
            self.assertEqual(chain.resource_limit_kind, "ram")
            self.assertEqual(chain.num_two_qubit_rewrites, 0)
            self.assertGreater(
                chain.last_preflight["projected_working_set_bytes"],
                chain.ram_budget_bytes,
            )
            np.testing.assert_allclose(chain.to_statevector(), before, atol=0)
        finally:
            chain.cleanup()

    def test_preflight_estimate_is_reported_in_results(self):
        backend = PathCMPSExactBackend(max_storage_mb=0.002)  # ~2097 bytes
        result = backend.execute(
            [("h", [0], []), ("h", [1], []), ("cx", [0, 1], [])], shots=8
        )
        # Bond growth may still fit; either way the estimate is present and the
        # result never claims success after a refusal.
        if result.unresolved:
            self.assertEqual(result.counts, {})
            self.assertIn("preflight_estimate", result.metadata)
        else:
            self.assertIn("preflight_estimate", result.metadata)


class TestPathCSamplingPaging(unittest.TestCase):
    def test_sampling_refuses_to_rehydrate_beyond_ram(self):
        chain = ExactMPSTensorChain(num_qubits=8, ram_budget_mb=0.0002)
        try:
            chain.apply_single_qubit_gate(
                0, np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)
            )
            self.assertTrue(any(s is None for s in chain.sites))
            counts, supported = chain.sample(shots=4, seed=1)
            self.assertEqual(counts, {})
            self.assertFalse(supported)
            self.assertIsNotNone(chain.sampling_refusal_reason)
            self.assertIn("rehydrating", chain.sampling_refusal_reason)
        finally:
            chain.cleanup()

    def test_backend_reports_paged_sampling_as_unresolved(self):
        backend = PathCMPSExactBackend(
            ram_budget_mb=0.0002, max_storage_mb=1.0
        )
        qc = [("h", [q], []) for q in range(8)]
        result = backend.execute(qc, shots=4, seed=1)
        self.assertTrue(result.unresolved)
        self.assertEqual(result.counts, {})
        self.assertEqual(result.metadata["resource_limit"], "ram")
        self.assertFalse(result.metadata["truncation_applied"])

    def test_missing_swap_page_fails_closed(self):
        chain = ExactMPSTensorChain(num_qubits=8, ram_budget_mb=0.0002)
        try:
            chain.apply_single_qubit_gate(
                0, np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)
            )
            paged = [q for q, s in enumerate(chain.sites) if s is None]
            self.assertTrue(paged)
            os.remove(chain.swap_files[paged[0]])
            with self.assertRaises(MPSResourceError):
                chain.to_statevector()
            self.assertIn("missing", chain.storage_error)
        finally:
            chain.cleanup()

    def test_cleanup_is_idempotent(self):
        # Idempotent cleanup must not raise or mask an earlier failure.
        chain = ExactMPSTensorChain(num_qubits=2)
        chain.cleanup()
        chain.cleanup()
        self.assertFalse(os.path.isdir(chain.temp_dir))


if __name__ == "__main__":
    unittest.main()
