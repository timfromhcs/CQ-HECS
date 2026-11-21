"""W3 / T6-03: a genuine CPU-only native build.

``cmake -DCQ_ENABLE_VULKAN=OFF`` must configure, build and pass CTest, and no
produced binary may import the Vulkan loader. Vulkan-dependent targets are
excluded, not stubbed: a CPU build must never pretend to have a GPU path.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CMAKE = shutil.which("cmake")
CTEST = shutil.which("ctest")

pytestmark = pytest.mark.skipif(not (CMAKE and CTEST), reason="cmake/ctest not installed")

# Import-table names are stored as ASCII, so a byte search is a sound detector.
LOADER_MARKERS = (b"vulkan-1", b"libvulkan")
BINARY_SUFFIXES = {".exe", ".dll", ".so", ".dylib", ""}


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _binaries(bin_dir: Path):
    for p in bin_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in BINARY_SUFFIXES and p.stat().st_size > 0:
            if p.suffix == "" and p.name.startswith("."):
                continue
            yield p


@pytest.fixture(scope="module")
def cpu_build(tmp_path_factory):
    build = tmp_path_factory.mktemp("cpu_build")
    cfg = _run([CMAKE, "-S", str(ROOT), "-B", str(build),
                "-DCMAKE_BUILD_TYPE=Release", "-DCQ_ENABLE_VULKAN=OFF"])
    assert cfg.returncode == 0, cfg.stdout[-2000:] + cfg.stderr[-2000:]
    bld = _run([CMAKE, "--build", str(build), "--config", "Release", "--parallel"])
    assert bld.returncode == 0, bld.stdout[-3000:] + bld.stderr[-2000:]
    return build


def test_cpu_only_configures_and_reports_capability(cpu_build):
    cache = (cpu_build / "CMakeCache.txt").read_text(errors="replace")
    assert "CQ_ENABLE_VULKAN:BOOL=OFF" in cache
    assert not (cpu_build / "bin" / "Release" / "cq_hecs.exe").exists()
    assert not (cpu_build / "bin" / "cq_hecs").exists()


def test_cpu_only_ctest_passes(cpu_build):
    res = _run([CTEST, "--test-dir", str(cpu_build), "-C", "Release", "--output-on-failure"])
    assert res.returncode == 0, res.stdout[-3000:]
    assert "No tests were found" not in res.stdout
    # Vulkan-only tests must be absent, not skipped-as-pass.
    assert "test_vulkan_compute_contract" not in res.stdout
    assert "cq_hecs_full_verification" not in res.stdout


def test_no_binary_imports_the_vulkan_loader(cpu_build):
    bins = list(_binaries(cpu_build / "bin"))
    assert bins, "CPU build produced no binaries"
    offenders = [b.name for b in bins
                 if any(m in b.read_bytes().lower() for m in LOADER_MARKERS)]
    assert offenders == [], f"CPU-only build links the Vulkan loader: {offenders}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
