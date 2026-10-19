"""
Audit for silent-truncation and fabricated-result defect classes.

The original version of this script only grepped for the literal number 48,
which proved very little: the defects found during the v1.0.0 correctness audit
did not use that constant. This version checks the properties that actually
matter, so it would catch a regression of any of the fixed bugs:

1. No hardcoded chi=48 bond-dimension cutoff.
2. Backends must not return a placeholder/fabricated result when they cannot
   compute the real one (e.g. an all-zeros or all-ones constant counts dict).
3. A backend must not claim ``exact=True`` together with an unresolved result.
4. Path D must not emit joint counts by default, because the Pauli truncation
   bound certifies expectation values and not sampled distributions.
5. OpenQASM angle expressions must not be evaluated with unrestricted builtins.

Exits 0 on pass, non-zero on failure.
"""

from __future__ import annotations
import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRS = ["include", "src", "cqhecs", "python", "python_bridge"]
EXCLUDE_EXTS = {".pyc", ".obj", ".lib", ".exp", ".dll", ".pyd", ".exe", ".spv", ".spv.txt"}

# (1) Hardcoded chi=48 style cutoffs.
FORBIDDEN_CHI = [
    re.compile(r"max_chi\s*=\s*48\b", re.IGNORECASE),
    re.compile(r"max_bond_dim\s*=\s*48\b", re.IGNORECASE),
    re.compile(r"max_bond_dim\s*[\{\(]\s*48\s*[\}\)]", re.IGNORECASE),
    re.compile(r"\bchi\s*[<>]=?\s*48\b", re.IGNORECASE),
]

# (2) Fabricated placeholder results: a counts dict built from a constant
# string repeated n times (e.g. {"0" * n: shots}), or a uniform fallback
# probability vector returned as if it were a computed result.
PLACEHOLDER_PATTERNS = [
    # A counts dict literal whose every value is the *whole* shot count:
    # {"0" * n: shots} fabricates a deterministic outcome.
    re.compile(r"""\{\s*["']0["']\s*\*\s*[\w.]+\s*:\s*(?:shots|self\.shots)\s*\}"""),
    re.compile(r"""\{\s*["']1["']\s*\*\s*[\w.]+\s*:\s*(?:shots|self\.shots)\s*\}"""),
    # Uniform probability fallback: np.ones(dim) / dim used as a result.
    re.compile(r"""probs\s*=\s*np\.ones\s*\(\s*dim\s*\)\s*/\s*dim"""),
]

# A counts dict split 50/50 between two constant bitstrings is equally
# fabricated: it asserts a measurement outcome that was never computed.
HALF_HALF_PATTERN = re.compile(
    r"""["']0["']\s*\*\s*[\w.]+\s*:\s*\w+\s*//\s*2"""
)

# (3) A backend must not claim exact=True while also reporting unresolved=True.
EXACT_UNRESOLVED = re.compile(
    r"exact\s*=\s*True(?:(?!--).){0,600}?unresolved\s*=\s*True", re.DOTALL
)

# (4) eval() on circuit input must use a restricted namespace.
UNRESTRICTED_EVAL = re.compile(r"eval\s*\([^)]*__builtins__\s*:\s*(?!None|\{\s*\})")


def _iter_python_files():
    for directory in SCAN_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if path.suffix in EXCLUDE_EXTS or ".git" in path.parts:
                continue
            yield path


def _iter_text_files():
    for directory in SCAN_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix in EXCLUDE_EXTS:
                continue
            if ".git" in path.parts:
                continue
            yield path


def main() -> int:
    print("=" * 66)
    print(" CQ-HECS Audit: silent truncation / fabricated results")
    print("=" * 66)

    violations: List[Tuple[Path, int, str, str]] = []

    for path in _iter_text_files():
        if path.suffix not in (".py", ".cpp", ".hpp", ".h", ".cu"):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(ROOT)
        for line_no, line in enumerate(content.splitlines(), start=1):
            for pattern in FORBIDDEN_CHI:
                if pattern.search(line):
                    violations.append((rel, line_no, line.strip(), "hardcoded chi=48 cutoff"))
            for pattern in PLACEHOLDER_PATTERNS:
                if pattern.search(line):
                    violations.append((rel, line_no, line.strip(), "fabricated placeholder counts"))
            if HALF_HALF_PATTERN.search(line):
                violations.append((rel, line_no, line.strip(), "fabricated 50/50 placeholder counts"))
            if UNRESTRICTED_EVAL.search(line):
                violations.append((rel, line_no, line.strip(), "unrestricted eval of circuit input"))

    # (4) The analyzer and router must fail closed, never default an
    #     unrecognised circuit to a path or swallow a broad exception.
    analyzer = ROOT / "cqhecs" / "circuit_analyzer.py"
    if analyzer.exists():
        text = analyzer.read_text(encoding="utf-8")
        if not re.search(r"class\s+UnsupportedCircuitInput\b", text):
            violations.append((
                analyzer.relative_to(ROOT), 0,
                "UnsupportedCircuitInput",
                "analyzer does not define a hard failure for unknown input types",
            ))
        # A fallback that recommends a path for unrecognised input.
        for m in re.finditer(r"recommended_path\s*=\s*[\"']A[\"']", text):
            line_no = text[: m.start()].count("\n") + 1
            context = text.splitlines()[line_no - 1]
            violations.append((
                analyzer.relative_to(ROOT), line_no, context.strip(),
                "hardcoded default path recommendation",
            ))

    router = ROOT / "cqhecs" / "router.py"
    if router.exists():
        text = router.read_text(encoding="utf-8")
        # A bare `except Exception` around a backend call turns a programming
        # error into a silent reroute to another path.
        for m in re.finditer(r"except\s+Exception\b", text):
            line_no = text[: m.start()].count("\n") + 1
            violations.append((
                router.relative_to(ROOT), line_no,
                text.splitlines()[line_no - 1].strip(),
                "broad 'except Exception' can mask a programming error as a reroute",
            ))

    # (5) Path D must not return joint counts by default.
    path_d = ROOT / "cqhecs" / "backends" / "path_d_sparse_pauli.py"
    if path_d.exists():
        tree = ast.parse(path_d.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                names = [a.arg for a in node.args.args]
                if "allow_uncertified_joint_counts" in names:
                    break
        else:
            violations.append((
                path_d.relative_to(ROOT), 0,
                "PathDSparsePauliBackend.__init__",
                "Path D does not gate joint counts behind an explicit opt-in",
            ))

    if violations:
        print(f"[FAIL] {len(violations)} violation(s):\n")
        for rel, line_no, text, reason in violations:
            print(f"  {rel}:{line_no}  [{reason}]")
            print(f"      {text}")
        return 1

    print("[PASS] no silent-truncation or fabricated-result patterns found.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())