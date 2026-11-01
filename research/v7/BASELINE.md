# CQ-HECS v4 baseline (M0/M1)

Recorded 2026-11-01 on the working checkout. Everything below was observed in
this session; nothing is copied from the v3.7.0 release report.

## Source state

| Item | Value |
|---|---|
| Base | `origin/main` = `78b970f` (merge of PR #42, v3.7.0 post-release audit) |
| Release tag | `v3.7.0` -> `6c18ad7` (ancestor of main) |
| Working branch | `agent/v4.0.0-foundation` (cut from `origin/main`, never `main`) |
| Pre-existing local files preserved | `.claude/launch.json` (untracked, not mine, left untouched) |
| Credential-bearing local file | `sdk-key-*.json` exists in the work tree; verified ignored by `.gitignore:74` and absent from `git ls-files`. Not read, not committed. |

`AGENTS.md` was untracked on arrival; it is the user's mission contract and is
committed on the feature branch unchanged.

## Toolchain

Python 3.13.13, Node v22.23.1, CMake 4.4.0, rustc/cargo 1.96.0, git 2.54.0
(Windows 11 Pro 10.0.26200). Python deps from `pip install -e ".[dev,benchmark]"`:
qiskit 2.6.1, qiskit-aer 0.18.2, stim 1.16.0, hypothesis 6.170.14, pytest 9.2.0,
flake8 7.5.0. `python-sat` (`.[sat]`) is **not** installed.

## Gates run against the unmodified v3.7.0 sources

| Gate | Result |
|---|---|
| `scripts/check_version.py` | PASS, all surfaces 3.7.0 |
| `scripts/verify_no_silent_truncation.py` | PASS |
| `compileall` (cqhecs, tests, scripts, python_bridge) | PASS |
| `flake8 --select=E9,F` | 0 findings |
| `pytest tests/` (non-slow) | **1964 passed, 13 skipped, 1 deselected, 2245 subtests passed**, 209 s |

Raw log: `evidence/baseline_pytest.txt`.

### Caveats

* The v3.7.0 audit recorded 1968 passed / 9 skipped. This run has 4 more skips
  and 4 fewer passes. The most likely cause is the absent optional
  `python-sat`/CaDiCaL adapter and optional native artifacts; this is **not yet
  verified** (skip reasons are collected with `-rs` in the next full run and
  recorded in `EXECUTION_LOG.md`). It is not counted as a regression until
  explained.
* The baseline pytest run started before the first v4 edit but the working tree
  was edited while it ran (router/CLI/MCP/Studio wiring). Collection had already
  imported the Python modules; subprocess-based tests (CLI) could have seen new
  code. The run passed in full, so no baseline failure is hidden, but the run is
  best read as "v3.7.0 + in-flight plan wiring", and the first clean-tree
  comparison is the milestone run recorded afterwards.

## Not run at baseline (status `NOT RUN`)

Native CMake/CTest (Vulkan SDK not verified present), shader verification,
web `npm ci/test/build/e2e`, mutation suite, Lean/Comparator/nanoda,
external DRAT/LRAT/cake_lpr checkers, OMNIWAVE benchmarks.
