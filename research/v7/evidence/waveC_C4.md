# Wave C / C4: W15 documentation (docs match code and evidence)

Date: 2026-11-22. Owned area only (README EN/DE/FR, ARCHITECTURE.md, docs/*.md except the web, conformance,
packaging and provenance files, MIGRATION_V7.md, CHANGELOG.md Wave B/C entries, CITATION.cff content,
llms*.txt, RELEASE_NOTES_DRAFT.md, tests/test_doc_*.py). No git mutation, no QPU, no Open Quantum call, no
credential, no version bump (the version is written as the placeholder `<NEXT_MAJOR>`).

## What changed

| File | Change |
|---|---|
| `ARCHITECTURE.md` | marked the single authoritative document; new section 7 (service layer, B/C numerics, SAT additions, calibration v3, native, web, QG, Lean, Paths E/F/G) |
| `docs/ARCHITECTURE.md` | HISTORICAL / NOT AUTHORITATIVE banner pointing at the root file |
| `README.md`, `README.de.md`, `README.fr.md` | current-tree vs historical-lane verification tables with commit and evidence; stale 1669 count labelled historical; stale "4.0.0 / latest release v4.0.0" claims removed; interfaces, Studio, SAT, limitations, documentation table updated; EN/DE/FR numbers kept in sync |
| `docs/API_REFERENCE.md` | C return codes (ABI 1.1), service layer, OpenAPI, MCP negotiation/cancel/tools, typed MaxSAT |
| `docs/STUDIO.md` | bearer token model, `/api/v1`, `/api/openapi.json`, `/api/plan`, `/api/diagnostics`, QG routes and the 403 Open Quantum refusals |
| `docs/QUANTUM_GRAVITY_LAB.md` | UI surfaces, current route list, plan parity as present in the tree |
| `MIGRATION_V7.md` (new) | 5.0.0 to `<NEXT_MAJOR>`; BREAKING / BEHAVIOR / ADDITIVE per area; 8 python examples |
| `RELEASE_NOTES_DRAFT.md` (new) | implemented / experimental / measured / formally checked / not supported / not run |
| `CHANGELOG.md` | Wave B and Wave C (C4 only) entries |
| `CITATION.cff` | abstract and two keywords (version and date untouched) |
| `llms.txt`, `llms-full.txt` | refreshed; stale GPU, Path B, Path C, Path D and native SAT statements corrected |
| `tests/test_doc_consistency_v7.py` (new) | 63 tests (see below) |

## Defects found in the existing docs while verifying (fixed)

1. README SAT examples used `--cnf "p cnf ...\n..."`; in a POSIX shell the backslash-n stays literal and the DIMACS
   parser rejects it (`expected 'p cnf <vars> <clauses>'`, reproduced for `sat count`, `sat maxsat`). Now `$'...'`
   (reproduced working for `models`, `count`, `maxsat`). A test forbids the double-quoted form.
2. `docs/STUDIO.md` said there is no authentication and printed an old version; `v5.0.0` had no token (grep), so the
   token is a BREAKING change for scripted clients, now stated in `MIGRATION_V7.md`.
3. README claimed "all surfaces report 4.0.0" and "latest release is v4.0.0" while the tree is 5.0.0.
4. `llms.txt` said no physical GPU execution was verified (A2 ran primitive dispatch and a BCP differential on an AMD
   iGPU) and described Path D as Z/ZZ only.
5. `docs/QUANTUM_GRAVITY_LAB.md` and my own first drafts said QG plan parity and provider routes were absent; the tree
   now has `cq-hecs qg plan`, MCP `cqhecs_qg_plan`, Studio `/api/qg/v1/experiments/plan` and Open Quantum routes that
   only return a typed 403 (`QG_PAID_PATH_UNAVAILABLE`). Docs corrected to match the tree.

## Commands and results (Windows, Python 3.13.13, pytest 9.2.0)

| Command | Result |
|---|---|
| `python -m pytest tests/test_doc_consistency_v7.py -q` | 63 passed |
| `python -m pytest tests/test_doc_consistency_v7.py tests/test_readme_languages.py tests/test_llms_txt.py -q` | 76 passed |
| `python -m pytest tests -q -k "doc or consistency or llms or readme or architecture or four_path"` | 141 passed, 3 skipped (pre-existing skips), 4056 deselected |
| `python scripts/qg_doc_consistency.py` | OK |
| `python scripts/check_version.py` | OK (version surfaces unchanged; no bump) |
| `python -m pytest tests/test_qg_surface_parity.py -q` (read-only check of another agent's surface) | 49 passed |

Hand-run examples that appear in the docs: `cq-hecs --format json plan preset:bell` (plan digest, schema
`cqhecs.execution_plan/1`), `plan ... --force-path D --require-counts` (refusal `COUNTS_UNAVAILABLE`, rc 0),
`sat maxsat` (OPTIMAL, weight 2.0, `EXHAUSTIVE_ENUMERATION_REVERIFIED`; `--random 25` gives UNKNOWN, rc 0),
`run name:bell --backend B|C` (new metadata keys), an MCP `initialize` with `2025-06-18` (negotiated, tools list has
`outputSchema`, `cqhecs_plan` returns `structuredContent`), `CalibrationV3` round trip and the `measured` refusal.

## What the new test pins (and a negative control)

Executes every `python` block of `MIGRATION_V7.md`; `<NEXT_MAJOR>` present in the three documents that carry it and
absent from `cqhecs/**/*.py`, packaging files and schemas; the two new documents contain no dotted version other than
the "from" side; nine stale-claim regexes (a manual run of five sample stale strings matched all five, and the
correctly negated sentence in `ARCHITECTURE.md` does not match); no double-quoted `\n` DIMACS; one authoritative
architecture file; suite numbers in all three READMEs equal `waveA_A5.md` / `waveA_A2.md` / `BASELINE_V7.md`; every
OpenAPI route, QG route and MCP tool in code is documented and no unknown MCP tool is documented; MCP protocol
versions, MaxSAT contract, calibration schema/labels/policies and native ABI version equal the code; relative links and
cited evidence files resolve.

## NOT RUN / limits

- Full pytest suite, native build, web build, mutation suite, benchmarks: NOT RUN (instructed; docs only).
- `docs/WEB_ENGINES.md`, `CONFORMANCE.md`, `PACKAGING.md`, `PROVENANCE.md` are not mine and were not edited; the
  migration guide cites `docs/PROVENANCE.md` for `error_scope`.
- `docs/USAGE_GUIDE.md`, `docs/BENCHMARKS.md`, `docs/EMBEDDING_GUIDE.md`, `docs/OMNIWAVE.md`, `docs/UNIFIED_SOLVER.md`,
  `docs/V2_IMPLEMENTATION_MATRIX.md` were checked only for the double-quoted `\n` and the stale strings above, not
  re-audited line by line.
- The QG routes, MCP tools and CLI subcommands described here were read from the working tree while another agent was
  editing it (uncommitted). `tests/test_doc_consistency_v7.py` will fail if they change before the freeze; the
  integrator should re-run it after the last surface change.
- `schemas/studio.openapi.json` still contains the literal version string of the last release (generated; not mine).
- README/DE/FR still carry the literal last-release version in the wheel, sdist and zip names because
  `scripts/check_version.py` requires the current wheel name there; the integrator's version bump handles them.
- The German and French READMEs remain partial translations (product-relevant sections), as their header states.
- Browser/Studio rendering of any doc change was not checked.
