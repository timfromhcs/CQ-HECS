"""P-07: release.yml asset policy lint (offline; never runs a workflow).

Policy under test: the release publishes EXACTLY the artifacts package.yml builds and the
README names (wheel, sdist, onedir EXE zip, native cpu/vulkan zips, CycloneDX SBOMs, SHA256SUMS),
by calling package.yml as a reusable workflow, with pinned actions, least privilege and the
unchanged trigger / tag-if-not-exists semantics. Regex checks always run; the structural YAML
checks run when PyYAML is importable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# Name templates, {v} = scripts/version.py. These are the whole published set.
EXPECTED_ASSETS = (
    "cqhecs-{v}-py3-none-any.whl",
    "cqhecs-{v}.tar.gz",
    "cqhecs-{v}-windows-x64.zip",
    "cq-hecs-cpu-{v}-windows-x64.zip",
    "cq-hecs-vulkan-{v}-windows-x64.zip",
    "cqhecs-{v}-wheel.cdx.json",
    "cqhecs-{v}-windows-x64.cdx.json",
    "SHA256SUMS",
)
SHA_PIN = re.compile(r"[\w./-]+@[0-9a-f]{40}")


def _text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _all_workflows():
    return sorted(WORKFLOWS.glob("*.yml"))


@pytest.mark.parametrize("path", _all_workflows(), ids=lambda p: p.name)
def test_every_workflow_parses_and_has_jobs(path):
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict) and doc.get("jobs"), path.name
    assert (True in doc or "on" in doc), f"{path.name}: no trigger block"


@pytest.mark.parametrize("path", _all_workflows(), ids=lambda p: p.name)
def test_every_remote_action_is_pinned_to_a_commit_sha(path):
    uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
    for u in uses:
        if u.startswith("./"):
            continue  # local reusable workflow: same commit by construction
        assert SHA_PIN.fullmatch(u), f"{path.name}: action not pinned to a 40-hex SHA: {u}"


def test_release_triggers_are_unchanged():
    text = _text("release.yml")
    on_block = re.search(r"^on:\n((?:[ \t]+.*\n|\n)+)", text, re.M).group(1)
    assert re.findall(r"^  (\w+):", on_block, re.M) == ["push"], "only push may trigger a release"
    assert re.search(r"tags:\s*\n\s*-\s*'v\*'", on_block)
    assert re.search(r"branches:\s*\n\s*-\s*main\s*$", on_block, re.M)
    for forbidden in ("pull_request", "workflow_dispatch", "schedule", "workflow_run"):
        assert forbidden not in on_block, forbidden


def test_release_keeps_tag_if_not_exists_semantics():
    text = _text("release.yml")
    assert "git ls-remote --exit-code --tags origin" in text
    assert 'echo "publish=false"' in text and 'echo "publish=true"' in text
    assert "target_commitish: ${{ github.sha }}" in text
    assert "verify-required-ci" in text


def test_release_permissions_are_least_privilege():
    text = _text("release.yml")
    assert re.search(r"^permissions:\n  contents: read\n", text, re.M)
    writers = re.findall(r"contents: write", text)
    assert len(writers) == 1, "only the final publishing job may hold contents: write"
    # The write permission belongs to the job that creates the release, nothing else.
    release_job = text[text.index("\n  release:\n"):]
    assert "contents: write" in release_job and "softprops/action-gh-release" in release_job
    assert "id-token" not in text and "packages: write" not in text


def test_release_calls_package_workflow_instead_of_rebuilding():
    rel, pkg = _text("release.yml"), _text("package.yml")
    assert re.search(r"uses:\s*\./\.github/workflows/package\.yml\s*$", rel, re.M)
    assert re.search(r"^  workflow_call:", pkg, re.M)
    assert "needs: [resolve-tag, verify-required-ci, package]" in rel
    # No second, divergent build of the same artifacts inside the release job.
    assert "python -m build" not in rel
    assert "pyinstaller" not in rel.lower()
    # package.yml itself must stay non-publishing.
    for forbidden in ("action-gh-release", "contents: write", "git push", "git tag"):
        assert forbidden not in pkg, forbidden


def test_release_uploads_exactly_the_expected_assets():
    text = _text("release.yml")
    block = re.search(r"files:\s*\|\n((?:\s+release-assets/.*\n)+)", text)
    assert block, "softprops files: list not found"
    uploaded = [line.strip() for line in block.group(1).splitlines()]
    want = [
        "release-assets/" + a.format(v="${{ steps.meta.outputs.version }}") for a in EXPECTED_ASSETS
    ]
    assert uploaded == want, f"uploaded set differs from policy:\n{uploaded}\n!=\n{want}"
    # The selection step must demand every non-manifest asset by exact name.
    for a in EXPECTED_ASSETS[:-1]:
        assert a.format(v="${VERSION}") in text, a


def test_expected_assets_are_what_package_workflow_and_scripts_produce():
    pkg = _text("package.yml")
    assert 'cqhecs-$V-wheel.cdx.json' in pkg or "cqhecs-$V-wheel.cdx.json" in pkg
    assert "cqhecs-$V-windows-x64.cdx.json" in pkg
    assert "cqhecs-$V-windows-x64.zip" in pkg
    assert "python -m build" in pkg and "make_manifest.py bundle --out bundle/SHA256SUMS" in pkg
    ps = (ROOT / "scripts" / "package_native.ps1").read_text(encoding="utf-8")
    assert '"$Pkg-$Version-windows-x64.zip"' in ps or "$Pkg-$Version-windows-x64.zip" in ps
    assert '"cq-hecs-cpu"' in ps and '"cq-hecs-vulkan"' in ps


def test_readme_names_every_published_asset_kind():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in ("cq-hecs-cpu-", "cq-hecs-vulkan-", "SHA256SUMS", "CycloneDX"):
        assert needle in readme, f"README does not name release asset: {needle}"
    assert "SPDX" not in readme.split("Published wheels")[-1][:400], "stale SPDX asset claim"


def test_release_never_runs_the_spdx_generator_any_more():
    assert "generate_sbom_and_checksums.py" not in _text("release.yml")


# --------------------------------------------------------------------------- E4 hardening

def _job_text(text: str, job: str) -> str:
    start = text.index(f"\n  {job}:\n")
    nxt = re.search(r"\n  [\w-]+:\n", text[start + 1:])
    return text[start: start + 1 + nxt.start()] if nxt else text[start:]


def test_tag_push_must_be_an_ancestor_of_origin_main():
    job = _job_text(_text("release.yml"), "resolve-tag")
    assert "fetch-depth: 0" in job
    assert "git merge-base --is-ancestor" in job and "origin/main" in job
    assert "is not an ancestor of origin/main" in job
    # The guard must run before the tag/publish decision is written.
    assert job.index("git merge-base --is-ancestor") < job.index('echo "tag=')
    # Tag-if-not-exists on main pushes is unchanged.
    assert "git ls-remote --exit-code --tags origin" in job


def test_release_is_created_as_draft_verified_then_promoted():
    text = _text("release.yml")
    rel = _job_text(text, "release")
    assert "draft: false" not in text
    assert re.search(r"draft:\s*true", rel)
    i_draft = rel.index("id: draft")
    i_verify = rel.index("Verify the uploaded draft assets")
    i_publish = rel.index("Publish the verified draft")
    assert i_draft < i_verify < i_publish
    verify = rel[i_verify:i_publish]
    assert "releases/assets/" in verify and "make_manifest.py uploaded --verify" in verify
    assert "cmp uploaded/SHA256SUMS release-assets/SHA256SUMS" in verify
    publish = rel[i_publish:]
    assert "draft=false" in publish and "GITHUB_SHA" in publish
    assert rel.count("draft=false") == 1, "only the last step may make the release public"


def test_published_release_is_never_modified():
    rel = _job_text(_text("release.yml"), "release")
    assert "releases/tags/" in rel and "already published" in rel
    assert rel.index("already published") < rel.index("id: draft")


def test_release_verifies_embedded_build_identity():
    rel = _job_text(_text("release.yml"), "release")
    assert "BUILD-INFO.json" in rel and "cqhecs:source-revision" in rel
    assert "venv tooling" in rel
    assert rel.index("BUILD-INFO.json") < rel.index("id: draft")


def test_release_job_is_still_the_only_writer_after_hardening():
    text = _text("release.yml")
    assert len(re.findall(r"contents: write", text)) == 1
    for forbidden in ("pull_request_target", "id-token", "packages: write", "git push", "git tag "):
        assert forbidden not in text, forbidden


def test_release_process_doc_exists_and_covers_required_procedures():
    doc = (ROOT / "docs" / "RELEASE_PROCESS.md").read_text(encoding="utf-8")
    for needle in ("git push origin", ":main", "merge-base --is-ancestor", "draft", "yank",
                   "vercel rollback", "Post-release verification", "SHA256SUMS", "BUILD-INFO.json"):
        assert needle in doc, f"RELEASE_PROCESS.md lacks: {needle}"


def test_package_workflow_wheel_sbom_uses_dependency_closure():
    assert "--closure-of cqhecs" in _text("package.yml")
