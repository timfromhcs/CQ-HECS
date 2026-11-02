"""The provenance card is only useful if it can be wrong.

These tests attack the card instead of admiring it: a tampered digest, a missing field, a
legacy v1 document, an oversized payload, a nonsense engine mode. The contract worth having
is the one that refuses, not the one that always validates.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cqhecs import provenance
from cqhecs.cli import EXIT_OK, main

CNF = "p cnf 2 4\n1 2 0\n1 -2 0\n-1 2 0\n-1 -2 0\n"


def card(**overrides):
    defaults = dict(
        software=provenance.Software("cqhecs", "5.0.0", "35506b7"),
        input_kind="cnf",
        payload=CNF,
        engine_kind="dpll",
        precision="exact-integer",
        mode="EXACT",
        status="UNSAT",
        elapsed_ms=1.25,
        limits=["SAT/UNSAT refers to this formula only."],
    )
    defaults.update(overrides)
    return provenance.build(**defaults)


def test_a_built_card_validates_and_carries_the_input_digest():
    document = card().to_dict()
    assert provenance.validate(document) == []
    assert document["schema"] == "hcs.run.v2"
    assert document["input"]["digest"] == provenance.sha256_text(CNF)
    assert document["input"]["payload"] == CNF


def test_a_tampered_payload_is_detected():
    document = card().to_dict()
    document["input"]["payload"] = document["input"]["payload"].replace("-1 2 0", "-1 1 0")
    problems = provenance.validate(document)
    assert any("digest does not match" in problem for problem in problems), problems


def test_a_missing_required_field_is_reported():
    document = card().to_dict()
    del document["limits"]
    problems = provenance.validate(document)
    assert any("missing required field 'limits'" in problem for problem in problems), problems


def test_a_legacy_v1_web_card_is_refused_not_reinterpreted():
    legacy = {"schema": "cqhecs.web.run/1.1", "app_version": "4.2.0", "input": {"qasm": "qreg q[1];"}}
    problems = provenance.validate(legacy)
    assert len(problems) == 1
    assert "not reinterpreted" in problems[0]
    assert "regenerate it" in problems[0]


def test_an_unknown_schema_is_refused():
    problems = provenance.validate({"schema": "something/else"})
    assert problems and "expected 'hcs.run.v2'" in problems[0]


def test_error_kinds_are_separate_and_may_be_null():
    document = card(error=provenance.Errors(approximation=0.01, numerical=None, sampling=None)).to_dict()
    assert provenance.validate(document) == []
    error = document["result"]["error"]
    assert error["approximation"] == 0.01
    assert error["numerical"] is None and error["sampling"] is None


def test_a_negative_error_bound_is_rejected():
    document = card().to_dict()
    document["result"]["error"]["numerical"] = -0.1
    assert any("result.error.numerical" in problem for problem in provenance.validate(document))


@pytest.mark.parametrize(
    "overrides",
    [
        {"precision": "float128"},
        {"mode": "PROBABLY"},
        {"input_kind": "qasm"},
        {"payload": ""},
        {"limits": []},
        {"seed": "42"},
    ],
)
def test_construction_refuses_nonsense(overrides):
    with pytest.raises(ValueError):
        card(**overrides)


def test_an_oversized_payload_is_refused_instead_of_truncated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(provenance, "MAX_PAYLOAD_BYTES", 64)
    oversized = card(payload=CNF * 20)
    with pytest.raises(ValueError, match="above the 64 byte limit"):
        oversized.write(tmp_path / "card.json")
    assert not (tmp_path / "card.json").exists()


def test_read_refuses_an_invalid_card(tmp_path: Path):
    document = card().to_dict()
    document["input"]["digest"] = "0" * 64
    path = tmp_path / "card.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="digest does not match"):
        provenance.read(path)


def test_the_schema_file_states_the_same_required_fields():
    schema = json.loads(provenance.SCHEMA_FILE.read_text(encoding="utf-8"))
    assert set(provenance.REQUIRED) <= set(schema["required"])
    assert schema["properties"]["schema"]["const"] == provenance.SCHEMA
    assert set(schema["properties"]["engine"]["properties"]["precision"]["enum"]) == set(provenance.PRECISIONS)
    assert set(schema["properties"]["engine"]["properties"]["mode"]["enum"]) == set(provenance.MODES)


def test_the_cli_writes_a_card_that_validates(tmp_path: Path):
    target = tmp_path / "card.json"
    assert main(["sat", "solve", "--cnf", CNF, "--provenance", str(target)]) == EXIT_OK
    document = json.loads(target.read_text(encoding="utf-8"))
    assert provenance.validate(document) == []
    assert document["input"]["kind"] == "cnf"
    assert document["result"]["status"] == "UNSAT"
    assert document["engine"]["kind"] == "dpll"


def test_the_cli_records_the_engine_that_ran(tmp_path: Path):
    target = tmp_path / "card.json"
    assert main(["sat", "solve", "--cnf", CNF, "--engine", "watched", "--provenance", str(target)]) == EXIT_OK
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["engine"]["kind"] == "watched"
    assert provenance.validate(document) == []
