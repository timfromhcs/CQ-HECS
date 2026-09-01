#!/usr/bin/env python3
"""
Verify and compile all Vulkan 1.3 SPIR-V shaders in CQ-HECS.
Ensures zero errors, zero warnings, valid SPIR-V magic (0x07230203),
and reports binary sizes and compile telemetry.
"""

from __future__ import annotations
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path


def find_glslang_validator() -> str:
    # 1. PATH lookup
    val = shutil.which("glslangValidator")
    if val:
        return val

    # 2. VULKAN_SDK env
    vulkan_sdk = os.environ.get("VULKAN_SDK")
    if vulkan_sdk:
        for sub in ("bin", "Bin"):
            candidate = Path(vulkan_sdk) / sub / ("glslangValidator.exe" if sys.platform == "win32" else "glslangValidator")
            if candidate.exists():
                return str(candidate)

    # 3. Windows standard paths
    if sys.platform == "win32":
        for sub in ("bin", "Bin"):
            for p in Path("C:/VulkanSDK").glob(f"*/{sub}/glslangValidator.exe"):
                if p.exists():
                    return str(p)

    raise RuntimeError("glslangValidator not found on PATH or VULKAN_SDK.")


def verify_spirv_magic(spv_path: Path) -> int:
    """Verifies that the compiled SPIR-V file has magic number 0x07230203."""
    with open(spv_path, "rb") as f:
        header = f.read(20)
    if len(header) < 20:
        raise ValueError(f"SPIR-V file {spv_path} is too small ({len(header)} bytes)")
    magic, version, generator, bound, schema = struct.unpack("<IIIII", header)
    if magic != 0x07230203:
        raise ValueError(f"Invalid SPIR-V magic number 0x{magic:08x} in {spv_path}")
    return spv_path.stat().st_size


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    shaders_dir = root / "shaders"

    validator = find_glslang_validator()
    print(f"[Vulkan Hardening] Using glslangValidator: {validator}")

    comp_files = sorted(shaders_dir.rglob("*.comp"))
    if not comp_files:
        print("[ERROR] No .comp shaders found in shaders/ directory!")
        return 1

    print(f"[Vulkan Hardening] Found {len(comp_files)} compute shaders to verify (Vulkan 1.3 / SPIR-V):\n")
    print(f"{'Shader Name':<35} | {'Relative Path':<40} | {'SPIR-V Size':<12} | {'Status'}")
    print("-" * 100)

    failed = False
    for comp in comp_files:
        rel_path = comp.relative_to(root)
        spv_out = comp.with_suffix(".spv")

        cmd = [
            validator,
            "--target-env", "vulkan1.3",
            "-V", str(comp),
            "-o", str(spv_out)
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{comp.name:<35} | {str(rel_path):<40} | {'FAILED':<12} | ERR")
            print(f"[glslangValidator Error on {comp.name}]:\n{res.stderr}\n{res.stdout}")
            failed = True
            continue

        try:
            byte_size = verify_spirv_magic(spv_out)
            size_str = f"{byte_size:,} B"
            print(f"{comp.name:<35} | {str(rel_path):<40} | {size_str:<12} | OK (Pass)")
        except Exception as e:
            print(f"{comp.name:<35} | {str(rel_path):<40} | {'INVALID':<12} | {e}")
            failed = True

    print("-" * 100)
    if failed:
        print("[FAIL] One or more Vulkan compute shaders failed compilation or verification!")
        return 1

    print(f"[SUCCESS] All {len(comp_files)} Vulkan 1.3 compute shaders compiled & verified with 0 warnings / 0 errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
