"""
Test Suite: 300-Qubit MPS Tensor Simulation & Tiered Memory Governor (< 120 MB VRAM)
"""

import unittest
import numpy as np
from python_bridge.cq_hecs import (
    MPS300QubitSimulator,
    TieredMemoryGovernor,
    JSpaceDelta
)


class TestMPS300Qbits(unittest.TestCase):
    def test_mps_300_qubits_vram_limit(self):
        """Verify 300-qubit MPS allocation stays strictly under 120 MB active VRAM."""
        governor = TieredMemoryGovernor(max_vram_mb=120.0)
        mps = MPS300QubitSimulator(num_qubits=300, max_chi=64, governor=governor)

        # Assert node count is 300
        self.assertEqual(len(mps.nodes), 300)

        # Measure active memory in governor
        active_bytes = governor.active_vram_bytes
        active_mb = active_bytes / (1024 * 1024)

        # Strict contract check: VRAM must be < 120 MB
        self.assertLess(active_mb, 120.0, f"Active VRAM {active_mb:.2f} MB exceeded 120 MB limit!")
        # Internal MPS size is ~5.2 MB
        self.assertGreater(active_mb, 1.0)

    def test_mps_gate_operations(self):
        """Verify gate applications across the 300-qubit MPS chain."""
        mps = MPS300QubitSimulator(num_qubits=300, max_chi=64)

        # Apply T-gates and S-gates to first 20 qubits
        for site in range(20):
            mps.apply_single_qubit_z8_gate(site, phase_shift=1) # T-gate
            mps.apply_single_qubit_z8_gate(site, phase_shift=2) # S-gate

        # Memory must still remain under 120 MB
        active_mb = mps.governor.active_vram_bytes / (1024 * 1024)
        self.assertLess(active_mb, 120.0)

    def test_tiered_memory_paging_integrity(self):
        """Test paging out to cold storage swap and fetching back."""
        governor = TieredMemoryGovernor(max_vram_mb=2.0) # Small 2 MB limit to force eviction

        # Allocate 3 pages of 1 MB each (3 MB > 2 MB limit)
        page1_data = b"ALPHA_PAGE_DATA_" * 65536 # 1 MB
        page2_data = b"BETA_PAGE_DATA__" * 65536 # 1 MB
        page3_data = b"GAMMA_PAGE_DATA_" * 65536 # 1 MB

        governor.allocate(1, page1_data)
        governor.allocate(2, page2_data)
        # Allocating 3rd page triggers eviction of older page to swap file
        governor.allocate(3, page3_data)

        # Active memory must be within budget
        self.assertLessEqual(governor.active_vram_bytes, governor.max_vram_bytes)
        self.assertGreater(governor.cold_storage_bytes, 0)

        # Fetch back evicted page and verify exact byte integrity
        fetched1 = governor.fetch(1)
        self.assertEqual(fetched1, page1_data)

    def test_residual_svd_frobenius_energy_tracking(self):
        """Test J-Space Delta residual SVD truncation and lossless re-inflation."""
        delta = JSpaceDelta(max_chi=8)

        # Create test matrix with rank 16
        rng = np.random.default_rng(42)
        A = rng.standard_normal((32, 16))
        B = rng.standard_normal((16, 32))
        M = A @ B

        original_frobenius_sq = float(np.sum(M ** 2))

        # Truncate at chi=8
        u_kept, s_kept, vt_kept, lambda_res = delta.truncate_svd_with_residual_tracking(M, bond_tag="bond_0")
        self.assertLessEqual(len(s_kept), 8)
        self.assertGreater(lambda_res, 0.0)

        # Re-inflate using cached residual subspace
        M_reinflated = delta.reinflate_matrix(u_kept, s_kept, vt_kept, bond_tag="bond_0")
        reinflated_frobenius_sq = float(np.sum(M_reinflated ** 2))

        # Assert 100% Frobenius energy conservation
        self.assertAlmostEqual(original_frobenius_sq, reinflated_frobenius_sq, places=6)
        self.assertTrue(np.allclose(M, M_reinflated, atol=1e-6))


if __name__ == "__main__":
    unittest.main()
