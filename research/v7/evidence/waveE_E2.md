# Wave E / E2 - documentation freeze numbers

Owner: E2 (docs). Status: the numbers below are the freeze-SHA figures **recorded by the
integrator** in the E2 task; E2 did not re-run those suites (NOT_RUN by E2). They are the single
source that `tests/test_doc_consistency_v7.py` compares the three READMEs and the release notes
against. If `research/v7/evidence/waveE_E5.md` exists and states different numbers, that file
wins and this block must be corrected, not the READMEs alone.

Skip reasons are environmental (native build directory not set, optional extras absent); see
`research/v7/SKIP_BUDGET.json` for the per-reason breakdown (that file may predate the freeze
and counts a different total; the freeze breakdown belongs to `waveE_E5.md`).

```json
{
  "schema": "hcs.freeze_numbers.v1",
  "freeze_sha": "38e799b",
  "python": {"passed": 4314, "skipped": 133, "failed": 0},
  "mutation": {"killed": 95, "total": 95, "scope": "in place at the freeze SHA"},
  "web_unit": {"passed": 167, "total": 167},
  "refreshed": "python, web_unit, ctest_cpu, ctest_vulkan re-measured at HEAD f880d0a (wave F) - raw output in waveF_*.txt; mutation and playwright remain freeze-SHA 38e799b figures (NOT re-run)",
  "playwright": {"passed": 128, "skipped": 1, "skipped_reason": "WebGPU adapter absent (NOT_RUN)"},
  "studio_plan_ui": 6,
  "ctest_vulkan": {"passed": 26, "total": 26},
  "ctest_cpu": {"passed": 15, "total": 15},
  "artifacts_built_from": "38e799b"
}
```

## Other facts used by the docs

- Production web URL `https://cq-hecs-web.vercel.app`: read-only `curl -sI` on 2026-11-22 returned
  `HTTP/1.1 200 OK` anonymously (no protection page). `docs/WEB_ENGINES.md` records the same
  (protection disabled 2026-11-02; delivery check 10/10 anonymous, commit `e7e5c1e`). The
  `1d38df2` / `vercel curl` wording in the DE/FR READMEs was the older state and was aligned.
- Path B measured dominance: `research/v7/evidence/PATHB_DOMINANCE.json` (dense statevector
  faster on every measured case).
- Release asset: no `v7.0.0` tag or release is published; docs now say the standalone zip
  "will be attached to the release".
- `RELEASE_NOTES_DRAFT.md` was NOT renamed: `release.yml` and `scripts/check_version.py` read
  `RELEASE_NOTES.md` (still the 4.0.0 notes, outside E2's area) and tests reference the DRAFT
  name. Reported to the integrator: `RELEASE_NOTES.md` must be replaced at publication.
