"""
Concurrency contract tests for the legacy bridge objects.

Supported contract
------------------
* Independent simulator/solver instances may run in parallel threads. Each
  worker owns its objects; no instance is shared between threads.
* ``CQSATSolver`` and ``MPS300QubitSimulator`` instances are **not** documented
  as thread-safe for concurrent use of the *same* instance. This module tests
  the independent-instance contract only and says so, instead of inferring
  race-freedom from a thread-pool run.

The tests synchronize starts, impose timeouts, collect every result (including
exceptions) and verify actual outputs rather than a boolean "it worked" flag.
"""

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from python_bridge.cq_hecs import MPS300QubitSimulator
from python_bridge.sat_engine import CQSATSolver, DIMACSParser

CNF_SOURCE = "p cnf 5 4\n1 2 -3 0\n-1 3 4 0\n-2 -4 5 0\n-5 1 2 0\n"
CNF_CLAUSES = [
    [1, 2, -3],
    [-1, 3, 4],
    [-2, -4, 5],
    [-5, 1, 2],
]
FUTURE_TIMEOUT_SECONDS = 60


def assignment_satisfies(clauses, assignment):
    """Independent oracle: evaluates the CNF under a concrete assignment."""
    for clause in clauses:
        if not any(
            assignment.get(abs(literal), False) == (literal > 0)
            for literal in clause
        ):
            return False
    return True


class TestIndependentInstanceConcurrency(unittest.TestCase):
    def test_16_workers_produce_verified_results(self):
        start_gate = threading.Barrier(16)
        results = []
        errors = []

        def sat_worker(worker_id: int):
            start_gate.wait(timeout=FUTURE_TIMEOUT_SECONDS)
            solver = CQSATSolver(table_capacity=2048)
            formula = DIMACSParser.parse_string(CNF_SOURCE)
            result = solver.solve(formula, timeout_seconds=10.0)
            return ("sat", worker_id, result)

        def mps_worker(worker_id: int):
            start_gate.wait(timeout=FUTURE_TIMEOUT_SECONDS)
            mps = MPS300QubitSimulator(num_qubits=300, max_chi=32)
            for step in range(20):
                mps.apply_single_qubit_z8_gate(step % 300, phase_shift=(step % 7) + 1)
            site = mps.governor.fetch(299)
            return ("mps", worker_id, site)

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(sat_worker, t) for t in range(8)]
            futures += [executor.submit(mps_worker, t) for t in range(8, 16)]

            for future in futures:
                try:
                    results.append(future.result(timeout=FUTURE_TIMEOUT_SECONDS))
                except FutureTimeout as exc:  # pragma: no cover - failure path
                    errors.append(f"worker timed out: {exc}")
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append(f"{type(exc).__name__}: {exc}")

        self.assertEqual(errors, [], msg=f"worker failures: {errors}")
        self.assertEqual(len(results), 16)

        for kind, worker_id, payload in results:
            with self.subTest(kind=kind, worker=worker_id):
                if kind == "sat":
                    self.assertTrue(payload.satisfiable)
                    self.assertTrue(payload.verified)
                    self.assertTrue(
                        assignment_satisfies(CNF_CLAUSES, payload.assignment),
                        msg=f"worker {worker_id} returned a non-satisfying assignment",
                    )
                else:
                    self.assertIsInstance(payload, (bytes, bytearray))
                    self.assertGreater(len(payload), 0)

    def test_parallel_mps_matches_sequential_reference(self):
        def run_sequence():
            mps = MPS300QubitSimulator(num_qubits=64, max_chi=16)
            for step in range(50):
                mps.apply_single_qubit_z8_gate(step % 64, phase_shift=(step % 5) + 1)
            return b"".join(mps.governor.fetch(site) for site in range(64))

        reference = run_sequence()

        def worker(_):
            return run_sequence()

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(8)]
            parallel = [f.result(timeout=FUTURE_TIMEOUT_SECONDS) for f in futures]

        for index, value in enumerate(parallel):
            self.assertEqual(
                value,
                reference,
                msg=f"parallel run {index} diverged from the sequential reference",
            )

    def test_worker_exception_is_not_swallowed(self):
        """A failing job must surface, not turn into a silent 'success'."""
        def boom():
            raise RuntimeError("injected worker failure")

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(boom)
            with self.assertRaises(RuntimeError):
                future.result(timeout=FUTURE_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main()
