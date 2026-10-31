#!/usr/bin/env python3
"""
Compile one compute shader with glslc and (re)write its SPIR-V array in
``src/vulkan/shaders_vrts_embedded.hpp``.

    python scripts/embed_vrts_shader.py omniwave_bcp

The block is delimited by marker comments, so running the script again replaces
it in place. Other arrays in the header are left untouched.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "src" / "vulkan" / "shaders_vrts_embedded.hpp"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="shader base name under shaders/compute/")
    args = parser.parse_args(argv)
    comp = ROOT / "shaders" / "compute" / f"{args.name}.comp"
    spv = comp.with_suffix(".spv")
    res = subprocess.run(["glslc", "--target-env=vulkan1.3", str(comp), "-o", str(spv)], capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        return 1
    data = spv.read_bytes()
    if len(data) % 4 or int.from_bytes(data[:4], "little") != 0x07230203:
        print("not a SPIR-V binary", file=sys.stderr)
        return 1
    words = [int.from_bytes(data[i:i + 4], "little") for i in range(0, len(data), 4)]
    lines = [", ".join(f"0x{w:08X}u" for w in words[i:i + 8]) + "," for i in range(0, len(words), 8)]
    begin, end = f"// BEGIN spv_{args.name}", f"// END spv_{args.name}"
    block = "\n".join([
        begin,
        f"inline const uint32_t spv_{args.name}[] = {{",
        *lines,
        "};",
        f"inline const size_t spv_{args.name}_size = sizeof(spv_{args.name});",
        end,
    ])
    text = HEADER.read_text("utf-8")
    if begin in text:
        head, rest = text.split(begin, 1)
        _, tail = rest.split(end, 1)
        text = head + block + tail
    else:
        marker = "} // namespace embedded_vrts_shaders"
        if marker not in text:
            print(f"cannot find '{marker}' in {HEADER}", file=sys.stderr)
            return 1
        text = text.replace(marker, block + "\n" + marker, 1)
    HEADER.write_text(text, "utf-8")
    print(f"embedded spv_{args.name}: {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
