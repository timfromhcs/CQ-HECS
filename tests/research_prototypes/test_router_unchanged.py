"""W7 guard: the default router must never select research Paths E/F/G."""
import os
import re

import pytest

from cqhecs.router import VALID_PATHS, EntanglementAdaptiveRouter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _circuits():
    return [
        [("h", [0], []), ("cx", [0, 1], [])],
        [("h", [0], []), ("t", [0], []), ("cx", [0, 1], []), ("t", [1], [])],
        [("rx", [0], [0.3]), ("ry", [1], [0.4]), ("cx", [0, 1], []), ("cx", [1, 2], []), ("rz", [2], [0.2])],
    ]


def test_valid_paths_are_exactly_a_to_d():
    assert tuple(VALID_PATHS) == ("A", "B", "C", "D")
    assert set(EntanglementAdaptiveRouter.PATH_CAPABILITIES) == {"A", "B", "C", "D"}


@pytest.mark.parametrize("circuit", _circuits())
def test_executed_path_is_never_a_research_path(circuit):
    res = EntanglementAdaptiveRouter().route_and_execute(circuit, shots=64, seed=1)
    assert res.path in ("A", "B", "C", "D"), res.path


@pytest.mark.parametrize("circuit", _circuits())
def test_plan_does_not_select_or_offer_research_paths(circuit):
    plan = EntanglementAdaptiveRouter().plan(circuit).to_dict()
    assert plan["selected_path"] in ("A", "B", "C", "D", None)
    text = repr(plan)
    assert not re.search(r"['\"]path['\"]: ['\"][EFG]['\"]", text)


def test_forcing_a_research_path_is_a_typed_refusal():
    for p in ("E", "F", "G"):
        with pytest.raises(ValueError):
            EntanglementAdaptiveRouter().route_and_execute(_circuits()[0], preferred_path=p)


def test_stable_package_never_imports_research_prototypes():
    pat = re.compile(r"(research\.v7|path_e_tn2d|path_f_mps_trajectory|path_g_mpe|mps_core|prototypes)")
    offenders = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "cqhecs")):
        for f in files:
            if not f.endswith(".py"):
                continue
            with open(os.path.join(base, f), encoding="utf-8") as fh:
                for line in fh.read().splitlines():
                    s = line.strip()
                    if (s.startswith("import ") or s.startswith("from ")) and pat.search(s):
                        offenders.append((f, s))
    assert offenders == []
