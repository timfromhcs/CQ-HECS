# Wave E / E4: release-process hardening

Status: implemented and linted offline. No workflow was run; hosted behaviour is NOT_RUN.

## Changes
- `.github/workflows/release.yml`
  - resolve-tag: `fetch-depth: 0` and `git merge-base --is-ancestor <sha> origin/main` guard (tag and main
    pushes) with a clear error; tag-if-not-exists unchanged.
  - release job: refuses to touch a published release; verifies BUILD-INFO.json / SBOM source revision /
    no venv tooling in the wheel SBOM; creates a DRAFT (softprops, `draft: true`); downloads uploaded
    assets from the draft via the API and checks asset set, state, size, `cmp` of SHA256SUMS and
    `make_manifest.py --verify`; only then `PATCH draft=false`, then checks the tag resolves to the tested SHA.
- `scripts/package_archive.py`: `build_info_bytes`, `make_zip(..., extra_files)`, CLI `--source-sha`,
  `--build-version`, `--builder`, `--no-build-info`; auto-embeds BUILD-INFO.json when
  `CQHECS_SOURCE_SHA`/`GITHUB_SHA` is set. Date from SOURCE_DATE_EPOCH, no run id. `--normalize-targz`
  untouched; wheel/sdist untouched.
- `scripts/sbom_cyclonedx.py`: `dependency_closure`, `--closure-of`, `--source-revision`,
  `--source-repository`; revision as property plus vcs externalReference; fails closed on a missing root.
- `docs/RELEASE_PROCESS.md` (new), `docs/PACKAGING.md` (section added).
- `scripts/make_manifest.py`: unchanged (existing `--verify` is what the workflow uses).

## Tests
`python -m pytest tests/test_native_release_workflow.py tests/test_packaging.py -q`: 60 passed, 1 xfailed.
Inline Python blocks of release.yml compile (3 blocks). Shell syntax (`bash -n`) of the run blocks: NOT_RUN
(no usable bash path on this host).

## Handoff / open
- `.github/workflows/package.yml` is not owned by E4: its wheel SBOM step must add `--closure-of cqhecs`
  (it currently uses `--exclude cqhecs --exclude pip`, which lists the whole venv). Until then
  `release.yml` rejects the wheel SBOM (by design) and `test_package_workflow_wheel_sbom_uses_dependency_closure`
  is xfail.
- Unverified assumptions: softprops v3.0.3 reuses an existing draft by tag and exposes `outputs.id`;
  `gh api .../releases/assets/<id>` with octet-stream Accept works for draft assets; publishing a draft
  creates the tag at `target_commitish`. All need a real run to confirm.
- Branch protection on main is out of scope (settings change, not done).
