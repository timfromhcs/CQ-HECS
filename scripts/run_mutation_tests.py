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

Mutation score is scoped: the source mutants listed in ``MUTANTS`` cover the
historically observed defect classes. It is not a proof of correctness and must not be reported as
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


def check_toffoli_lowering() -> bool:
    """The lowered CCX must equal Qiskit's CCX unitary, phases included.

    A truth-table check is not enough: a T/T-dagger swap on a control qubit
    only changes relative phases, which basis-state inputs never observe.
    """
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import CCXGate
    from qiskit.quantum_info import Operator

    from cqhecs.circuit_parsing import parse_circuit

    lowered, _ = parse_circuit([("ccx", [0, 1, 2], [])])
    qc = QuantumCircuit(3)
    for name, qubits, params in lowered:
        getattr(qc, name)(*params, *qubits)
    reference = QuantumCircuit(3)
    reference.append(CCXGate(), [0, 1, 2])
    return not np.allclose(Operator(qc).data, Operator(reference).data, atol=1e-12)


def check_stabilizer_expectation_sign() -> bool:
    """Bell <YY> is -1 and the stabilizer engine must report the sign."""
    from cqhecs.expectation import expectation_values

    res = expectation_values(
        [("h", [0], []), ("cx", [0, 1], [])], ["YY", "XX"], method="stabilizer"
    )
    return not (res.values["YY"] == -1.0 and res.values["XX"] == 1.0)


def check_dense_y_orientation() -> bool:
    """H then S prepares |+i>, so <Y> must be +1 in the dense engine."""
    from cqhecs.expectation import expectation_values

    res = expectation_values(
        [("h", [0], []), ("s", [0], [])], ["Y0"], method="dense"
    )
    return abs(res.values["Y0"] - 1.0) > 1e-9



def check_hardware_authorization() -> bool:
    """Real hardware execution without authorized=True must fail closed."""
    from cqhecs.hardware_bridge import RealHardwareProvider, HardwareAuthorizationRequiredError
    provider = RealHardwareProvider()
    backend = provider.get_backend("ibm_brisbane")
    try:
        backend.run([("h", [0], [])], authorized=False, api_token="valid_token")
        return True  # defect observed: did not fail closed on unauthorized run
    except HardwareAuthorizationRequiredError:
        return False
    except Exception:
        return True


def check_profile_self_loop() -> bool:
    """BackendProfile must reject self-loops in coupling map."""
    from cqhecs.hardware_bridge import BackendProfile, InvalidProfileError
    try:
        BackendProfile(name="test", num_qubits=2, coupling_map=[(0, 0)])
        return True  # defect observed: self-loop was accepted
    except InvalidProfileError:
        return False

def check_noisy_dm_bit_order() -> bool:
    """Noisy density-matrix output must render qubit 0 rightmost."""
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
    res = NoisyDensityMatrixBackend().simulate([("x", [0], []), ("id", [1], [])])
    return res.probabilities != {"01": 1.0}


def check_noisy_dm_measured_marginal() -> bool:
    """Only the measured qubit may be reported, with its own value."""
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
    res = NoisyDensityMatrixBackend().simulate(
        [("x", [2], []), ("id", [0], []), ("measure", [2], [])]
    )
    return res.probabilities != {"1": 1.0}


def check_noise_on_source_gate() -> bool:
    """A channel calibrated on sx must fire after every sx as written."""
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
    from cqhecs.hardware_bridge import AmplitudeDampingChannel, NoiseModel
    noise = NoiseModel()
    # gamma = 1 resets to |0> after each sx, so sx.sx (= X) must read "0".
    noise.add_1q_channel("sx", 0, AmplitudeDampingChannel(1.0))
    res = NoisyDensityMatrixBackend().simulate(
        [("sx", [0], []), ("sx", [0], [])], noise_model=noise
    )
    return abs(res.probabilities.get("0", 0.0) - 1.0) > 1e-12


def check_profile_provenance_required() -> bool:
    """A profile claiming real calibration must carry its provenance."""
    from cqhecs.hardware_bridge import BackendProfile, InvalidProfileError
    try:
        BackendProfile(name="claims_real", num_qubits=2, is_synthetic=False)
        return True  # defect observed: unprovenanced "real" profile accepted
    except InvalidProfileError:
        return False


def check_path_b_t_sign() -> bool:
    """H T S H |0> has P(0) = (1 + cos(3 pi / 4)) / 2 on Path B."""
    import math
    from cqhecs.router import FourPathRouter

    shots = 4000
    res = FourPathRouter().route_and_execute(
        [("h", [0], []), ("t", [0], []), ("s", [0], []), ("h", [0], [])],
        shots=shots, seed=1, preferred_path="B",
    )
    expected = (1.0 + math.cos(3.0 * math.pi / 4.0)) / 2.0
    return abs(res.counts.get("0", 0) / shots - expected) > 0.1


def check_gate_error_is_infidelity() -> bool:
    """The channel built from a gate error must have that average infidelity."""
    import numpy as np
    from cqhecs.hardware_bridge import BackendProfile

    profile = BackendProfile(name="t", num_qubits=1, gate_errors={"x": {(0,): 0.02}})
    kraus = profile.to_noise_model().channels_1q["x"][0][0].kraus_operators
    # F_avg = (sum_k |Tr K_k|^2 + d) / (d (d + 1)) (Horodecki et al. 1999),
    # computed here without the conversion code under test.
    d = 2
    f_avg = (sum(abs(np.trace(k)) ** 2 for k in kraus) + d) / (d * (d + 1))
    return abs((1.0 - f_avg) - 0.02) > 1e-9


def check_profile_t2_bound() -> bool:
    """T2 > 2 T1 is physically impossible and must be refused."""
    from cqhecs.hardware_bridge import BackendProfile, InvalidProfileError
    try:
        BackendProfile(name="t", num_qubits=1, t1_us={0: 10.0}, t2_us={0: 50.0})
        return True
    except InvalidProfileError:
        return False


def check_profile_gate_key_width() -> bool:
    """A 3-qubit gate-error key would be dropped by the noise model; refuse it.

    The gate name is not in the manifest, so the arity check cannot catch it
    and the width check is the only guard.
    """
    from cqhecs.hardware_bridge import BackendProfile, InvalidProfileError
    try:
        BackendProfile(name="t", num_qubits=3, gate_errors={"vendor_ms": {(0, 1, 2): 0.1}})
        return True
    except InvalidProfileError:
        return False


def check_relaxation_after_depolarizing() -> bool:
    """Device-model order: depolarizing first, then T1/T2 relaxation (Aer)."""
    import numpy as np
    from qiskit.quantum_info import Kraus, SuperOp
    from qiskit_aer.noise import depolarizing_error, thermal_relaxation_error
    from cqhecs.hardware_bridge import BackendProfile

    profile = BackendProfile(
        name="t", num_qubits=1, t1_us={0: 30.0}, t2_us={0: 20.0},
        gate_errors={"x": {(0,): 0.1}}, gate_durations_ns={"x": {(0,): 200.0}},
    )
    # p > 0 here (relaxation alone stays below the error); with p = 0 the
    # order would not matter and the check could not see the mutant.
    from qiskit.quantum_info import average_gate_fidelity
    from cqhecs.hardware_bridge import depolarizing_parameter_with_relaxation

    channel = profile.to_noise_model(relaxation=True).channels_1q["x"][0][0]
    relax = thermal_relaxation_error(30e3, 20e3, 200.0)
    p, _ = depolarizing_parameter_with_relaxation(0.1, 1, float(average_gate_fidelity(relax)))
    expected = SuperOp(depolarizing_error(p, 1)).compose(SuperOp(relax))
    return float(np.max(np.abs(SuperOp(Kraus(channel.kraus_operators)).data - expected.data))) > 1e-12


def check_import_flags_inconsistent_t2() -> bool:
    """ibm_oslo qubit 6 reports T2 > 2 T1; it must be flagged, not clipped."""
    from pathlib import Path
    from cqhecs.calibration_import import load_ibm_snapshot_files

    data = Path(__file__).resolve().parent.parent / "tests" / "data" / "ibm_calibration"
    profile = load_ibm_snapshot_files(data / "props_oslo.json", data / "conf_oslo.json", provenance_uri="t")
    return 6 in profile.t2_us or 6 not in profile.calibration_flags.get("relaxation_excluded", {})


def check_import_flags_non_operational() -> bool:
    """ibm_algiers reports cx(15, 18) with gate_error 1; circuits on it are refused."""
    from pathlib import Path
    from cqhecs.calibration_import import load_ibm_snapshot_files
    from cqhecs.hardware_bridge import FakeHardwareBackend, OutOfModelError

    data = Path(__file__).resolve().parent.parent / "tests" / "data" / "ibm_calibration"
    profile = load_ibm_snapshot_files(data / "props_algiers.json", data / "conf_algiers.json", provenance_uri="t")
    try:
        FakeHardwareBackend(profile).run([("cx", [15, 18], []), ("measure", [15], [])], shots=4, seed=1)
    except OutOfModelError:
        return False
    return True


def check_noisy_readout_phase() -> bool:
    """<Y> after sx|0> is -1; with readout (p01, p10) = (0.1, 0.3) it reads 0.2 - 0.6 * 1."""
    from cqhecs.hardware_bridge import NoiseModel
    from cqhecs.noisy_expectation import noisy_expectation_values

    model = NoiseModel()
    model.set_readout_error(0, 0.1, 0.3)
    res = noisy_expectation_values([("sx", [0], [])], ["Y[0]"], model, method="pauli_propagation")
    return abs(res.values["Y[0]"] - (-0.4)) > 1e-12


def check_noisy_channels_applied() -> bool:
    """x then depolarizing p = 0.5 gives <Z> = -(1 - p)."""
    from cqhecs.hardware_bridge import DepolarizingChannel, NoiseModel
    from cqhecs.noisy_expectation import noisy_expectation_values

    model = NoiseModel()
    model.add_1q_channel("x", 0, DepolarizingChannel(0.5))
    res = noisy_expectation_values([("x", [0], [])], ["Z[0]"], model, method="pauli_propagation")
    return abs(res.values["Z[0]"] - (-0.5)) > 1e-12


def check_noisy_two_qubit_operand_order() -> bool:
    """|11> with damping 0.5 on cx's first operand: <Z0> = 0, <Z1> = -1."""
    from cqhecs.hardware_bridge import AmplitudeDampingChannel, DepolarizingChannel, NoiseModel, TensorChannel
    from cqhecs.noisy_expectation import noisy_expectation_values

    model = NoiseModel()
    model.add_2q_channel("cx", (0, 1), TensorChannel(AmplitudeDampingChannel(0.5), DepolarizingChannel(0.0)))
    res = noisy_expectation_values([("x", [0], []), ("cx", [0, 1], [])], ["Z[0]", "Z[1]"], model,
                                   method="pauli_propagation")
    return abs(res.values["Z[0]"]) > 1e-12 or abs(res.values["Z[1]"] + 1.0) > 1e-12


def check_noisy_truncation_bound() -> bool:
    """Dropping the sin(0.3) Y term must be reported in the bound."""
    import math
    from cqhecs.hardware_bridge import NoiseModel
    from cqhecs.noisy_expectation import noisy_expectation_values

    res = noisy_expectation_values([("h", [0], []), ("rz", [0], [0.3]), ("h", [0], [])], ["Z[0]"],
                                   NoiseModel(), method="pauli_propagation", prune_threshold=0.5,
                                   error_tolerance=1.0)
    return res.error_bound < math.sin(0.3) - 1e-12


def check_reference_hash_bypass() -> bool:
    """A corrupted pinned file must be rejected by verify_dataset."""
    import shutil
    import tempfile
    from pathlib import Path

    from cqhecs.reference import IntegrityError, dataset, verify_dataset

    root = REPO_ROOT / "tests" / "data" / "quantum_noise_transfer"
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary)
        for entry in dataset("r-io-5").files:
            shutil.copy(root / Path(entry.path).name, target / Path(entry.path).name)
        victim = target / "noisy_A.json"
        payload = bytearray(victim.read_bytes())
        payload[10] ^= 0x01
        victim.write_bytes(payload)
        try:
            verify_dataset(dataset("r-io-5"), target)
        except IntegrityError:
            return False
        return True


def check_reference_verdict_suppression() -> bool:
    """The preregistered pooled H-V3-1 verdict is INCONCLUSIVE on the fixture."""
    from cqhecs.reference import evaluate

    result = evaluate(
        REPO_ROOT / "tests" / "data" / "quantum_noise_transfer",
        backends=("A",),
        bootstrap_samples=100,
        seed=7,
    )
    return result.aggregate["verdict"] != "INCONCLUSIVE"


def check_selftest_inverse_property() -> bool:
    """A broken inverse relation must make the installation self-test fail."""
    from cqhecs.selftest import run_selftest

    report = run_selftest(cases=2, seed=3)
    return not report.passed


def check_selftest_composition_property() -> bool:
    """A reversed ComposedChannel order must make the self-test fail."""
    from cqhecs.selftest import run_selftest

    report = run_selftest(cases=2, seed=5)
    return not report.passed


def check_sat_timeout_unknown() -> bool:
    """A timeout must stay UNKNOWN; a mutant that returns UNSAT is caught."""
    from python_bridge.sat_engine import TIMEOUT_UNKNOWN, CNFFormula, CQSATSolver

    formula = CNFFormula(num_vars=2, num_clauses=2, clauses=[[1, 2], [-1, 2]])
    return CQSATSolver().solve(formula, timeout_seconds=-1.0).status != TIMEOUT_UNKNOWN


def check_sat_exact_memo() -> bool:
    """32 forced variables plus a satisfiable rest must stay SAT."""
    from python_bridge.sat_engine import CNFFormula, CQSATSolver

    # Found by a seeded search: the first branch is refuted with branching,
    # the sibling is satisfiable, and both share the 32 forced variables.
    clauses = [[v] for v in range(1, 33)]
    clauses += [
        [35, -34, 36], [33, -36, -35], [-35, 34, -36], [34, -33, -35], [36, -34, 33],
        [-33, 36, -35], [33, 34, 36], [-35, 36, -33], [35, -36, -33], [-34, -36, -35],
        [-33, -34, -35], [-33, -35, -34], [35, -33, -36], [-33, -36, -35], [33, 34, -36],
        [36, -35, 34],
    ]
    formula = CNFFormula(num_vars=36, num_clauses=len(clauses), clauses=clauses)
    return CQSATSolver().solve(formula).satisfiable is not True


def check_dimacs_empty_clause() -> bool:
    """An empty clause ``0`` must make the formula UNSAT."""
    from python_bridge.sat_engine import CQSATSolver, DIMACSParser

    formula = DIMACSParser.parse_string("p cnf 1 2\n0\n1 0\n")
    return CQSATSolver().solve(formula).satisfiable is not False


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
    "toffoli_lowering": check_toffoli_lowering,
    "stabilizer_expectation_sign": check_stabilizer_expectation_sign,
    "dense_y_orientation": check_dense_y_orientation,
    "hardware_authorization": check_hardware_authorization,
    "profile_self_loop": check_profile_self_loop,
    "noisy_dm_bit_order": check_noisy_dm_bit_order,
    "noisy_dm_measured_marginal": check_noisy_dm_measured_marginal,
    "noise_on_source_gate": check_noise_on_source_gate,
    "profile_provenance_required": check_profile_provenance_required,
    "path_b_t_sign": check_path_b_t_sign,
    "gate_error_is_infidelity": check_gate_error_is_infidelity,
    "profile_t2_bound": check_profile_t2_bound,
    "profile_gate_key_width": check_profile_gate_key_width,
    "relaxation_after_depolarizing": check_relaxation_after_depolarizing,
    "import_flags_inconsistent_t2": check_import_flags_inconsistent_t2,
    "import_flags_non_operational": check_import_flags_non_operational,
    "noisy_readout_phase": check_noisy_readout_phase,
    "noisy_channels_applied": check_noisy_channels_applied,
    "noisy_two_qubit_operand_order": check_noisy_two_qubit_operand_order,
    "noisy_truncation_bound": check_noisy_truncation_bound,
    "reference_hash_bypass": check_reference_hash_bypass,
    "reference_verdict_suppression": check_reference_verdict_suppression,
    "selftest_inverse_property": check_selftest_inverse_property,
    "selftest_composition_property": check_selftest_composition_property,
    "sat_timeout_unknown": check_sat_timeout_unknown,
    "sat_exact_memo": check_sat_exact_memo,
    "dimacs_empty_clause": check_dimacs_empty_clause,
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
    SourceMutant(
        name="Toffoli lowering phase error",
        target="cqhecs/gate_lowering.py",
        original=(
            '        ("t", [a], []),\n'
            '        ("tdg", [b], []),\n'
        ),
        replacement=(
            '        ("tdg", [a], []),\n'
            '        ("tdg", [b], []),\n'
        ),
        check="toffoli_lowering",
        mechanism="flips one T to T-dagger in the exact CCX decomposition",
    ),
    SourceMutant(
        name="Stabilizer expectation sign dropped",
        target="cqhecs/expectation.py",
        original="    return 1 - 2 * int(tab[2 * n, 2 * n])\n",
        replacement="    return 1\n",
        check="stabilizer_expectation_sign",
        mechanism="reports +1 for every deterministic Pauli, ignoring the tableau phase",
    ),
    SourceMutant(
        name="Dense Pauli-Y orientation flipped",
        target="cqhecs/backends/dense_reference.py",
        original='        "y": [[0, -1j], [1j, 0]],\n',
        replacement='        "y": [[0, 1j], [-1j, 0]],\n',
        check="dense_y_orientation",
        mechanism="transposes the Pauli-Y matrix so Y expectations change sign",
    ),
    SourceMutant(
        name="Real hardware authorization bypassed",
        target="cqhecs/hardware_bridge.py",
        original="        if not authorized:\n",
        replacement="        if False and not authorized:\n",
        check="hardware_authorization",
        mechanism="bypasses authorization check in RealHardwareBackend.run()",
    ),
    SourceMutant(
        name="Hardware profile self-loop allowed",
        target="cqhecs/hardware_bridge.py",
        original="            if u == v:\n",
        replacement="            if False and u == v:\n",
        check="profile_self_loop",
        mechanism="allows self-loops in backend coupling map",
    ),
    SourceMutant(
        name="Noisy density-matrix bit order mirrored",
        target="cqhecs/backends/noisy_density_matrix.py",
        original="        rho_mat = np.transpose(rho, row_axes + col_axes).reshape((dim, dim))\n",
        replacement="        rho_mat = rho.reshape((dim, dim))\n",
        check="noisy_dm_bit_order",
        mechanism="flattens with qubit 0 as the most-significant bit",
    ),
    SourceMutant(
        name="Noisy density-matrix marginal ignores measured qubit",
        target="cqhecs/backends/noisy_density_matrix.py",
        original="                    out_idx |= ((idx >> q) & 1) << j\n",
        replacement="                    out_idx |= ((idx >> j) & 1) << j\n",
        check="noisy_dm_measured_marginal",
        mechanism="reads output bit j from qubit j instead of the j-th measured qubit",
    ),
    SourceMutant(
        name="Noise attached to lowered gate instead of source gate",
        target="cqhecs/backends/noisy_density_matrix.py",
        original="            gate = source_name.lower()\n",
        replacement="            gate = ops[-1][0].lower() if ops else source_name.lower()\n",
        check="noise_on_source_gate",
        mechanism="looks noise up by the last lowered gate (sx -> h) as v2.5.0 did",
    ),
    SourceMutant(
        name="Non-synthetic profile provenance not required",
        target="cqhecs/hardware_bridge.py",
        original="        if not self.is_synthetic and (not self.capture_timestamp or not self.provenance_uri):\n",
        replacement="        if False:\n",
        check="profile_provenance_required",
        mechanism="accepts a profile that claims real calibration without provenance",
    ),
    SourceMutant(
        name="Path B T decomposition sign flipped",
        target="cqhecs/backends/path_b_stabilizer_rank.py",
        original="                c1 = (1.0 - w) / 2.0\n",
        replacement="                c1 = (w - 1.0) / 2.0\n",
        check="path_b_t_sign",
        mechanism="decomposes T as diag(w, 1), the adjoint up to global phase, as before v2.5.2",
    ),
    SourceMutant(
        name="Gate error used as depolarizing parameter",
        target="cqhecs/hardware_bridge.py",
        original="    return min(1.0, d * float(infidelity) / (d - 1))\n",
        replacement="    return float(infidelity)\n",
        check="gate_error_is_infidelity",
        mechanism="treats the reported gate infidelity as the channel parameter p",
    ),
    SourceMutant(
        name="Profile T2 <= 2 T1 check removed",
        target="cqhecs/hardware_bridge.py",
        original="            if t1 is not None and t2 > 2.0 * t1 * (1.0 + 1e-12):\n",
        replacement="            if False:\n",
        check="profile_t2_bound",
        mechanism="accepts T2 above the physical limit 2 T1",
    ),
    SourceMutant(
        name="Profile gate-error key width unchecked",
        target="cqhecs/hardware_bridge.py",
        original="        if not isinstance(qubits, tuple) or len(qubits) not in (1, 2):\n",
        replacement="        if not isinstance(qubits, tuple):\n",
        check="profile_gate_key_width",
        mechanism="accepts gate-error keys the noise model cannot represent",
    ),
    SourceMutant(
        name="Relaxation applied before depolarizing",
        target="cqhecs/hardware_bridge.py",
        original="                channel = depol if relax is None else ComposedChannel(depol, relax)\n",
        replacement="                channel = depol if relax is None else ComposedChannel(relax, depol)\n",
        check="relaxation_after_depolarizing",
        mechanism="reverses the depolarizing/relaxation order of the device model",
    ),
    SourceMutant(
        name="Imported T2 clipped to 2 T1 instead of flagged",
        target="cqhecs/calibration_import.py",
        original='            relaxation_excluded[q] = {"reason": "T2 > 2*T1 or non-positive", "T1_us": t1, "T2_us": t2}\n',
        replacement="            t1_us[q], t2_us[q] = t1, min(t2, 2.0 * t1)\n",
        check="import_flags_inconsistent_t2",
        mechanism="silently truncates a physically inconsistent T2 (as Aer does)",
    ),
    SourceMutant(
        name="Non-operational gate dropped without a flag",
        target="cqhecs/calibration_import.py",
        original='            non_operational.append({"gate": gate, "qubits": list(qubits), "gate_error": error})\n',
        replacement="            pass\n",
        check="import_flags_non_operational",
        mechanism="drops gate_error = 1 entries so circuits on broken pairs run noiseless",
    ),
    SourceMutant(
        name="Readout phase of a Y factor flipped",
        target="cqhecs/noisy_expectation.py",
        original="            factor_phase = -1j if ((x_mask & bit) and (z_mask & bit)) else 1.0\n",
        replacement="            factor_phase = 1j if ((x_mask & bit) and (z_mask & bit)) else 1.0\n",
        check="noisy_readout_phase",
        mechanism="uses XZ = +iY in the readout map",
    ),
    SourceMutant(
        name="Noise channels skipped in Pauli propagation",
        target="cqhecs/noisy_expectation.py",
        original="        for channel in reversed(list(_channels(noise_model, gate, qubits))):\n",
        replacement="        for channel in ():\n",
        check="noisy_channels_applied",
        mechanism="propagates the ideal circuit while reporting NOISY_CLASSICAL",
    ),
    SourceMutant(
        name="Two-qubit noise map operands swapped",
        target="cqhecs/noisy_expectation.py",
        original="        for ax, az, bx, bz, c in columns[4 * ja + jb]:\n",
        replacement="        for ax, az, bx, bz, c in columns[4 * jb + ja]:\n",
        check="noisy_two_qubit_operand_order",
        mechanism="applies a two-qubit channel with its operands exchanged",
    ),
    SourceMutant(
        name="Gate-step truncation left out of the noisy bound",
        target="cqhecs/noisy_expectation.py",
        original=(
            "            terms = sim._apply_gate_backward(terms, name, list(op_qubits), list(params))\n"
            "            terms, dropped = sim._truncate_terms(terms)\n"
            "            bound += dropped\n"
        ),
        replacement=(
            "            terms = sim._apply_gate_backward(terms, name, list(op_qubits), list(params))\n"
            "            terms, dropped = sim._truncate_terms(terms)\n"
            "            bound += 0.0\n"
        ),
        check="noisy_truncation_bound",
        mechanism="drops Pauli terms after a gate without adding them to the certified bound",
    ),
    SourceMutant(
        name="Reference dataset hash check bypassed",
        target="cqhecs/reference.py",
        original=(
            "        actual = _sha256(candidate)\n"
            "        if actual != entry.sha256:\n"
            "            raise IntegrityError(\n"
            "                f\"{candidate} has SHA-256 {actual}, expected {entry.sha256}\"\n"
            "            )\n"
        ),
        replacement=(
            "        actual = _sha256(candidate)\n"
            "        if False:\n"
            "            raise IntegrityError(\n"
            "                f\"{candidate} has SHA-256 {actual}, expected {entry.sha256}\"\n"
            "            )\n"
        ),
        check="reference_hash_bypass",
        mechanism="accepts a corrupted real-data file whose pinned digest does not match",
    ),
    SourceMutant(
        name="Reference verdict always SUPPORTED",
        target="cqhecs/reference.py",
        original=(
            '        "verdict": "SUPPORTED" if high < 0.0 else ("REJECTED" if low > 0.0 else "INCONCLUSIVE"),\n'
        ),
        replacement='        "verdict": "SUPPORTED",\n',
        check="reference_verdict_suppression",
        mechanism="turns an inconclusive pooled H-V3-1 interval into a success claim",
    ),
    SourceMutant(
        name="Selftest inverse property silently skipped",
        target="cqhecs/selftest.py",
        original="        combined = list(circuit) + _inverse(circuit)\n",
        replacement="        combined = list(circuit)\n",
        check="selftest_inverse_property",
        mechanism="runs C instead of C†C while the selftest still reports PASS",
    ),
    SourceMutant(
        name="ComposedChannel operands reversed",
        target="cqhecs/hardware_bridge.py",
        original="        self._kraus = _prune([b @ a for a in first.kraus_operators for b in second.kraus_operators])\n",
        replacement="        self._kraus = _prune([a @ b for a in first.kraus_operators for b in second.kraus_operators])\n",
        check="selftest_composition_property",
        mechanism="applies the second channel before the first",
    ),
    SourceMutant(
        name="SAT timeout reported as UNSAT",
        target="python_bridge/sat_engine.py",
        original="            raise _SearchTimeout()\n",
        replacement="            return False, None\n",
        check="sat_timeout_unknown",
        mechanism="restores the v2 behaviour: a timeout becomes satisfiable=False, verified=True",
    ),
    SourceMutant(
        name="SAT memo keyed by the first 32 variables",
        target="python_bridge/sat_engine.py",
        original="        state_key = frozenset(assignment.items())\n",
        replacement="        state_key = frozenset(sorted(assignment.items())[:32])\n",
        check="sat_exact_memo",
        mechanism="merges states that differ only above variable 32 (the v2 hash collision)",
    ),
    SourceMutant(
        name="DIMACS empty clause dropped",
        target="python_bridge/sat_engine.py",
        original="                    clauses.append(current)\n",
        replacement="                    if current:\n                        clauses.append(current)\n",
        check="dimacs_empty_clause",
        mechanism="turns an UNSAT formula with an empty clause into a verified SAT",
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
    """Writes text preserving the file's native newline convention."""
    newline = "\n"
    if path.exists():
        try:
            raw = path.read_bytes()
            if b"\r\n" in raw:
                newline = "\r\n"
        except Exception:
            pass
    normalized = text.replace("\r\n", "\n")
    encoded = normalized.replace("\n", newline).encode("utf-8")
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(path.parent)) as handle:
        handle.write(encoded)
        temp_name = handle.name
    os.replace(temp_name, path)


def apply_mutant(mutant: SourceMutant) -> Tuple[Path, str]:
    """Validates the anchor, writes the mutated source and returns (path, original_text)."""
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
