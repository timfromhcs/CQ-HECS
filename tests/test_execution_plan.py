"""Dry-run ExecutionPlan: determinism, router parity, refusals and surface parity."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cqhecs import execution_plan as ep
from cqhecs.circuit_analyzer import CircuitAnalyzer
from cqhecs.circuit_library import build_builtin_circuit
from cqhecs.circuit_parsing import parse_circuit
from cqhecs.execution_plan import (
    PLAN_SCHEMA_VERSION,
    build_execution_plan,
    normalized_circuit_digest,
)
from cqhecs.gate_manifest import path_gate_names
from cqhecs.router import EntanglementAdaptiveRouter, UnsupportedCircuitError

ROOT = Path(__file__).parent.parent

BELL = (
    "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\n"
    "h q[0];\ncx q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n"
)
LOW_T = (
    "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[3];\n"
    "h q[0];\nt q[0];\ncx q[0],q[1];\ncx q[1],q[2];\n"
)
MID_MEASURE = (
    "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\ncreg c[2];\n"
    "h q[0];\nmeasure q[0] -> c[0];\ncx q[0],q[1];\n"
)


def _wide_t_heavy():
    """40 qubits, non-Clifford, 40 crossings of every cut -> Path D only."""
    ops = [("h", [0], []), ("t", [0], [])]
    ops += [("cx", [0, 39], [])] * 40
    return ops


def _brick(n=24, layers=4):
    ops = []
    for _ in range(layers):
        for i in range(n):
            ops.append(("h", [i], []))
            ops.append(("t", [i], []))
        for i in range(0, n - 1, 2):
            ops.append(("cx", [i, i + 1], []))
    return ops


CORPUS = {
    "bell": BELL,
    "low_t": LOW_T,
    "ghz8": build_builtin_circuit("ghz8"),
    "wide_t_heavy": _wide_t_heavy(),
    "brick24": _brick(),
}


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_plan_matches_router_selection_and_manifest(name):
    circuit = CORPUS[name]
    instructions, n = parse_circuit(circuit)
    props = CircuitAnalyzer().analyze_instructions(instructions, n)
    plan = build_execution_plan(circuit)

    assert plan.schema_version == PLAN_SCHEMA_VERSION
    assert plan.selected_path == (props.recommended_path or None)
    assert {c["path"] for c in plan.candidate_paths if c["capable"]} == set(
        props.supported_paths
    )
    # Capability comes only from the shared manifest: every capable path's gate
    # set covers every gate used (barrier/measure live in the manifest too).
    for cand in plan.candidate_paths:
        if cand["capable"]:
            assert set(props.gate_counts) <= path_gate_names(cand["path"])
        else:
            assert cand["capability_blockers"], "an incapable path must say why"
    # Exactly one candidate is chosen when the plan would execute.
    chosen = [c["path"] for c in plan.candidate_paths if c["chosen"]]
    assert chosen == ([plan.selected_path] if plan.would_execute else [])


def test_plan_digest_is_deterministic_and_input_sensitive():
    a = build_execution_plan(BELL)
    b = build_execution_plan(BELL)
    assert a.plan_digest == b.plan_digest == a.compute_digest()
    assert a.to_json() == b.to_json()
    c = build_execution_plan(LOW_T)
    assert c.plan_digest != a.plan_digest
    # Forcing a path changes the plan, and therefore the digest.
    d = build_execution_plan(LOW_T, forced_path="C")
    assert d.plan_digest != c.plan_digest


def test_input_digest_distinguishes_text_from_normalized_circuit():
    reformatted = BELL.replace("\n", "\n\n")
    a, b = build_execution_plan(BELL), build_execution_plan(reformatted)
    assert a.normalized_circuit_digest == b.normalized_circuit_digest
    assert a.input_digest != b.input_digest


def test_normalized_digest_depends_on_gate_order_and_params():
    base = [("rz", [0], [0.5]), ("cx", [0, 1], [])]
    swapped = [("cx", [0, 1], []), ("rz", [0], [0.5])]
    other = [("rz", [0], [0.5000001]), ("cx", [0, 1], [])]
    d = normalized_circuit_digest
    assert d(base, 2) == d([list(x) for x in base], 2)
    assert len({d(base, 2), d(swapped, 2), d(other, 2), d(base, 3)}) == 4


def test_dry_run_allocates_no_backend(monkeypatch):
    """Planning must work even if every backend constructor/executor is poisoned."""
    from cqhecs.backends.path_a_stabilizer import PathAStabilizerBackend
    from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend
    from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend
    from cqhecs.backends.path_d_sparse_pauli import PathDSparsePauliBackend

    def boom(*_a, **_k):
        raise AssertionError("dry run touched a backend")

    for cls in (
        PathAStabilizerBackend,
        PathBStabilizerRankBackend,
        PathCMPSExactBackend,
        PathDSparsePauliBackend,
    ):
        monkeypatch.setattr(cls, "__init__", boom)
        monkeypatch.setattr(cls, "execute", boom)
    plan = build_execution_plan(CORPUS["brick24"])
    assert plan.selected_path in ("C", "D")


def test_features_are_computed_from_the_normalised_circuit():
    plan = build_execution_plan(LOW_T)
    assert plan.num_qubits == 3
    assert plan.num_gates == 4
    assert plan.one_qubit_gate_count == 2
    assert plan.two_qubit_gate_count == 2
    assert plan.estimated_t_count == 1
    assert plan.circuit_depth == 4  # h,t on q0 then cx(0,1), cx(1,2)
    graph = plan.interaction_graph_summary
    assert graph["num_edges"] == 2
    assert graph["nearest_neighbour_only"] is True
    assert graph["num_connected_components"] == 1


def test_forced_unsupported_path_is_a_typed_refusal_not_a_reroute():
    plan = build_execution_plan(LOW_T, forced_path="A")  # T gate: not Clifford
    assert plan.selected_path is None and not plan.would_execute
    assert plan.refusal["code"] == ep.REFUSAL_FORCED_PATH_UNSUPPORTED
    assert not any(c["chosen"] for c in plan.candidate_paths)
    router = EntanglementAdaptiveRouter()
    with pytest.raises(UnsupportedCircuitError):
        router.route_and_execute(LOW_T, preferred_path="A")


def test_unknown_forced_path_refuses():
    plan = build_execution_plan(BELL, forced_path="Z")
    assert plan.refusal["code"] == ep.REFUSAL_UNKNOWN_PATH


def test_forced_supported_path_is_selected_verbatim():
    plan = build_execution_plan(BELL, forced_path="c")
    assert plan.selected_path == "C" and plan.forced_path == "C"
    assert plan.fallback_policy["forced"] is True
    assert plan.fallback_policy["runtime_fallback_chain"] == []


def test_mid_circuit_measurement_is_a_dynamic_refusal():
    plan = build_execution_plan(MID_MEASURE)
    assert plan.refusal["code"] == ep.REFUSAL_DYNAMIC_CIRCUIT
    assert plan.selected_path is None
    assert all(not c["capable"] for c in plan.candidate_paths)


def test_unsupported_operation_is_refused_before_execution():
    plan = build_execution_plan([("frobnicate", [0], [])])
    assert plan.refusal["code"] == ep.REFUSAL_UNSUPPORTED_OPERATION
    assert plan.unsupported_operations == ["frobnicate"]


def test_path_d_cannot_satisfy_require_counts():
    circuit = CORPUS["wide_t_heavy"]
    free = build_execution_plan(circuit)
    assert free.selected_path == "D" and free.would_execute
    needs = build_execution_plan(circuit, require_counts=True)
    assert needs.refusal["code"] == ep.REFUSAL_COUNTS_UNAVAILABLE
    assert needs.selected_path is None


def test_resource_budget_refuses_without_switching_paths():
    plan = build_execution_plan(CORPUS["brick24"], max_memory_bytes=1)
    assert plan.refusal["code"] == ep.REFUSAL_RESOURCE_BUDGET
    assert plan.selected_path is None
    assert "No other path was substituted" in plan.refusal["message"]
    with pytest.raises(ValueError):
        build_execution_plan(BELL, max_memory_bytes=0)


def test_estimates_are_labelled_heuristic_and_saturate_instead_of_overflowing():
    plan = build_execution_plan(CORPUS["wide_t_heavy"])
    assert plan.estimate_quality == "heuristic"
    for cand in plan.candidate_paths:
        assert 0 < cand["estimated_peak_memory_bytes"] <= (1 << 63) - 1
        assert 0 < cand["estimated_work_units"] <= (1 << 63) - 1
    path_c = next(c for c in plan.candidate_paths if c["path"] == "C")
    assert path_c["estimate_saturated"] is True


def test_qiskit_circuit_input_matches_instruction_list():
    qiskit = pytest.importorskip("qiskit")
    qc = qiskit.QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    from_qiskit = build_execution_plan(qc)
    from_list = build_execution_plan([("h", [0], []), ("cx", [0, 1], [])])
    assert from_qiskit.normalized_circuit_digest == from_list.normalized_circuit_digest
    assert from_qiskit.selected_path == from_list.selected_path == "A"


def test_executed_result_records_plan_check_without_changing_routing():
    router = EntanglementAdaptiveRouter()
    result = router.route_and_execute(BELL, shots=64, seed=1)
    check = result.metadata["plan_check"]
    planned = router.plan(BELL)
    assert check["plan_digest"] == planned.plan_digest
    assert check["planned_path"] == "A" == check["actual_path"] == result.path
    assert check["deviated"] is False
    assert check["execution_time_ms"] == result.execution_time_ms


# --- surface parity: Python == CLI == MCP == Studio -----------------------

def _normalised(plan_dict):
    return json.dumps(plan_dict, sort_keys=True)


def test_cli_mcp_studio_return_the_python_plan():
    from cqhecs import mcp_server
    from cqhecs.studio import StudioState

    python_plan = build_execution_plan(build_builtin_circuit("ghz8")).to_dict()

    cli = subprocess.run(
        [sys.executable, "-m", "cqhecs.cli", "--format", "json", "analyze",
         "name:ghz8", "--explain"],
        capture_output=True, text=True, cwd=ROOT, timeout=120,
    )
    assert cli.returncode == 0, cli.stderr
    cli_plan = json.loads(cli.stdout)["plan"]

    mcp = mcp_server._tool_plan({"circuit": "preset:ghz8"})

    studio = StudioState(ROOT).plan({"source": "preset:ghz8"})["plan"]

    assert _normalised(cli_plan) == _normalised(python_plan)
    assert _normalised(mcp) == _normalised(python_plan)
    assert _normalised(studio) == _normalised(python_plan)


def test_mcp_tools_list_exposes_plan():
    from cqhecs import mcp_server

    response = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in response["result"]["tools"]}
    assert "cqhecs_plan" in names


def test_studio_plan_rejects_bad_path_and_source():
    from cqhecs.studio import StudioState
    from cqhecs.studio.app import StudioError

    state = StudioState(ROOT)
    with pytest.raises(StudioError):
        state.plan({"source": "preset:bell", "path": "Q"})
    with pytest.raises(StudioError):
        state.plan({"source": "garbage"})
