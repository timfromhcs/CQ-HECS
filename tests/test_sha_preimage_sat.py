"""Differential tests: the CNF encoder of reduced-round SHA-256 against Python.

Two independent implementations must agree. The clauses in
``cqhecs.sha.preimage_sat`` are compared with

* ``cqhecs.sha.sha256_reference.compress`` at W = 32 (the shipped reference), and
* an exhaustive Python search over the free schedule words at the toy widths
  W = 8 and W = 16.

The toy widths reduce every rotation of FIPS 180-4 by 2, 13, 22 (and so on)
modulo W. **They are not SHA-256**; they exist so that an exhaustive oracle is
possible and so that UNSAT can be certified cheaply. No test here says anything
about inverting 32-bit SHA-256, and nothing here is a statement about
``P`` versus ``NP``.

Every solved verdict comes from ``cqhecs.sat``: a SAT model is verified clause by
clause by that module and then replayed against the Python reference; an UNSAT
verdict is accepted only with a checked tree-resolution certificate (or, for the
flipped-bit case, a DRAT proof accepted by ``cqhecs.drat``).
"""
from __future__ import annotations

import itertools

import pytest

from cqhecs import drat
from cqhecs import sat as sat
from cqhecs.omniwave.engine import OmniwaveConfig, OmniwaveEngine
from cqhecs.sha import preimage_sat as ps
from cqhecs.sha import sha256_reference as ref

#: Fixed blocks used by the differential tests.
BLOCKS = {
    "counting": bytes(range(64)),
    "zeros": bytes(64),
    "mixed": bytes((i * 37 + 11) & 0xFF for i in range(64)),
}

#: Rounds that actually finish at W = 32 on this hardware (see SAT_SHA.md).
FULL_WIDTH_ROUNDS = (1, 2, 4, 8)


def brute_force_matches(block, rounds, free_words, target_state, width):
    """Every assignment of the free schedule words that reaches ``target_state``.

    This is the oracle for the toy widths: it uses only the integer model in
    :mod:`cqhecs.sha.preimage_sat`, never the clauses.
    """
    words = ps.block_words(block, width)
    iv = ps.masked_iv(width)
    hits = []
    for combination in itertools.product(*[range(1 << width) for _ in free_words]):
        trial = list(words)
        for index, value in zip(free_words, combination):
            trial[index] = value
        if ps.width_compress(iv, trial, rounds=rounds, width=width) == tuple(target_state):
            hits.append(tuple(combination))
    return hits


# ---------------------------------------------------------------------------
# The Python side: the toy model really is the reference algorithm at W = 32
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("rounds", [0, 1, 3, 7, 16, 24])
def test_toy_model_reduces_to_the_shipped_reference(rounds):
    """At W = 32 the generalised model must equal ``sha256_reference.compress``.

    This anchors the oracle used for the toy widths: the only difference between
    the two is the word width.
    """
    block = BLOCKS["mixed"]
    words = ref.block_words(block)
    assert ps.toy_compress(ref.IV, words, rounds=rounds, width=32) == ref.compress(
        ref.IV, words, rounds=rounds
    )


def test_full_width_block_words_and_iv_are_the_reference_ones():
    block = BLOCKS["counting"]
    assert ps.block_words(block) == ref.block_words(block)
    assert ps.masked_iv() == tuple(ref.IV)


# ---------------------------------------------------------------------------
# Encoder correctness: CNF vs the shipped reference at W = 32
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(BLOCKS))
@pytest.mark.parametrize("rounds", FULL_WIDTH_ROUNDS)
def test_encoder_matches_the_reference(name, rounds):
    """SAT, and the decoded state equals ``compress(IV, words, rounds)``."""
    block = BLOCKS[name]
    instance = ps.build_verification_instance(block, rounds)
    formula = instance.to_cnf()

    # The recorded counts describe the text that the solver actually parses.
    assert formula.num_vars == instance.num_vars
    assert formula.num_clauses == instance.num_clauses

    result = sat.solve(formula, timeout_seconds=120.0, certify=False)
    assert result.status == sat.SAT, result.note
    assert result.model_verified

    expected = ref.compress(ref.IV, ref.block_words(block), rounds=rounds)
    assert instance.decode_output(result.assignment) == expected
    assert instance.decode_input_words(result.assignment) == ref.block_words(block)

    replay = ps.verify_model(instance, result.assignment)
    assert replay["agrees"] is True
    assert replay["reference"] == "cqhecs.sha.sha256_reference.compress"
    assert replay["formula_satisfied"] is True


def test_all_sixty_four_rounds_match_the_reference():
    """The encoder covers the complete compression function, not a toy subset.

    This is a correctness statement about the clauses only. It says nothing about
    preimage search: every input word here is a constant.
    """
    block = BLOCKS["mixed"]
    instance = ps.build_verification_instance(block, 64)
    formula = instance.to_cnf()
    result = sat.solve(formula, timeout_seconds=180.0, certify=False)
    assert result.status == sat.SAT, result.note
    assert instance.decode_output(result.assignment) == ref.compress(ref.IV, ref.block_words(block))
    assert ps.verify_model(instance, result.assignment)["agrees"] is True


# ---------------------------------------------------------------------------
# Unsatisfiability: one flipped output bit
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("rounds", [1, 4, 8])
def test_flipping_one_output_bit_is_unsat_with_a_checked_certificate(rounds):
    """A state one bit away from the reference output has no model at all."""
    block = BLOCKS["counting"]
    honest = list(ref.compress(ref.IV, ref.block_words(block), rounds=rounds))
    honest[3] ^= 0x40
    instance = ps.build_verification_instance(block, rounds, expected_state=honest)
    formula = instance.to_cnf()

    result = sat.solve(formula, timeout_seconds=120.0)
    assert result.status == sat.UNSAT, result.note
    assert result.certified and result.certification == "TREE_RESOLUTION_CHECKED"
    assert sat.check_refutation(formula.clauses, result.certificate) is True


def test_drat_proof_for_the_flipped_bit_is_produced_and_checked():
    """The same UNSAT verdict also carries a DRAT proof, re-checked here.

    ``cqhecs.sat`` emits a tree-resolution certificate; OMNIWAVE emits DRAT. Both
    are proof logs replayed by separate checkers, so the UNSAT verdict does not
    rest on the search engine alone.
    """
    block = BLOCKS["counting"]
    honest = list(ref.compress(ref.IV, ref.block_words(block), rounds=8))
    honest[0] ^= 1
    instance = ps.build_verification_instance(block, 8, expected_state=honest)
    formula = instance.to_cnf()

    engine = OmniwaveEngine(formula, OmniwaveConfig(timeout_seconds=120.0))
    result = engine.run()
    assert result.status == sat.UNSAT, result.note
    assert result.certification == "DRAT_CHECKED"

    # Re-check the same log here, independently of the engine that wrote it.
    proof = engine.proof()
    assert proof, "an exhaustive refutation must come with a proof log"
    checked = drat.check_drat(formula.clauses, proof, timeout_seconds=120.0)
    assert checked.valid is True, checked.reason


def test_toy_width_unsat_matches_exhaustive_search():
    """W = 8, 2 rounds: an unreachable target has no preimage, and is UNSAT."""
    block = BLOCKS["mixed"]
    target = (0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88)
    assert brute_force_matches(block, 2, [0], target, 8) == []

    instance = ps.build_partial_preimage_instance(block, 2, [0], width=8, target_state=target)
    formula = instance.to_cnf()
    result = sat.solve(formula, timeout_seconds=120.0)
    assert result.status == sat.UNSAT, result.note
    assert result.certified and result.certification == "TREE_RESOLUTION_CHECKED"
    assert sat.check_refutation(formula.clauses, result.certificate) is True


# ---------------------------------------------------------------------------
# A genuine preimage search whose oracle is exhaustive enumeration
# ---------------------------------------------------------------------------
def test_one_free_word_preimage_matches_brute_force():
    """W = 8, 2 rounds, one free word: exactly one preimage, found by both sides."""
    block = BLOCKS["mixed"]
    words = ps.block_words(block, 8)
    target = ps.width_compress(ps.masked_iv(8), words, rounds=2, width=8)

    hits = brute_force_matches(block, 2, [0], target, 8)
    assert hits == [(words[0],)], "the block's own word must be the unique preimage"

    instance = ps.build_partial_preimage_instance(block, 2, [0], width=8)
    formula = instance.to_cnf()
    assert instance.free_bits == 8

    result = sat.solve(formula, timeout_seconds=120.0, certify=False)
    assert result.status == sat.SAT
    assert (instance.decode_input_words(result.assignment)[0],) in hits
    assert ps.verify_model(instance, result.assignment)["agrees"] is True

    counted = sat.count_models(formula, timeout_seconds=120.0)
    assert counted["status"] == sat.COUNTED
    assert int(counted["count"]) == len(hits)

    models = sat.enumerate_models(formula, limit=16, timeout_seconds=120.0)
    assert models["status"] == "COMPLETE" and models["complete"] is True
    assert sorted({(instance.decode_input_words(m)[0],) for m in models["models"]}) == sorted(hits)


def test_two_free_words_match_brute_force():
    """W = 8, 2 rounds, two free words: 65 536 candidates, one preimage."""
    block = BLOCKS["mixed"]
    words = ps.block_words(block, 8)
    target = ps.width_compress(ps.masked_iv(8), words, rounds=2, width=8)

    hits = brute_force_matches(block, 2, [0, 1], target, 8)
    assert hits == [(words[0], words[1])]

    instance = ps.build_partial_preimage_instance(block, 2, [0, 1], width=8)
    formula = instance.to_cnf()
    assert instance.free_bits == 16

    counted = sat.count_models(formula, timeout_seconds=120.0)
    assert counted["status"] == sat.COUNTED
    assert int(counted["count"]) == len(hits)

    models = sat.enumerate_models(formula, limit=8, timeout_seconds=120.0)
    assert models["complete"] is True
    decoded = {
        (instance.decode_input_words(m)[0], instance.decode_input_words(m)[1])
        for m in models["models"]
    }
    assert decoded == set(hits)


def test_sixteen_bit_preimage_matches_brute_force():
    """W = 16, 2 rounds, one free word: 65 536 candidates against the CNF count."""
    block = BLOCKS["counting"]
    words = ps.block_words(block, 16)
    target = ps.width_compress(ps.masked_iv(16), words, rounds=2, width=16)

    hits = brute_force_matches(block, 2, [0], target, 16)
    assert hits == [(words[0],)]

    instance = ps.build_partial_preimage_instance(block, 2, [0], width=16)
    formula = instance.to_cnf()
    result = sat.solve(formula, timeout_seconds=120.0, certify=False)
    assert result.status == sat.SAT
    assert instance.decode_input_words(result.assignment)[0] == hits[0][0]

    counted = sat.count_models(formula, timeout_seconds=180.0)
    assert counted["status"] == sat.COUNTED
    assert int(counted["count"]) == len(hits)


def test_preimage_through_the_encoded_message_schedule():
    """W = 8, 20 rounds: the schedule is CNF, not a Python pre-computation.

    Above 16 rounds the encoder has to define W[16..] with clauses
    (FIPS 180-4 §5.2.2). The last schedule word is freed and the answer is
    checked against an exhaustive 256-candidate search.
    """
    block = BLOCKS["mixed"]
    words = ps.block_words(block, 8)
    target = ps.width_compress(ps.masked_iv(8), words, rounds=20, width=8)

    hits = brute_force_matches(block, 20, [15], target, 8)
    assert hits == [(words[15],)]

    instance = ps.build_partial_preimage_instance(block, 20, [15], width=8)
    formula = instance.to_cnf()
    result = sat.solve(formula, timeout_seconds=120.0, certify=False)
    assert result.status == sat.SAT, result.note
    assert instance.decode_input_words(result.assignment)[15] == hits[0][0]
    assert ps.verify_model(instance, result.assignment)["agrees"] is True

    # Without the freed word the instance must derive the same output.
    fixed = ps.build_verification_instance(block, 20, width=8)
    assert sat.solve(fixed.to_cnf(), timeout_seconds=120.0, certify=False).status == sat.SAT


# ---------------------------------------------------------------------------
# Scale: cost per round at W = 32
# ---------------------------------------------------------------------------
def test_scale_growth_is_monotone_and_matches_the_gate_count():
    """Variables and clauses per round at W = 32 for rounds 1..8.

    Per round the encoder allocates, per bit: two XORs for each big Sigma (2 + 2),
    three gates for Ch, five for Maj and five for each of the seven adders -- so
    47 fresh variables and 162 clauses per bit in the steady state, i.e.
    ``47 * W`` variables and ``162 * W`` clauses per round. The first rounds are
    slightly cheaper in clauses because gates on two constants collapse
    tautologies, which is why the steady-state delta is asserted from round 5 on.
    """
    block = BLOCKS["counting"]
    width = ps.DEFAULT_WIDTH
    measurements = []
    for rounds in range(1, 9):
        instance = ps.sha256_round_cnf(ps.masked_iv(width), ps.block_words(block, width), rounds)
        measurements.append((rounds, instance.num_vars, instance.num_clauses))

    variables = [item[1] for item in measurements]
    clauses = [item[2] for item in measurements]
    assert variables == sorted(variables) and len(set(variables)) == 8
    assert clauses == sorted(clauses) and len(set(clauses)) == 8

    # Exact closed form: the true constant, 40*W feed-forward variables and
    # 47*W per round.
    for rounds, var_count, _ in measurements:
        assert var_count == 1 + 40 * width + 47 * width * rounds

    # Steady-state clause cost per round, once every state word is a variable.
    for (previous, _, before), (current, _, after) in zip(measurements, measurements[1:]):
        if current >= 5:
            assert after - before == 162 * width, f"rounds {previous}->{current}"

    # The clause-to-variable ratio is measurable and bounded; it is ~3.45 here,
    # so a bound of "more than five clauses per variable" would be false.
    for _, var_count, clause_count in measurements:
        assert 3 * var_count < clause_count < 4 * var_count


def test_partial_assertion_and_no_feed_forward():
    """Subset assertions and the ``feed_forward=False`` variant both track the reference."""
    block = BLOCKS["mixed"]
    words = ref.block_words(block)
    raw = ref.compress(ref.IV, words, rounds=2, feed_forward=False)

    instance = ps.build_verification_instance(block, 2, feed_forward=False)
    result = sat.solve(instance.to_cnf(), timeout_seconds=120.0, certify=False)
    assert result.status == sat.SAT
    assert instance.decode_output(result.assignment) == raw
    assert ps.verify_model(instance, result.assignment)["agrees"] is True

    # Assert only word 4: the rest of the state is left free, which must still be
    # satisfiable, and the asserted word must equal the reference value.
    partial = ps.sha256_round_cnf(
        ps.masked_iv(), words, 2, asserted_state=raw, asserted_words=(4,), feed_forward=False
    )
    partial_result = sat.solve(partial.to_cnf(), timeout_seconds=120.0, certify=False)
    assert partial_result.status == sat.SAT
    assert partial.asserted_state == raw


# ---------------------------------------------------------------------------
# Refusals: the encoder rejects sizes and indices it cannot encode
# ---------------------------------------------------------------------------
def test_encoder_rejects_invalid_requests():
    block = BLOCKS["counting"]
    with pytest.raises(ValueError):
        ps.build_verification_instance(b"\x00" * 63, 1)  # not a 64-byte block
    with pytest.raises(ValueError):
        ps.build_verification_instance(block, 65)  # more rounds than SHA-256 has
    with pytest.raises(ValueError):
        ps.build_verification_instance(block, 1, width=33)
    with pytest.raises(ValueError):
        ps.build_partial_preimage_instance(block, 1, [16], width=8)
    with pytest.raises(ValueError):
        ps.build_partial_preimage_instance(block, 1, [0], width=8, target_state=(0x100,) * 8)

    encoder = ps.WordEncoder(8)
    with pytest.raises(ValueError):
        encoder.add(encoder.const_bits(0), encoder.const_bits(0), W=16)
    with pytest.raises(ValueError):
        encoder.add_many([encoder.const_bits(0)])

    instance = ps.build_verification_instance(block, 1)
    with pytest.raises(ValueError):
        instance.decode_output({})  # a partial assignment is not a model
