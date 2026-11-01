"""
Explainable dry-run execution planning (v4).

:func:`build_execution_plan` answers "what would the router do with this
circuit, and why?" **without allocating a statevector, tableau, MPS or any
backend object**. It reads only the normalised instruction list and the shared
gate manifest.

Design rules
------------
* *Capability is separate from cost.* A path is a candidate only if the
  manifest-backed analysis says it can execute the normalised circuit. Cost
  estimates never make an incapable path selectable, and they never make a
  capable path unselectable behind the caller's back: a budget overshoot is a
  typed refusal, not a silent switch.
* *Selection is the deterministic router's selection.* The plan reuses
  :class:`~cqhecs.circuit_analyzer.CircuitAnalyzer`'s A -> B -> C -> D decision,
  so ``plan.selected_path`` is what ``route_and_execute`` would run first.
* *Estimates are estimates.* ``estimated_peak_memory_bytes`` and
  ``estimated_work_units`` are conservative, input-derived heuristics. They are
  never guarantees; ``estimate_quality`` says so and ``estimate_inputs`` names
  what they were computed from.
* *Forced paths do not reroute.* A forced path is either the selected path or
  the plan carries a typed refusal.
* *Deterministic.* The plan contains no timestamps, hostnames or random values;
  :attr:`ExecutionPlan.plan_digest` is a SHA-256 over the canonical JSON of
  every other field.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cqhecs.circuit_analyzer import (
    PATH_B_MAX_QUBITS,
    CircuitAnalyzer,
    CircuitProperties,
)
from cqhecs.circuit_parsing import Instruction, parse_circuit
from cqhecs.gate_manifest import get_gate, path_gate_names

PLAN_SCHEMA_VERSION = "cqhecs.execution_plan/1"
VALID_PATHS = ("A", "B", "C", "D")

#: Estimates above this are reported as this value with ``estimate_saturated``.
_ESTIMATE_CAP = (1 << 63) - 1

# Refusal codes (stable; asserted by tests and consumed by the Studio/MCP).
REFUSAL_UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
REFUSAL_DYNAMIC_CIRCUIT = "DYNAMIC_CIRCUIT"
REFUSAL_UNKNOWN_PATH = "UNKNOWN_PATH"
REFUSAL_FORCED_PATH_UNSUPPORTED = "FORCED_PATH_UNSUPPORTED"
REFUSAL_NO_CAPABLE_PATH = "NO_CAPABLE_PATH"
REFUSAL_COUNTS_UNAVAILABLE = "COUNTS_UNAVAILABLE"
REFUSAL_RESOURCE_BUDGET = "RESOURCE_BUDGET"

_RESULT_CONTRACTS = {
    "A": "exact_counts_stabilizer_tableau",
    "B": "exact_amplitudes_stabilizer_rank_float64",
    "C": "counts_mps_numerical_rank_only",
    "D": "expectation_values_with_triangle_inequality_bound",
}


def _saturate(value: int) -> Tuple[int, bool]:
    if value > _ESTIMATE_CAP:
        return _ESTIMATE_CAP, True
    return int(value), False


def normalized_circuit_digest(
    instructions: Sequence[Instruction], num_qubits: int
) -> str:
    """SHA-256 over the canonical form of the parsed instruction list."""
    canonical = [
        [name, [int(q) for q in qubits], [repr(float(p)) for p in params]]
        for name, qubits, params in instructions
    ]
    blob = json.dumps(
        {"num_qubits": int(num_qubits), "instructions": canonical},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _input_digest(circuit: Any, normalized: str) -> str:
    """Digest of the caller's input.

    OpenQASM text is hashed verbatim (so whitespace edits change it, unlike the
    normalised digest). Qiskit circuits and instruction lists have no canonical
    text form, so their input digest equals the normalised digest.
    """
    if isinstance(circuit, str):
        return hashlib.sha256(circuit.encode("utf-8")).hexdigest()
    return normalized


def _circuit_depth(instructions: Sequence[Instruction], num_qubits: int) -> int:
    level = [0] * max(num_qubits, 1)
    depth = 0
    for name, qubits, _params in instructions:
        spec = get_gate(name)
        if spec is not None and spec.barrier:
            continue
        if not qubits:
            continue
        layer = max(level[q] for q in qubits) + 1
        for q in qubits:
            level[q] = layer
        depth = max(depth, layer)
    return depth


def _interaction_graph(
    instructions: Sequence[Instruction], num_qubits: int
) -> Tuple[Dict[int, set], Dict[str, int]]:
    """Qubit interaction graph (any gate on >= 2 qubits links every pair)."""
    adjacency: Dict[int, set] = {q: set() for q in range(num_qubits)}
    one_q = two_q = multi_q = 0
    for name, qubits, _params in instructions:
        spec = get_gate(name)
        if spec is not None and (spec.barrier or spec.measurement or spec.reset):
            continue
        k = len(qubits)
        if k == 1:
            one_q += 1
        elif k == 2:
            two_q += 1
        elif k > 2:
            multi_q += 1
        for i in range(k):
            for j in range(i + 1, k):
                a, b = qubits[i], qubits[j]
                if a != b:
                    adjacency[a].add(b)
                    adjacency[b].add(a)
    return adjacency, {
        "one_qubit_gate_count": one_q,
        "two_qubit_gate_count": two_q,
        "multi_qubit_gate_count": multi_q,
    }


def _components(adjacency: Dict[int, set]) -> int:
    seen: set = set()
    count = 0
    for start in adjacency:
        if start in seen:
            continue
        count += 1
        stack = [start]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(adjacency[node] - seen)
    return count


def _interaction_summary(
    adjacency: Dict[int, set], num_qubits: int
) -> Dict[str, Any]:
    edges = {
        (min(a, b), max(a, b)) for a, nbrs in adjacency.items() for b in nbrs
    }
    degrees = [len(n) for n in adjacency.values()]
    max_span = max((b - a for a, b in edges), default=0)
    possible = num_qubits * (num_qubits - 1) // 2
    return {
        "num_edges": len(edges),
        "num_connected_components": _components(adjacency) if num_qubits else 0,
        "max_degree": max(degrees, default=0),
        "max_edge_span": max_span,
        "nearest_neighbour_only": max_span <= 1,
        "density": round(len(edges) / possible, 6) if possible else 0.0,
    }


def _cut_crossings(
    instructions: Sequence[Instruction], num_qubits: int
) -> List[int]:
    """Entangling gates crossing each 1D cut ``(c, c+1)`` of the logical order."""
    cuts = [0] * max(num_qubits - 1, 0)
    for name, qubits, _params in instructions:
        spec = get_gate(name)
        if spec is not None and (spec.barrier or spec.measurement or spec.reset):
            continue
        if len(qubits) < 2:
            continue
        lo, hi = min(qubits), max(qubits)
        for c in range(lo, min(hi, num_qubits - 1)):
            cuts[c] += 1
    return cuts


# ---------------------------------------------------------------------------
# Heuristic resource estimates
# ---------------------------------------------------------------------------

def _estimate_path(
    path: str,
    *,
    num_qubits: int,
    num_gates: int,
    t_count: int,
    cuts: Sequence[int],
    max_pauli_terms: int,
) -> Dict[str, Any]:
    if path == "A":
        n = max(num_qubits, 1)
        memory = ((2 * n) * (2 * n + 1) + 7) // 8 + 32 * n
        work = max(num_gates, 1) * n
    elif path == "B":
        branches = 1 << min(t_count, 62)
        memory = 16 * (1 << min(num_qubits, 62)) * 2
        work = branches * max(num_gates, 1) * (1 << min(num_qubits, 62))
    elif path == "C":
        n = max(num_qubits, 1)
        # Schmidt rank across cut c is <= 4^crossings and <= 2^min(c+1, n-c-1).
        # Backend swap routing of non-adjacent gates can exceed this: the
        # figure is a heuristic, not an upper bound on the implementation.
        chi_max = 1
        for c, crossing in enumerate(cuts):
            geometric = 1 << min(c + 1, n - c - 1)
            chi_max = max(chi_max, min(geometric, 1 << min(2 * crossing, 62)))
        memory = n * 2 * chi_max * chi_max * 16
        work = max(num_gates, 1) * chi_max ** 3 * 8
    elif path == "D":
        memory = max_pauli_terms * 96
        work = max(num_gates, 1) * max_pauli_terms
    else:  # pragma: no cover - guarded by VALID_PATHS
        raise ValueError(path)
    memory, mem_sat = _saturate(memory)
    work, work_sat = _saturate(work)
    return {
        "estimated_peak_memory_bytes": memory,
        "estimated_work_units": work,
        "estimate_saturated": bool(mem_sat or work_sat),
    }


@dataclass
class ExecutionPlan:
    """Serializable dry-run plan. See module docstring for the contract."""

    schema_version: str
    input_digest: str
    normalized_circuit_digest: str
    num_qubits: int
    num_gates: int
    circuit_depth: int
    one_qubit_gate_count: int
    two_qubit_gate_count: int
    multi_qubit_gate_count: int
    non_clifford_count: int
    estimated_t_count: int
    interaction_graph_summary: Dict[str, Any]
    connectivity_summary: Dict[str, Any]
    estimated_entanglement_features: Dict[str, Any]
    measurement_and_dynamic_features: Dict[str, Any]
    candidate_paths: List[Dict[str, Any]]
    selected_path: Optional[str]
    selection_reason: str
    forced_path: Optional[str]
    estimated_peak_memory_bytes: Optional[int]
    estimated_work_units: Optional[int]
    known_hard_limits: List[Dict[str, Any]]
    unsupported_operations: List[str]
    required_result_contract: Optional[str]
    fallback_policy: Dict[str, Any]
    estimate_quality: str
    estimate_inputs: Dict[str, Any]
    refusal: Optional[Dict[str, str]]
    software_version: str
    plan_digest: str = field(default="")

    @property
    def would_execute(self) -> bool:
        return self.refusal is None and self.selected_path is not None

    def _body(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "software_version": self.software_version,
            "input_digest": self.input_digest,
            "normalized_circuit_digest": self.normalized_circuit_digest,
            "num_qubits": self.num_qubits,
            "num_gates": self.num_gates,
            "circuit_depth": self.circuit_depth,
            "one_qubit_gate_count": self.one_qubit_gate_count,
            "two_qubit_gate_count": self.two_qubit_gate_count,
            "multi_qubit_gate_count": self.multi_qubit_gate_count,
            "non_clifford_count": self.non_clifford_count,
            "estimated_t_count": self.estimated_t_count,
            "interaction_graph_summary": self.interaction_graph_summary,
            "connectivity_summary": self.connectivity_summary,
            "estimated_entanglement_features": self.estimated_entanglement_features,
            "measurement_and_dynamic_features": self.measurement_and_dynamic_features,
            "candidate_paths": self.candidate_paths,
            "selected_path": self.selected_path,
            "selection_reason": self.selection_reason,
            "forced_path": self.forced_path,
            "estimated_peak_memory_bytes": self.estimated_peak_memory_bytes,
            "estimated_work_units": self.estimated_work_units,
            "known_hard_limits": self.known_hard_limits,
            "unsupported_operations": self.unsupported_operations,
            "required_result_contract": self.required_result_contract,
            "fallback_policy": self.fallback_policy,
            "estimate_quality": self.estimate_quality,
            "estimate_inputs": self.estimate_inputs,
            "refusal": self.refusal,
            "would_execute": self.would_execute,
        }

    def compute_digest(self) -> str:
        blob = json.dumps(self._body(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        body = self._body()
        body["plan_digest"] = self.plan_digest
        return body

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, **kwargs)

    def explain(self) -> str:
        """Human-readable multi-line explanation."""
        lines = [
            f"Plan digest   : {self.plan_digest[:16]}  (schema {self.schema_version})",
            f"Circuit       : {self.num_qubits} qubits, {self.num_gates} gates, "
            f"depth {self.circuit_depth}, T-count {self.estimated_t_count}",
        ]
        if self.refusal is not None:
            lines.append(
                f"REFUSED       : [{self.refusal['code']}] {self.refusal['message']}"
            )
        else:
            lines.append(f"Selected path : {self.selected_path}")
            lines.append(f"Reason        : {self.selection_reason}")
            lines.append(
                f"Estimate      : ~{self.estimated_peak_memory_bytes} bytes, "
                f"~{self.estimated_work_units} work units "
                f"({self.estimate_quality}, not a guarantee)"
            )
        lines.append("Candidates    :")
        for cand in self.candidate_paths:
            if cand["capable"]:
                state = "capable"
            else:
                state = "NOT capable: " + "; ".join(cand["capability_blockers"])
            lines.append(f"  Path {cand['path']}: {state}")
            for note in cand["policy_notes"]:
                lines.append(f"      note: {note}")
        return "\n".join(lines)


def build_execution_plan(
    circuit: Any,
    *,
    forced_path: Optional[str] = None,
    require_counts: bool = False,
    max_memory_bytes: Optional[int] = None,
    analyzer: Optional[CircuitAnalyzer] = None,
    max_storage_mb: float = 5120.0,
    max_pauli_terms: int = 1024,
) -> ExecutionPlan:
    """
    Builds a dry-run plan for ``circuit``.

    Unparseable input raises the same ``UnsupportedCircuitInputError`` /
    ``QASMParseError`` as the router (a circuit nobody can read has no plan).
    Every other problem is reported as a typed ``refusal`` inside the plan.

    Args:
        circuit: Qiskit circuit, OpenQASM string or instruction list.
        forced_path: Mirrors ``preferred_path`` of ``route_and_execute``.
        require_counts: Mirrors the router flag; Path D cannot produce counts.
        max_memory_bytes: Optional caller budget. If the *selected* path's
            heuristic estimate exceeds it the plan refuses with
            ``RESOURCE_BUDGET``; no other path is substituted.
        analyzer: Optional pre-configured analyzer (router thresholds).
    """
    from cqhecs import __version__

    if max_memory_bytes is not None and max_memory_bytes <= 0:
        raise ValueError(f"max_memory_bytes must be > 0, got {max_memory_bytes}")
    analyzer = analyzer or CircuitAnalyzer()
    instructions, num_qubits = parse_circuit(circuit)
    props = analyzer.analyze_instructions(instructions, num_qubits)
    return _plan_from_props(
        circuit,
        instructions,
        num_qubits,
        props,
        forced_path=forced_path,
        require_counts=require_counts,
        max_memory_bytes=max_memory_bytes,
        analyzer=analyzer,
        max_storage_mb=max_storage_mb,
        max_pauli_terms=max_pauli_terms,
        software_version=__version__,
    )


def _capability_blockers(
    path: str,
    props: CircuitProperties,
    analyzer: CircuitAnalyzer,
) -> List[str]:
    """Reasons ``path`` cannot execute the normalised circuit (capability only)."""
    if path in props.supported_paths:
        return []
    blockers: List[str] = []
    if props.has_reset:
        blockers.append("reset is non-unitary and implemented by no path")
    if props.has_mid_circuit_measurement:
        blockers.append("mid-circuit measurement is implemented by no path")
    if props.unsupported_gates:
        blockers.append(
            "no backend implements: " + ", ".join(props.unsupported_gates)
        )
    supported = path_gate_names(path)
    missing = sorted(n for n in props.gate_counts if n not in supported)
    missing = [n for n in missing if n not in props.unsupported_gates]
    if missing:
        blockers.append(f"gate(s) outside this path's manifest: {missing}")
    if path in ("B", "D") and props.has_measurement:
        blockers.append("path does not support measurement instructions")
    if path == "A" and not missing and not blockers:
        blockers.append("circuit is not Clifford (non-Clifford angle or gate)")
    if path == "B" and props.num_qubits > PATH_B_MAX_QUBITS:
        blockers.append(
            f"{props.num_qubits} qubits exceeds the Path B ceiling "
            f"({PATH_B_MAX_QUBITS})"
        )
    if not blockers:
        blockers.append("arity/parameter signature outside the manifest entry")
    return blockers


def _policy_notes(
    path: str,
    props: CircuitProperties,
    analyzer: CircuitAnalyzer,
    selected: Optional[str],
) -> List[str]:
    """Why a *capable* path was not the router's first choice (cost/policy)."""
    notes: List[str] = []
    if path not in props.supported_paths or path == selected:
        return notes
    if path == "A" and not props.is_clifford:
        notes.append("circuit contains non-Clifford operations")
    if path == "B" and props.t_count > analyzer.t_rank_threshold:
        notes.append(
            f"T-count {props.t_count} exceeds the rank threshold "
            f"{analyzer.t_rank_threshold}"
        )
    if path == "C":
        if props.num_qubits > analyzer.max_mps_qubits:
            notes.append(
                f"{props.num_qubits} qubits exceeds the routing ceiling "
                f"{analyzer.max_mps_qubits}"
            )
        elif (
            props.max_cut_width > analyzer.mps_entanglement_threshold
            and props.num_qubits > 20
        ):
            notes.append(
                f"max cut width {props.max_cut_width} exceeds the entanglement "
                f"threshold {analyzer.mps_entanglement_threshold}"
            )
    if selected is not None and path != selected:
        order = VALID_PATHS.index
        if order(path) > order(selected):
            notes.append(f"lower priority than selected Path {selected} (A->B->C->D)")
    return notes


def _plan_from_props(
    circuit: Any,
    instructions: Sequence[Instruction],
    num_qubits: int,
    props: CircuitProperties,
    *,
    forced_path: Optional[str],
    require_counts: bool,
    max_memory_bytes: Optional[int],
    analyzer: CircuitAnalyzer,
    max_storage_mb: float,
    max_pauli_terms: int,
    software_version: str,
) -> ExecutionPlan:
    normalized = normalized_circuit_digest(instructions, num_qubits)
    adjacency, counts = _interaction_graph(instructions, num_qubits)
    cuts = _cut_crossings(instructions, num_qubits)

    # --- selection (same decision procedure as the router) ---------------
    refusal: Optional[Dict[str, str]] = None
    selected: Optional[str] = None
    reason = ""
    forced = forced_path.upper() if isinstance(forced_path, str) else None

    if props.has_reset:
        refusal = {
            "code": REFUSAL_DYNAMIC_CIRCUIT,
            "message": "reset is non-unitary and is not implemented by any path.",
        }
    elif props.has_mid_circuit_measurement:
        refusal = {
            "code": REFUSAL_DYNAMIC_CIRCUIT,
            "message": "mid-circuit measurement is not implemented by any path.",
        }
    elif props.unsupported_gates:
        refusal = {
            "code": REFUSAL_UNSUPPORTED_OPERATION,
            "message": "No backend implements: " + ", ".join(props.unsupported_gates),
        }
    elif forced_path is not None:
        if forced not in VALID_PATHS:
            refusal = {
                "code": REFUSAL_UNKNOWN_PATH,
                "message": f"Unknown path {forced_path!r}; valid paths are "
                f"{list(VALID_PATHS)}.",
            }
        elif forced not in props.supported_paths:
            blockers = _capability_blockers(forced, props, analyzer)
            refusal = {
                "code": REFUSAL_FORCED_PATH_UNSUPPORTED,
                "message": f"Path {forced} was forced but cannot execute this "
                f"circuit ({'; '.join(blockers)}). A forced path is never "
                "rerouted.",
            }
        else:
            selected = forced
            reason = f"Path {forced} was forced by the caller; capability verified."
    else:
        if props.recommended_path:
            selected = props.recommended_path
            reason = props.reason
        else:
            refusal = {
                "code": REFUSAL_NO_CAPABLE_PATH,
                "message": props.reason or "No path supports this circuit.",
            }

    if refusal is None and selected == "D" and require_counts:
        refusal = {
            "code": REFUSAL_COUNTS_UNAVAILABLE,
            "message": "Path D is an expectation-value backend and cannot "
            "produce joint bitstring counts, but counts were required.",
        }

    # --- candidates -------------------------------------------------------
    candidates: List[Dict[str, Any]] = []
    for path in VALID_PATHS:
        capable = path in props.supported_paths and not (
            props.has_reset or props.has_mid_circuit_measurement
        )
        est = _estimate_path(
            path,
            num_qubits=num_qubits,
            num_gates=len(instructions),
            t_count=props.t_count,
            cuts=cuts,
            max_pauli_terms=max_pauli_terms,
        )
        candidates.append(
            {
                "path": path,
                "capable": capable,
                "capability_blockers": (
                    [] if capable else _capability_blockers(path, props, analyzer)
                ),
                "policy_notes": _policy_notes(path, props, analyzer, selected),
                "chosen": path == selected and refusal is None,
                **est,
            }
        )

    chosen = next((c for c in candidates if c["chosen"]), None)
    if (
        refusal is None
        and max_memory_bytes is not None
        and chosen is not None
        and chosen["estimated_peak_memory_bytes"] > max_memory_bytes
    ):
        alternatives = [
            c["path"] for c in candidates if c["capable"] and not c["chosen"]
        ]
        refusal = {
            "code": REFUSAL_RESOURCE_BUDGET,
            "message": f"Path {selected} heuristic estimate "
            f"({chosen['estimated_peak_memory_bytes']} bytes) exceeds the "
            f"budget ({max_memory_bytes} bytes). No other path was substituted; "
            f"other capable paths: {alternatives or 'none'}.",
        }
        chosen["chosen"] = False

    hard_limits = [
        {"path": "B", "limit": "max_qubits", "value": PATH_B_MAX_QUBITS},
        {"path": "B", "limit": "t_rank_threshold", "value": analyzer.t_rank_threshold},
        {"path": "C", "limit": "max_mps_qubits", "value": analyzer.max_mps_qubits},
        {
            "path": "C",
            "limit": "mps_entanglement_threshold",
            "value": analyzer.mps_entanglement_threshold,
        },
        {"path": "C", "limit": "max_storage_mb", "value": max_storage_mb},
        {"path": "D", "limit": "max_pauli_terms", "value": max_pauli_terms},
        {"path": "D", "limit": "result", "value": "expectation_values_only"},
    ]

    effective = selected if refusal is None else None
    fallback_chain: List[str] = []
    if forced is None and effective in ("B", "C"):
        if effective == "B":
            fallback_chain = [p for p in ("C", "D") if p in props.supported_paths]
        else:
            fallback_chain = ["D"] if "D" in props.supported_paths else []
        if require_counts and "D" in fallback_chain:
            fallback_chain.remove("D")
    fallback_policy = {
        "forced": forced is not None,
        "runtime_fallback_chain": fallback_chain,
        "description": (
            "A forced path never reroutes."
            if forced is not None
            else "Runtime fallback only on documented capability limits "
            "(Path B rank budget, Path C memory ceiling); reported in "
            "result.metadata."
        ),
    }

    plan = ExecutionPlan(
        schema_version=PLAN_SCHEMA_VERSION,
        input_digest=_input_digest(circuit, normalized),
        normalized_circuit_digest=normalized,
        num_qubits=num_qubits,
        num_gates=len(instructions),
        circuit_depth=_circuit_depth(instructions, num_qubits),
        one_qubit_gate_count=counts["one_qubit_gate_count"],
        two_qubit_gate_count=counts["two_qubit_gate_count"],
        multi_qubit_gate_count=counts["multi_qubit_gate_count"],
        non_clifford_count=props.non_clifford_rotations
        + sum(
            n
            for g, n in props.gate_counts.items()
            if g in ("t", "tdg", "ccx", "toffoli", "ch", "cs", "csdg")
        ),
        estimated_t_count=props.t_count,
        interaction_graph_summary=_interaction_summary(adjacency, num_qubits),
        connectivity_summary={
            "is_clifford": props.is_clifford,
            "supported_paths": list(props.supported_paths),
        },
        estimated_entanglement_features={
            "max_cut_width": props.max_cut_width,
            "entanglement_estimate": props.entanglement_estimate,
            "max_cut_crossings_all_multiqubit_gates": max(cuts, default=0),
            "basis": "1D cut crossings in the logical qubit order",
        },
        measurement_and_dynamic_features={
            "has_measurement": props.has_measurement,
            "has_mid_circuit_measurement": props.has_mid_circuit_measurement,
            "has_reset": props.has_reset,
        },
        candidate_paths=candidates,
        selected_path=effective,
        selection_reason=reason if refusal is None else "",
        forced_path=forced if forced_path is not None else None,
        estimated_peak_memory_bytes=(
            next(c for c in candidates if c["path"] == effective)[
                "estimated_peak_memory_bytes"
            ]
            if effective
            else None
        ),
        estimated_work_units=(
            next(c for c in candidates if c["path"] == effective)[
                "estimated_work_units"
            ]
            if effective
            else None
        ),
        known_hard_limits=hard_limits,
        unsupported_operations=list(props.unsupported_gates),
        required_result_contract=_RESULT_CONTRACTS.get(effective) if effective else None,
        fallback_policy=fallback_policy,
        estimate_quality="heuristic",
        estimate_inputs={
            "num_qubits": num_qubits,
            "num_gates": len(instructions),
            "t_count": props.t_count,
            "max_cut_crossings": max(cuts, default=0),
            "max_pauli_terms": max_pauli_terms,
            "note": "Estimates are conservative heuristics derived only from "
            "these inputs; they are not guarantees and do not model backend "
            "swap routing or scratch I/O.",
        },
        refusal=refusal,
        software_version=software_version,
    )
    plan.plan_digest = plan.compute_digest()
    return plan


def plan_check(plan: ExecutionPlan, actual_path: str, elapsed_ms: float) -> Dict[str, Any]:
    """Post-execution record comparing the plan with what actually ran."""
    return {
        "plan_digest": plan.plan_digest,
        "planned_path": plan.selected_path,
        "actual_path": actual_path,
        "deviated": plan.selected_path != actual_path,
        "estimated_peak_memory_bytes": plan.estimated_peak_memory_bytes,
        "estimated_work_units": plan.estimated_work_units,
        "execution_time_ms": elapsed_ms,
        "note": "Calibration data only; it never alters later routing.",
    }
