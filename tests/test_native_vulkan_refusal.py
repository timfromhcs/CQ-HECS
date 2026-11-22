"""P-03: native cq_hecs CLI must refuse, not pretend, when no Vulkan ICD exists.

Reproducer: point the Vulkan loader at a nonexistent ICD manifest
(``VK_DRIVER_FILES`` / ``VK_ICD_FILENAMES``). The VRTS commands used to print an
empty ``Device:`` line, report ``Ground State: VERIFIED`` and exit 0. They must
now exit with code 3 and a typed ``vulkan_unavailable`` refusal. The CPU
reference path is available only through the explicit ``--cpu-reference`` flag
and is labelled in the output.

A missing native build skips unless ``CQ_HECS_REQUIRE_NATIVE=1`` (CI).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests import native_artifacts

EXIT_VULKAN_UNAVAILABLE = 3


@pytest.fixture(scope="module")
def exe() -> Path:
    path = native_artifacts.find_executable()
    if path is None:
        msg = "cq_hecs executable not found (Vulkan build; set CQ_HECS_BUILD_DIR)"
        if os.environ.get("CQ_HECS_REQUIRE_NATIVE") == "1":
            raise AssertionError(msg + " (CQ_HECS_REQUIRE_NATIVE=1)")
        pytest.skip(msg)
    return path


@pytest.fixture()
def no_icd_env(tmp_path) -> dict:
    env = dict(os.environ)
    missing = str(tmp_path / "definitely_missing_icd.json")
    env["VK_DRIVER_FILES"] = missing
    env["VK_ICD_FILENAMES"] = missing
    # The device override must not mask the failure being tested.
    env.pop("CQ_HECS_VULKAN_DEVICE", None)
    return env


def _run(exe: Path, args: list[str], env: dict):
    return subprocess.run([str(exe), *args], capture_output=True, text=True,
                          env=env, timeout=120)


@pytest.mark.parametrize("cmd", [["vrts"], ["ghz", "--shots", "100"], ["echo", "--gates", "10"],
                                 ["maxcut"]])
def test_no_icd_is_typed_refusal_not_success(exe, no_icd_env, cmd):
    res = _run(exe, cmd, no_icd_env)
    out = res.stdout + res.stderr
    assert res.returncode == EXIT_VULKAN_UNAVAILABLE, out
    assert "VERIFIED" not in res.stdout, "must never report VERIFIED without a device"
    assert "vulkan_unavailable" in res.stderr
    assert "--cpu-reference" in res.stderr  # the refusal names the explicit escape hatch


def test_no_icd_json_refusal_is_machine_readable(exe, no_icd_env):
    res = _run(exe, ["vrts", "--json"], no_icd_env)
    assert res.returncode == EXIT_VULKAN_UNAVAILABLE, res.stdout + res.stderr
    payload = json.loads(res.stdout.strip().splitlines()[-1])
    assert payload["status"] == "refused"
    assert payload["code"] == "vulkan_unavailable"
    assert payload["exit_code"] == EXIT_VULKAN_UNAVAILABLE
    assert payload["cpu_reference_available"] is True


def test_cpu_reference_is_explicit_and_labelled(exe, no_icd_env):
    res = _run(exe, ["vrts", "--cpu-reference"], no_icd_env)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "CPU reference" in res.stdout
    assert "NONE" in res.stdout  # device line says there is no device
    assert "no Vulkan device used" in res.stdout
    assert "WARNING" in res.stderr and "NOT GPU-verified" in res.stderr


def test_cpu_reference_json_backend_label(exe, no_icd_env):
    res = _run(exe, ["vrts", "--json", "--cpu-reference"], no_icd_env)
    assert res.returncode == 0, res.stdout + res.stderr
    assert json.loads(res.stdout.strip().splitlines()[-1])["backend"] == "cpu_reference"
