---
name: openquantum-suite
description: Run CQ-HECS's preregistered 25-job real-QPU suite (r-io-7) on Open Quantum and evaluate hypothesis H-V3-8. Use when asked to run the real quantum reference runs, collect their results, or evaluate them.
---

# Open Quantum suite (r-io-7)

The circuits, split, model and hypothesis are fixed in
`research/v3/OPENQUANTUM_RUN_PLAN.md`. Do not edit circuits, seeds or the
split after a job has been submitted; that would void the preregistration.

## Requirements

- The `openquantum` skill (`oq.py`) on a machine that reaches
  `id.`, `scheduler.` and `management.openquantum.com` (`python oq.py doctor`
  passes). Cloud sandboxes usually cannot; use the person's computer.
- The key is stored with `oq.py setup` (stdin). Never write it into this
  repository, a script, a commit or a log.

## Steps

1. `python scripts/run_openquantum_suite.py generate`, then
   `git diff --exit-code research/v3/openquantum_suite` must be empty.
2. Pick a backend: `python oq.py backends --online`; at least 5 qubits.
3. `python scripts/run_openquantum_suite.py --oq <oq.py> quote -b <backend>`.
   This charges nothing. Show the per-job table and the total.
4. Wait for an explicit approval of the **total** in chat, then
   `... submit -b <backend> --budget <approved total> --yes`
   (add `--allow-full` only if the person approved paid Full credits).
5. Jobs that outlast the wait: `... collect -b <backend>` later.
6. `... evaluate -b <backend>` writes
   `research/v3/evidence/openquantum/<backend>/h_v3_8_evaluation.json`.
7. Record the verdict as measured (SUPPORTED, REJECTED or INCONCLUSIVE) in
   `research/v3/HYPOTHESES.md`, `V3_STABLE_PLAN.md` and `EXECUTION_LOG.md`.
   A negative result is reported, not retried with other settings.
8. When done: `python oq.py forget` and tell the person to rotate the key at
   https://www.openquantum.com/keys.

## Stop conditions

- OQ-03 does not return `00001`: the evaluation raises; investigate the
  backend's bit order, do not reverse strings by hand.
- Any QASM digest mismatch: stop.
- Results from two backends in one folder: stop; one backend per run.
