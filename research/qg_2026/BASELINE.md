# BASELINE.md — repository & environment baseline (M0)

Recorded 2026-11-21 on branch `research/quantum-gravity-studio`.

## Repository

| Item | Value |
|---|---|
| Local `HEAD` | `fa1cc875a74fecf067c4395db812cac3b7f0ba14` |
| `origin/main` | `fa1cc875a74fecf067c4395db812cac3b7f0ba14` |
| `git describe` | `v5.0.0-1-gfa1cc87` |
| Version surfaces | `scripts/check_version.py` → "Version consistency OK: all surfaces report 5.0.0" |
| Worktree at recon | clean except untracked `QGRAVITY.md` (mission file, preserved) |
| Tags present | `v5.0.0`, `v4.2.0`, `v4.1.0`, `v4.0.0`, … `v0.2.0` |

### Branch divergence (ahead / behind `origin/main`)

- `origin/main` == local `main` (0/0).
- Two small unmerged branches ahead of main; the rest are merged/behind:
  - `origin/agent/v4-studio-mfit2-sat` (ahead 7, behind 101)
  - `origin/claude/beautiful-rubin-3hcoym` (ahead 1, behind 126)
  - `origin/claude/vigilant-ritchie-mscxry` (ahead 1, behind 79)
  - `origin/codex/hcspnp-studio-guard` (ahead 6, behind 1) — its tip `3cfc96f` already
    landed on `main` as PR #53; treat as merged.
  - `origin/release/5.0.0-provenance` (behind 6) — merged via PR #52.
- None of the ahead-branches touch Quantum Gravity. No QG work exists upstream.

### Absent-before-this-branch (confirms greenfield)

`research/qg_2026/`, `cqhecs/quantum_gravity/`, `scripts/run_qg_openquantum_campaign.py`,
`docs/QUANTUM_GRAVITY_LAB.md`.

## Environment

| Tool | Version |
|---|---|
| Python | 3.14.6 |
| pip | 26.2.2 |
| NumPy | 2.4.6 |
| Qiskit | 2.5.1 |
| openquantum-sdk | 1.0.0 |
| CMake | 4.4.0 |
| Node | v22.23.1 |
| npm | 11.21.1 |
| rustc / cargo | 1.96.0 |
| git | 2.54.0.windows.1 |
| OS | Windows 10.0.26200 |

Not probed in session 1 (mark `NOT_RUN`, not pass): Vulkan SDK/`vulkaninfo`, MSVC compiler
identity, Playwright browser runtime.

## Baseline test observations (session 1)

| Command | Result |
|---|---|
| `python -m pytest tests/ --collect-only -q` | 2819 collected / 2820 (1 deselected) in ~18.5 s |
| `python scripts/check_version.py` | exit 0, all surfaces 5.0.0 |
| `pytest tests/test_reference.py tests/test_provenance.py tests/test_execution_plan.py tests/test_path_d_pauli_observables.py -q` | 268 passed in 6.9 s |

Full-suite, native CTest, web `npm test`, Playwright and mutation gates were **NOT_RUN**
in session 1; they are scheduled for the M13 hardening wave.

## Credentials

- No `OPENQUANTUM_*` environment variable set (User/Machine/Process).
- `~/.openquantum/accounts.json` exists but is empty (`{}`); only `oq-cache/` and
  `quotes/` caches are present (historical).
- A read-only probe using the provided `s_…` value as a bearer token → `401 UNAUTHORIZED`
  (consistent with it being the Client **ID**, not a token or the full key pair).
