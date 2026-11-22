"""T6-01: Quantum Gravity ``ExecutionPlan`` parity.

A QG experiment that compiles to a circuit gets *the same* dry-run plan object as any other
circuit (:class:`cqhecs.execution_plan.ExecutionPlan`, schema ``cqhecs.execution_plan/1``),
unchanged and with its own digest. The QG envelope only adds QG identity and the two facts a
reader must always see: which **engine** the plan would run on and at what **precision**.

Rules
-----
* The embedded plan is byte-for-byte what :func:`build_execution_plan` returns for the same
  QASM; this module never edits, re-ranks or re-routes it. Refusals stay refusals.
* The plan describes the *classical CQ-HECS route* for the compiled circuit. It never plans,
  quotes, submits or implies a QPU job; ``physical_execution`` is always ``False`` here.
* Dense reference computations (matrix exponentials, eigendecompositions) are declared as a
  separate ``reference_engine`` with their own precision; they are not the routed engine.
* Engine/precision come from the plan's selected path through a fixed table; an unselected
  plan has ``engine = None`` and its refusal code, never a guessed engine.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

from cqhecs.execution_plan import ExecutionPlan, build_execution_plan
from cqhecs.quantum_gravity.catalog import EXECUTION_SURFACES, ExecutionSurface
from cqhecs.quantum_gravity.circuits import bmv_qasm
from cqhecs.quantum_gravity.errors import QGModelError

QG_PLAN_SCHEMA = "cqhecs.qg.execution_plan/1"

#: path -> (engine name, arithmetic/precision statement). Fixed; mirrors ARCHITECTURE.md.
_ENGINES: Dict[str, Dict[str, str]] = {
    "A": {"engine": "stabilizer_tableau", "precision": "exact_integer_gf2"},
    "B": {"engine": "stabilizer_rank", "precision": "float64"},
    "C": {"engine": "mps", "precision": "float64_numerical_rank_floor"},
    "D": {"engine": "sparse_pauli_heisenberg", "precision": "float64_triangle_inequality_bound"},
}

REFERENCE_ENGINE_DENSE = {
    "engine": "dense_numpy_scipy",
    "precision": "float64",
    "scope": "model reference (matrix exponential / eigendecomposition); <= 8 qubits",
}


@dataclass
class QGExecutionPlan:
    schema: str
    experiment_id: str
    model_id: str
    model_version: str
    hypothesis_id: Optional[str]
    execution_surface: str
    physical_execution: bool
    engine: Optional[Dict[str, str]]
    reference_engine: Optional[Dict[str, str]]
    plan: ExecutionPlan
    limitations: Sequence[str]

    @property
    def would_execute(self) -> bool:
        return self.plan.would_execute

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": self.schema,
            "experiment_id": self.experiment_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "hypothesis_id": self.hypothesis_id,
            "execution_surface": self.execution_surface,
            "physical_execution": self.physical_execution,
            "engine": self.engine,
            "reference_engine": self.reference_engine,
            "would_execute": self.would_execute,
            "plan": self.plan.to_dict(),
            "limitations": list(self.limitations),
        }

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, **kwargs)

    def digest(self) -> str:
        return hashlib.sha256(self.to_json(separators=(",", ":")).encode("utf-8")).hexdigest()

    def run_card_fragment(self) -> Dict[str, Any]:
        """Compact, JSON-safe plan provenance to embed under ``run_card['execution_plan']``."""
        refusal = self.plan.refusal
        return {
            "schema": self.schema,
            "plan_schema_version": self.plan.schema_version,
            "plan_digest": self.plan.plan_digest,
            "input_digest": self.plan.input_digest,
            "normalized_circuit_digest": self.plan.normalized_circuit_digest,
            "selected_path": self.plan.selected_path,
            "engine": (self.engine or {}).get("engine"),
            "precision": (self.engine or {}).get("precision"),
            "refusal_code": refusal["code"] if refusal else None,
            "estimate_quality": self.plan.estimate_quality,
            "physical_execution": self.physical_execution,
        }

    def explain(self) -> str:
        head = [
            f"QG plan       : {self.experiment_id} ({self.model_id} {self.model_version})",
            f"Surface       : {self.execution_surface}  (physical execution: {self.physical_execution})",
        ]
        if self.engine:
            head.append(f"Engine        : {self.engine['engine']} / {self.engine['precision']}")
        else:
            head.append("Engine        : none (plan refused)")
        if self.reference_engine:
            head.append(
                f"Reference     : {self.reference_engine['engine']} / {self.reference_engine['precision']}"
            )
        return "\n".join(head + [self.plan.explain()])


def build_qg_execution_plan(
    qasm: Any,
    *,
    experiment_id: str,
    model_id: str,
    model_version: str,
    hypothesis_id: Optional[str] = None,
    execution_surface: str = ExecutionSurface.CQ_HECS_CPU.value,
    reference_engine: Optional[Mapping[str, str]] = None,
    forced_path: Optional[str] = None,
    require_counts: bool = True,
    max_memory_bytes: Optional[int] = None,
) -> QGExecutionPlan:
    """Plan a QG experiment's compiled circuit through the generic planner (no re-routing)."""
    if not experiment_id or not model_id or not model_version:
        raise QGModelError("experiment_id, model_id and model_version are required")
    if execution_surface not in EXECUTION_SURFACES:
        raise QGModelError(f"execution_surface {execution_surface!r} is not one of {EXECUTION_SURFACES}")
    if execution_surface == ExecutionSurface.OPENQUANTUM_QPU.value:
        raise QGModelError(
            "an ExecutionPlan describes the classical CQ-HECS route; it cannot plan a QPU surface"
        )
    plan = build_execution_plan(
        qasm,
        forced_path=forced_path,
        require_counts=require_counts,
        max_memory_bytes=max_memory_bytes,
    )
    engine = dict(_ENGINES[plan.selected_path]) if plan.would_execute and plan.selected_path else None
    return QGExecutionPlan(
        schema=QG_PLAN_SCHEMA,
        experiment_id=experiment_id,
        model_id=model_id,
        model_version=model_version,
        hypothesis_id=hypothesis_id,
        execution_surface=execution_surface,
        physical_execution=False,
        engine=engine,
        reference_engine=dict(reference_engine) if reference_engine else None,
        plan=plan,
        limitations=(
            "plan describes the classical CQ-HECS route for the compiled circuit only",
            "no QPU job is planned, quoted or implied; model quantity, not a gravity measurement",
            "estimates are heuristics, not guarantees",
        ),
    )


def attach_plan_to_run_card(
    run_card: Optional[Mapping[str, Any]], plan: QGExecutionPlan
) -> Dict[str, Any]:
    """Return a copy of ``run_card`` with the plan provenance under ``execution_plan``."""
    card: Dict[str, Any] = dict(run_card or {})
    card["execution_plan"] = plan.run_card_fragment()
    return card


# -- experiment adapters ------------------------------------------------------------
def bmv_execution_plan(theta: float, **kwargs: Any) -> QGExecutionPlan:
    from cqhecs.quantum_gravity.models import MODEL_ID, MODEL_VERSION

    return build_qg_execution_plan(
        bmv_qasm(theta),
        experiment_id=f"bmv-zz-plan-theta-{theta:.6g}",
        model_id=MODEL_ID,
        model_version=MODEL_VERSION,
        hypothesis_id=kwargs.pop("hypothesis_id", None),
        reference_engine=REFERENCE_ENGINE_DENSE,
        **kwargs,
    )


def syk_execution_plan(syk: Any, t: float, steps: int = 1, **kwargs: Any) -> QGExecutionPlan:
    from cqhecs.quantum_gravity.syk_trotter import syk_trotter_qasm

    return build_qg_execution_plan(
        syk_trotter_qasm(syk, t, steps, measure=True),
        experiment_id=f"syk-q4-n{syk.num_qubits}-seed{syk.seed}-t{t:.6g}-r{steps}",
        model_id=syk.model_id,
        model_version=syk.model_version,
        hypothesis_id=kwargs.pop("hypothesis_id", None),
        reference_engine=REFERENCE_ENGINE_DENSE,
        **kwargs,
    )


def gauge_execution_plan(lattice: Any, t: float, steps: int = 1, **kwargs: Any) -> QGExecutionPlan:
    """Plan ``exp(+i t sum_p B_p)`` (the commuting plaquette product, exact for any step count)."""
    from cqhecs.quantum_gravity.gauge import _label
    from cqhecs.quantum_gravity.syk_trotter import trotter_qasm

    terms = [
        (_label(lattice.num_links, lattice.plaquette_links(r, c), "Z"), -1.0)
        for r in range(lattice.rows)
        for c in range(lattice.cols)
    ]
    return build_qg_execution_plan(
        trotter_qasm(terms, lattice.num_links, t, steps, measure=True),
        experiment_id=f"z2-gauge-{lattice.rows}x{lattice.cols}-t{t:.6g}-r{steps}",
        model_id=lattice.model_id,
        model_version=lattice.model_version,
        hypothesis_id=kwargs.pop("hypothesis_id", None),
        reference_engine=REFERENCE_ENGINE_DENSE,
        **kwargs,
    )
