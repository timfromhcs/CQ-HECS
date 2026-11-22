"""W12: FEATURE_COVERAGE.json has no empty cell and no unresolved TODO_VERIFY outside the Web column.

An empty cell blocks release (V7 section 16.1). The Web column belongs to the Web wave and is not
checked for ``TODO_VERIFY`` here, but it must still be non-empty and carry a legal status.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((ROOT / "research" / "v7" / "FEATURE_COVERAGE.json").read_text("utf-8"))
SURFACES = DOC["surfaces"]
LEGEND = set(DOC["status_legend"])
#: ``N/A`` is the legacy spelling used in the first cut for "not applicable".
LEGACY_NA = {"N/A"}


def _rows():
    return [(c["area"], s, c.get(s)) for c in DOC["capabilities"] for s in SURFACES]


def _status(cell):
    return str(cell).strip().split(" ", 1)[0]


def test_every_surface_is_declared_and_every_row_has_an_area_and_parity_rule():
    assert SURFACES == ["python_api", "cli", "mcp", "studio", "web", "windows_exe", "native_hardware"]
    for row in DOC["capabilities"]:
        assert row["area"].strip() and row.get("parity_rule", "").strip()


@pytest.mark.parametrize("area,surface,cell", _rows(), ids=lambda v: str(v)[:40])
def test_no_cell_is_empty_and_every_status_is_legal(area, surface, cell):
    assert isinstance(cell, str) and cell.strip(), f"empty cell: {area} / {surface}"
    status = _status(cell)
    assert status in LEGEND | LEGACY_NA, f"{area}/{surface}: unknown status {status!r}"


@pytest.mark.parametrize("area,surface,cell", [r for r in _rows() if r[1] != "web"], ids=lambda v: str(v)[:40])
def test_no_todo_verify_remains_outside_the_web_column(area, surface, cell):
    assert "TODO_VERIFY" not in cell, f"unresolved: {area} / {surface}: {cell}"
    assert "(verify)" not in cell.lower(), f"unresolved: {area} / {surface}: {cell}"


@pytest.mark.parametrize("area,surface,cell", [r for r in _rows() if r[1] == "windows_exe"], ids=lambda v: str(v)[:40])
def test_windows_exe_claims_are_never_done_without_a_run(area, surface, cell):
    status = _status(cell)
    if status == "DONE":
        pytest.fail(f"{area}: windows_exe DONE needs an EXE run, none exists in this tree")
    if status == "PARTIAL":
        assert "NOT_RUN" in cell, f"{area}: PARTIAL EXE cell must say what was not run"


def test_every_non_web_cell_says_what_it_is_not_just_a_status_word():
    for area, surface, cell in _rows():
        if surface != "web":
            assert len(cell.split()) >= 3, f"{area}/{surface}: bare status {cell!r}"


def test_unavailable_and_not_applicable_cells_carry_a_reason():
    for area, surface, cell in _rows():
        status = _status(cell)
        if status in {"UNAVAILABLE", "NOT_APPLICABLE"} and surface != "web":
            assert len(cell.split()) >= 3, f"{area}/{surface}: {status} needs a technical reason"


def test_research_paths_efg_are_not_in_the_package_or_the_router():
    from cqhecs.router import EntanglementAdaptiveRouter

    assert sorted(EntanglementAdaptiveRouter.PATH_CAPABILITIES) == ["A", "B", "C", "D"]
    backends = ROOT / "cqhecs" / "backends"
    assert not [p.name for p in backends.glob("path_[efg]*")]
    for name in (ROOT / "cqhecs").rglob("*.py"):
        assert not re.search(r"^from .*(path_e_tn2d|path_f_mps_trajectory|path_g_mpe)", name.read_text("utf-8"), re.M)


def test_the_mcp_tool_count_in_the_matrix_is_the_real_count():
    from cqhecs.mcp_server import TOOLS

    row = next(c for c in DOC["capabilities"] if c["area"] == "Studio / MCP / API")
    match = re.search(r"(\d+) tools", row["mcp"])
    assert match and int(match.group(1)) == len(TOOLS)
