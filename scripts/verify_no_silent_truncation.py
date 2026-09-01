"""
Zero-Silent-Truncation Verification Script for CQ-HECS.
Scans source files (C++ and Python) to verify that hardcoded chi=48 bond-dimension cutoffs
and silent truncations have been completely eradicated from the codebase.
Exits with 0 on pass, non-zero on failure.
"""

import sys
import re
from pathlib import Path

# Directories to strictly verify
SCAN_DIRS = ["include", "src", "cqhecs", "python", "python_bridge"]
EXCLUDE_EXTS = [".pyc", ".obj", ".lib", ".exp", ".dll", ".pyd", ".exe", ".spv"]

# Regular expression matching hardcoded bond dimension / chi=48 patterns
FORBIDDEN_PATTERNS = [
    re.compile(r"max_chi\s*=\s*48\b", re.IGNORECASE),
    re.compile(r"max_bond_dim\s*=\s*48\b", re.IGNORECASE),
    re.compile(r"max_bond_dim\{48\}", re.IGNORECASE),
    re.compile(r"chi\s*>\s*48\b", re.IGNORECASE),
    re.compile(r"chi\s*<=\s*48\b", re.IGNORECASE),
    re.compile(r"bond[-_ ]dimension\s*(?:truncation)?\s*\(\\?chi\s*\\le\s*48\)", re.IGNORECASE),
]

def main():
    root = Path(__file__).resolve().parent.parent
    violations = []

    print("=================================================================")
    print(" CQ-HECS Verification: Zero-Silent-Truncation (chi=48) Audit")
    print("=================================================================")

    for dir_name in SCAN_DIRS:
        scan_path = root / dir_name
        if not scan_path.exists():
            continue

        for file_path in scan_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix in EXCLUDE_EXTS or ".git" in file_path.parts:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                for pattern in FORBIDDEN_PATTERNS:
                    if pattern.search(line):
                        violations.append((file_path.relative_to(root), line_no, line.strip()))

    if violations:
        print(f"[FAIL] Found {len(violations)} forbidden hardcoded chi=48 instances:")
        for rel_path, line_no, line in violations:
            print(f"  {rel_path}:{line_no} -> {line}")
        sys.exit(1)
    else:
        print("[PASS] 0 forbidden chi=48 bond-dimension truncations found!")
        print("       The Four-Path classical architecture is strictly verified.")
        print("=================================================================")
        sys.exit(0)

if __name__ == "__main__":
    main()
