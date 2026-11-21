"""W4-18: C-ABI hardening contract, observed from a foreign caller (ctypes).

The C++ twins of these checks live in ``tests/cpp/test_c_abi_core.cpp`` and
``tests/cpp/test_vulkan_bcp_differential.cpp`` (run by CTest, including under
ASan/UBSan). This file proves the same contract through the shipped shared
libraries, the way Python/Rust/C# callers actually bind them. A missing native
build skips, unless ``CQ_HECS_REQUIRE_NATIVE=1`` (CI), where it fails.
"""

from __future__ import annotations

import ctypes
import os

import pytest

from tests import native_artifacts


def _lib(name_windows: str, name_posix: str) -> ctypes.CDLL:
    name = name_windows if os.name == "nt" else name_posix
    path = native_artifacts.find_native(name)
    if path is None:
        msg = f"native library {name} not found (set CQ_HECS_BUILD_DIR)"
        if os.environ.get("CQ_HECS_REQUIRE_NATIVE") == "1":
            raise AssertionError(msg + " (CQ_HECS_REQUIRE_NATIVE=1)")
        pytest.skip(msg)
    return ctypes.CDLL(str(path))


@pytest.fixture(scope="module")
def core() -> ctypes.CDLL:
    lib = _lib("cq_hecs_core.dll", "libcq_hecs_core.so")
    if not hasattr(lib, "cq_core_abi_version"):
        pytest.skip("cq_hecs_core predates ABI 1.1 (stale build)")
    c_void_p, u32 = ctypes.c_void_p, ctypes.c_uint32
    lib.cq_core_abi_version.restype = u32
    lib.cq_core_check_abi.argtypes = [u32, u32]
    lib.cq_core_check_abi.restype = ctypes.c_int
    lib.cq_core_last_error.restype = ctypes.c_int
    lib.cq_core_clear_error.restype = None
    lib.cq_core_build_capabilities.restype = ctypes.c_char_p
    lib.cq_create_simulator.argtypes = [u32, u32]
    lib.cq_create_simulator.restype = c_void_p
    lib.cq_destroy_simulator.argtypes = [c_void_p]
    lib.cq_destroy_simulator.restype = None
    for name in ("cq_apply_h", "cq_apply_x", "cq_apply_t"):
        getattr(lib, name).argtypes = [c_void_p, u32]
        getattr(lib, name).restype = None
    lib.cq_apply_cx.argtypes = [c_void_p, u32, u32]
    lib.cq_apply_cx.restype = None
    lib.cq_apply_rz.argtypes = [c_void_p, u32, ctypes.c_double]
    lib.cq_apply_rz.restype = None
    lib.cq_sample_counts_json.argtypes = [c_void_p, u32, ctypes.c_char_p, ctypes.c_size_t]
    lib.cq_sample_counts_json.restype = ctypes.c_int
    lib.cq_execute_qasm.argtypes = [c_void_p, ctypes.c_char_p, u32, ctypes.c_char_p, ctypes.c_size_t]
    lib.cq_execute_qasm.restype = ctypes.c_int
    return lib


def _sample(core, handle, shots=4) -> str:
    buf = ctypes.create_string_buffer(4096)
    rc = core.cq_sample_counts_json(handle, shots, buf, 4096)
    assert rc == 0, rc
    return buf.value.decode()


def test_core_abi_version_and_check(core):
    assert core.cq_core_abi_version() == (1 << 16) | 1
    assert core.cq_core_check_abi(1, 0) == 0
    assert core.cq_core_check_abi(1, 1) == 0
    assert core.cq_core_check_abi(1, 2) == -1   # caller newer than the library
    assert core.cq_core_check_abi(2, 0) == -1   # different major
    assert b'"cpu_core":true' in core.cq_core_build_capabilities()


@pytest.mark.parametrize("n,bond", [(0, 64), (4097, 64), (4, 0), (4, 65537)])
def test_core_create_rejects_bad_sizes_without_throwing(core, n, bond):
    # Before W4-18 these threw a C++ exception across the C boundary (SEH 0xE06D7363
    # on Windows, std::terminate elsewhere), killing the host process.
    core.cq_core_clear_error()
    assert core.cq_create_simulator(n, bond) is None
    assert core.cq_core_last_error() == 4  # CQ_CORE_ERR_INVALID_ARG


def test_core_out_of_range_qubit_is_refused_and_state_unchanged(core):
    h = core.cq_create_simulator(2, 64)
    assert h
    core.cq_apply_x(h, 1)
    before = _sample(core, h)
    core.cq_core_clear_error()
    core.cq_apply_x(h, 2)
    assert core.cq_core_last_error() == 2       # CQ_CORE_ERR_QUBIT_RANGE
    core.cq_apply_cx(h, 1, 1)
    assert core.cq_core_last_error() == 3       # CQ_CORE_ERR_DUPLICATE_QUBIT
    assert _sample(core, h) == before
    core.cq_destroy_simulator(h)


def test_core_wide_non_clifford_is_refused_not_silently_wrong(core):
    """The hybrid engine keeps a 16-qubit shadow statevector; a T on a 20-qubit
    simulator used to return a 16-bit bitstring for a 20-qubit circuit (rc 0)."""
    h = core.cq_create_simulator(20, 64)
    out = ctypes.create_string_buffer(256)
    rc = core.cq_execute_qasm(
        h, b"OPENQASM 2.0;\nqreg q[20];\nh q[0];\nt q[0];\nh q[0];\n", 4, out, 256)
    assert rc == -4
    assert out.value == b""
    core.cq_core_clear_error()
    core.cq_apply_t(h, 0)
    assert core.cq_core_last_error() == 6       # CQ_CORE_ERR_UNSUPPORTED
    core.cq_destroy_simulator(h)


def test_core_nonfinite_angle_refused(core):
    h = core.cq_create_simulator(2, 64)
    core.cq_core_clear_error()
    core.cq_apply_rz(h, 0, float("nan"))
    assert core.cq_core_last_error() == 4
    core.cq_core_clear_error()
    core.cq_apply_rz(h, 0, -1.0e300)            # legal: reduced modulo 2*pi
    assert core.cq_core_last_error() == 0
    core.cq_destroy_simulator(h)


def test_core_execute_qasm_return_codes(core):
    h = core.cq_create_simulator(2, 64)
    out = ctypes.create_string_buffer(4096)
    bell = b'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\n'
    assert core.cq_execute_qasm(h, bell, 50, out, 4096) == 0
    assert b'"01"' not in out.value and b'"10"' not in out.value
    assert core.cq_execute_qasm(h, None, 1, out, 4096) == -1
    assert core.cq_execute_qasm(h, bell, 1 << 25, out, 4096) == -4
    assert core.cq_execute_qasm(h, b"OPENQASM 2.0;\nqreg q[2];\nteleport q[0];\n", 1, out, 4096) == -3
    assert core.cq_execute_qasm(h, b"OPENQASM 2.0;\nqreg q[5];\nh q[4];\n", 1, out, 4096) == -6
    tiny = ctypes.create_string_buffer(3)
    assert core.cq_execute_qasm(h, bell, 10, tiny, 3) == -2
    core.cq_destroy_simulator(h)


# --------------------------------------------------------------------------- facade
@pytest.fixture(scope="module")
def facade() -> ctypes.CDLL:
    lib = _lib("cq_hecs.dll", "libcq_hecs.so")
    if not hasattr(lib, "cq_abi_version"):
        pytest.skip("cq_hecs predates ABI 1.1 (stale build)")
    u32p = ctypes.POINTER(ctypes.c_uint32)
    lib.cq_abi_version.restype = ctypes.c_uint32
    lib.cq_check_abi.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.cq_check_abi.restype = ctypes.c_int
    lib.cq_create_context.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.cq_create_context.restype = ctypes.c_void_p
    lib.cq_omniwave_bcp_eval.argtypes = [u32p, u32p, ctypes.c_uint32, u32p, u32p,
                                         ctypes.c_uint32, ctypes.c_uint32, u32p]
    lib.cq_omniwave_bcp_eval.restype = ctypes.c_int
    lib.cq_solve_sat.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
    lib.cq_solve_sat.restype = ctypes.c_int
    return lib


def _u32(*vals):
    arr = (ctypes.c_uint32 * max(1, len(vals)))()
    for i, v in enumerate(vals):
        arr[i] = v
    return arr


def test_facade_abi_version_and_check(facade):
    assert facade.cq_abi_version() == (1 << 16) | 1
    assert facade.cq_check_abi(1, 1) == 0
    assert facade.cq_check_abi(1, 2) == -1
    assert facade.cq_check_abi(2, 0) == -1


def test_facade_create_context_rejects_absurd_sizes(facade):
    assert facade.cq_create_context(5000, 64) is None
    assert facade.cq_create_context(8, 1 << 20) is None


def test_omniwave_bcp_rejects_malformed_input_before_any_device_work(facade):
    """Validation runs before the Vulkan context is touched, so these codes are
    observable on machines without a GPU. The output buffer is never written."""
    out = _u32(*([0xA5A5A5A5] * 8))
    off, codes, asg, val = _u32(0, 1, 2), _u32(0, 2), _u32(0, 0), _u32(0, 0)

    def call(offsets, cds, n_clauses, n_fronts, words):
        return facade.cq_omniwave_bcp_eval(offsets, cds, n_clauses, asg, val, n_fronts, words, out)

    assert call(None, codes, 2, 1, 1) == 1
    assert call(off, codes, 0, 1, 1) == 1
    assert call(off, codes, 2, 65536, 1) == 2                 # too many fronts
    assert call(off, codes, 65535 * 64 + 1, 1, 1) == 2        # too many clauses
    assert call(off, codes, 70000, 65535, 1) == 2             # cells overflow 32 bits
    assert call(_u32(1, 1, 2), codes, 2, 1, 1) == 4           # offsets must start at 0
    assert call(_u32(0, 2, 1), codes, 2, 1, 1) == 4           # offsets must be monotone
    assert call(off, _u32(0, 64), 2, 1, 1) == 4               # variable 32 outside words=1
    assert call(off, _u32(0, 0xFFFFFFFF), 2, 1, 1) == 4
    assert call(off, None, 2, 1, 1) == 1                      # literals but no codes
    assert all(out[i] == 0xA5A5A5A5 for i in range(8))


def test_solve_sat_garbage_is_a_defined_failure(facade):
    class Result(ctypes.Structure):
        _fields_ = [("satisfiable", ctypes.c_int), ("num_vars", ctypes.c_uint32),
                    ("num_clauses", ctypes.c_uint32), ("decisions", ctypes.c_uint32),
                    ("pruned_cycles", ctypes.c_uint32), ("elapsed_ms", ctypes.c_double),
                    ("verified", ctypes.c_int), ("assignment", ctypes.c_int8 * 1024)]

    res = Result()
    res.satisfiable = 77            # poison: must be overwritten on EVERY path
    assert facade.cq_solve_sat(b"this is not a cnf", ctypes.byref(res)) == 1
    assert res.satisfiable == -1    # "no verdict", never a stale/UNSAT-shaped value
    assert res.verified == 0
