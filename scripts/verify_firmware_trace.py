"""Validate the firmware's on-device SHA trace against the Python reference.

The firmware test binary (simulation/test_research_sha.c) can emit one
`hcs.sha.trace.v1` object for a given 64-byte block:

    ./test_research_sha --emit <128 hex chars>

This script feeds a set of blocks through that binary and runs
`cqhecs.sha.round_trace.replay()` on each result. Replay re-derives every value
from the block and the input state and raises on the first deviation, so it also
proves the device JSON has no missing, extra or reordered fields that the format
depends on.

Usage (from the CQ-HECS repository root, or with PYTHONPATH pointing at it):

    python scripts/verify_firmware_trace.py --binary <path to test_research_sha>

Without --binary the script builds the C sources with the first available host
compiler (clang or gcc) and runs from a temporary directory.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
# The firmware lives in a separate repository. Point --firmware-root at it, or
# keep the two checkouts as siblings; no machine-specific path is committed.
DEFAULT_FW_ROOT = REPO.parent / "ESP-Miner"

def _padded(text: bytes) -> str:
    """Exactly one 64-byte block, zero padded, for a short ASCII message."""
    if len(text) > 64:
        raise ValueError(f"fixture is {len(text)} bytes, not a single block")
    return (text + b"\x00" * (64 - len(text))).hex()


# Deterministic blocks: all zero, all 0xFF, a counting pattern, the SHA padding
# of b"abc", an ASCII sentence, and a pseudo-random but fixed pattern.
BLOCKS = [
    "00" * 64,
    "ff" * 64,
    "".join(f"{i:02x}" for i in range(64)),
    _padded(b"abc\x80"),
    _padded(b"the quick brown fox jumps over the lazy dog, 64 bytes exactly!!"),
    "".join(f"{((i * 37 + 11) * 2654435761) & 0xFF:02x}" for i in range(64)),
]


def find_compiler() -> list[str] | None:
    for name in ("clang", "gcc", "cc"):
        exe = shutil.which(name)
        if exe:
            return [exe]
    rocm = pathlib.Path("C:/Program Files/AMD/ROCm/7.1/bin/clang.exe")
    if rocm.exists():
        return [str(rocm)]
    return None


def build(fw_root: pathlib.Path, binary_out: pathlib.Path) -> pathlib.Path:
    fw_main = fw_root / "main" / "research" / "research_sha.c"
    fw_test = fw_root / "simulation" / "test_research_sha.c"
    for path in (fw_main, fw_test):
        if not path.exists():
            raise SystemExit(f"firmware source not found: {path}")
    compiler = find_compiler()
    if compiler is None:
        raise SystemExit("no host compiler found; pass --binary instead")
    cmd = compiler + [
        "-Wall",
        "-Wextra",
        "-Werror",
        "-O2",
        "-std=c11",
        "-D_CRT_SECURE_NO_WARNINGS",
        f"-I{fw_main.parent}",
        "-o",
        str(binary_out),
        str(fw_main),
        str(fw_test),
    ]
    subprocess.run(cmd, check=True)
    return binary_out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=pathlib.Path, default=None)
    parser.add_argument("--firmware-root", type=pathlib.Path, default=DEFAULT_FW_ROOT)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))

    # Imported late so the script fails with a clear message if run outside the repo.
    from cqhecs.sha import round_trace  # noqa: E402

    tmpdir = None
    if args.binary:
        binary = args.binary
    else:
        tmpdir = tempfile.mkdtemp(prefix="sha_forge_fw_")
        binary = build(args.firmware_root, pathlib.Path(tmpdir) / "test_research_sha")

    failures = 0
    for block_hex in BLOCKS:
        try:
            proc = subprocess.run([str(binary), "--emit", block_hex], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"FAIL block {block_hex[:16]}...: emitter exited {exc.returncode}: {exc.stderr.strip()}")
            failures += 1
            continue

        try:
            trace = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            print(f"FAIL block {block_hex[:16]}...: device output is not JSON ({exc})")
            failures += 1
            continue

        try:
            state = round_trace.replay(trace)
        except (round_trace.TraceMismatch, KeyError, ValueError) as exc:
            print(f"FAIL block {block_hex[:16]}...: replay rejected the device trace ({exc})")
            failures += 1
            continue

        if args.verbose:
            print(f"ok   block {block_hex[:16]}... output_state={state}")
        else:
            print(f"ok   block {block_hex[:16]}...")

    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\n{len(BLOCKS) - failures}/{len(BLOCKS)} device traces accepted by the Python reference")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
