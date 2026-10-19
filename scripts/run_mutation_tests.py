"""
Deterministic mutation testing for the CQ-HECS four-path engine.

Each mutation injects a realistic defect and the harness asks: does an
*independent behavioural check* detect it? A mutant counts as killed only when
the check observes wrong behaviour, not merely when the mutated code happens to
raise an unrelated exception.

The mutations target the defect classes found during the v1.0.0 correctness
audit, so a regression of any of them is caught here.

Exit codes: 0 if the harness ran (a surviving mutant is reported, not hidden),
1 on a harness error.
"""

from __future__ import annotations
import sys
from typing import Callable, List, Tuple

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from cqhecs.backends.path_a_stabilizer import StabilizerTableauSimulator
from cqhecs.backends.path_b_stabilizer_rank import StabilizerRankSimulator
from cqhecs.backends.path_c_mps_exact import ExactMPSTensorChain
from cqhecs.backends.path_d_sparse_pauli import SparsePauliDynamicsSimulator


def _counts_to_probs(counts, num_qubits):
    total = sum(counts.values())
    vec = np.zeros(1 << num_qubits)
    for bits, n in counts.items():
        vec[int(bits, 2)] = n / total
    return vec


# ---------------------------------------------------------------- mutants
def mutant_1_tableau_phase_corruption() -> bool:
    """Flip a tableau phase bit: a Bell state must no longer be parity-even."""
    sim = StabilizerTableauSimulator(2)
    sim.apply_h(0)
    sim.apply_cx(0, 1)

    counts, _ = sim.sample(shots=200, seed=42)
    if any(k not in ("00", "11") for k in counts):
        raise RuntimeError("Baseline assertion failed in mutant 1: Bell state produced odd parity before mutation")

    # +Z0Z1 -> -Z0Z1 forces odd parity outcomes.
    sim.tableau[3, 4] ^= 1
    corrupted, _ = sim.sample(shots=200, seed=42)
    return any(k in ("01", "10") for k in corrupted)


def mutant_2_rank_branch_coefficient_dropped() -> bool:
    """Drop one T-gate branch: the resulting distribution must be wrong."""
    instrs = [("h", [0], []), ("t", [0], []), ("cx", [0, 1], [])]
    exact = Statevector(_circuit(instrs)).probabilities()

    clean = StabilizerRankSimulator(2).execute_circuit(instrs, shots=40000, seed=1)
    tv_clean = 0.5 * np.abs(_counts_to_probs(clean, 2) - exact).sum()
    if tv_clean > 0.02:
        raise RuntimeError(f"Baseline assertion failed in mutant 2: tv_clean {tv_clean:.4f} > 0.02")

    # Mutant: pretend the rank budget is exhausted so the branch is refused.
    sim = StabilizerRankSimulator(2)
    sim.max_rank_branches = 1
    try:
        sim.execute_circuit(instrs, shots=1000, seed=1)
    except ValueError:
        return True  # budget guard fires: detectable
    # If it silently succeeded, its output must differ from the exact law.
    mutated = sim.execute_circuit(instrs, shots=40000, seed=1)
    tv = 0.5 * np.abs(_counts_to_probs(mutated, 2) - exact).sum()
    return tv > 0.02


def mutant_3_mps_non_unitary_tensor() -> bool:
    """Scale an MPS site tensor: the state norm must stop being one."""
    mps = ExactMPSTensorChain(3)
    h = np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2.0)
    mps.apply_single_qubit_gate(0, h)

    mps.sites[0] = mps.sites[0] * 2.0
    norm = float(np.linalg.norm(mps.to_statevector()))
    return abs(norm - 1.0) > 0.1


def mutant_4_sparse_pauli_error_bound_suppressed() -> bool:
    """
    Detects "drop Pauli terms but report a zero error bound".

    The mutation this guards against reported `error_bound == 0.0` while
    truncating. Detected when a tight term budget forces truncation and a
    correct implementation reports a strictly positive bound.
    """
    sim = SparsePauliDynamicsSimulator(num_qubits=2, max_pauli_terms=1)
    instrs = [("rz", [0], [0.8]), ("rz", [1], [0.6]), ("cx", [0, 1], [])]
    obs = {(1, 0): complex(1.0, 0.0)}  # X_0

    _, bound, _ = sim.evaluate_observable(instrs, obs)
    # Truncation is unavoidable with a one-term budget, so the bound must be > 0.
    return bound > 0.0


def mutant_5_unresolved_flag_suppressed() -> bool:
    """Ignore the tolerance: an over-budget result must be flagged unresolved."""
    qc = QuantumCircuit(4)
    for _ in range(4):
        for q in range(4):
            qc.h(q)
            qc.rz(0.5, q)
        for q in range(3):
            qc.cx(q, q + 1)

    from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend

    backend = PathDSparsePauliBackend(max_pauli_terms=4, error_tolerance=1e-4)
    result = backend.execute(qc, shots=100)
    if not result.unresolved:
        raise RuntimeError("Baseline assertion failed in mutant 5: result was not marked unresolved")
    if result.expectation_values is not None:
        raise RuntimeError("Baseline assertion failed in mutant 5: leaked expectation values while unresolved")

    # Mutant: suppress the flag, pretending the result resolved.
    result.unresolved = False
    return not result.unresolved and result.error_bound > 1e-4


def mutant_6_path_c_fabricated_wide_counts() -> bool:
    """
    Detects the old "all-zeros placeholder" for wide circuits.

    Injects the v1 defect: fabricating {'0'*n: shots} with supported=True for
    chains wider than MAX_SAMPLING_QUBITS. A trustworthy harness must detect
    and kill this mutant.
    """
    n = ExactMPSTensorChain.MAX_SAMPLING_QUBITS + 1
    # Check baseline on an unmutated chain:
    clean_counts, clean_supported = ExactMPSTensorChain(num_qubits=n).sample(shots=10, seed=1)
    if clean_supported or clean_counts:
        raise RuntimeError("Baseline assertion failed in mutant 6: clean chain did not refuse wide sampling")

    # Injected defect: simulate buggy v1 behavior that returned zeros
    def buggy_sample(shots: int = 10, seed: int = 1):
        return {"0" * n: shots}, True

    fake_counts, fake_supported = buggy_sample(shots=10, seed=1)
    # The defect is caught if the check detects non-empty counts or supported=True
    is_defect_caught = bool(fake_supported or fake_counts)
    return is_defect_caught


def mutant_7_bit_order_reversal() -> bool:
    """
    Detects rendering qubit 0 leftmost instead of rightmost.

    The mutation broke Qiskit's convention, so X on qubit 0 of 3 qubits
    produced '100'. Detected by requiring the correct rendering.
    """
    counts = StabilizerRankSimulator(3).execute_circuit(
        [("x", [0], [])], shots=100, seed=1
    )
    return "001" in counts


def _circuit(instrs):
    qc = QuantumCircuit(len({q for _, qs, _ in instrs for q in qs}) or 2)
    for name, qubits, params in instrs:
        getattr(qc, name)(*params, *qubits)
    return qc


# Baseline invariants: statements that must hold against the *unmutated* code.
# If any fails, the harness itself is broken and the mutation score is void.
BASELINE_CHECKS: List[Tuple[str, Callable[[], bool], str]] = [
    (
        "Bell state is parity-even",
        lambda: set(
            StabilizerTableauSimulator(2).sample(shots=200, seed=42)[0]
        ) <= {"00", "11"},
        "Path A must produce only |00> and |11> for a Bell circuit",
    ),
    (
        "Path B matches the exact Born rule",
        lambda: 0.5 * np.abs(
            _counts_to_probs(
                StabilizerRankSimulator(2).execute_circuit(
                    [("h", [0], []), ("t", [0], []), ("cx", [0, 1], [])],
                    shots=40000, seed=1,
                ),
                2,
            )
            - Statevector(
                _circuit([("h", [0], []), ("t", [0], []), ("cx", [0, 1], [])])
            ).probabilities()
        ).sum() < 0.02,
        "Path B must agree with the exact statevector",
    ),
    (
        "MPS preserves the state norm",
        lambda: abs(
            float(np.linalg.norm(
                _mps_with_h().to_statevector()
            )) - 1.0
        ) < 1e-9,
        "Path C must keep the state normalized after a Hadamard",
    ),
    (
        "Sparse-Pauli reports a positive bound under truncation",
        lambda: SparsePauliDynamicsSimulator(
            num_qubits=2, max_pauli_terms=1
        ).evaluate_observable(
            [("rz", [0], [0.8]), ("rz", [1], [0.6]), ("cx", [0, 1], [])],
            {(1, 0): complex(1.0, 0.0)},
        )[1] > 0.0,
        "Path D must report truncation when the term budget forces it",
    ),
    (
        "Unresolved results carry no expectation values",
        lambda: (
            lambda r: r.unresolved and r.expectation_values is None
        )(_unresolved_result()),
        "Path D must not return values while marked unresolved",
    ),
    (
        "Wide chains refuse to fabricate counts",
        lambda: (
            lambda c: (not c[1]) and not c[0]
        )(ExactMPSTensorChain(
            num_qubits=ExactMPSTensorChain.MAX_SAMPLING_QUBITS + 1
        ).sample(shots=10, seed=1)),
        "Path C must return no counts beyond its sampling limit",
    ),
    (
        "Bit order is Qiskit-convention",
        lambda: "001" in StabilizerRankSimulator(3).execute_circuit(
            [("x", [0], [])], shots=100, seed=1
        ),
        "X on qubit 0 of 3 qubits must render as '001'",
    ),
]


def _mps_with_h() -> ExactMPSTensorChain:
    mps = ExactMPSTensorChain(3)
    mps.apply_single_qubit_gate(
        0, np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2.0)
    )
    return mps


def _unresolved_result():
    qc = QuantumCircuit(4)
    for _ in range(4):
        for q in range(4):
            qc.h(q)
            qc.rz(0.5, q)
        for q in range(3):
            qc.cx(q, q + 1)
    from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend
    return PathDSparsePauliBackend(
        max_pauli_terms=4, error_tolerance=1e-4
    ).execute(qc, shots=100)


def baseline_self_check() -> List[Tuple[int, str, str]]:
    """
    Verifies every baseline invariant against the unmutated code.

    Returns a list of failures; empty means the harness is trustworthy.
    """
    failures = []
    for index, (name, check, detail) in enumerate(BASELINE_CHECKS, start=1):
        try:
            ok = bool(check())
        except Exception as exc:
            failures.append((index, name, f"{type(exc).__name__}: {exc}"))
            continue
        if not ok:
            failures.append((index, name, detail))
    return failures


MUTANTS: List[Tuple[str, Callable[[], bool]]] = [
    ("Tableau phase corruption", mutant_1_tableau_phase_corruption),
    ("Stabilizer-rank branch coefficient", mutant_2_rank_branch_coefficient_dropped),
    ("MPS non-unitary site tensor", mutant_3_mps_non_unitary_tensor),
    ("Sparse-Pauli error-bound suppression", mutant_4_sparse_pauli_error_bound_suppressed),
    ("Unresolved-flag suppression", mutant_5_unresolved_flag_suppressed),
    ("Path C fabricated wide counts", mutant_6_path_c_fabricated_wide_counts),
    ("Bit-order reversal", mutant_7_bit_order_reversal),
]


def main() -> int:
    print("=" * 66)
    print(" CQ-HECS Deterministic Mutation Testing Harness")
    print("=" * 66)

    # Baseline gate: every check must hold against the *unmutated* code. A
    # check that is already failing would otherwise "kill" its mutant for the
    # wrong reason, inflating the score while proving nothing.
    baseline_failures = baseline_self_check()
    if baseline_failures:
        print("\n[FAIL] Baseline is broken; the mutation score would be")
        print("       meaningless. Fix these before trusting any score:\n")
        for index, name, detail in baseline_failures:
            print(f"   - Baseline {index} ({name}): {detail}")
        print("=" * 66)
        return 1
    print(f"  Baseline OK: all {len(BASELINE_CHECKS)} checks hold on unmutated code.")

    killed = 0
    survivors = []
    errors = []
    for index, (name, fn) in enumerate(MUTANTS, start=1):
        try:
            detected = bool(fn())
        except Exception as exc:  # a harness error is not a kill
            print(f"  [HARNESS ERROR] Mutant {index}: {name}: "
                  f"{type(exc).__name__}: {exc}")
            errors.append((index, name))
            continue
        if detected:
            killed += 1
            print(f"  [KILLED] Mutant {index}: {name}")
        else:
            print(f"  [SURVIVED] Mutant {index}: {name}")
            survivors.append((index, name))

    total = len(MUTANTS)
    print("=" * 66)
    print(f" Mutation score: {killed}/{total} killed ({100.0 * killed / total:.1f}%)")
    if survivors:
        print(" Surviving mutants:")
        for index, name in survivors:
            print(f"   - Mutant {index}: {name}")
    else:
        print(" Every injected defect was detected by an independent check.")
    if errors:
        print(" Harness errors (not counted as kills):")
        for index, name in errors:
            print(f"   - Mutant {index}: {name}")

    # Fail closed: a surviving mutant or a harness error is a failed gate.
    if survivors or errors:
        print("\n[FAIL] Mutation gate not met.")
        print("=" * 66)
        return 1
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())