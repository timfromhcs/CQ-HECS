"""
Locates native CQ-HECS build artifacts for tests.

The build writes into ``${CMAKE_BINARY_DIR}/bin`` rather than the source tree,
so tests must search the build output rather than assume a fixed location.
Tests that require the native artifact should skip with a clear reason when it
has not been built, rather than erroring with a confusing message.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def _search_dirs() -> List[Path]:
    """Directories that may contain build output, most specific first."""
    dirs: List[Path] = []
    env_dir = os.environ.get("CQ_HECS_BUILD_DIR")
    if env_dir:
        dirs.append(Path(env_dir))
    build = REPO_ROOT / "build"
    # Support both single-config (Ninja: build/bin) and multi-config
    # generators (MSVC: build/bin/Release).
    dirs.extend([
        build / "bin" / "Release",
        build / "bin",
        build / "Release",
        build / "lib" / "Release",
        build / "lib",
        build,
    ])
    # Legacy in-source output, still supported for existing checkouts.
    dirs.append(REPO_ROOT / "bin" / "Release")
    dirs.append(REPO_ROOT / "bin")
    return [d for d in dirs if d.is_dir()]


def find_native(relative_name: str) -> Optional[Path]:
    """Returns the first existing build artifact matching `relative_name`."""
    for directory in _search_dirs():
        candidate = directory / relative_name
        if candidate.exists():
            return candidate
    return None


def find_library() -> Optional[Path]:
    """Locates the C-ABI shared library for the current platform."""
    if os.name == "nt":
        return find_native("cq_hecs.dll")
    return find_native("libcq_hecs.so")


def find_executable() -> Optional[Path]:
    """Locates the standalone native executable for the current platform."""
    if os.name == "nt":
        return find_native("cq_hecs.exe")
    return find_native("cq_hecs")


def require_library() -> Path:
    """
    Returns the C-ABI library path, or skips the test if it is not built.

    Skipping is honest: the artifact is a build product, and a test run that
    did not build the native component has not verified it. CI builds the
    native component before running these tests, so they run there.
    """
    import unittest

    path = find_library()
    if path is None:
        raise unittest.SkipTest(
            "Native C-ABI library not found. Build the native component first: "
            "cmake -B build -DCMAKE_BUILD_TESTS=ON && cmake --build build "
            "--config Release"
        )
    return path


def require_executable() -> Path:
    """Returns the native executable path, or skips the test if not built."""
    import unittest

    path = find_executable()
    if path is None:
        raise unittest.SkipTest(
            "Native executable not found. Build the native component first: "
            "cmake -B build -DCMAKE_BUILD_TESTS=ON && cmake --build build "
            "--config Release"
        )
    return path