"""Property and fuzz tests for the DIMACS parser and CNF constructor (W15 / C5)."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from cqhecs.sat import CNF, CNFFormatError, count_models, parse_dimacs, solve

FUZZ = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
    derandomize=True,
)

_DIMACS_ALPHABET = "pcnf 0123456789-\n\t\r%+x.e"


@st.composite
def formulas(draw, max_vars=6, max_clauses=8):
    n = draw(st.integers(1, max_vars))
    lit = st.integers(1, n).flatmap(lambda v: st.sampled_from([v, -v]))
    clauses = draw(st.lists(st.lists(lit, min_size=0, max_size=4, unique_by=abs), max_size=max_clauses))
    return n, clauses


def _render(n, clauses):
    return f"p cnf {n} {len(clauses)}\n" + "".join(" ".join(map(str, c + [0])) + "\n" for c in clauses)


@FUZZ
@given(text=st.text(alphabet=_DIMACS_ALPHABET, max_size=200))
def test_arbitrary_dimacs_like_text_is_a_cnf_or_a_format_error(text):
    try:
        cnf = parse_dimacs(text)
    except CNFFormatError:
        return
    assert isinstance(cnf, CNF)
    assert cnf.num_vars >= 0
    for clause in cnf.clauses:
        assert len(set(clause)) == len(clause)
        assert all(lit != 0 and abs(lit) <= cnf.num_vars for lit in clause)


@FUZZ
@given(text=st.text(max_size=200))
def test_arbitrary_unicode_never_escapes_as_another_exception(text):
    try:
        parse_dimacs(text)
    except CNFFormatError:
        pass


@FUZZ
@given(data=formulas())
def test_render_parse_round_trip(data):
    n, clauses = data
    cnf = parse_dimacs(_render(n, clauses))
    assert cnf.num_vars == n
    assert [list(c) for c in cnf.clauses] == clauses
    again = parse_dimacs(cnf.to_dimacs())
    assert again.clauses == cnf.clauses and again.sha256 == cnf.sha256


@FUZZ
@given(data=formulas(), newline=st.sampled_from(["\n", "\r\n", "\r"]), pad=st.sampled_from(["", " ", "\t"]))
def test_whitespace_and_newline_style_do_not_change_the_formula(data, newline, pad):
    n, clauses = data
    base = parse_dimacs(_render(n, clauses))
    text = _render(n, clauses).replace("\n", newline).replace(" ", pad + " ")
    assert parse_dimacs(text).clauses == base.clauses


@FUZZ
@given(data=formulas(), where=st.integers(0, 200), junk=st.sampled_from(["x", "1.5", "--1", "0x1", "9" * 30, "1e2"]))
def test_a_junk_token_is_refused_not_ignored(data, where, junk):
    n, clauses = data
    assume(clauses)
    text = _render(n, clauses)
    lines = text.split("\n")
    body = [i for i, ln in enumerate(lines) if i > 0 and ln]
    idx = body[where % len(body)]
    lines[idx] = junk + " " + lines[idx]
    with pytest.raises(CNFFormatError):
        parse_dimacs("\n".join(lines))


@FUZZ
@given(data=formulas())
def test_truncating_the_final_terminator_is_refused(data):
    n, clauses = data
    assume(clauses and clauses[-1] is not None)
    text = _render(n, clauses).rstrip("\n")
    assert text.endswith(" 0") or text.endswith("0")
    cut = text[: text.rfind("0")]
    if cut.strip().split() == ["p", "cnf", str(n), str(len(clauses))]:
        return
    with pytest.raises(CNFFormatError):
        parse_dimacs(cut + "\n")


@FUZZ
@given(data=formulas(), delta=st.sampled_from([-1, 1, 5]))
def test_wrong_declared_clause_count_is_refused(data, delta):
    n, clauses = data
    assume(len(clauses) + delta >= 0)
    text = f"p cnf {n} {len(clauses) + delta}\n" + _render(n, clauses).split("\n", 1)[1]
    with pytest.raises(CNFFormatError):
        parse_dimacs(text)


@FUZZ
@given(data=formulas(max_vars=5, max_clauses=6))
def test_solver_and_counter_agree_with_brute_force(data):
    n, clauses = data
    cnf = parse_dimacs(_render(n, clauses))
    brute = 0
    for bits in range(1 << n):
        if all(any(((bits >> (abs(l) - 1)) & 1) == (l > 0) for l in c) for c in clauses):
            brute += 1
    result = solve(cnf, timeout_seconds=5)
    assert (result.status == "SAT") == (brute > 0)
    counted = count_models(cnf, timeout_seconds=5)
    assert counted["status"] in ("EXACT", "COUNTED", "OK") or counted.get("count") is not None
    assert int(counted["count"]) == brute


@pytest.mark.parametrize(
    "text",
    [
        "", "c only a comment\n", "p cnf 1 1\n", "p cnf 1 0\np cnf 1 0\n", "p cnf -1 0\n", "p cnf 1 -1\n",
        "p cnf 1\n", "p dnf 1 1\n1 0\n", "1 0\np cnf 1 1\n", "p cnf 1 1\n2 0\n", "p cnf 1 1\n1\n",
        "p cnf 1 1\n1 -1 0\np cnf 1 1\n", "p cnf a b\n", "p cnf 1 1\n\x00 0\n",
    ],
)
def test_known_malformed_inputs_are_format_errors(text):
    with pytest.raises(CNFFormatError):
        parse_dimacs(text)


def test_non_string_input_is_a_format_error():
    for bad in (None, b"p cnf 1 0\n", 5, ["p cnf 1 0"]):
        with pytest.raises(CNFFormatError):
            parse_dimacs(bad)  # type: ignore[arg-type]


def test_tautology_empty_clause_and_duplicates_follow_the_documented_contract():
    cnf = parse_dimacs("p cnf 2 3\n1 -1 0\n0\n2 2 0\n")
    assert cnf.clauses == ((1, -1), (), (2,))
    assert solve(cnf, timeout_seconds=2).status == "UNSAT"  # the empty clause


@pytest.mark.parametrize("bad", [True, 1.5, "1", None, 0])
def test_cnf_constructor_rejects_non_integer_or_zero_literals(bad):
    with pytest.raises(CNFFormatError):
        CNF(num_vars=3, clauses=((bad,),))


def test_cnf_constructor_rejects_duplicate_literals_and_out_of_range():
    with pytest.raises(CNFFormatError):
        CNF(num_vars=3, clauses=((1, 1),))
    with pytest.raises(CNFFormatError):
        CNF(num_vars=3, clauses=((4,),))
    with pytest.raises(CNFFormatError):
        CNF(num_vars=-1, clauses=())


def test_original_and_canonical_digests_are_separate():
    a = parse_dimacs("p cnf 2 1\n1 1 2 0\n")
    b = parse_dimacs("p cnf 2 1\n1 2 0\n")
    assert a.sha256 == b.sha256  # canonical form (duplicate removed)
    assert a.original_sha256 != b.original_sha256  # original text differs


@pytest.mark.parametrize("token", ["1_0", "+1", "\u0661"])
def test_non_ascii_or_decorated_integers_are_refused(token):
    with pytest.raises(CNFFormatError):
        parse_dimacs(f"p cnf 20 1\n{token} 0\n")
