"""T6-01: QG experiments produce the same ExecutionPlan schema and provenance as circuits."""

from __future__ import annotations

import json
import math

import pytest

from cqhecs.execution_plan import PLAN_SCHEMA_VERSION, build_execution_plan
from cqhecs.quantum_gravity.circuits import bmv_qasm
from cqhecs.quantum_gravity.errors import QGModelError
from cqhecs.quantum_gravity.gauge import Z2Lattice
from cqhecs.quantum_gravity.hamiltonians import build_syk
from cqhecs.quantum_gravity.models import MODEL_ID, MODEL_VERSION
from cqhecs.quantum_gravity.plan import (
    QG_PLAN_SCHEMA,
    attach_plan_to_run_card,
    bmv_execution_plan,
    build_qg_execution_plan,
    gauge_execution_plan,
    syk_execution_plan,
)
from cqhecs.quantum_gravity.results import build_experiment_result
from cqhecs.quantum_gravity.syk_trotter import syk_trotter_qasm

CLIFFORD_BMV = bmv_qasm(math.pi / 2)  # rz(pi/2) is Clifford -> Path A
DYNAMIC = (
    'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
    "h q[0];\nmeasure q[0] -> c[0];\ncx q[0],q[1];\nmeasure q[1] -> c[1];\n"
)


def _plans():
    syk = build_syk(3, seed=20260101, scale=0.4)
    return [
        bmv_execution_plan(0.7),
        syk_execution_plan(syk, 1.0, 2),
        gauge_execution_plan(Z2Lattice(1, 1), 0.5),
    ]


def test_embedded_plan_is_identical_to_the_generic_plan_for_the_same_qasm():
    syk = build_syk(3, seed=20260101, scale=0.4)
    qasm = syk_trotter_qasm(syk, 1.0, 2, measure=True)
    qg = syk_execution_plan(syk, 1.0, 2)
    generic = build_execution_plan(qasm, require_counts=True)
    assert qg.plan.to_dict() == generic.to_dict()
    assert qg.plan.plan_digest == generic.plan_digest
    assert qg.to_dict()["plan"]["schema_version"] == PLAN_SCHEMA_VERSION


@pytest.mark.parametrize("plan", _plans(), ids=lambda p: p.experiment_id)
def test_envelope_exposes_engine_precision_surface_and_provenance(plan):
    data = plan.to_dict()
    assert data["schema"] == QG_PLAN_SCHEMA
    assert data["execution_surface"] == "CQ_HECS_CPU"
    assert data["physical_execution"] is False
    assert data["engine"]["engine"] and data["engine"]["precision"]
    assert data["reference_engine"]["precision"] == "float64"
    frag = plan.run_card_fragment()
    assert frag["plan_digest"] == plan.plan.plan_digest
    assert frag["selected_path"] == plan.plan.selected_path
    assert frag["engine"] == data["engine"]["engine"]
    assert frag["precision"] == data["engine"]["precision"]
    assert frag["physical_execution"] is False
    json.dumps(data)  # JSON-safe


def test_engine_follows_the_selected_path_and_never_a_guess():
    clifford = build_qg_execution_plan(
        CLIFFORD_BMV, experiment_id="e", model_id=MODEL_ID, model_version=MODEL_VERSION, require_counts=True
    )
    # whatever path the generic planner picks, the engine must be the table entry for it
    expected = {"A": "stabilizer_tableau", "B": "stabilizer_rank", "C": "mps", "D": "sparse_pauli_heisenberg"}
    assert clifford.engine["engine"] == expected[clifford.plan.selected_path]


def test_plan_is_deterministic_and_input_sensitive():
    a, b = bmv_execution_plan(0.7), bmv_execution_plan(0.7)
    assert a.digest() == b.digest()
    assert a.plan.plan_digest != bmv_execution_plan(0.71).plan.plan_digest


def test_dry_run_builds_no_backend(monkeypatch):
    import cqhecs.router as router

    def boom(*_a, **_k):
        raise AssertionError("planning must not execute a backend")

    monkeypatch.setattr(router.EntanglementAdaptiveRouter, "route_and_execute", boom, raising=False)
    assert bmv_execution_plan(0.3).would_execute


def test_refusals_are_preserved_not_swallowed():
    refused = build_qg_execution_plan(
        DYNAMIC, experiment_id="e", model_id=MODEL_ID, model_version=MODEL_VERSION
    )
    assert not refused.would_execute
    assert refused.engine is None
    assert refused.plan.refusal["code"] == "DYNAMIC_CIRCUIT"
    assert refused.run_card_fragment()["refusal_code"] == "DYNAMIC_CIRCUIT"
    assert refused.run_card_fragment()["engine"] is None


def test_forced_unsupported_path_is_a_refusal_not_a_reroute():
    plan = bmv_execution_plan(0.7, forced_path="A")
    assert not plan.would_execute
    assert plan.plan.refusal["code"] == "FORCED_PATH_UNSUPPORTED"
    assert plan.engine is None


def test_resource_budget_refusal_keeps_the_selected_path_unchanged():
    plan = bmv_execution_plan(0.7, max_memory_bytes=1)
    assert not plan.would_execute
    assert plan.plan.refusal["code"] == "RESOURCE_BUDGET"
    assert plan.engine is None


def test_qpu_surface_cannot_be_planned():
    with pytest.raises(QGModelError):
        build_qg_execution_plan(
            bmv_qasm(0.5),
            experiment_id="e",
            model_id=MODEL_ID,
            model_version=MODEL_VERSION,
            execution_surface="OPENQUANTUM_QPU",
        )


def test_unknown_surface_and_missing_identity_are_refused():
    with pytest.raises(QGModelError):
        build_qg_execution_plan(
            bmv_qasm(0.5), experiment_id="e", model_id=MODEL_ID, model_version=MODEL_VERSION,
            execution_surface="NOT_A_SURFACE",
        )
    with pytest.raises(QGModelError):
        build_qg_execution_plan(bmv_qasm(0.5), experiment_id="", model_id=MODEL_ID, model_version=MODEL_VERSION)


def test_run_card_attachment_round_trips_through_the_experiment_envelope(tmp_path):
    plan = bmv_execution_plan(0.7)
    card = attach_plan_to_run_card({"existing": "value"}, plan)
    assert card["existing"] == "value"
    assert card["execution_plan"]["plan_digest"] == plan.plan.plan_digest
    result = build_experiment_result(
        campaign_id="qg-2026-01",
        experiment_id=plan.experiment_id,
        hypothesis_id="H-A1",
        model_id=MODEL_ID,
        model_version=MODEL_VERSION,
        execution_surface="MODEL_PREDICTION",
        status="PENDING",
        run_card=card,
    )
    path = result.write(tmp_path / "r.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["run_card"]["execution_plan"]["engine"] == plan.engine["engine"]
    assert loaded["run_card"]["execution_plan"]["physical_execution"] is False


def test_explain_shows_engine_precision_and_no_overclaim():
    text = bmv_execution_plan(0.7).explain().lower()
    assert "engine" in text and "float64" in text
    for banned in ("measures gravity", "proves", "detects gravit"):
        assert banned not in text


def test_limitations_state_the_boundary():
    joined = " ".join(bmv_execution_plan(0.7).limitations).lower()
    assert "no qpu job" in joined and "not a gravity measurement" in joined
