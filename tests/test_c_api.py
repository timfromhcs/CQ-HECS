"""
Test Suite: C-ABI Shared Library (cq_hecs.dll) Verification via ctypes
Tests programmatic embedding into Python / foreign language runtimes.
"""

import unittest
import ctypes
from pathlib import Path


class CQResult(ctypes.Structure):
    _fields_ = [
        ("gate_count", ctypes.c_uint32),
        ("qubit_count", ctypes.c_uint32),
        ("elapsed_ms", ctypes.c_double),
        ("active_vram_mb", ctypes.c_double),
        ("lambda_res", ctypes.c_double),
        ("success", ctypes.c_int),
    ]


class CQSATResult(ctypes.Structure):
    _fields_ = [
        ("satisfiable", ctypes.c_int),
        ("num_vars", ctypes.c_uint32),
        ("num_clauses", ctypes.c_uint32),
        ("decisions", ctypes.c_uint32),
        ("pruned_cycles", ctypes.c_uint32),
        ("elapsed_ms", ctypes.c_double),
        ("verified", ctypes.c_int),
        ("assignment", ctypes.c_int8 * 1024),
    ]


class TestCAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = Path(__file__).parent.parent
        import os
        if os.name == 'nt':
            candidates = [
                base_dir / "bin" / "Release" / "cq_hecs.dll",
                base_dir / "bin" / "cq_hecs.dll",
            ]
        else:
            candidates = [
                base_dir / "bin" / "libcq_hecs.so",
                base_dir / "bin" / "Release" / "libcq_hecs.so",
                base_dir / "build" / "libcq_hecs.so",
            ]
        dll_path = next((p for p in candidates if p.exists()), candidates[0])
        cls.assertTrue(cls, dll_path.exists(), f"Missing {dll_path}")
        cls.lib = ctypes.CDLL(str(dll_path))

        # Setup function prototypes
        cls.lib.cq_get_version.restype = ctypes.c_char_p
        cls.lib.cq_get_version.argtypes = []

        cls.lib.cq_create_context.restype = ctypes.c_void_p
        cls.lib.cq_create_context.argtypes = [ctypes.c_uint32, ctypes.c_uint32]

        cls.lib.cq_get_active_vram_mb.restype = ctypes.c_double
        cls.lib.cq_get_active_vram_mb.argtypes = [ctypes.c_void_p]

        cls.lib.cq_execute_qasm.restype = ctypes.c_int
        cls.lib.cq_execute_qasm.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(CQResult)]

        cls.lib.cq_solve_sat.restype = ctypes.c_int
        cls.lib.cq_solve_sat.argtypes = [ctypes.c_char_p, ctypes.POINTER(CQSATResult)]

        cls.lib.cq_invert_arx.restype = ctypes.c_int
        cls.lib.cq_invert_arx.argtypes = [
            ctypes.c_char_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)
        ]

        cls.lib.cq_destroy_context.restype = None
        cls.lib.cq_destroy_context.argtypes = [ctypes.c_void_p]

    def test_version_query(self):
        ver = self.lib.cq_get_version().decode("utf-8")
        self.assertEqual(ver, "4.5.0")

    def test_context_lifecycle_and_vram(self):
        ctx = self.lib.cq_create_context(300, 64)
        self.assertIsNotNone(ctx)

        vram = self.lib.cq_get_active_vram_mb(ctx)
        self.assertGreater(vram, 0.0)
        self.assertLess(vram, 120.0)

        self.lib.cq_destroy_context(ctx)

    def test_execute_qasm_via_c_api(self):
        ctx = self.lib.cq_create_context(300, 64)
        self.assertIsNotNone(ctx)

        qasm_src = b"""
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[300];
        creg c[300];
        h q[0];
        cx q[0], q[1];
        cx q[1], q[2];
        measure q[0] -> c[0];
        """

        res = CQResult()
        status = self.lib.cq_execute_qasm(ctx, qasm_src, ctypes.byref(res))

        self.assertEqual(status, 0)
        self.assertEqual(res.success, 1)
        self.assertEqual(res.qubit_count, 300)
        self.assertEqual(res.gate_count, 4)
        self.assertLess(res.active_vram_mb, 120.0)

        self.lib.cq_destroy_context(ctx)

    def test_solve_sat_via_c_api(self):
        # 1. Satisfiable formula
        sat_cnf = b"p cnf 3 2\n1 2 0\n-1 3 0\n"
        res_sat = CQSATResult()
        code_sat = self.lib.cq_solve_sat(sat_cnf, ctypes.byref(res_sat))
        self.assertEqual(code_sat, 0) # 0 for SAT
        self.assertEqual(res_sat.satisfiable, 1)
        self.assertEqual(res_sat.verified, 1)

        # 2. Unsatisfiable formula
        unsat_cnf = b"p cnf 1 2\n1 0\n-1 0\n"
        res_unsat = CQSATResult()
        code_unsat = self.lib.cq_solve_sat(unsat_cnf, ctypes.byref(res_unsat))
        self.assertEqual(code_unsat, 10) # 10 for UNSAT
        self.assertEqual(res_unsat.satisfiable, 0)

    def test_invert_arx_via_c_api(self):
        target = (ctypes.c_uint64 * 4)(0x1111, 0x2222, 0x3333, 0x4444)
        preimage = (ctypes.c_uint64 * 4)(0, 0, 0, 0)

        ret = self.lib.cq_invert_arx(b"blake2b", 1, target, preimage)
        self.assertEqual(ret, 0)
        # Preimage words must not be all zeros
        self.assertTrue(any(preimage[i] != 0 for i in range(4)))


if __name__ == "__main__":
    unittest.main()
