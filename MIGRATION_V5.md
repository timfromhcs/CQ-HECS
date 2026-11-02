# Migrating from v4.2.0 to v5.0.0

v5.0.0 introduces one provenance contract, `hcs.run.v2`, for the CLI, the Studio export and
the browser. It is a major version because a document that used to be written in one shape
(`cqhecs.web.run/1.1`) now has a different shape and a different schema id.

## Browser run card: `cqhecs.web.run/1.1` → `hcs.run.v2`

The exported JSON from **Export** in the lab changed. Old and new cards are both readable,
but they are not the same document, and the validator refuses to reinterpret one as the
other.

| v1 (`cqhecs.web.run/1.1`) | v2 (`hcs.run.v2`) |
|---|---|
| `schema: "cqhecs.web.run/1.1"` | `schema: "hcs.run.v2"` |
| `app_version` | `software.version` |
| `source_revision` | `software.source_revision` |
| `input.qasm` | `input.payload` |
| `input_digest` | `input.digest` (`digest_algorithm: "SHA-256"`) |
| `input.shots`, `input.engine`, `input.noise` | same fields inside `input` |
| seed implicit / absent | `seed` (top level, integer or `null`) |
| `engine.kind`, `engine.precision` | same, plus `engine.mode` (`SAMPLED`, `NOISY_CLASSICAL`, …) |
| `result` (raw engine result) | `result.status`, `result.elapsed_ms`, `result.error{approximation,numerical,sampling}`, plus the raw fields |
| `limitations` | `limits` |

### Reading an old card

```python
from cqhecs import provenance
provenance.validate(old_document)   # -> refuses with "regenerate it"
```

The refusal is deliberate: a v1 card has no `input.payload`, so its digest cannot be
reproduced from the card alone. Regenerate it from the run, or read it with your own v1
reader.

## CLI

`cq-hecs sat solve` gained `--provenance PATH`. It is additive: without the flag nothing
changes, including the existing `--json-out` document.

```bash
cq-hecs sat solve --cnf formula.cnf --engine unified --provenance card.json
```

The `--json-out` document keeps `schema_version: "1.0"` and its current fields; the card is
a separate artefact with its own schema.

## Python

New module `cqhecs.provenance`:

```python
from cqhecs import provenance

card = provenance.build(
    software=provenance.Software("cqhecs", "5.0.0", provenance.source_revision()),
    input_kind="cnf", payload=dimacs_text,
    engine_kind="dpll", precision="exact-integer", mode="EXACT",
    status="UNSAT", elapsed_ms=1.2, limits=["SAT/UNSAT refers to this formula only."],
)
card.write("card.json")
provenance.validate(card.to_dict())   # []
```

Nothing existing was removed or repurposed. `SimulationResult`, its three error fields and
the CLI JSON shapes are unchanged.

## Not in this release

- No card for the circuit-simulation CLI path yet (SAT and the browser are wired; the
  circuit path is the next step and is listed as such in `PLAN_HORIZON_8_V5.md`).
- No Studio endpoint for cards; the Studio can call `cqhecs.provenance` directly.
- The SHA Forge research records keep their own schema (`research/sha_forge/`).
