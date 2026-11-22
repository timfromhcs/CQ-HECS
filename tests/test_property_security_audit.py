"""Self-tests and gates for ``scripts/security_audit.py`` (W15 / C5).

The scanner must find what it claims to find (positive controls) and ignore documentation placeholders,
and the repository must satisfy the static contracts: no secret-shaped strings in tracked files, every
GitHub Action pinned to a commit SHA, Studio/MCP contract intact, and no new dynamic-code primitives.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "security_audit.py"
spec = importlib.util.spec_from_file_location("security_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules["security_audit"] = audit
spec.loader.exec_module(audit)  # type: ignore[union-attr]

#: Findings already reported in research/v7/SECURITY_AUDIT.md. A *new* entry fails this test.
KNOWN_CODE_FINDINGS: set = set()  # SEC-M2 fixed in wave D1 (eval removed)


@pytest.mark.parametrize(
    "line,pattern",
    [
        ('k = "AKIA' + "ABCDEFGHIJKLMNOP" + '"', "aws_access_key_id"),
        ('t = "ghp_' + "a" * 36 + '"', "github_token"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private_key_block"),
        ('api_key = "' + "Ab3" * 10 + '"', "assigned_secret"),
        ("https://bob:hunter22pw@internal.host/x", "credential_in_url"),
        ("sk-ant-" + "A1b2C3d4" * 5, "anthropic_or_openai_key"),
    ],
)
def test_positive_controls_are_detected(line, pattern):
    assert pattern in list(audit._scan_line(line))


@pytest.mark.parametrize(
    "line",
    [
        'api_key = "<your-api-key-goes-here-please>"',
        'password = "${SECRET_PASSWORD_FROM_ENV_VAR}"',
        "token = os.environ['TOKEN']",
        "AKIA is a prefix",
        "def test_token_is_unpredictable():",
    ],
)
def test_placeholders_and_code_are_not_flagged(line):
    assert list(audit._scan_line(line)) == []


def test_tracked_files_contain_no_secret_shaped_strings():
    assert audit.scan_tree() == []


def test_every_action_is_pinned_to_a_commit_sha_and_permissions_are_explicit():
    result = audit.scan_actions()
    assert result["inventory"], "no workflows found: the scan would be vacuous"
    assert result["unpinned"] == []
    assert result["other"] == []


@pytest.mark.parametrize(
    "ref,ok",
    [
        ("actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", True),
        ("actions/checkout@v4", False),
        ("actions/checkout@main", False),
        ("owner/repo/sub/path@" + "0" * 40, True),
        ("owner/repo@" + "0" * 39, False),
    ],
)
def test_action_pin_pattern(ref, ok):
    assert bool(audit._SHA.match(ref)) is ok


def test_studio_and_mcp_contracts_hold():
    assert audit.scan_studio_contract() == []


def test_no_new_dynamic_code_primitives():
    found = {(f["file"], f["issue"]) for f in audit.scan_code()}
    assert found <= KNOWN_CODE_FINDINGS, found - KNOWN_CODE_FINDINGS
