"""W13: the Web column of FEATURE_COVERAGE.json is closed and its evidence exists.

Rules checked for every capability row:

* the Web cell has a legal status and is not ``TODO_VERIFY``;
* ``DONE`` / ``PARTIAL`` cells cite at least one repository file, and every cited path exists;
* ``NOT_APPLICABLE`` / ``UNAVAILABLE`` cells carry a technical reason (not a bare status) and
  every path they cite exists;
* claims that can be checked mechanically are (no MaxSAT control, the visual baselines, the
  documented bundle budget equals the enforced one, the i18n keys for import exist).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = json.loads((ROOT / "research" / "v7" / "FEATURE_COVERAGE.json").read_text("utf-8"))
LEGEND = set(DOC["status_legend"]) - {"TODO_VERIFY"}
PATH_RE = re.compile(r"\b((?:web|tests|docs|research|scripts)/[\w./-]+\.[A-Za-z0-9]+)")


def _cells():
    return [(row["area"], row["web"]) for row in DOC["capabilities"]]


@pytest.mark.parametrize("area,cell", _cells(), ids=lambda v: str(v)[:40])
def test_web_cell_is_closed_and_cites_real_files(area, cell):
    status, _, rest = cell.partition(" ")
    assert status in LEGEND, f"{area}: web status {status!r} is not a closed status"
    paths = [p.rstrip(".,;:)") for p in PATH_RE.findall(cell)]
    for path in paths:
        assert (ROOT / path).exists(), f"{area}: cited path does not exist: {path}"
    if status in ("DONE", "PARTIAL"):
        assert paths, f"{area}: a {status} cell must cite the file or test that shows it"
    else:
        assert len(rest.strip()) >= 40, f"{area}: {status} needs a technical reason"
    if status == "PARTIAL":
        assert re.search(r"Remainder|NOT_APPLICABLE|UNAVAILABLE|NOT_RUN", cell), f"{area}: PARTIAL must name what is missing"


def test_no_web_cell_is_todo_verify():
    assert not [a for a, c in _cells() if "TODO_VERIFY" in c]


def test_the_browser_has_no_maxsat_control():
    html = (ROOT / "web" / "index.html").read_text("utf-8")
    sources = "".join(p.read_text("utf-8") for p in (ROOT / "web" / "src").glob("*.ts"))
    assert not re.search(r"maxsat", html + sources, re.IGNORECASE)


def test_visual_baselines_cover_the_declared_views():
    shots = ROOT / "web" / "e2e" / "__snapshots__" / "visual.spec.ts"
    names = {p.name for p in shots.glob("*-win32.png")}
    expected = {f"{r}-{s}-{v}-win32.png" for r in ("lab", "code", "sat", "guide") for s in ("light", "dark") for v in ("360", "desktop")}
    assert expected <= names, sorted(expected - names)


def test_documented_bundle_budget_equals_the_enforced_one():
    script = (ROOT / "web" / "scripts" / "check_bundle_budget.mjs").read_text("utf-8")
    enforced = {k: int(v) for k, v in re.findall(r"(js|wasm|css): (\d+) \* 1024", script)}
    doc = (ROOT / "docs" / "WEB_ENGINES.md").read_text("utf-8")
    assert enforced == {"js": 270, "wasm": 18, "css": 8}
    assert "JS 270 KB, WebAssembly 18 KB, CSS 8 KB" in doc


def test_documented_memory_rule_matches_the_code():
    device = (ROOT / "web" / "src" / "device.ts").read_text("utf-8")
    assert "WASM_MAX_QUBITS = 27" in device and "MAX_RUN_SECONDS = 90" in device
    doc = (ROOT / "docs" / "WEB_ENGINES.md").read_text("utf-8")
    assert "capped at 27 qubits" in doc and "above 90 s is refused" in doc


def test_import_messages_exist_in_every_language():
    text = (ROOT / "web" / "src" / "i18n.ts").read_text("utf-8")
    for code in ("too_large", "not_json", "wrong_schema", "not_a_circuit", "digest_mismatch", "qasm_invalid", "bad_shots", "bad_seed", "bad_engine"):
        assert text.count(f'"import.{code}"') == 3, code
    assert text.count('"err.worker"') == 3
