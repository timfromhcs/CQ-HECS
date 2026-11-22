"""Tests for scripts/release_flip_check.py (F-12). Offline; works on temp copies only."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import release_flip_check as rfc  # noqa: E402

FILES = sorted({s.path for s in rfc.SURFACES})


def _copy(tmp_path: Path) -> Path:
    for rel in FILES:
        shutil.copy(REPO / rel, tmp_path / rel)
    return tmp_path


def _flip(root: Path) -> None:
    """Apply a complete synthetic flip so 'released' mode has a positive case."""
    subs = {
        "README.md": [
            (r"Development tree \(`[^`]*` release candidate[^)]*unreleased\)", "Release"),
            (r"will be attached to the release once", "is attached to the release"),
            (r"\(nothing is published yet\)", ""),
            (r"not published(?!,)", "published"),
            (r"\(no tag exists yet\)", "(done)"),
        ],
        "RELEASE_NOTES.md": [(r"\(planned; no tag exists[^)]*\)", ""),
                             (r"not published, no tag exists", "published")],
        "RELEASE_NOTES_DRAFT.md": [(r"not published, no tag exists", "published")],
        "CHANGELOG.md": [(r"\(unreleased candidate\)", ""),
                         (r"Release candidate: no `v[^`]*` tag or GitHub release exists yet",
                          "Released")],
    }
    import re
    for rel, rules in subs.items():
        p = root / rel
        t = p.read_text(encoding="utf-8")
        for pat, rep in rules:
            t = re.sub(pat, rep, t)
        p.write_text(t, encoding="utf-8")


def test_current_tree_is_a_consistent_candidate():
    assert rfc.check("candidate") == []


def test_current_tree_is_not_released():
    problems = rfc.check("released")
    assert problems, "the tree must not pass 'released' before the flip commit"
    assert any("README banner" in p for p in problems)


def test_every_surface_is_distinct_and_exists():
    assert len({(s.path, s.name) for s in rfc.SURFACES}) == len(rfc.SURFACES)
    for s in rfc.SURFACES:
        assert (REPO / s.path).is_file(), s.path


def test_synthetic_full_flip_passes_released_and_fails_candidate(tmp_path):
    root = _copy(tmp_path)
    _flip(root)
    assert rfc.check("released", root) == []
    assert rfc.check("candidate", root)


@pytest.mark.parametrize("surface", [s.name for s in rfc.SURFACES])
def test_half_flip_is_caught_in_released_mode(tmp_path, surface):
    """Flip everything, then restore one surface to its candidate wording: must be flagged."""
    root = _copy(tmp_path)
    _flip(root)
    s = next(x for x in rfc.SURFACES if x.name == surface)
    original = (REPO / s.path).read_text(encoding="utf-8")
    import re
    m = re.search(s.candidate, original, re.MULTILINE)
    assert m
    p = root / s.path
    p.write_text(p.read_text(encoding="utf-8") + "\n" + m.group(0) + "\n", encoding="utf-8")
    problems = rfc.check("released", root)
    assert any(surface in x for x in problems), problems


def test_missing_candidate_wording_is_caught_in_candidate_mode(tmp_path):
    root = _copy(tmp_path)
    p = root / "RELEASE_NOTES.md"
    p.write_text(p.read_text(encoding="utf-8").replace("planned; no tag exists", "released"),
                 encoding="utf-8")
    assert any("RELEASE_NOTES date line" in x for x in rfc.check("candidate", root))


def test_missing_file_is_reported(tmp_path):
    root = _copy(tmp_path)
    (root / "CHANGELOG.md").unlink()
    assert any("CHANGELOG.md is missing" in x for x in rfc.check("candidate", root))


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        rfc.check("nope")


def test_cli_exit_codes(capsys):
    assert rfc.main(["--mode", "candidate"]) == 0
    assert rfc.main(["--mode", "released"]) == 1
    assert rfc.main(["--list"]) == 0
    with pytest.raises(SystemExit) as e:
        rfc.main([])
    assert e.value.code == 2
