# Release process

Operational procedure for cutting, verifying and (if needed) withdrawing a CQ-HECS release. It describes
what `.github/workflows/release.yml` does and what the maintainer must do around it. The workflow
definitions have NOT been executed as a whole yet; treat every step below as unproven until a real
release has run it. What HAS been done: `actionlint` 1.7.7 is clean on `release.yml` and `package.yml`,
every pinned action SHA was resolved against its tag, and the shell/Python steps were replayed locally
against fake inputs (see `research/v7/evidence/waveF_release.md`). A dry run on GitHub is still pending.

Invariant to preserve: **tag == tested SHA**. The release is built from, and the tag must point to, the
exact commit whose CI (`ci.yml`) and packaging (`package.yml`) were green.

## 1. Why a normal PR merge breaks the invariant

Pushes to `main` deploy the web app to Vercel production and trigger `release.yml`. `main` is not
protected. A GitHub "Merge pull request" or "Squash and merge" creates a NEW commit on `main`; the SHA
that was tested on the PR branch is then not the SHA that is released. Rebase-merge rewrites SHAs too.
Only a fast-forward keeps the tested SHA.

## 2. Safe merge procedure (choose one)

### A. Fast-forward main to the tested SHA (preferred, maintainer action)

```bash
git fetch origin --prune
TESTED=$(git rev-parse origin/release/v7-stable)          # the exact head whose PR checks are green
git merge-base --is-ancestor origin/main "$TESTED" \
  || { echo "main has moved: rebase/merge main into the branch and re-run CI first"; exit 1; }
git push origin "$TESTED":main                            # fast-forward only; never --force
```

The push is rejected by Git if it is not a fast-forward. Because the pushed SHA is the tested SHA, the
`release.yml` run that follows (main push, tag does not exist yet) releases exactly that commit.
Before pushing, confirm that `ci.yml` is green for `$TESTED` in a run whose event is `push` (the push of
the branch itself): `gh run list --workflow ci.yml --commit "$TESTED" --json event,conclusion,status`.
A `pull_request` run does NOT count for the release gate because it tests the PR merge ref.
Pushing to `main` has two effects that start at the same time and are independent of each other:
Vercel deploys the web app to production, and `release.yml` starts. If `release.yml` later fails, the
web app is already live; roll it back as in section 5 if needed.
Do not use `--force` or `--force-with-lease`. Pushing to `main` deploys production: do it only when
the release is approved.

### B. Merge commit or squash via the GitHub UI

The merge result is a new SHA, so the tested SHA is not the released SHA. Re-run the full freeze on
the merge result before it reaches `main`: merge `main` into the branch first (so the PR head equals the
future merge content), wait for `ci.yml` AND `package.yml` on that head, and accept that the commit
on `main` still differs. In that case `verify-required-ci` in `release.yml` requires a green `ci.yml`
run for the new `main` SHA itself, which is the real gate; the tested-PR-SHA statement is then NOT
true and the release report must say so.

## 3. What release.yml enforces

1. `resolve-tag`: for a `v*` tag push AND a main push, the released commit must be an ancestor of
   `origin/main` (`git merge-base --is-ancestor`). A tag on a side branch fails with a clear error.
   On a main push the tag `v<scripts/version.py>` is created only if it does not exist yet.
2. `verify-required-ci`: a green `ci.yml` run of event `push` or `workflow_dispatch` for the released SHA
   (waits up to 70 minutes). Any `failure`, `timed_out` or `startup_failure` run for that SHA fails the
   gate even if another run is green. Cancelled runs are ignored; if no success ever appears the gate
   times out and fails (fail closed).
3. `package` (`package.yml`): wheel, sdist, EXE zip, native zips, SBOMs, built once from this commit.
4. `release` job, in order:
   0. `resolve-tag` already refused a tag push whose name is not `v<scripts/version.py>`;
   1. refuses if a PUBLISHED release for the tag already exists (releases are immutable);
   2. checks the tag equals `v<version>`, selects exactly the eight assets, checks byte identity with
      `package.yml`'s manifest, writes and verifies `SHA256SUMS`;
   3. checks build identity: each zip root contains `BUILD-INFO.json` with the release SHA and
      version; both SBOMs carry `cqhecs:source-revision` equal to the release SHA; the wheel SBOM lists
      no venv tooling;
   4. creates the release as a DRAFT and uploads all assets (`softprops/action-gh-release`, pinned;
      `fail_on_unmatched_files: true`, `overwrite_files: true`; its `id` output is the draft's release id);
   5. downloads the uploaded assets back from the draft and verifies them against the uploaded
      `SHA256SUMS` (it is still a draft, its tag name, exact set of asset names, upload state, size,
      byte equality of `SHA256SUMS`, `make_manifest.py --verify`);
   6. only then promotes the draft (`draft=false`, together with `target_commitish=<tested SHA>` so a
      reused draft cannot create the tag on an older commit) and checks that the tag resolves to the
      tested SHA.

A failure in steps 1 to 5 leaves nothing public. A failure in step 6 leaves a published release that must
be yanked (section 5).

## 4. Re-running after a partial failure

* Failure before or during upload: a draft may exist. It is invisible to the public and has no tag
  (for main-push releases). Re-run the failed workflow run ("Re-run failed jobs" or "Re-run all
  jobs"). The release job reuses the draft by tag name and overwrites assets with the same names.
  Stale drafts can be deleted in the GitHub Releases page ("Delete draft") with no effect on `main`.
  A draft that still carries assets from an older attempt under different names makes step 5 fail with
  "uploaded asset set differs ... extra=[...]"; delete that draft and re-run. Tags created through the
  Releases API with `GITHUB_TOKEN` do not start another workflow run, so publishing does not retrigger
  `release.yml`.
* Failure in verification (step 5): the draft stays. Do not publish it by hand. Find the cause in the
  job log, fix it, re-run. A mismatch between `SHA256SUMS` and the uploaded bytes is a hard error.
* Failure after promotion: the release is public. Follow section 5; do not edit published assets.
* Concurrency: the pipeline has `concurrency: release-pipeline` with `cancel-in-progress: false`, so
  two runs queue instead of racing.

## 5. Rollback / yank

Published releases are immutable; a bad release is withdrawn and replaced by a NEW version.
Never re-publish different bytes under the same tag. Ask first: each command below is destructive or
externally visible; the maintainer (or an explicitly authorized agent) runs them.

1. **Withdraw the GitHub release and tag**

   ```bash
   gh release delete v7.0.0 --repo timfromhcs/CQ-HECS --cleanup-tag --yes
   git ls-remote --tags origin v7.0.0        # must print nothing
   ```

   Alternative that keeps history: edit the release, mark it as a pre-release and prepend "WITHDRAWN: do
   not use" to the notes. Downstream users may already have the assets; the checksums in the notes remain
   the reference for what was published.
2. **Revert main** (no history rewrite, no force push)

   ```bash
   git fetch origin && git switch -c revert/v7.0.0 origin/main
   git revert --no-edit <bad-commit-or-range>       # or: git revert -m 1 <merge-commit>
   git push origin revert/v7.0.0                    # open a PR, or fast-forward main as in 2A after CI is green
   ```

   Note: a push to `main` that changes `scripts/version.py` back to an older version whose tag still
   exists is a no-op for the release workflow; a revert that keeps version 7.0.0 and removes the tag
   would re-create the tag on the next main push. Bump to the next version (7.0.1) in the fix instead.
3. **Roll back the Vercel production deployment** to the previous good deployment. Either:
   * Dashboard: Project > Deployments > pick the last good production deployment > "Promote to
     Production" (instant rollback; no rebuild); or
   * CLI: `vercel rollback` (previous production deployment) or `vercel rollback <deployment-url>`, run
     from the linked project with a team-scoped login; or
   * Vercel MCP `request_rollback` with the project and the target deployment id (read-only listing
     with `list_deployments` first to pick the id).

   Vercel's automatic production alias assignment is turned off by a rollback until you promote a newer
   deployment; remember to promote the fixed build afterwards.
4. **Record** the incident (cause, affected assets and SHAs, who was notified) in `research/v7/` and
   in the next release notes.

## 6. Post-release verification checklist

Run after the release is published. All commands are read-only.

```bash
TAG=v7.0.0; REPO=timfromhcs/CQ-HECS
# 1. tag points to the tested commit, and that commit is on main
gh api repos/$REPO/commits/$TAG --jq .sha                 # == the tested SHA
git fetch origin --tags && git merge-base --is-ancestor $TAG origin/main && echo "on main"
# 2. release is public, not draft, with exactly the eight assets
gh release view $TAG --repo $REPO --json isDraft,isPrerelease,assets --jq '{isDraft,isPrerelease,n:(.assets|length)}'
# 3. download and verify SHA256SUMS
mkdir -p rel && gh release download $TAG --repo $REPO --dir rel
python scripts/make_manifest.py rel --verify rel/SHA256SUMS
# 4. build identity inside the artifacts
unzip -p rel/cqhecs-7.0.0-windows-x64.zip cq-hecs/BUILD-INFO.json    # source_sha == tag commit
unzip -p rel/cq-hecs-cpu-7.0.0-windows-x64.zip cq-hecs-cpu/BUILD-INFO.json
python -c "import json;b=json.load(open('rel/cqhecs-7.0.0-wheel.cdx.json'));print([p for p in b['metadata']['component']['properties']])"
# 5. wheel installs in a clean venv and reports the version
python -m venv /tmp/v && /tmp/v/bin/pip install rel/cqhecs-7.0.0-py3-none-any.whl && /tmp/v/bin/cq-hecs version
# 6. production web bundle reports the version and source SHA (see docs/WEB_ENGINES.md)
curl -sI https://<production-host>/ | head -n 5
```

Also confirm: the release job log shows the verification step before the publish step; `ci.yml` is green
for the tag commit; the Vercel production deployment's git SHA equals the tag commit
(`list_deployments` or the dashboard); the checksums in the release body equal `SHA256SUMS`.
Items not run are reported `NOT_RUN`, not assumed.

## 7. Build identity

* `BUILD-INFO.json` (zip root folder of the EXE zip and both native zips): `schema`, `version`,
  `source_sha`, `build_date` (from `SOURCE_DATE_EPOCH`, not the clock), `builder`
  (`github-actions:<repo>:<workflow>`). No run id, so the zips stay byte-reproducible for one commit. It is
  added by `scripts/package_archive.py` when `GITHUB_SHA` / `CQHECS_SOURCE_SHA` / `--source-sha` is
  available (`--no-build-info` disables it). Wheel and sdist are NOT modified, so their reproducibility
  is unchanged.
* SBOMs: the root component carries the property `cqhecs:source-revision` and a CycloneDX `vcs` external
  reference.
* The wheel SBOM is generated with `--closure-of cqhecs` so only the wheel's runtime dependency closure
  is listed (package.yml must pass that flag; see PACKAGING.md).
