"""
Test Suite: Multi-Threading Contention & Concurrency Stress Test
Tests concurrent execution across 16+ CPU threads to verify zero data races.
"""

import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from python_bridge.cq_hecs import GlobalWorkspaceMetaLayer, JSpaceAlpha, JSpaceBeta, JSpaceGamma, MPS300QubitSimulator
from python_bridge.sat_engine import CQSATSolver, DIMACSParser


class TestConcurrencyStress(unittest.TestCase):
    def test_16_threads_concurrent_sat_and_mps(self):
        """Run parallel SAT solving and MPS state operations across 16 threads without races."""
        results = []
        errors = []

        cnf_src = "p cnf 5 4\n1 2 -3 0\n-1 3 4 0\n-2 -4 5 0\n-5 1 2 0\n"

        def sat_worker(thread_id: int):
            try:
                solver = CQSATSolver(table_capacity=2048)
                formula = DIMACSParser.parse_string(cnf_src)
                res = solver.solve(formula, timeout_seconds=5.0)
                return ("sat", thread_id, res.satisfiable, res.verified)
            except Exception as e:
                errors.append(f"SAT thread {thread_id} error: {e}")
                return ("sat", thread_id, False, False)

        def mps_worker(thread_id: int):
            try:
                gwt = GlobalWorkspaceMetaLayer()
                mps = MPS300QubitSimulator(num_qubits=300, max_chi=32)
                for step in range(20):
                    mps.apply_single_qubit_z8_gate(step % 300, phase_shift=(step % 7) + 1)
                attn = gwt.cross_attention_aggregation(0.5, 0.5, 0.2, 0.01, 0.8)
                ent = gwt.harvest_hardware_entropy()
                return ("mps", thread_id, True, ent > 0)
            except Exception as e:
                errors.append(f"MPS thread {thread_id} error: {e}")
                return ("mps", thread_id, False, False)

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = []
            for t in range(8):
                futures.append(executor.submit(sat_worker, t))
            for t in range(8, 16):
                futures.append(executor.submit(mps_worker, t))

            for f in futures:
                results.append(f.result())

        self.assertEqual(len(errors), 0, f"Encountered thread errors: {errors}")
        self.assertEqual(len(results), 16)
        for r_type, t_id, success, verified in results:
            self.assertTrue(success, f"Thread {t_id} failed")
            self.assertTrue(verified, f"Thread {t_id} verification failed")


if __name__ == "__main__":
    unittest.main()
