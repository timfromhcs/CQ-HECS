"""W4-07: a typed exact model-count contract (``hcs.sat.count.v1``).

``count_models`` must return its integer as a decimal string so a value above 2**53
survives a JSON round-trip, and every returned document must carry the schema id. The
count is never a partial number: an exhausted budget is ``UNKNOWN`` with ``count=None``.
"""
import json

from cqhecs.sat import CNF, count_models


def test_a_count_document_carries_the_schema_id_and_a_decimal_string():
    result = count_models(CNF(num_vars=4, clauses=((1, 2),)))
    assert result["schema"] == "hcs.sat.count.v1"
    assert isinstance(result["count"], str)
    assert result["count"].isdigit()
    json.dumps(result)  # must not raise


def test_a_large_count_survives_json_as_a_string():
    # 60 unconstrained variables -> exactly 2**60 assignments.
    result = count_models(CNF(num_vars=60, clauses=()))
    assert result["status"] == "COUNTED"
    assert result["count"] == str(2**60)
    # It is a string, and JSON preserves it exactly (a float would lose the low bits).
    restored = json.loads(json.dumps(result))
    assert restored["count"] == "1152921504606846976"
    assert int(restored["count"]) == 2**60


def test_the_separator_backend_uses_the_same_schema():
    result = count_models(CNF(num_vars=4, clauses=((1, 2), (3, 4), (-1, -3))), method="separator")
    assert result["schema"] == "hcs.sat.count.v1"
    assert result["backend"] == "separator"
    assert isinstance(result["count"], str)


def test_an_exhausted_budget_is_unknown_with_no_count():
    result = count_models(CNF(num_vars=4, clauses=((1, 2), (3, 4), (-1, -3))), method="separator", separator_max_table_entries=1)
    assert result["schema"] == "hcs.sat.count.v1"
    assert result["status"] == "UNKNOWN"
    assert result["count"] is None
