# Provenance cards (`hcs.run.v2`)

One contract for "what was run, by what, with which reproducibility data, and with what
limits" - written by the CLI, the Studio export and the browser, checked by one schema.

- Schema: [`provenance/hcs.run.v2.schema.json`](provenance/hcs.run.v2.schema.json)
- Python: `cqhecs/provenance.py` (`build`, `validate`, `read`)
- Browser: `web/src/provenance.ts` (`buildRunCard`)
- CLI: `cq-hecs sat solve … --provenance card.json`

## Why a card at all

A result without its input digest cannot be reproduced, and a result without its limits
invites over-reading. The card makes three things impossible to separate by accident:

| Question | Field |
|---|---|
| What exactly was run? | `input.payload` and `input.digest` (SHA-256 over that same text) |
| By what? | `engine.kind`, `engine.precision`, `engine.mode` |
| Reproducible? | `seed`, `software.version`, `software.source_revision` |
| What does it not claim? | `limits[]` |

The digest is always over the payload **stored in the card**, so a card can be verified
without the original file, an e-mail attachment or a second machine.

## The three error kinds

They are separate fields and they may be `null`. `null` means *not quantified*, never
*zero*:

| Field | Meaning |
|---|---|
| `result.error.approximation` | deliberate approximation (discarded terms, rank cut) |
| `result.error.numerical` | floating-point roundoff |
| `result.error.sampling` | finite-shot sampling error |

A single "error" number would invite adding quantities that do not share a metric. The
Python `SimulationResult` keeps the same separation for the same reason.

## Example (CLI, SAT)

```bash
cq-hecs sat solve --cnf formula.cnf --engine unified --provenance card.json
```

```json
{
  "schema": "hcs.run.v2",
  "created_at": "2026-11-02T13:40:00Z",
  "software": { "name": "cqhecs", "version": "5.0.0", "source_revision": "…" },
  "input": {
    "kind": "cnf",
    "payload": "p cnf 2 4\n…",
    "digest_algorithm": "SHA-256",
    "digest": "9f2c…"
  },
  "engine": { "kind": "unified", "precision": "exact-integer", "mode": "EXACT" },
  "seed": null,
  "result": {
    "status": "UNSAT",
    "elapsed_ms": 0.16,
    "error": { "approximation": null, "numerical": null, "sampling": null },
    "decided_by": "watched",
    "attempts": [ … ]
  },
  "limits": [
    "SAT/UNSAT refers to this formula only; UNKNOWN is a timeout, not a proof.",
    "The digest covers the DIMACS text in input.payload."
  ]
}
```

The browser writes the same shape with `input.kind: "circuit"`, the QASM text as payload,
`engine.precision: "f64"` for the WebAssembly path and `"f32"` for WebGPU, and
`engine.mode: "SAMPLED"` or `"NOISY_CLASSICAL"`.

## What the validator refuses

Each of these has a test in `tests/test_provenance.py` and
`web/tests/provenance.test.ts`:

- a payload that does not match its digest;
- a missing required field;
- an unknown schema, including the v1 web cards (`cqhecs.web.run/1.0` and `/1.1`), which
  are **refused with a pointer to regenerate**, never silently re-read as v2;
- a negative error bound;
- an empty payload or an empty `limits` list;
- a payload above 4 MiB: refused instead of truncated, because a truncated card is worse
  than no card.

## What it does not do

- It does not prove the run happened; it records what the software says it did, with a
  digest that makes tampering visible to anyone who has the payload.
- It does not turn `UNKNOWN` into evidence. A card can carry `status: "UNKNOWN"`.
- It does not cover the miner/SHA Forge research path yet; that path has its own records
  under `research/sha_forge/`.
