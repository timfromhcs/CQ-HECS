"""W4-04: the ExecutionPlan document is published as a JSON Schema.

The schema is the shared contract for the plan across Python, CLI, MCP and Studio. These
tests keep the schema and the live document in step: a field added or removed without the
schema fails, and (when ``jsonschema`` is installed) a real document validates.
"""
import json
from pathlib import Path

import pytest

from cqhecs.execution_plan import PLAN_SCHEMA_VERSION, build_execution_plan

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "schemas" / "execution_plan.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

CIRCUITS = [
    [("h", [0], []), ("cx", [0, 1], []), ("measure", [0], [])],
    [("h", [0], []), ("t", [0], []), ("cx", [0, 1], [])],
]


def test_schema_declares_exactly_the_plan_fields():
    document = build_execution_plan(CIRCUITS[0]).to_dict()
    assert set(document) == set(SCHEMA["properties"])
    assert set(SCHEMA["required"]) == set(document)


def test_the_schema_is_a_closed_json_schema():
    assert SCHEMA["$schema"].startswith("https://json-schema.org")
    assert SCHEMA["additionalProperties"] is False
    assert SCHEMA["properties"]["schema_version"]["const"] == PLAN_SCHEMA_VERSION


def test_a_forced_refusal_document_still_matches_the_schema():
    document = build_execution_plan(CIRCUITS[1], forced_path="A").to_dict()
    assert set(document) == set(SCHEMA["properties"])
    assert document["refusal"] is not None


@pytest.mark.parametrize("circuit", CIRCUITS)
def test_a_real_document_validates_when_jsonschema_is_available(circuit):
    jsonschema = pytest.importorskip("jsonschema")
    document = build_execution_plan(circuit).to_dict()
    jsonschema.validate(instance=document, schema=SCHEMA)
