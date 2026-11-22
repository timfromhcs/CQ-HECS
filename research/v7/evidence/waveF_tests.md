# Wave F / tests - skip-budget test, fresh numbers, non-circular doc gates

Tree: branch `release/v7-stable`, HEAD `f880d0a` plus an uncommitted working tree that other wave-F
agents were editing concurrently (so the Python count is tree-state dependent: 4298 before the wave-F
test additions of this slice, 4314 in the final run below). Windows 11, Python 3.13.13 (the "default"
skip-budget environment, but `web/node_modules` was present), MSVC 2022 + Vulkan SDK. Nothing committed,
pushed, tagged or published. No test was skipped, weakened or deselected by this slice.

## Raw outputs (these files are parsed by tests/test_doc_consistency_v7.py)

| File | What it is |
|---|---|
| `waveF_pytest_tail.txt` | last line of `python -m pytest tests -q`: `4314 passed, 133 skipped, 1 deselected in 610.56s` |
| `waveF_skip_reasons.json` | `python scripts/skip_budget.py --junitxml <that run's junit>` (133 skips by reason) |
| `waveF_web_unit_tail.txt` | tail of `npm test` (`node tests/run.mjs`): 167 pass / 0 fail |
| `waveF_ctest_cpu.txt` | `ctest -C Release` of a fresh `-DCQ_ENABLE_VULKAN=OFF` build: 15/15 |
| `waveF_ctest_vulkan.txt` | `ctest -C Release` of a fresh `-DCQ_ENABLE_VULKAN=ON` build: 26/26 |

Build dirs were in the session scratchpad, not the repo. Both `cmake --build --config Release`
runs exited 0.

## Results

* Full Python suite: **4314 passed, 133 skipped, 1 deselected, 0 failed** (run 2, 10 min). Run 1
  (started before this slice's tests were added) gave 4298 passed / 133 skipped in 22 min (it was
  slowed by concurrent native builds). 0 failures in both.
* Skip budget: `skip_budget.py --check` on both junit files -> OK (133). It is one below the 134
  budgeted: the Studio-plan-UI skip ("node or web/node_modules ...") did not occur because
  `web/node_modules` exists here. Fewer skips are allowed; the budget was not lowered.
* Web unit: 167/167. CTest CPU 15/15, Vulkan 26/26 (the recorded 21/21 in `native_ctest.txt` is the
  older v4 file).
* Differences vs the E2 freeze block (38e799b): Python 4269/134 -> 4314/133 (HEAD has more tests);
  web unit, CTest counts unchanged. The block in `waveE_E2.md`, the three READMEs, both release-notes
  files and the pinned test were updated together. Mutation (95/95) and Playwright (128/1) were NOT
  re-run here and stay freeze-SHA figures.

## Tests added

* `tests/test_skip_budget.py` (+5): `--environment` selects its ceilings, a reason absent from an
  environment has budget 0, strict `with_native` accepts only budgeted skips, unknown environment is
  refused, and the committed `SKIP_BUDGET.json` is internally consistent (top-level == `default`,
  totals equal the sum of reasons, no native/Vulkan reason budgeted in `with_native`).
* `tests/test_doc_consistency_v7.py` (+4, non-circular): the freeze JSON block and the READMEs are now
  compared with the parsed raw tool output above (pytest summary, TAP, ctest, skip JSON), not with
  each other; the fresh skip reasons must fit the default budget. Verified to bite: changing the raw
  pytest line to 4299 made two of them fail; restored.

## NOT_RUN

Playwright / axe, mutation suite, Lean, PyInstaller exe smoke (`CQ_HECS_EXE`), py3.14 with-native
Python lane, external DRAT/LRAT/cake_lpr checkers, python-sat. The `with_native` skip budget was not
re-measured.
