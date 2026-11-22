# W0 baseline (AGENTS_V6.md) — 2026-11-21

Exact checkout: `25e16e5c7054be09d6493b062f19f8476dbf2bcd` (`origin/main`, merge of PR #54),
branch `claude/repo-status-agents-v6-49d8ca`, clean worktree. The earlier
`BASELINE.md` is the v3.7.0→v4 record and is left unchanged (immutable history).

## Repository position

- `origin/main` = v5.0.0 (`scripts/check_version.py`: all surfaces 5.0.0). Tags v3.4.0…v5.0.0 exist.
- Every remote branch is an ancestor of `origin/main` (0 commits ahead): `agent/v4.0.0-foundation`,
  `release/4.1.0-public`, `release/4.2.0-sota`, `release/5.0.0-provenance`,
  `research/quantum-gravity-studio`, `dev/sha-forge-hardware-lab`, `feat/*-conformance*`, … .
  No unmerged work exists on any branch; old branches are cleanup candidates only (not deleted).
- `QGRAVITY.md` exists untracked in the primary checkout (user file, untouched).

## Gates (this checkout, Windows 11, Python 3.13.13, Node 22.23.1, CMake 4.4.0, Vulkan SDK 1.4.357)

| Gate | Result |
|---|---|
| `check_version.py`, `verify_no_silent_truncation.py` | PASS |
| `pytest tests/` | 2814 passed, 109 skipped, 1 deselected (290 s) |
| Web `npm ci`, `npm test`, `npm run build` | PASS; 61/61 unit; bundle budgets ok |
| Native configure/build Release + CTest | PASS; 21/21 |
| Playwright e2e, mutation suite, ASan/UBSan, clean-venv wheel | NOT RUN in W0 |

Skips: native-library/executable tests skip because the native build is not installed into
the Python lookup path (they pass-or-skip, no failure); `python-sat` and
`qiskit-ibm-runtime` optional extras not installed. No test deleted or relaxed.

## Open work (AGENTS_V6.md backlog)

Confirmed by source: `CMakeLists.txt` still `FATAL_ERROR`s on `CQ_ENABLE_VULKAN=OFF`
because public headers (`tensor_network.hpp`, `constraint_solver.hpp`) include
`cq_hecs/vulkan/vulkan_context.hpp` → `<vulkan/vulkan.h>`. T6-03 (W3) is therefore not started.
