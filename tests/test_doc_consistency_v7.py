"""W15 documentation gates: the docs must match the code and the evidence files.

What these tests pin (each one failed against the tree before the W15 rewrite):

* every ``python`` example in ``MIGRATION_V7.md`` runs, so an example cannot drift;
* the version placeholder ``<NEXT_MAJOR>`` appears only in documents that are allowed to
  carry it, never in code or packaging files, and the new documents carry no literal
  version number of their own;
* stale claims that earlier drafts made (and that the audits corrected) do not come back;
* there is one authoritative architecture document and the other one says it is historical;
* the numbers in the READMEs equal the numbers in the evidence files they cite;
* every documented HTTP route and MCP tool exists in the code, and the other way round;
* relative links and cited evidence files resolve.

Nothing here contacts a network, a provider or a credential.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

PLACEHOLDER = "<NEXT_MAJOR>"
#: Documents that may carry the placeholder (the integrator substitutes it at the freeze).
PLACEHOLDER_DOCS = (
    "MIGRATION_V7.md",
    "RELEASE_NOTES_DRAFT.md",
    "ARCHITECTURE.md",
    "README.md",
    "README.de.md",
    "README.fr.md",
    "llms.txt",
    "llms-full.txt",
    "CHANGELOG.md",
)
LANGUAGE_READMES = ("README.md", "README.de.md", "README.fr.md")
#: Documents that describe the current system; historical snapshots are excluded.
CURRENT_DOCS = (
    "README.md",
    "README.de.md",
    "README.fr.md",
    "ARCHITECTURE.md",
    "MIGRATION_V7.md",
    "RELEASE_NOTES_DRAFT.md",
    "llms.txt",
    "llms-full.txt",
    "docs/API_REFERENCE.md",
    "docs/STUDIO.md",
    "docs/QUANTUM_GRAVITY_LAB.md",
)
MISSION_ALLOWLIST = {"QGRAVITY.md"}


def read(relative: str) -> str:
    return (REPO / relative).read_text(encoding="utf-8-sig").replace("\r\n", "\n")


# ---------------------------------------------------------------------------
# 1. The migration guide's examples are executed
# ---------------------------------------------------------------------------

def _python_blocks(text: str):
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


_BLOCKS = _python_blocks(read("MIGRATION_V7.md"))


def test_migration_guide_has_examples():
    assert len(_BLOCKS) >= 8, "MIGRATION_V7.md lost its executable examples"


@pytest.mark.parametrize("index", range(len(_BLOCKS)))
def test_every_python_example_in_the_migration_guide_runs(index, monkeypatch):
    monkeypatch.chdir(REPO)
    namespace = {"__name__": f"migration_example_{index}"}
    exec(compile(_BLOCKS[index], f"MIGRATION_V7.md[python block {index}]", "exec"), namespace)


# ---------------------------------------------------------------------------
# 2. Version placeholder discipline
# ---------------------------------------------------------------------------

def test_placeholder_is_gone_from_shipped_docs():
    for relative in PLACEHOLDER_DOCS:
        assert PLACEHOLDER not in read(relative), f"{relative} still carries {PLACEHOLDER}"
    assert read("MIGRATION_V7.md").startswith("# Migrating from 5.0.0 to 7.0.0")
    assert "no 6.x release" in read("MIGRATION_V7.md")


def test_no_stale_current_release_claim():
    from version import VERSION

    assert VERSION == "7.0.0"
    for name in LANGUAGE_READMES:
        text = read(name)
        assert "Last published release: `v5.0.0`" not in text or "release candidate" in text


def test_placeholder_never_leaks_into_code_or_packaging():
    leaked = []
    candidates = [
        REPO / "pyproject.toml",
        REPO / "CMakeLists.txt",
        REPO / "CITATION.cff",
        REPO / "scripts" / "version.py",
        REPO / "web" / "package.json",
    ]
    candidates += sorted((REPO / "cqhecs").rglob("*.py"))
    candidates += sorted((REPO / "schemas").glob("*.json"))
    for path in candidates:
        if path.is_file() and PLACEHOLDER in path.read_text(encoding="utf-8", errors="replace"):
            leaked.append(str(path.relative_to(REPO)))
    assert not leaked, f"{PLACEHOLDER} leaked into: {leaked}"


def test_placeholder_is_confined_to_the_documents_that_may_carry_it():
    unexpected = []
    for path in list(REPO.glob("*.md")) + list((REPO / "docs").glob("*.md")) + [REPO / "llms.txt", REPO / "llms-full.txt"]:
        if path.name in {Path(name).name for name in PLACEHOLDER_DOCS} and path.parent in (REPO,):
            continue
        if path.is_file() and PLACEHOLDER in path.read_text(encoding="utf-8-sig", errors="replace"):
            unexpected.append(str(path.relative_to(REPO)))
    assert not unexpected, f"{PLACEHOLDER} found in documents not meant to carry it: {unexpected}"


@pytest.mark.parametrize("relative", ["MIGRATION_V7.md", "RELEASE_NOTES_DRAFT.md"])
def test_new_documents_write_no_version_number_of_their_own(relative):
    # 5.0.0 is the last released major (the "from" side), 7.0.0 the target. Any other
    # dotted triple would be a hard-coded version that the freeze would have to hunt down.
    found = set(re.findall(r"(?<![\w.])\d+\.\d+\.\d+(?![\w.])", read(relative)))
    assert found <= {"5.0.0", "7.0.0"}, f"{relative} hard-codes version numbers: {sorted(found - {'5.0.0', '7.0.0'})}"


# ---------------------------------------------------------------------------
# 3. Stale claims must not come back
# ---------------------------------------------------------------------------

#: (document glob, regex that must NOT match, why it is wrong)
STALE_CLAIMS = [
    (CURRENT_DOCS, r"no authentication because there is no", "Studio API has a per-launch bearer token"),
    (CURRENT_DOCS, r"CQ-HECS Studio 3\.1\.0 on", "hard-coded old Studio version in an example"),
    (CURRENT_DOCS, r"(?<!not )(?<!\*\* )reported as `?numerical_error_bound", "the discarded mass is a diagnostic, not a bound (F-004)"),
    (CURRENT_DOCS, r"all surfaces report `4\.0\.0`", "stale version-consistency claim"),
    (CURRENT_DOCS, r"latest\s+release is `v4\.0\.0`", "stale latest-release claim"),
    (CURRENT_DOCS, r"No physical GPU execution has been verified", "primitive Vulkan dispatch ran on an AMD iGPU (waveA_A2)"),
    (CURRENT_DOCS, r"Counts from Path C stop at a documented 20-qubit", "Path C sampling ceiling is 500; 20 is the dense conversion cap"),
    (CURRENT_DOCS, r"Exact decomposition for T <= 14", "Path B is a dense branch sum; PATHB_DOMINANCE.json"),
    (CURRENT_DOCS, r"\bpure-Python 54/54\b", "mutation count"),
]


@pytest.mark.parametrize("pattern_index", range(len(STALE_CLAIMS)))
def test_stale_claims_do_not_return(pattern_index):
    documents, pattern, why = STALE_CLAIMS[pattern_index]
    hits = [name for name in documents if re.search(pattern, read(name))]
    assert not hits, f"stale claim /{pattern}/ ({why}) found in {hits}"


@pytest.mark.parametrize("relative", CURRENT_DOCS)
def test_multiline_dimacs_is_never_written_with_a_double_quoted_backslash_n(relative):
    # The DIMACS parser rejects a literal backslash-n; a POSIX double-quoted "\n" stays literal.
    bad = re.findall(r'--cnf "[^"\n]*\\n', read(relative))
    assert not bad, f"{relative}: use --cnf $'...\\n...' in a POSIX shell, found {bad[:1]}"


def test_the_1669_test_count_is_only_quoted_as_history():
    for name in LANGUAGE_READMES:
        for line in read(name).splitlines():
            if "1669" in line:
                assert "Historical" in line or "historique" in line.lower() or "historisch" in line.lower(), (
                    f"{name}: '1669 Python tests' must be labelled historical: {line[:80]}"
                )


# ---------------------------------------------------------------------------
# 4. One authoritative architecture document
# ---------------------------------------------------------------------------

def test_root_architecture_is_the_single_authority():
    root = read("ARCHITECTURE.md")
    assert "single authoritative architecture document" in root
    assert "docs/ARCHITECTURE.md" in root and "historical" in root.lower()


def test_docs_architecture_is_marked_historical_and_points_to_the_root():
    old = read("docs/ARCHITECTURE.md")
    head = old[:900]
    assert "HISTORICAL" in head and "NOT AUTHORITATIVE" in head
    assert "(../ARCHITECTURE.md)" in head


def test_readme_documentation_table_says_which_architecture_file_is_authoritative():
    text = read("README.md")
    assert "the single authoritative architecture document" in text
    assert "historical" in text.split("## Documentation", 1)[1].lower()


# ---------------------------------------------------------------------------
# 5. Numbers in the docs equal the numbers in the evidence
# ---------------------------------------------------------------------------

def freeze_numbers() -> dict:
    """The freeze-SHA gate numbers, parsed from the evidence file (not typed into the test)."""
    text = read("research/v7/evidence/waveE_E2.md")
    match = re.search(r"```json\n(.*?)```", text, flags=re.DOTALL)
    assert match, "waveE_E2.md lost its machine-readable freeze-number block"
    data = json.loads(match.group(1))
    assert data["schema"] == "hcs.freeze_numbers.v1"
    return data


def test_readme_numbers_equal_the_freeze_evidence_file():
    n = freeze_numbers()
    expected = [
        n["freeze_sha"],
        f'{n["python"]["passed"]}',
        f'{n["python"]["skipped"]}',
        f'{n["mutation"]["killed"]}/{n["mutation"]["total"]}',
        f'{n["web_unit"]["passed"]}/{n["web_unit"]["total"]}',
        f'{n["playwright"]["passed"]}',
        f'{n["ctest_vulkan"]["passed"]}/{n["ctest_vulkan"]["total"]}',
        f'{n["ctest_cpu"]["passed"]}/{n["ctest_cpu"]["total"]}',
    ]
    assert n["python"]["failed"] == 0
    for name in LANGUAGE_READMES + ("RELEASE_NOTES_DRAFT.md",):
        text = read(name)
        missing = [token for token in expected if token not in text]
        assert not missing, f"{name} does not state the freeze-SHA numbers {missing}"


# --- raw, freshly produced evidence (non-circular) --------------------------------------
# The freeze-number JSON block above is itself typed by a human from the same run the READMEs
# were copied from, so comparing README == block alone proves nothing. These tests parse the
# RAW tool output captured in research/v7/evidence/waveF_* (pytest summary, node:test TAP,
# ctest summaries, skip_budget JSON) and require the block and the READMEs to agree with it.

EVIDENCE = REPO / "research" / "v7" / "evidence"


def _raw(name: str) -> str:
    path = EVIDENCE / name
    assert path.is_file(), f"missing raw evidence file research/v7/evidence/{name}"
    return path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")


def raw_pytest() -> dict:
    line = [l for l in _raw("waveF_pytest_tail.txt").splitlines() if re.search(r"\d+ passed", l)][-1]
    counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|skipped|error|errors|deselected|xfailed|xpassed)", line)}
    return {"passed": counts.get("passed", 0), "skipped": counts.get("skipped", 0),
            "failed": counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)}


def raw_web_unit() -> dict:
    text = _raw("waveF_web_unit_tail.txt")
    return {"passed": int(re.search(r"^# pass (\d+)", text, re.M).group(1)),
            "total": int(re.search(r"^# tests (\d+)", text, re.M).group(1)),
            "failed": int(re.search(r"^# fail (\d+)", text, re.M).group(1))}


def raw_ctest(name: str) -> dict:
    text = _raw(name)
    m = re.search(r"(\d+)% tests passed(?:, (\d+) tests failed)? out of (\d+)", text)
    assert m, f"{name} has no ctest summary line"
    total = int(m.group(3))
    failed = len(re.findall(r"\*\*\*(?:Failed|Exception|Timeout|Not Run)", text)) + int(m.group(2) or 0)
    return {"passed": total - failed, "total": total}


def test_fresh_raw_evidence_has_no_failures():
    py = raw_pytest()
    assert py["failed"] == 0, py
    web = raw_web_unit()
    assert web["failed"] == 0 and web["passed"] == web["total"], web
    for name in ("waveF_ctest_cpu.txt", "waveF_ctest_vulkan.txt"):
        c = raw_ctest(name)
        assert c["passed"] == c["total"] > 0, (name, c)


def test_freeze_block_equals_the_raw_tool_output():
    n = freeze_numbers()
    py = raw_pytest()
    assert (n["python"]["passed"], n["python"]["skipped"], n["python"]["failed"]) == (py["passed"], py["skipped"], py["failed"])
    web = raw_web_unit()
    assert (n["web_unit"]["passed"], n["web_unit"]["total"]) == (web["passed"], web["total"])
    cpu, vk = raw_ctest("waveF_ctest_cpu.txt"), raw_ctest("waveF_ctest_vulkan.txt")
    assert (n["ctest_cpu"]["passed"], n["ctest_cpu"]["total"]) == (cpu["passed"], cpu["total"])
    assert (n["ctest_vulkan"]["passed"], n["ctest_vulkan"]["total"]) == (vk["passed"], vk["total"])


def test_readmes_state_the_raw_tool_output_numbers():
    py, web = raw_pytest(), raw_web_unit()
    cpu, vk = raw_ctest("waveF_ctest_cpu.txt"), raw_ctest("waveF_ctest_vulkan.txt")
    for name in LANGUAGE_READMES:
        text = read(name)
        for token in (f"{py['passed']}", f"{py['skipped']}", f"{web['passed']}/{web['total']}",
                      f"{vk['passed']}/{vk['total']}", f"{cpu['passed']}/{cpu['total']}"):
            assert token in text, f"{name} does not state fresh-evidence number {token}"


def test_fresh_skip_reasons_are_within_the_default_environment_budget():
    import skip_budget

    fresh = json.loads(_raw("waveF_skip_reasons.json"))
    assert fresh["total"] == raw_pytest()["skipped"], "skip JSON and pytest summary disagree"
    budget_doc = json.loads((REPO / "research" / "v7" / "SKIP_BUDGET.json").read_text(encoding="utf-8"))
    problems = skip_budget.compare(skip_budget.select_budget(budget_doc, None), fresh["reasons"])
    assert not problems, problems


def test_superseded_suite_numbers_are_gone_from_the_current_tables():
    # 2896/109 (commit 6fe4f01) and 105 web unit tests were the pre-freeze numbers.
    for name in LANGUAGE_READMES + ("RELEASE_NOTES_DRAFT.md",):
        text = read(name)
        for stale in ("2896", "6fe4f01", "105 passed"):
            assert stale not in text, f"{name} still quotes the superseded number {stale!r}"


def test_the_waveE_evidence_cited_by_the_docs_exists():
    for name in LANGUAGE_READMES + ("RELEASE_NOTES_DRAFT.md", "ARCHITECTURE.md"):
        assert "waveE_E2.md" in read(name), f"{name} does not cite the freeze evidence file"
    assert (REPO / "research" / "v7" / "evidence" / "waveE_E2.md").is_file()


def test_standalone_zip_is_described_as_future_until_published():
    for name in LANGUAGE_READMES:
        for line in read(name).splitlines():
            if "windows-x64.zip" in line:
                assert "on the release page" not in line, f"{name}: asset claimed as already published"
    text = read("README.md")
    assert "will be attached to the release" in text


def test_path_b_row_carries_the_measured_dominance_caveat():
    row = next(line for line in read("README.md").splitlines() if line.startswith("| **B** |"))
    assert "PATHB_DOMINANCE.json" in row and "dense statevector" in row and "faster" in row
    dominance = json.loads((REPO / "research/v7/evidence/PATHB_DOMINANCE.json").read_text(encoding="utf-8"))
    ran = [c for c in dominance["cases"] if c.get("state") == "RUN"]
    assert ran and all(c["ratio_path_b_over_dense"] > 1 for c in ran), "the caveat no longer matches the data"


def test_translations_do_not_state_a_protected_production_deployment():
    for name in ("README.de.md", "README.fr.md"):
        text = read(name)
        assert "1d38df2" not in text and "vercel curl" not in text, f"{name}: stale deployment statement"
        assert "cq-hecs-web.vercel.app" in text and "10/10" in text


def test_architecture_result_table_says_numerical_error_bound_is_none_unless_derived():
    text = read("ARCHITECTURE.md")
    row = next(line for line in text.splitlines() if line.startswith("| `numerical_error_bound` |"))
    assert "`None`" in row and "diagnostic only" in row and "Paths B and C derive none" in row


def test_llms_headline_does_not_overclaim_exactness():
    head = read("llms.txt").split("\n\n", 2)[1]
    assert "float64" in head and "native C++" in head
    assert "exact ring arithmetic, Vulkan" not in head
    assert "native C++ research component" in read("llms.txt")
    assert "native C++ research component" in read("llms-full.txt")


def test_changelog_marks_the_current_version_as_an_unreleased_candidate():
    from version import VERSION

    line = next(l for l in read("CHANGELOG.md").splitlines() if l.startswith(f"## [{VERSION}]"))
    assert "unreleased candidate" in line


def test_release_notes_draft_uses_the_five_status_headings():
    text = read("RELEASE_NOTES_DRAFT.md")
    for heading in ("## Implemented", "## Experimental", "## Measured", "## Formally checked", "## Not supported", "## Not run"):
        assert heading in text, f"RELEASE_NOTES_DRAFT.md lost {heading}"


# ---------------------------------------------------------------------------
# 6. Documented surface equals implemented surface
# ---------------------------------------------------------------------------

def test_every_openapi_route_is_documented_in_studio_md():
    spec = json.loads((REPO / "schemas" / "studio.openapi.json").read_text(encoding="utf-8"))
    studio = read("docs/STUDIO.md")
    missing = []
    for path in spec["paths"]:
        if path.startswith("/api/v1"):
            continue
        probe = path.split("{", 1)[0].rstrip("/") + ("/start" if "{" in path else "")
        if probe not in studio:
            missing.append(path)
    assert not missing, f"docs/STUDIO.md does not document: {missing}"


def test_every_qg_route_in_the_code_is_documented():
    source = (REPO / "cqhecs" / "studio" / "app.py").read_text(encoding="utf-8")
    routes = set(re.findall(r'"(/api/qg/v1/[a-z/\-]+)"', source))
    assert routes, "no QG routes found in the Studio source"
    text = read("docs/STUDIO.md") + read("docs/QUANTUM_GRAVITY_LAB.md")
    missing = []
    for route in sorted(routes):
        tail = route[len("/api/qg/v1/"):]
        if route not in text and tail not in text:
            missing.append(route)
    assert not missing, f"undocumented QG routes: {missing}"


def test_every_mcp_tool_is_documented_and_no_unknown_tool_is_documented():
    source = (REPO / "cqhecs" / "mcp_server.py").read_text(encoding="utf-8")
    tools = set(re.findall(r'"(cqhecs_[a-z_]+)":', source))
    assert len(tools) >= 11
    doc = read("docs/API_REFERENCE.md")
    assert not sorted(t for t in tools if t not in doc), "an MCP tool is undocumented"
    documented = set(re.findall(r"`(cqhecs_[a-z_]+)`", doc))
    assert documented <= tools, f"documented MCP tools that do not exist: {sorted(documented - tools)}"


def test_documented_mcp_protocol_versions_equal_the_implementation():
    from cqhecs import mcp_server

    doc = read("docs/API_REFERENCE.md")
    for version in mcp_server.SUPPORTED_PROTOCOL_VERSIONS:
        assert version in doc, f"MCP protocol {version} is not documented"


def test_documented_maxsat_contract_and_limits_match_the_code():
    from cqhecs import sat

    guide = read("MIGRATION_V7.md") + read("docs/API_REFERENCE.md")
    assert sat.MAXSAT_CONTRACT in guide
    assert "20 variables" in guide and "optimality_certificate" in guide


def test_documented_calibration_schema_and_labels_match_the_code():
    from cqhecs import calibration_v3

    text = read("MIGRATION_V7.md") + read("ARCHITECTURE.md")
    assert calibration_v3.SCHEMA_V3 in text
    for label in calibration_v3.PROVENANCE_LABELS:
        assert label in text, f"calibration provenance label {label!r} is undocumented"
    for policy in calibration_v3.POLICIES:
        assert policy in text


def test_documented_native_abi_version_equals_the_headers():
    header = (REPO / "include" / "cq_hecs_api.h").read_text(encoding="utf-8")
    major = re.search(r"CQ_HECS_ABI_MAJOR\s+(\d+)", header).group(1)
    minor = re.search(r"CQ_HECS_ABI_MINOR\s+(\d+)", header).group(1)
    assert f"{major}.{minor}" in read("docs/API_REFERENCE.md")
    assert f"{major}.{minor}" in read("MIGRATION_V7.md")


# ---------------------------------------------------------------------------
# 7. Links and cited evidence resolve
# ---------------------------------------------------------------------------

LINK_DOCS = CURRENT_DOCS + ("docs/ARCHITECTURE.md",)


@pytest.mark.parametrize("relative", LINK_DOCS)
def test_relative_links_resolve(relative):
    base = (REPO / relative).parent
    missing = []
    for target in re.findall(r"\]\(([^)\s]+)\)", read(relative)):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if not target or Path(target).name in MISSION_ALLOWLIST:
            continue
        if not (base / target).resolve().exists():
            missing.append(target)
    assert not missing, f"{relative} links to missing files: {missing}"


@pytest.mark.parametrize("relative", ["RELEASE_NOTES_DRAFT.md", "MIGRATION_V7.md", "ARCHITECTURE.md"])
def test_cited_evidence_files_exist(relative):
    text = read(relative)
    names = set(re.findall(r"`((?:research/v7/)?(?:evidence/)?wave[ABC]_[A-Za-z0-9_]+\.(?:md|json))`", text))
    names |= set(re.findall(r"`(research/v7/[A-Za-z0-9_/\.\-]+\.(?:md|json))`", text))
    for bare in re.findall(r"`(wave[ABC]_[A-Za-z0-9_]+\.(?:md|json))`", text):
        names.add(bare)
    missing = []
    for name in sorted(names):
        candidates = [
            REPO / name,
            REPO / "research" / "v7" / name,
            REPO / "research" / "v7" / "evidence" / name,
            REPO / "research" / "v7" / "evidence" / Path(name).name,
        ]
        if not any(c.is_file() for c in candidates):
            missing.append(name)
    assert not missing, f"{relative} cites evidence that does not exist: {missing}"


def test_release_notes_mirror_the_draft_body():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    norm = lambda p: (root / p).read_text(encoding="utf-8").replace("\r\n", "\n")
    notes, draft = norm("RELEASE_NOTES.md"), norm("RELEASE_NOTES_DRAFT.md")
    marker = "Migration steps for every"
    assert "**Version:** 7.0.0" in notes
    assert notes[notes.index(marker):] == draft[draft.index(marker):]
