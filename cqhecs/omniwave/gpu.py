"""
Vulkan backend for the OMNIWAVE batched BCP pass (``shaders/compute/omniwave_bcp.comp``).

The kernel runs through the native shared library's C ABI
(``cq_omniwave_bcp_eval``). Its output must be bit-identical to the CPU reference
:func:`cqhecs.omniwave.bcp.evaluate_batch`; :func:`evaluate_batch_vulkan` can verify
every call against the reference (``verify=True``), and the test suite always does.

Availability is reported, not assumed. :func:`status` says whether the library was
found, whether a Vulkan device answered, and which device it was. A software ICD
(llvmpipe, lavapipe, SwiftShader) is named as such. No speedup is claimed: the
benchmark in ``scripts/omniwave_benchmark.py`` measures it.
"""

from __future__ import annotations

import atexit
import ctypes
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from cqhecs.omniwave import bcp

ROOT = Path(__file__).resolve().parents[2]
_lib: Optional[ctypes.CDLL] = None
_tried = False
_shutdown_registered = False


def _shutdown() -> None:
    """Destroy the native Vulkan context before the DLL is unloaded."""
    lib = _lib
    if lib is None:
        return
    try:
        lib.cq_omniwave_shutdown()
    except (AttributeError, OSError):
        pass


class GpuUnavailable(RuntimeError):
    """No native library or no Vulkan device; use the CPU reference."""


def _candidates() -> List[Path]:
    name = "cq_hecs.dll" if sys.platform == "win32" else "libcq_hecs.so"
    dirs = []
    if os.environ.get("CQ_HECS_BUILD_DIR"):
        dirs.append(Path(os.environ["CQ_HECS_BUILD_DIR"]))
    build = ROOT / "build"
    dirs += [build / "bin" / "Release", build / "bin", build / "Release", build / "lib", build]
    return [d / name for d in dirs if (d / name).is_file()]


def _load() -> Optional[ctypes.CDLL]:
    global _lib, _tried, _shutdown_registered
    if _tried:
        return _lib
    _tried = True
    for path in _candidates():
        try:
            lib = ctypes.CDLL(str(path))
        except OSError:
            continue
        if not hasattr(lib, "cq_omniwave_bcp_eval"):
            continue
        u32p = ctypes.POINTER(ctypes.c_uint32)
        lib.cq_omniwave_bcp_eval.argtypes = [u32p, u32p, ctypes.c_uint32, u32p, u32p, ctypes.c_uint32,
                                             ctypes.c_uint32, u32p]
        lib.cq_omniwave_bcp_eval.restype = ctypes.c_int
        lib.cq_omniwave_device_name.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        lib.cq_omniwave_device_name.restype = ctypes.c_int
        if hasattr(lib, "cq_omniwave_shutdown"):
            lib.cq_omniwave_shutdown.argtypes = []
            lib.cq_omniwave_shutdown.restype = None
        _lib = lib
        if not _shutdown_registered:
            atexit.register(_shutdown)
            _shutdown_registered = True
        break
    return _lib


def status() -> Dict[str, object]:
    lib = _load()
    if lib is None:
        return {"available": False, "reason": "native library with cq_omniwave_bcp_eval not found"}
    buf = ctypes.create_string_buffer(256)
    rc = lib.cq_omniwave_device_name(buf, 256)
    if rc != 0:
        return {"available": False, "reason": "no Vulkan device"}
    name = buf.value.decode("utf-8", "replace")
    software = any(s in name.lower() for s in ("llvmpipe", "lavapipe", "swiftshader"))
    return {"available": True, "device": name, "software_icd": software}


def available() -> bool:
    return bool(status()["available"])


def _array(values: Sequence[int]):
    arr = (ctypes.c_uint32 * max(1, len(values)))()
    for i, v in enumerate(values):
        arr[i] = v & 0xFFFFFFFF
    return arr


def evaluate_batch_vulkan(clauses: Sequence[Sequence[int]], fronts: bcp.Fronts, verify: bool = False) -> List[List[int]]:
    """One BCP evaluation pass on the GPU; same contract as ``bcp.evaluate_batch``."""
    lib = _load()
    if lib is None:
        raise GpuUnavailable("native library with cq_omniwave_bcp_eval not found")
    offsets, codes = bcp.flatten_clauses(clauses)
    nf, words, m = len(fronts.assigned), fronts.words, len(clauses)
    if m == 0 or nf == 0:
        return [[] for _ in range(nf)]
    out = (ctypes.c_uint32 * (nf * m))()
    rc = lib.cq_omniwave_bcp_eval(
        _array(offsets), _array(codes), m,
        _array([w for row in fronts.assigned for w in row]),
        _array([w for row in fronts.value for w in row]),
        nf, words, out,
    )
    if rc == -2:
        raise GpuUnavailable("no Vulkan device")
    if rc != 0:
        raise RuntimeError(f"cq_omniwave_bcp_eval failed with code {rc}")
    result = [list(out[f * m:(f + 1) * m]) for f in range(nf)]
    if verify:
        reference = bcp.evaluate_batch(clauses, fronts)
        if result != reference:
            raise AssertionError("GPU BCP result differs from the CPU reference")
    return result
