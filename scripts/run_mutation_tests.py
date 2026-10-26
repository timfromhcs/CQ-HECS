"""
Deterministic **source-level** mutation testing for CQ-HECS.

Why this harness rewrites real source files
-------------------------------------------
An earlier version "simulated" defects inside hand-written helpers (for example
constructing ``{"0"*n: shots}`` locally) and counted that as a killed mutant.
That measures nothing about the production code. This harness instead:

1. applies an exact text patch to a real production source file,
2. runs an independent behavioural check in a *fresh subprocess* (so the mutated
   module is imported, not a cached one),
3. restores the file byte-for-byte in a ``finally`` block,
4. counts the mutant as killed only when the check observes the injected defect.

A clean baseline is a prerequisite: every check must report "not detected" on
unmutated code. Surviving mutants, harness errors, timeouts and missing anchors
all fail the gate with a non-zero exit code.

Mutation score is scoped: 11 source mutants covering the historically observed
defect classes. It is not a proof of correctness and must not be reported as
one.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

EXIT_OK = 0
EXIT_GATE_FAILED = 1
EXIT_NOT_DETECTED = 3
DEFAULT_CHECK_TIMEOUT = 240


# --------------------------------------------------------------------------- checks
# A check returns True when it *observes the injected defect*, False when the
# production code behaves correctly. Checks must exercise shipped code paths.


def check_qubit_bit_order() -> bool:
    """X on qubit 0 of 3 must render as '001' (qubit 0 rightmost)."""
    from cqhecs.backends.path_a_stabilizer import StabilizerTableauSimulator

    sim = StabilizerTableauSimulator(3)
    sim.apply_x(0)
    counts, sampled = sim.sample(shots=50, seed=1)
    if sampled != 50:
        return False  # unrelated sampling failure is not evidence of this defect
    return "100" in counts and "001" not in counts


def check_cz_conjugation() -> bool:
    """H,H,CZ,H on two qubits must produce Bell parity; a CZ-as-CX shortcut breaks it."""
    from cqhecs.backends.path_a_stabilizer import StabilizerTableauSimulator

    sim = StabilizerTableauSimulator(2)
    sim.apply_h(0)
    sim.apply_h(1)
    sim.apply_cz(0, 1)
    sim.apply_h(1)
    counts, _ = sim.sample(shots=400, seed=13)
    return not set(counts).issubset({"00", "11"})


def check_rank_budget_fail_closed() -> bool:
    """A T-count exceeding the rank budget must raise, not return a result."""
    from cqhecs.backends.path_b_stabilizer_rank import StabilizerRankSimulator

    instrs = [("h", [0], []), ("t", [0], []), ("t", [0], []), ("cx", [0, 1], [])]
    try:
        StabilizerRankSimulator(2, max_rank_branches=1).execute_circuit(
            instrs, shots=10, seed=1
        )
    except ValueError:
        return False  # correct: refused fail-closed
    except Exception:
        return False  # unrelated failure is not evidence of this defect
    return True  # silently produced a result -> defect present


def check_mps_state_norm() -> bool:
    """The MPS statevector must be normalized after a Hadamard."""
    import numpy as np

    from cqhecs.backends.path_c_mps_exact import ExactMPSTensorChain

    mps = ExactMPSTensorChain(3)
    h = np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2.0)
    mps.apply_single_qubit_gate(0, h)
    return abs(float(np.linalg.norm(mps.to_statevector())) - 1.0) > 1e-6


def check_wide_sampling_fabrication() -> bool:
    """Beyond MAX_SAMPLING_QUBITS the chain must refuse instead of fabricating counts."""
    from cqhecs.backends.path_c_mps_exact import ExactMPSTensorChain

    width = ExactMPSTensorChain.MAX_SAMPLING_QUBITS + 1
    counts, supported = ExactMPSTensorChain(num_qubits=width).sample(shots=10, seed=1)
    return bool(supported or counts)


def check_sparse_pauli_bound() -> bool:
    """Truncating Pauli terms must leave a strictly positive error bound."""
    from cqhecs.backends.path_d_sparse_pauli import SparsePauliDynamicsSimulator

    sim = SparsePauliDynamicsSimulator(num_qubits=2, max_pauli_terms=1)
    _, bound, _ = sim.evaluate_observable(
        [("rz", [0], [0.8]), ("rz", [1], [0.6]), ("cx", [0, 1], [])],
        {(1, 0): complex(1.0, 0.0)},
    )
    return not (bound > 0.0)


def check_unresolved_suppression() -> bool:
    """An over-budget evaluation must report ``unresolved=True``."""
    from cqhecs.backends.path_d_sparse_pauli import SparsePauliDynamicsSimulator

    sim = SparsePauliDynamicsSimulator(
        num_qubits=2, max_pauli_terms=1, error_tolerance=1e-9
    )
    _, bound, unresolved = sim.evaluate_observable(
        [("rz", [0], [0.8]), ("rz", [1], [0.6]), ("cx", [0, 1], [])],
        {(1, 0): complex(1.0, 0.0)},
    )
    if not (bound > sim.error_tolerance):
        return False  # scenario did not exercise the unresolved branch
    return not unresolved


def check_governor_allocation_failure() -> bool:
    """An oversized page must raise MemoryError, never silently exceed the budget."""
    from python_bridge.cq_hecs import TieredMemoryGovernor

    governor = TieredMemoryGovernor(max_vram_mb=1.0)
    try:
        governor.allocate(1, b"x" * (2 * 1024 * 1024))
    except MemoryError:
        return False  # correct
    return True  # oversize accepted -> defect present


def check_cli_usage_exit_status() -> bool:
    """A successful command must report the documented success exit code."""
    import contextlib
    import io

    from cqhecs.cli import main

    with contextlib.redirect_stdout(io.StringIO()):
        code = main(["--format", "json", "version"])
    return code != 0


def check_cli_json_schema_field() -> bool:
    """JSON mode must include schema_version on the version payload."""
    import contextlib
    import io
    import json

    from cqhecs.cli import main

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["--format", "json", "version"])
    if code != 0:
        return False
    payload = json.loads(out.getvalue())
    return "schema_version" not in payload


def check_t_count_classification() -> bool:
    """A QASM circuit containing T must report t_count >= 1 and is_clifford False."""
    from cqhecs.circuit_analyzer import CircuitAnalyzer

    qasm = (
        'OPENQASM 2.0;\n'
        'include "qelib1.inc";\n'
        "qreg q[1];\n"
        "h q[0];\n"
        "t q[0];\n"
    )
    props = CircuitAnalyzer().analyze(qasm)
    return props.t_count < 1 or props.is_clifford


CHECKS: Dict[str, Callable[[], bool]] = {
    "qubit_bit_order": check_qubit_bit_order,
    "cz_conjugation": check_cz_conjugation,
    "rank_budget_fail_closed": check_rank_budget_fail_closed,
    "mps_state_norm": check_mps_state_norm,
    "wide_sampling_fabrication": check_wide_sampling_fabrication,
    "sparse_pauli_bound": check_sparse_pauli_bound,
    "unresolved_suppression": check_unresolved_suppression,
    "governor_allocation_failure": check_governor_allocation_failure,
    "cli_usage_exit_status": check_cli_usage_exit_status,
    "cli_json_schema_field": check_cli_json_schema_field,
    "t_count_classification": check_t_count_classification,
}


# --------------------------------------------------------------------------- mutants
@dataclass(frozen=True)
class SourceMutant:
    name: str
    target: str          # path relative to REPO_ROOT
    original: str        # exact text, must occur exactly once
    replacement: str
    check: str
    mechanism: str       # what the injected source change actually does


MUTANTS: List[SourceMutant] = [
    SourceMutant(
        name="Qubit bit-order reversal",
        target="cqhecs/backends/path_a_stabilizer.py",
        original='bs = "".join(bits)[::-1]',
        replacement='bs = "".join(bits)',
        check="qubit_bit_order",
        mechanism="drops the Qiskit rightmost-qubit reversal in sampled bitstrings",
    ),
    SourceMutant(
        name="CZ conjugation shortcut",
        target="cqhecs/backends/path_a_stabilizer.py",
        original=(
            "    def apply_cz(self, ctrl: int, tgt: int):\n"
            "        self.apply_h(tgt)\n"
            "        self.apply_cx(ctrl, tgt)\n"
            "        self.apply_h(tgt)\n"
        ),
        replacement=(
            "    def apply_cz(self, ctrl: int, tgt: int):\n"
            "        self.apply_cx(ctrl, tgt)\n"
        ),
        check="cz_conjugation",
        mechanism="implements CZ as bare CX (missing H-conjugation)",
    ),
    SourceMutant(
        name="Stabilizer-rank budget silently ignored",
        target="cqhecs/backends/path_b_stabilizer_rank.py",
        original=(
            "        if num_branches > self.max_rank_branches:\n"
            "            raise ValueError(\n"
        ),
        replacement=(
            "        if False:\n"
            "            raise ValueError(\n"
        ),
        check="rank_budget_fail_closed",
        mechanism="removes the rank-budget refusal, allowing over-budget execution",
    ),
    SourceMutant(
        name="MPS statevector unscaled",
        target="cqhecs/backends/path_c_mps_exact.py",
        original="        return curr.flatten()",
        replacement="        return curr.flatten() * 2.0",
        check="mps_state_norm",
        mechanism="returns a non-normalized statevector from the MPS contraction",
    ),
    SourceMutant(
        name="Fabricated wide-register counts",
        target="cqhecs/backends/path_c_mps_exact.py",
        original=(
            "        if self.num_qubits > self.MAX_SAMPLING_QUBITS:\n"
            "            return {}, False\n"
        ),
        replacement=(
            "        if self.num_qubits > self.MAX_SAMPLING_QUBITS:\n"
            '            return {"0" * self.num_qubits: int(shots)}, True\n'
        ),
        check="wide_sampling_fabrication",
        mechanism="returns an all-zeros count dictionary with supported=True",
    ),
    SourceMutant(
        name="Sparse-Pauli error-bound suppression",
        target="cqhecs/backends/path_d_sparse_pauli.py",
        original="self.accumulated_error_bound += discarded_weight",
        replacement="self.accumulated_error_bound += 0.0",
        check="sparse_pauli_bound",
        mechanism="discards Pauli terms while reporting a zero error contribution",
    ),
    SourceMutant(
        name="Unresolved flag suppression",
        target="cqhecs/backends/path_d_sparse_pauli.py",
        original="unresolved = (self.accumulated_error_bound > self.error_tolerance)",
        replacement="unresolved = False",
        check="unresolved_suppression",
        mechanism="forces resolved status even when the error bound exceeds tolerance",
    ),
    SourceMutant(
        name="Swallowed resource failure",
        target="python_bridge/cq_hecs.py",
        original=(
            "            if self.active_vram_bytes - old_size + size > self.max_vram_bytes:\n"
            "                # Fail closed: an oversized page must not be accepted silently.\n"
            "                raise MemoryError("
        ),
        replacement=(
            "            if False:\n"
            "                # Fail closed: an oversized page must not be accepted silently.\n"
            "                raise MemoryError("
        ),
        check="governor_allocation_failure",
        mechanism="accepts an oversized page instead of raising MemoryError",
    ),
    SourceMutant(
        name="Incorrect CLI exit status",
        target="cqhecs/cli.py",
        original="EXIT_OK = 0",
        replacement="EXIT_OK = 5",
        check="cli_usage_exit_status",
        mechanism="reports a non-zero exit status for a successful command",
    ),
    SourceMutant(
        name="Missing JSON schema field",
        target="cqhecs/cli.py",
        original=(
            '        "schema_version": JSON_SCHEMA_VERSION,\n'
            '        "name": "cq-hecs",\n'
        ),
        replacement='        "name": "cq-hecs",\n',
        check="cli_json_schema_field",
        mechanism="drops schema_version from the version JSON payload",
    ),
    SourceMutant(
        name="Wrong T-count classification",
        target="cqhecs/circuit_analyzer.py",
        original=(
            '    if name in ("t", "tdg"):\n'
            "        return 1\n"
        ),
        replacement=(
            '    if name in ("t", "tdg"):\n'
            "        return 0\n"
        ),
        check="t_count_classification",
        mechanism="drops the T contribution in the shared resource classifier",
    ),
]


# --------------------------------------------------------------------------- runner
class HarnessError(RuntimeError):
    pass


def _check_env() -> dict:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
    # Checks must never create bytecode for mutated source; otherwise a later
    # check can import a cache that belongs to a mutant.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_check_in_subprocess(name: str, timeout: int = DEFAULT_CHECK_TIMEOUT) -> bool:
    """Runs one check in a fresh interpreter; returns True when the defect is seen."""
    command = [sys.executable, str(Path(__file__).resolve()), "--check", name]
    try:
        proc = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=_check_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise HarnessError(f"check {name!r} timed out after {timeout}s") from exc

    if proc.returncode == EXIT_OK:
        return True
    if proc.returncode == EXIT_NOT_DETECTED:
        return False
    raise HarnessError(
        f"check {name!r} failed with exit code {proc.returncode}\n"
        f"stdout: {proc.stdout.strip()}\nstderr: {proc.stderr.strip()}"
    )


def _invalidate_bytecode(path: Path) -> None:
    """Deletes cached bytecode for ``path``.

    CPython validates a ``.pyc`` against the source mtime truncated to whole
    seconds plus the source size. A same-size mutant written and restored
    within one second can therefore leave a cache that is still considered
    valid for the restored source, so a later check would execute mutated
    code. Removing the cache forces compilation from the file on disk.
    """
    cache_dir = path.parent / "__pycache__"
    if not cache_dir.is_dir():
        return
    for cached in cache_dir.glob(f"{path.stem}.*.pyc"):
        try:
            cached.unlink()
        except FileNotFoundError:
            pass


def _atomic_write(path: Path, text: str) -> None:
    """Writes text so an interrupted run cannot leave a half-written file."""
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", delete=False, dir=str(path.parent)
    ) as handle:
        handle.write(text)
        temp_name = handle.name
    os.replace(temp_name, path)


def apply_mutant(mutant: SourceMutant) -> Tuple[Path, str]:
    """Validates the anchor, writes the mutated source and returns (path, original)."""
    path = REPO_ROOT / mutant.target
    if not path.is_file():
        raise HarnessError(f"mutant target missing: {mutant.target}")

    original_text = path.read_text(encoding="utf-8")
    occurrences = original_text.count(mutant.original)
    if occurrences != 1:
        raise HarnessError(
            f"anchor for {mutant.name!r} occurs {occurrences} time(s) in "
            f"{mutant.target} (expected exactly 1). Update the mutation anchor."
        )

    mutated = original_text.replace(mutant.original, mutant.replacement, 1)
    _atomic_write(path, mutated)
    _invalidate_bytecode(path)
    if path.read_text(encoding="utf-8") != mutated:
        raise HarnessError(f"failed to write mutated source for {mutant.name!r}")
    return path, original_text


def restore_source(path: Path, original_text: str) -> None:
    _atomic_write(path, original_text)
    _invalidate_bytecode(path)
    if path.read_text(encoding="utf-8") != original_text:
        raise HarnessError(f"FAILED TO RESTORE {path}; manual repair required")


def baseline_self_check(mutants: List[SourceMutant]) -> List[str]:
    """Every check must report 'not detected' on unmutated source."""
    failures = []
    checks = sorted({mutant.check for mutant in mutants})
    for name in checks:
        if name not in CHECKS:
            failures.append(f"{name}: no such check")
            continue
        try:
            detected = run_check_in_subprocess(name)
        except HarnessError as exc:
            failures.append(f"{name}: harness error: {exc}")
            continue
        if detected:
            failures.append(
                f"{name}: reported a defect on unmutated source (baseline is broken)"
            )
    return failures


def run(mutants: List[SourceMutant], verbose: bool = True) -> int:
    print("=" * 70)
    print(" CQ-HECS Source-Level Mutation Harness")
    print(f" mutants: {len(mutants)} | checks: {len({m.check for m in mutants})}")
    print("=" * 70)

    failures = baseline_self_check(mutants)
    if failures:
        print("\n[FAIL] Baseline is broken; the mutation score would be meaningless:\n")
        for failure in failures:
            print(f"   - {failure}")
        print("=" * 70)
        return EXIT_GATE_FAILED
    print(f"  Baseline OK: {len({m.check for m in mutants})} checks pass on unmutated source.")

    killed = 0
    survivors: List[str] = []
    errors: List[str] = []

    for index, mutant in enumerate(mutants, start=1):
        original_text = None
        path = None
        try:
            path, original_text = apply_mutant(mutant)
            detected = run_check_in_subprocess(mutant.check)
        except HarnessError as exc:
            print(f"  [HARNESS ERROR] Mutant {index}: {mutant.name}: {exc}")
            errors.append(mutant.name)
            detected = False
        except Exception as exc:  # noqa: BLE001 - harness must fail closed
            print(f"  [HARNESS ERROR] Mutant {index}: {mutant.name}: {exc}")
            errors.append(mutant.name)
            detected = False
        finally:
            if path is not None and original_text is not None:
                try:
                    restore_source(path, original_text)
                except HarnessError as exc:
                    print(f"  [RESTORE ERROR] {exc}")
                    errors.append(mutant.name)

        if mutant.name in errors:
            continue
        if detected:
            killed += 1
            if verbose:
                print(f"  [KILLED] Mutant {index}: {mutant.name} ({mutant.mechanism})")
        else:
            survivors.append(mutant.name)
            print(f"  [SURVIVED] Mutant {index}: {mutant.name} ({mutant.mechanism})")

    total = len(mutants)
    print("=" * 70)
    print(f" Mutation score: {killed}/{total} killed ({100.0 * killed / max(total, 1):.1f}%)")
    if survivors:
        print(" Surviving mutants:")
        for name in survivors:
            print(f"   - {name}")
    if errors:
        print(" Harness errors (not counted as kills):")
        for name in errors:
            print(f"   - {name}")
    print(
        " Scope: source patches listed in MUTANTS; not a proof of correctness."
    )

    if survivors or errors:
        print("\n[FAIL] Mutation gate not met.")
        print("=" * 70)
        return EXIT_GATE_FAILED
    print("=" * 70)
    return EXIT_OK


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", help="run a single check (internal subprocess mode)")
    parser.add_argument("--list", action="store_true", help="list mutants and exit")
    args = parser.parse_args(argv)

    if args.check:
        check = CHECKS.get(args.check)
        if check is None:
            print(f"unknown check: {args.check}", file=sys.stderr)
            return EXIT_GATE_FAILED
        try:
            detected = bool(check())
        except Exception:  # noqa: BLE001 - surfaced as a harness error by the parent
            traceback.print_exc()
            return EXIT_GATE_FAILED
        return EXIT_OK if detected else EXIT_NOT_DETECTED

    if args.list:
        for mutant in MUTANTS:
            print(f"{mutant.name}\t{mutant.target}\t{mutant.check}")
        return EXIT_OK

    return run(MUTANTS)


if __name__ == "__main__":
    sys.exit(main())
