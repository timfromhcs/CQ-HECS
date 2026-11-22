# Wave F: release.yml static and local dry run

Scope: `.github/workflows/release.yml`, `docs/RELEASE_PROCESS.md`. Nothing was pushed, tagged or published.
Workflow has still never run on GitHub: the whole pipeline is `NOT_RUN` remotely.

## Commands and results

| Check | Result |
|---|---|
| `actionlint` v1.7.7 (built with `go install`, pinned) on `release.yml` and `package.yml` | clean, rc 0 (shellcheck not installed, so embedded shell was NOT shellchecked) |
| Pinned action SHAs vs tags via `gh api` (checkout v7.0.1, setup-python v7.1.0, download-artifact v8.0.2, upload-artifact v7.0.2, softprops/action-gh-release v3.0.3 peeled from annotated tag) | all 5 match |
| softprops `action.yml` @ v3.0.3 | outputs `id`, `url`, `upload_url`, `assets` exist; `fail_on_unmatched_files` defaults to false (now set true); drafts reusable by tag |
| `pytest tests/test_native_release_workflow.py` | 23 passed (no test edited) |
| `git push --dry-run origin HEAD:main` | would be a clean fast-forward 25e16e5..f880d0a; main is an ancestor of HEAD |
| `gh api .../branches/main` | `protected: false`; default workflow permission `read` (job-level `contents: write` is explicit) |

## Local simulation (real step text extracted from the YAML, fake inputs, Git Bash on Windows)

* resolve-tag (temp repo with bare origin): main push without tag -> `publish=true`; main push with tag -> `publish=false`;
  tag push on main commit -> `publish=true`; tag `v0.0.1` -> refused (new early check); tag on side-branch commit
  -> refused by ancestor guard.
* asset selection: all 7 assets selected and `SHA256SUMS` written/verified; missing asset, tampered byte, and asset absent
  from package manifest all fail with a clear `::error::`.
* build identity: matching SHA passes; wrong SHA fails.
* draft verification with a fake `gh`: correct draft passes; missing asset, extra asset, non-draft, wrong tag,
  asset state `starter`, tampered downloaded bytes each fail.
* CI gate python (no run / running / green / red / cancelled only / cancelled+green / red+green): WAIT/WAIT/GREEN/FAIL/WAIT/GREEN/FAIL as designed.
  The event filter added afterwards was only re-checked for syntax and the unchanged WAIT/FAIL branches, not for the green branch with real `gh` JSON.
* Simulation caveats: Windows CRLF from `python` text mode had to be stripped in the harness (Linux runners do not have this).

## Defects fixed in release.yml

1. `grep -F "  asset"` for the package manifest lookup could match a longer name and, under `set -e` with no match, exited silently; replaced by exact `awk '$2 == name'`.
2. CI gate treated `cancelled` runs as failures (concurrency cancellation could block a release forever) and accepted a green `pull_request` run, which tests the merge ref, not the exact SHA. Now failures are `failure|timed_out|startup_failure`, cancelled is ignored, and green must come from a `push` or `workflow_dispatch` run.
3. Tag push with a name different from `v<version>` was only rejected late (after CI wait and package build); now rejected in `resolve-tag`.
4. softprops `fail_on_unmatched_files` was implicit false; now true. `overwrite_files: true` made explicit.
5. A reused stale draft could carry an old `target_commitish`; the publish PATCH now sends `target_commitish=$GITHUB_SHA`. The draft's `tag_name` is also checked before download.
6. `python` -> `python3` in the CI-gate step (no setup-python in that job).

## Merge strategy (tag == tested SHA)

Fast-forward `git push origin <tested-sha>:main` (documented in `docs/RELEASE_PROCESS.md` section 2A, maintainer action, never force).
Pushing to main also deploys Vercel production immediately and independently of `release.yml`.

## NOT_RUN / residual risk

* The workflow itself on GitHub (all jobs), `package.yml` reuse via `workflow_call`, real `softprops` draft reuse and its `id` output, `gh api` octet-stream asset download from a draft, and PATCH `target_commitish` acceptance on a draft: not exercised; documented API behaviour only.
* Whether GITHUB_SHA is the commit (not tag object) for annotated tag pushes: believed so, fail-closed tripwires otherwise.
* shellcheck on the embedded scripts; Windows runner behaviour of package.yml.
* Concurrency group allows only one pending run; a second pending main-push run replaces the first (acceptable, noted).
