"""W3-16: llms.txt must describe the shipped system honestly and stay consistent.

The file claimed Path C reports the discarded singular-value mass "as
numerical_error_bound" — the exact overclaim the D12 audit (FINDINGS F-004) corrected —
and Path B was described as an exact stabilizer-rank method with a T-count ceiling. These
tests pin the corrected wording, the version line, and that the linked docs exist.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from version import VERSION  # noqa: E402

TEXT = (ROOT / "llms.txt").read_text(encoding="utf-8")


def test_llms_txt_states_the_current_version():
    assert f"Software version: {VERSION}" in TEXT


def test_llms_txt_does_not_claim_the_discarded_mass_is_a_bound():
    assert "reported as numerical_error_bound" not in TEXT
    assert "discarded_spectral_mass_diagnostic" in TEXT
    assert "numerical_error_bound` stays `None`" in TEXT


def test_llms_txt_describes_path_b_as_a_dense_branch_sum():
    assert "branch decomposition over a dense statevector" in TEXT
    assert "PATHB_DOMINANCE.json" in TEXT


def test_every_llms_txt_link_resolves():
    links = re.findall(r"\]\(([^)]+)\)", TEXT)
    assert links, "llms.txt has no documentation links"
    missing = [target for target in links if not (ROOT / target).exists()]
    assert not missing, f"llms.txt links to missing files: {missing}"
