"""The README exists in three languages and the three tell the same story.

A translation that drifts is worse than no translation: a reader picks their language
and gets different claims. These tests keep the files structurally equal where it
matters - the language selector, the shared evidence numbers, and the links to the
documents that carry the measurements.

The English file is canonical and holds the exhaustive detail; the German and French
files are full translations of the product-relevant sections and say so at the top.
"""
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
LANGUAGES = {
    "README.md": "English",
    "README.de.md": "Deutsch",
    "README.fr.md": "Français",
}

#: Numbers that must appear identically in every language file. They are the evidence
#: table; if one of them changes, all three files have to change together.
SHARED_EVIDENCE = ("2786", "2690", "21/21", "60/60", "39/39", "41/41")


@pytest.mark.parametrize("filename", sorted(LANGUAGES))
def test_exists_and_is_marked_with_its_language(filename):
    path = REPO / filename
    assert path.is_file(), f"{filename} is missing"
    text = path.read_text(encoding="utf-8")
    assert LANGUAGES[filename] in text, f"{filename} does not name its own language"
    assert "<h1" not in text.lower() or "cq-hecs" in text.lower()


@pytest.mark.parametrize("filename", sorted(LANGUAGES))
def test_selector_links_all_three_files(filename):
    text = (REPO / filename).read_text(encoding="utf-8")
    for target in LANGUAGES:
        if target == filename:
            continue
        assert target in text, f"{filename} does not link to {target}"


def test_every_language_carries_the_same_evidence_numbers():
    for filename in LANGUAGES:
        text = (REPO / filename).read_text(encoding="utf-8")
        missing = [number for number in SHARED_EVIDENCE if number not in text]
        assert not missing, f"{filename} is missing evidence numbers: {missing}"


def test_translations_point_back_to_the_canonical_file():
    for filename in ("README.de.md", "README.fr.md"):
        text = (REPO / filename).read_text(encoding="utf-8")
        assert "README.md" in text, f"{filename} must link the canonical README"
        assert "recherche" in text.lower() or "research/" in text, (
            f"{filename} must point at the research records that stay in English"
        )


def test_selector_sits_at_the_top_of_every_file():
    for filename in LANGUAGES:
        text = (REPO / filename).read_text(encoding="utf-8")
        head = text[:600]
        linked = sum(1 for target in LANGUAGES if target in head)
        assert linked == len(LANGUAGES) - 1 or filename in head, (
            f"{filename}: the language selector should be within the first screen"
        )
