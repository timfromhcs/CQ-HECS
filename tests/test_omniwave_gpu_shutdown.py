"""Process-exit contract for the native Vulkan status probe.

On Windows the lazy Vulkan context used to be destroyed during DLL unload, which
terminated the interpreter with 0xC0000409 after the tests had already passed.
``gpu.py`` now registers an ``atexit`` hook that calls the native
``cq_omniwave_shutdown`` while the loader and driver are still mapped. This test
runs the probe in a fresh process so a regression is visible as a non-zero exit.
"""

from __future__ import annotations

import subprocess
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gpu_status_process_exits_cleanly():
    completed = subprocess.run(
        [sys.executable, "-c", "from cqhecs.omniwave import gpu; gpu.status()"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, (
        f"gpu status process exited {completed.returncode}\n"
        f"stdout={completed.stdout}\nstderr={completed.stderr}"
    )
