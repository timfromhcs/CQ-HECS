# Migrating from 5.0.0 to 7.0.0

There is no 6.x release: 6 was only an internal planning label, so the upgrade goes from
5.0.0 straight to 7.0.0. This guide lists every caller-visible change since the last released major
(`MIGRATION_V5.md` covers the release before it), grouped by area. Each change is marked:

* **BREAKING**: code that worked before can now fail or return something different.
* **BEHAVIOR**: the same call returns a more honest value; read the new field.
* **ADDITIVE**: new field, command or route; nothing existing changed.

No API was deprecated with a runtime `DeprecationWarning` in this cycle. Where a newer
call supersedes an older one, the older one is named as "superseded" and still works.

Every `python` block below is executed by `tests/test_doc_consistency_v7.py`
(`test_every_python_example_in_the_migration_guide_runs`), so an example cannot drift from
the code. The shell commands were run by hand on the same tree
(`research/v7/evidence/waveC_C4.md`).

## Summary

| Area | Change | Kind |
| :--- | :--- | :--- |
| Path A | Wide sampling draws every requested shot or raises `PathAShotBudgetError` | **BREAKING** |
| Studio API | Every `/api` call needs a bearer token, an allowed Host and JSON bodies | **BREAKING** (for scripted clients) |
| Native C ABI | New refusal codes; a SAT timeout is `3`, no longer UNSAT-shaped | **BREAKING** (for C callers) |
| MaxSAT | `cq-hecs sat maxsat` and `max_sat_checked` return the typed `hcs.sat.maxsat.v1` | **BEHAVIOR** |
| Unified SAT | `certified`, `proof_level`, `require_certified`; `attempts[].proof` is honest | **BEHAVIOR** |
| Noisy runs | Gates with no calibrated channel are listed in `uncovered_gates` | **BEHAVIOR** |
| Synthetic profiles | `capture_timestamp` is `None` | **BEHAVIOR** |
| Paths B and C | Error-story metadata; `numerical_error_bound` still `None` | ADDITIVE |
| Run card | `error_scope` explains each null error kind | ADDITIVE |
| ExecutionPlan | `cq-hecs plan`, shared service, OpenAPI, `/api/v1` | ADDITIVE |
| MCP | Protocol negotiation, `structuredContent`, cancel, concurrency cap | ADDITIVE (legacy shape unchanged) |
| Calibration | Schema `cqhecs.calibration/3.0` | ADDITIVE |
| Quantum Gravity | `cq-hecs qg`, MCP `cqhecs_qg_*`, `/api/qg/v1`, web and Studio labs | ADDITIVE |
| Doctor | New `sat_solver` check | ADDITIVE |

## Quantum paths

### Path A shot counts are no longer silently truncated (BREAKING)

Before, a wide (`n > 30`) circuit that was not all-equal was capped at 100
re-measurements, so asking for 1000 shots returned 100. Now every requested shot is drawn,
or the call raises `PathAShotBudgetError` (a `ValueError` subclass) when the estimated work
exceeds `MAX_RESAMPLE_WORK`.

```python
from cqhecs.backends.path_a_stabilizer import (
    MAX_RESAMPLE_WORK, PathAShotBudgetError, StabilizerTableauSimulator,
)

sim = StabilizerTableauSimulator(32)
for q in range(32):
    sim.apply_h(q)
counts, drawn = sim.sample(shots=250, seed=1)
assert drawn == 250 and sum(counts.values()) == 250      # nothing is dropped

try:
    sim.sample(shots=MAX_RESAMPLE_WORK, seed=1)           # too much work: refused
except PathAShotBudgetError:
    pass
else:
    raise AssertionError("expected a typed refusal")

# Opt back in to truncated counts, still disclosed through the returned shot count:
capped = StabilizerTableauSimulator(32, max_resample_shots=5)
for q in range(32):
    capped.apply_h(q)
counts, drawn = capped.sample(shots=10, seed=1)
assert drawn == 5
```

Caller action: if you relied on the 100-shot cap for speed, pass
`PathAStabilizerBackend(max_resample_shots=100)` or reduce `shots`. If you catch
`ValueError` around a wide sampling call you now also catch the budget refusal.

### Paths B and C: more metadata, the same bounds (ADDITIVE)

`numerical_error_bound` is still `None` for both paths. `None` means "not derived", never
zero. The new metadata explains what was measured instead:

```python
import io, json
from contextlib import redirect_stdout
from cqhecs.cli import main

def cli(*argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()

code, text = cli("--format", "json", "run", "name:bell", "--backend", "C", "--shots", "100", "--seed", "1")
result = json.loads(text)["result"]
meta = result["metadata"]
assert code == 0 and result["numerical_error_bound"] is None
assert meta["numerical_error_bound_reason"].startswith("not derived")
assert {"svd_count", "max_discarded_relative", "numerical_rank_truncation_applied"} <= set(meta)

code, text = cli("--format", "json", "run", "name:bell", "--backend", "B", "--shots", "100", "--seed", "1")
meta = json.loads(text)["result"]["metadata"]
assert {"born_norm_sum", "renormalization_applied", "discarded_branch_count"} <= set(meta)
```

Path B `error_bound` is the dropped-branch weight and nothing else; float64 round-off can
exceed it (observed 1.1e-13 against a dropped mass of 2.4e-16), which is why it is not a
numerical bound. See `research/v7/NUMERICS_B_C.md` for the proven-versus-tested split.

### Run card: `error_scope` (ADDITIVE)

The `hcs.run.v2` document gains an optional `error_scope` object: one plain-language reason
per error kind explaining why a null error is null (`docs/provenance/hcs.run.v2.schema.json`,
`docs/PROVENANCE.md`). The schema id did not change; consumers that ignore unknown keys
are unaffected.

## ExecutionPlan, service layer, OpenAPI (ADDITIVE)

`cq-hecs plan` and `cqhecs.service.plan_document` produce the same
`cqhecs.execution_plan/1` document as MCP `cqhecs_plan` and Studio `/api/plan`. A refusal is
a successful plan with `selected_path: null`, `would_execute: false` and a `refusal` object;
it is not a process error.

```python
import json
from cqhecs import service
from cqhecs.cli import main
import io
from contextlib import redirect_stdout

plan = service.plan_document("preset:bell")
assert plan["schema_version"] == "cqhecs.execution_plan/1" and plan["selected_path"] == "A"

refused = service.plan_document("preset:bell", force_path="D", require_counts=True)
assert refused["selected_path"] is None and refused["would_execute"] is False
assert refused["refusal"]["code"] == "COUNTS_UNAVAILABLE"

out = io.StringIO()
with redirect_stdout(out):
    code = main(["--format", "json", "plan", "preset:bell"])
envelope = json.loads(out.getvalue())
assert code == 0 and envelope["plan"]["plan_digest"] == plan["plan_digest"]
```

The CLI wraps the plan in `{"plan": ..., "schema_version": "1.0", "version": ...}`; Studio
wraps it in `{"schema_version": "1.0", "plan": ...}`. The plan digest is the same on every
surface. Estimates in the plan are heuristics (`estimate_quality: "heuristic"`).

## SAT

### Typed MaxSAT (BEHAVIOR)

`cq-hecs sat maxsat` now returns contract `hcs.sat.maxsat.v1` through
`cqhecs.sat.max_sat_checked`. `status` is `OPTIMAL` only when exhaustive enumeration ran
(at most 20 variables) and the optimum was recomputed from the returned assignment. Above
the limit the result is `UNKNOWN` with `limit_reached: true`, `assignment: null` and
`trust: "NONE"`; the call returns normally (exit code 0) and **no optimum is claimed**.
`optimality_certificate` is always `null`: the claim rests on enumeration, not on a proof.

```python
from cqhecs.sat import parse_dimacs, max_sat, max_sat_checked, random_3sat

ok = max_sat_checked(parse_dimacs("p cnf 2 2\n1 0\n-1 0\n"), [1.0, 2.0])
assert ok["contract"] == "hcs.sat.maxsat.v1" and ok["status"] == "OPTIMAL"
assert ok["satisfied_weight"] == 2.0 and ok["assignment"] == {1: False, 2: False}
assert ok["trust"] == "EXHAUSTIVE_ENUMERATION_REVERIFIED"
assert ok["optimality_certificate"] is None and ok["limit_reached"] is False

big = max_sat_checked(random_3sat(25, 100, seed=1))
assert big["status"] == "UNKNOWN" and big["limit_reached"] is True
assert big["assignment"] is None and big["satisfied_weight"] is None and big["trust"] == "NONE"

# Superseded, still works: the older function raises above the limit.
try:
    max_sat(random_3sat(25, 100, seed=1))
except ValueError:
    pass
else:
    raise AssertionError("max_sat must refuse above 20 variables")
```

Shell, run by hand (the `$'...'` form passes real newlines; a double-quoted `"\n"` stays a
literal backslash-n in a POSIX shell and the DIMACS parser rejects it):

```bash
cq-hecs --format json sat maxsat --cnf $'p cnf 2 2\n1 0\n-1 0\n' --weights 1,2
cq-hecs --format json sat maxsat --random 25          # UNKNOWN, limit_reached: true
```

Caller action: read `status` before `assignment`. A consumer that assumed a non-null
assignment on every exit-code-0 run must handle `UNKNOWN`.

### Unified solver: what an UNSAT is backed by (BEHAVIOR)

`UnifiedResult` gained `certified` and `proof_level` (`MODEL_VERIFIED`,
`TREE_RESOLUTION_CHECKED`, `DRAT_CHECKED`, `UNCERTIFIED`, `REJECTED`, `NONE`).
`solve_unified(..., require_certified=True)` records an uncertified UNSAT as `UNKNOWN` and
keeps searching. `attempts[].proof` no longer says "DRAT proof checked" for a proof that
was rejected, undecided or never produced; it reads `UNCERTIFIED: ...`. `SATResult` gained
`proof_status` (`accepted`, `rejected`, `undecided`, `disabled`, `None`).

```python
from cqhecs.sat import parse_dimacs
from cqhecs.unified import solve_unified

unsat = parse_dimacs("p cnf 1 2\n1 0\n-1 0\n")
strict = solve_unified(unsat, require_certified=True).to_dict()
assert strict["status"] in ("UNSAT", "UNKNOWN")
assert strict["status"] != "UNSAT" or (strict["certified"] and strict["proof_level"] != "UNCERTIFIED")
```

Caller action: a consumer that treated `UNSAT` plus a non-null `attempts[].proof` as "proof
checked" must read `certified` and `proof_level` instead.

### CaDiCaL isolation and the doctor check (ADDITIVE)

`cqhecs.sat_external.solve_external_isolated` runs the raw solve in a child process and
re-verifies the model and the DRAT proof in the parent. A child that crashes without a
result gives `UNKNOWN`; a complete result followed by an abnormal exit is re-verified and
carries a warning in `note`. `cq-hecs doctor` reports a `sat_solver` check
(`available` / `not_available`). `python-sat` remains an optional extra
(`pip install cqhecs[sat]`).

### Separator counting preflight (ADDITIVE)

`count_by_elimination(preflight=True)` returns `UNKNOWN` before any table is allocated when
the predicted bound `2^(w+1)` exceeds the budget. The default call is unchanged.

## Noise and calibration

### Uncovered gates are no longer silently noiseless (BEHAVIOR)

The noise model is built from the profile's `gate_errors` and `basis_gates`; circuits are
not transpiled into that basis. A gate the profile never declared used to run with no
channel while the result was labelled `NOISY_CLASSICAL`. Now:

```python
import pytest
from cqhecs.hardware_bridge import FakeHardwareBackend, OutOfModelError, create_linear_profile

circuit = [("h", [0], []), ("cx", [0, 1], [])]
warned = FakeHardwareBackend(create_linear_profile(2)).run(circuit, shots=64, seed=1)
assert warned.uncovered_gates == ["h"]                         # default policy "warn"
assert warned.metadata["uncovered_gate_policy"] == "warn"

strict = FakeHardwareBackend(create_linear_profile(2), uncovered_gate_policy="refuse")
with pytest.raises(OutOfModelError):
    strict.run(circuit, shots=64, seed=1)                      # fails closed, before simulating
```

Caller action: a circuit that ran before still runs under the default `warn`; read
`result.uncovered_gates` to know which gates had no channel, or pass
`uncovered_gate_policy="refuse"` to fail closed.

### Synthetic profiles carry no timestamp (BEHAVIOR)

`create_linear_profile` no longer stamps `capture_timestamp` with the current time; it is
`None`, so two calls serialise identically and a synthetic profile cannot be mistaken for a
dated device calibration.

### Calibration schema v3 (ADDITIVE)

`cqhecs.calibration/3.0` wraps an unchanged `BackendProfile` (schema 1.0 or 2.0 files are
not rewritten; there is no on-disk migration). Provenance label, freshness and the gate
policy are explicit; `measured` is refused for a synthetic profile.

```python
from cqhecs.calibration_v3 import CalibrationV3
from cqhecs.hardware_bridge import InvalidProfileError, create_fake_manila_profile
import pytest

profile = create_fake_manila_profile()
record = CalibrationV3.from_profile(profile, max_age_hours=24)
document = record.to_dict()
assert document["schema"] == "cqhecs.calibration/3.0"
assert document["provenance_label"] == "synthetic"
assert record.freshness()["status"] == "unknown"               # never defaulted to fresh
assert CalibrationV3.from_dict(document).backend_identity == record.backend_identity

with pytest.raises(InvalidProfileError):
    CalibrationV3.from_profile(profile, provenance_label="measured")
```

A v3 record describes a model input. It is not evidence that the model predicts a device,
and it is not yet shown in the CLI or Studio. Transpilation into the calibrated basis and a
VALIDATION split are not implemented.

## MCP (ADDITIVE; legacy shape unchanged)

`initialize` negotiates `protocolVersion` among `2025-06-18`, `2025-03-26` and
`2024-11-05`; a client that sends none gets the previous behaviour byte for byte.
`2025-03-26` adds tool `annotations`; `2025-06-18` adds `title`, `outputSchema` and
`structuredContent` with a JSON text mirror in `content`. Tool calls run on worker threads;
`notifications/cancelled` answers once with `status: CANCELLED` and `verdict: null`
(this deviates from the specification's "should not respond" and the compute is abandoned,
not stopped); at most 8 calls run at once (`SERVER_BUSY`, reported as `UNKNOWN`); `timeout`,
`waves`, `workers`, `limit` and `node_budget` are bounded. New tools: `cqhecs_plan`,
`cqhecs_qg_catalog`, `cqhecs_qg_circuit_preview`, `cqhecs_qg_run_local`.

Caller action: none for existing clients. A client that wants structured results sends
`protocolVersion: "2025-06-18"` and reads `structuredContent`.

## Studio HTTP API (BREAKING for scripted clients)

Every `/api` route now requires `Authorization: Bearer <token>`, an allowed Host, no foreign
Origin and `application/json` POST bodies (rejected bodies are drained under a deadline).
Before, the loopback API had no token. The page keeps working because `cq-hecs studio`
prints a URL whose fragment carries the per-launch token. Scripts must read the token
(or set `CQ_HECS_STUDIO_TOKEN` / `CQ_HECS_STUDIO_TOKEN_FILE` to choose it, in which case it
is not embedded in the URL).

Additive: `/api/v1/<x>` answers every `/api/<x>` route with the same guard; the original
paths are unchanged. `GET /api/openapi.json` serves `schemas/studio.openapi.json`
(OpenAPI 3.1). `POST /api/plan` is new. The Quantum Gravity routes live under `/api/qg/v1`.

## Native C ABI (BREAKING for C callers)

Both libraries export an ABI version (1.1): `cq_abi_version()` / `cq_check_abi(1, 1)` and
`cq_core_abi_version()` / `cq_core_check_abi(1, 1)`. Call the check first.

| Entry point | Before | Now |
| :--- | :--- | :--- |
| `cq_solve_sat` timeout | returned `10` (UNSAT-shaped) | returns `3`, `satisfiable = -1`; **no verdict** |
| `cq_create_context` / `cq_create_simulator` | could throw across the C boundary for absurd sizes | returns `NULL` (qubits above 4096, bond dimension above 65536) |
| core `cq_execute_qasm` on a simulator wider than 16 qubits with T, Tdg or RZ | returned a 16-bit bitstring with rc 0 | refused before any gate runs |
| `cq_apply_*` | unchecked qubit indices, NaN angles cast to integers | range, duplicate and finite checks; a refused call changes no state |
| core gate after measure, RX/RY | skipped | refused |
| `cq_omniwave_bcp_eval` | unvalidated clause data; failed readback left `out_status` unwritten with rc 0 | validated on the host (`1`, `2`, `4`); `-5` device lost, `-6` readback failed, output never half-written |
| input size | unlimited | `-5` above 64 MiB (16 MiB in the core QASM entry) |

Caller action: treat `3` from `cq_solve_sat` as "unknown", never as UNSAT; always check the
pointer returned by the create functions; on `-5` from the BCP call fall back to the CPU
reference. `cq_core_build_capabilities()` is unchanged.

## Quantum Gravity Lab (ADDITIVE)

`cq-hecs qg catalog | preview | run-local | plan | export | compare | backends`, MCP
`cqhecs_qg_*`, Studio tab 08 and the web route `#/qg`. Everything runs on a classical
reference. The Open Quantum routes and MCP tools exist only to return the typed refusal
`QG_PAID_PATH_UNAVAILABLE` (HTTP 403 in Studio); no surface can quote, submit or spend.

```python
import io, json
from contextlib import redirect_stdout
from cqhecs.cli import main

out = io.StringIO()
with redirect_stdout(out):
    code = main(["--format", "json", "qg", "run-local", "--theta", "0.5"])
payload = json.loads(out.getvalue())
assert code == 0 and payload["execution_surface"] == "CLASSICAL_REFERENCE"
assert abs(payload["observables"]["concurrence"] - abs(__import__("math").sin(0.5))) < 1e-12
```

`theta` is a model parameter, not a physical mass or separation; a request for a physical
mapping is a typed refusal (`QG_NO_DIMENSIONAL_MODEL`).

## Browser

The WebGPU path now falls back to the WASM core when a device is lost, and the run card
labels the fallback; WebGPU refusals carry a stable code; one noise predicate drives the
simulator, the planner and the run card (a run with per-qubit readout error or X bit flips
can no longer export as `SAMPLED`). See `docs/WEB_ENGINES.md`.

## What did not change

The four paths, the gate manifest, the `SimulationResult` field names, the `hcs.run.v2`
schema id, the SAT result contract (`1.2`), the CLI JSON `schema_version` (`1.0`) and the
legacy MCP wire shape. The deferred and research-only items (Paths E, F and G, CDCL,
transpilation-aware noise models, GPU speedups) are not shipped: see
`RELEASE_NOTES_DRAFT.md` for the status of each.
