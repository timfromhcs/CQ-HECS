# EXPERIMENT_PROTOCOL.md — preregistration protocol

## Phase gates (per QGRAVITY.md §3.2)

1. Generate QASM/model manifests, seeds and metadata deterministically (LF, UTF-8).
2. SHA-256 every circuit, model, config, transpiler output, calibration snapshot, manifest.
3. Store exact bytes submitted (post-transpile), not just the source.
4. Local correctness gates + Open Quantum simulator checks before any paid job.
5. Freeze `FIT`/`EVAL` groups; tune on `FIT`, evaluate once on `EVAL`.
6. Commit manifests + preregistration to the feature branch before paid jobs.
7. Never edit a submitted circuit or criterion after seeing results.

## Spend gates (per §4.4.1)

Before the first paid job, record: organisation, Spark balance, Full balance, backend live
`QPU` type, plan `public`, priority `standard`, per-job quotes, proposed total, remaining
Spark. Maintain `QUOTE_LEDGER.json` (write-ahead) + `JOB_LEDGER.jsonl` (append-only).
Enforce `submitted/charged + next ≤ min(25.0, available Spark)` **in the runner**, not only
in the SDK/MCP. `auto_approve_quote=False`. Reconcile remote jobs on any ambiguity.

## Lifecycle

`DISCOVER → QUOTE → REVIEW → SUBMIT → QUEUED/RUNNING → COLLECT → VERIFY → ANALYSE → ARCHIVE`
(`doctor/discover/generate/validate/quote/submit/collect/analyse/report` as CLI verbs).

## Statistical plan

- Preserve raw integer counts; never average rounded probabilities.
- Deterministic bootstrap seed; resampling unit explicitly stated (circuits, not shots).
- Holm correction across sweeps; report effect sizes and CIs.
- Keep error classes separate and nullable: numerical, approximation/Trotter, shot,
  device-noise-model, calibration-uncertainty.
- Missing/failed jobs are missing data; never synthesise a complete table.

## Evidence immutability

- Raw results are append-only; processed results reference the raw file hash.
- Time stamps UTC ISO-8601; store calibration retrieval time + content hash + gap to run.
- A rerun is a new attempt id referencing the previous attempt; never overwrite raw output.
