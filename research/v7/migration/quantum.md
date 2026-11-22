# Migration notes — quantum paths (stream Q, Wave 3)

## Path A shot counts are no longer silently truncated (D1, W3-01) — BREAKING

Before: `StabilizerTableauSimulator.sample` / `PathAStabilizerBackend` capped a wide
(`n > 30`) *non-all-equal* circuit at 100 re-measurements. A request for 1000 shots returned
100; the only hint was `result.metadata["sampled_shots"]`.

After: every requested shot is drawn. If `shots * num_qubits` exceeds `MAX_RESAMPLE_WORK`
(2,000,000) a `PathAShotBudgetError` (subclass of `ValueError`) is raised instead of truncating.

Caller action:
- If you relied on the ≈100-shot behaviour for speed, pass
  `PathAStabilizerBackend(max_resample_shots=100)` to opt back into truncated counts
  (still disclosed via `sampled_shots`), or reduce `shots`.
- If you catch `ValueError` around a wide sampling call, you now also catch the budget refusal.

The GHZ/all-equal fast path and `n <= 30` are unchanged.
