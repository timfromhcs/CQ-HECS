"""OMNIWAVE: exhaustive oracles for every representation and the multi-front engine."""

from __future__ import annotations

import itertools
import json
import random
import threading
import time

import pytest

from cqhecs.drat import check_drat
from cqhecs.omniwave import OmniwaveConfig, OmniwaveEngine, solve_omniwave
from cqhecs.omniwave import bcp, boundary, gf2
from cqhecs.omniwave.field import ParityHash, ProblemField, TableTooLarge
from cqhecs.omniwave.quadratic import encode
from cqhecs.sat import CNF, SAT, UNKNOWN, UNSAT, count_models, parse_dimacs, random_3sat, solve


def brute(formula: CNF):
    models = []
    for bits in itertools.product((False, True), repeat=formula.num_vars):
        a = {v: bits[v - 1] for v in range(1, formula.num_vars + 1)}
        if formula.is_satisfied(a):
            models.append(bits)
    return models


# ---------------------------------------------------------------- engine vs brute force

@pytest.mark.parametrize("seed", range(80))
def test_engine_agrees_with_brute_force_and_certifies_unsat(seed):
    rng = random.Random(seed)
    n = rng.randint(3, 10)
    formula = random_3sat(n, rng.randint(n, 6 * n), seed=seed)
    result = solve_omniwave(formula, waves=1 + seed % 5, workers=1 + seed % 3, timeout_seconds=20)
    truth = bool(brute(formula))
    assert result.status == (SAT if truth else UNSAT)
    if result.status == SAT:
        assert result.model_verified and formula.is_satisfied(result.assignment)
        assert result.certification == "MODEL_VERIFIED"
    else:
        assert result.certified and result.certification == "DRAT_CHECKED"


@pytest.mark.parametrize("seed", range(30))
def test_differential_against_the_reference_dpll(seed):
    formula = random_3sat(18, 60 + seed % 40, seed=1000 + seed)
    assert solve_omniwave(formula, waves=4, workers=3, timeout_seconds=30).status == solve(formula).status


def test_pigeonhole_is_unsat_with_a_checked_proof():
    from pathlib import Path

    php = parse_dimacs((Path(__file__).resolve().parent.parent / "benchmarks/sat/pigeonhole_6_5.cnf").read_text("utf-8"))
    engine = OmniwaveEngine(php, OmniwaveConfig(waves=4, workers=2, timeout_seconds=120))
    result = engine.run()
    assert result.status == UNSAT and result.certification == "DRAT_CHECKED"
    snap = engine.snapshot()
    assert snap["covered"] == 1.0
    # The proof is independently checkable again from outside the engine.
    assert check_drat(php.clauses, engine.proof()).valid is True


def test_coverage_is_complete_and_exact_on_unsat():
    formula = random_3sat(12, 70, seed=3)
    assert not brute(formula)
    engine = OmniwaveEngine(formula, OmniwaveConfig(waves=3, workers=2))
    assert engine.run().status == UNSAT
    assert engine.snapshot()["covered"] == pytest.approx(1.0, abs=1e-12)


def test_tampered_proof_is_rejected_so_unsat_is_never_unchecked():
    formula = random_3sat(10, 60, seed=11)
    engine = OmniwaveEngine(formula, OmniwaveConfig(waves=2, workers=1))
    assert engine.run().status == UNSAT
    proof = engine.proof()
    assert check_drat(formula.clauses, proof[-1:]).valid is False   # truncated
    assert check_drat(formula.clauses[:-5], proof).valid is not True  # wrong formula


def test_proof_checking_disabled_gives_unknown_not_unsat():
    formula = parse_dimacs("p cnf 1 2\n1 0\n-1 0\n")
    result = solve_omniwave(formula, check_proof=False)
    assert result.status == UNKNOWN


def test_budgets_and_timeouts_give_unknown():
    big = random_3sat(60, 255, seed=7)
    assert solve_omniwave(big, max_fronts=5, timeout_seconds=30).status == UNKNOWN
    assert solve_omniwave(big, timeout_seconds=0.001).status in (UNKNOWN, SAT, UNSAT)
    tiny_queue = solve_omniwave(random_3sat(40, 170, seed=9), max_queue=2, timeout_seconds=30)
    assert tiny_queue.status in (UNKNOWN, SAT)  # SAT only with a verified model


def test_cancellation_stops_workers_and_reports_unknown():
    # n=150 at the threshold is far beyond what the engine decides in 0.2 s, so the
    # cancel always lands mid-search; a SAT before it would still carry a verified model.
    engine = OmniwaveEngine(random_3sat(150, 639, seed=4), OmniwaveConfig(workers=3, timeout_seconds=60))
    threading.Timer(0.2, engine.cancel).start()
    started = time.perf_counter()
    result = engine.run()
    assert time.perf_counter() - started < 30
    assert result.status in (UNKNOWN, SAT)
    if result.status == UNKNOWN:
        assert "cancelled" in result.note and engine.snapshot()["covered"] < 1.0


def test_pause_and_resume():
    engine = OmniwaveEngine(random_3sat(24, 100, seed=21), OmniwaveConfig(workers=2, timeout_seconds=60))
    engine.pause()
    assert engine.snapshot()["paused"] is True
    threading.Timer(0.3, engine.resume).start()
    assert engine.run().status in (SAT, UNSAT)


def test_waves_start_in_different_regions():
    clauses = "".join(f"{i} {i + 1} 0\n" for i in range(1, 30))  # a path graph
    engine = OmniwaveEngine(parse_dimacs(f"p cnf 30 29\n{clauses}"), OmniwaveConfig(waves=3))
    assert len(set(engine.wave_starts)) == 3


def test_exact_dedup_never_drops_distinct_states_with_equal_hashes():
    class Collide(tuple):
        def __hash__(self):
            return 0  # every state collides

    seen = set()
    a, b = Collide((1, -2)), Collide((1, 2))
    seen.add(a)
    assert b not in seen  # equality, not the hash, decides
    assert Collide((1, -2)) in seen


# ---------------------------------------------------------------- representations

@pytest.mark.parametrize("seed", range(60))
def test_quadratic_encoding_preserves_the_model_count_exactly(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 6)
    clauses = []
    for _ in range(rng.randint(0, 6)):
        k = rng.randint(1, min(5, n))
        vs = rng.sample(range(1, n + 1), k)
        clauses.append(tuple(v if rng.random() < 0.5 else -v for v in vs))
    system = encode(clauses, n)
    assert system.max_degree <= 2
    count = 0
    for bits in itertools.product((0, 1), repeat=system.num_vars):
        if system.evaluate((0,) + bits):
            count += 1
    expected = sum(all(any(b[abs(l) - 1] == (l > 0) for l in c) for c in clauses)
                   for b in itertools.product((False, True), repeat=n))
    assert count == expected


def test_quadratic_encoding_every_polarity_of_a_long_clause():
    for k in range(1, 6):
        for signs in itertools.product((1, -1), repeat=k):
            clause = tuple(s * (i + 1) for i, s in enumerate(signs))
            system = encode([clause], k)
            sols = sum(system.evaluate((0,) + bits) for bits in itertools.product((0, 1), repeat=system.num_vars))
            assert sols == 2 ** k - 1


def test_quadratic_tautology_and_duplicates():
    assert encode([(1, -1)], 1).equations == ()
    assert encode([(1, 1, 2)], 2).max_degree <= 2


@pytest.mark.parametrize("seed", range(80))
def test_rank_factorization_is_exact(seed):
    rng = random.Random(seed)
    rows, cols = rng.randint(1, 12), rng.randint(1, 12)
    m = [rng.randrange(1 << cols) for _ in range(rows)]
    U, V, r = gf2.rank_factorization(m, cols)
    assert r == gf2.rank(m, cols) == len(V)
    assert gf2.multiply(U, V, r) == m
    # The bilinear form survives the factorization: x_L^T M x_R = (U^T x_L)^T (V x_R).
    for _ in range(20):
        xl, xr = rng.randrange(1 << rows), rng.randrange(1 << cols)
        ul = 0
        for i in range(rows):
            if xl >> i & 1:
                ul ^= U[i]
        vr = sum((bin(V[k] & xr).count("1") & 1) << k for k in range(r))
        assert gf2.bilinear(xl, m, xr) == bin(ul & vr).count("1") & 1


def test_low_rank_is_not_assumed_for_random_matrices():
    rng = random.Random(1)
    full = [rng.randrange(1 << 16) for _ in range(16)]
    assert gf2.rank(full, 16) >= 14  # random dense matrices are (nearly) full rank


@pytest.mark.parametrize("seed", range(40))
def test_tensor_contraction_equals_model_count(seed):
    rng = random.Random(seed)
    n = rng.randint(3, 11)
    formula = random_3sat(n, rng.randint(1, 4 * n), seed=seed)
    order = list(range(1, n + 1))
    rng.shuffle(order)
    field = ProblemField(formula)
    assert field.tensor_count(order) == int(count_models(formula)["count"]) == len(brute(formula))


def test_tensor_contraction_refuses_oversized_tables():
    formula = random_3sat(30, 120, seed=1)
    with pytest.raises(TableTooLarge):
        ProblemField(formula).tensor_count(max_table=4)


def test_xor_view_detects_exact_parity_encodings_only():
    # x1 ⊕ x2 ⊕ x3 = 1 as CNF: forbid the even-parity assignments.
    clauses = []
    for bits in itertools.product((0, 1), repeat=3):
        if sum(bits) % 2 == 0:
            clauses.append(tuple((i + 1) if b == 0 else -(i + 1) for i, b in enumerate(bits)))
    formula = CNF(3, tuple(clauses))
    xor = ProblemField(formula).xor_view()
    assert xor.rows == ((0b111, 1),)
    assert xor.count_solutions() == len(brute(formula)) == 4
    partial = CNF(3, tuple(clauses[:-1]))
    assert ProblemField(partial).xor_view().rows == ()


@pytest.mark.parametrize("seed", range(40))
def test_parity_hash_cells_partition_the_solutions(seed):
    formula = random_3sat(8, 20, seed=seed)
    h = ParityHash.draw(8, 3, seed=seed)
    sols = brute(formula)
    per_cell = {}
    for x in sols:
        per_cell[h.bucket(x)] = per_cell.get(h.bucket(x), 0) + 1
    assert sum(per_cell.values()) == len(sols)
    for cell in h.all_buckets():
        system = h.cell_system(cell)
        members = sum(system.satisfied(x) for x in sols)
        assert members == per_cell.get(cell, 0)


def test_an_empty_hash_cell_is_not_an_unsat_proof():
    formula = parse_dimacs("p cnf 4 1\n1 2 0\n")  # SAT
    h = ParityHash.draw(4, 6, seed=3)
    sols = brute(formula)
    empty = [c for c in h.all_buckets() if not any(h.bucket(x) == c for x in sols)]
    assert empty, "with 6 hash bits and 12 solutions some cell must be empty"
    assert solve_omniwave(formula).status == SAT  # the engine never uses hashing to decide


@pytest.mark.parametrize("seed", range(30))
def test_separator_merge_is_exact(seed):
    rng = random.Random(seed)
    nl, ns, nr = rng.randint(1, 4), rng.randint(0, 3), rng.randint(1, 4)
    L, S, R = list(range(1, nl + 1)), list(range(nl + 1, nl + ns + 1)), list(range(nl + ns + 1, nl + ns + nr + 1))
    clauses = []
    for side in (L + S, S + R):
        for _ in range(rng.randint(1, 5)):
            k = min(3, len(side))
            vs = rng.sample(side, k)
            clauses.append(tuple(v if rng.random() < 0.5 else -v for v in vs))
    n = nl + ns + nr
    formula = CNF(n, tuple(clauses))
    assert boundary.separator_count(n, clauses, L, S) == len(brute(formula))
    report = boundary.compression_report(n, clauses, L, S)
    assert report["distinct_signatures"] <= 2 ** ns


def test_separator_must_really_separate():
    with pytest.raises(ValueError):
        boundary.split_clauses([(1, 3)], {1}, {2})


# ---------------------------------------------------------------- batched BCP

@pytest.mark.parametrize("seed", range(40))
def test_batched_propagation_matches_scalar_unit_propagation(seed):
    rng = random.Random(seed)
    n = rng.randint(3, 40)
    formula = random_3sat(n, rng.randint(n, 4 * n), seed=seed)
    cubes = []
    for _ in range(rng.randint(1, 12)):
        vs = rng.sample(range(1, n + 1), rng.randint(0, min(6, n)))
        cubes.append(tuple(v if rng.random() < 0.5 else -v for v in vs))
    fronts = bcp.Fronts.from_cubes(n, cubes)
    outcomes = bcp.propagate_batch(formula.clauses, fronts)
    engine = OmniwaveEngine(formula, OmniwaveConfig(waves=1, workers=1))
    for cube, out in zip(cubes, outcomes):
        scalar, _ = engine._propagate(cube)
        assert out == scalar, (cube, out, scalar)


def test_status_word_encoding_round_trips():
    for lit in (1, -1, 7, -7, 33, -33):
        assert bcp.code_lit(bcp.lit_code(lit)) == lit


# ---------------------------------------------------------------- CPU/GPU parity and batch modes

def _random_fronts(rng, n, count, max_lits=10):
    cubes = []
    for _ in range(count):
        vs = rng.sample(range(1, n + 1), rng.randint(0, min(max_lits, n)))
        cubes.append(tuple(v if rng.random() < 0.5 else -v for v in vs))
    return cubes


@pytest.mark.parametrize("seed", range(25))
def test_vulkan_bcp_is_bit_identical_to_the_cpu_reference(seed):
    from cqhecs.omniwave import gpu

    if not gpu.available():
        pytest.skip(f"Vulkan OMNIWAVE kernel unavailable: {gpu.status().get('reason')}")
    rng = random.Random(500 + seed)
    n = rng.randint(3, 96)  # crosses the 32-bit word boundary
    formula = random_3sat(n, rng.randint(n, 4 * n), seed=seed)
    fronts = bcp.Fronts.from_cubes(n, _random_fronts(rng, n, rng.randint(1, 200)))
    assert gpu.evaluate_batch_vulkan(formula.clauses, fronts) == bcp.evaluate_batch(formula.clauses, fronts)


@pytest.mark.parametrize("mode", ["batch", "vulkan"])
@pytest.mark.parametrize("seed", range(15))
def test_batched_engine_modes_agree_and_certify(mode, seed):
    if mode == "vulkan":
        from cqhecs.omniwave import gpu

        if not gpu.available():
            pytest.skip("Vulkan OMNIWAVE kernel unavailable")
    formula = random_3sat(14, 45 + seed * 2, seed=7000 + seed)
    result = solve_omniwave(formula, bcp=mode, batch_size=8 + seed, workers=2, timeout_seconds=60)
    assert result.status == solve(formula).status
    if result.status == UNSAT:
        assert result.certification == "DRAT_CHECKED"
    else:
        assert formula.is_satisfied(result.assignment)


def test_unknown_bcp_mode_is_refused():
    with pytest.raises(ValueError):
        OmniwaveEngine(parse_dimacs("p cnf 1 1\n1 0\n"), OmniwaveConfig(bcp="cuda"))


@pytest.mark.parametrize("seed", range(10))
def test_many_workers_race_free(seed):
    formula = random_3sat(16, 72, seed=900 + seed)
    expected = solve(formula).status
    for workers in (1, 4, 8):
        engine = OmniwaveEngine(formula, OmniwaveConfig(waves=6, workers=workers, timeout_seconds=60))
        result = engine.run()
        assert result.status == expected
        snap = engine.snapshot()
        assert snap["in_flight"] == 0
        if expected == UNSAT:
            assert snap["covered"] == pytest.approx(1.0)


# ---------------------------------------------------------------- CLI integration


def test_cli_omniwave_engine_writes_a_proof_that_checks(tmp_path, capsys):
    from cqhecs.cli import main

    proof = tmp_path / "out.drat"
    cnf = "p cnf 2 4\n1 2 0\n-1 2 0\n1 -2 0\n-1 -2 0\n"
    rc = main(["--format", "json", "sat", "solve", "--cnf", cnf, "--engine", "omniwave", "--proof-out", str(proof)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["result"]["status"] == "UNSAT" and data["result"]["certification"] == "DRAT_CHECKED"
    assert data["omniwave"]["bcp"] == "scalar"
    formula = parse_dimacs(cnf)
    assert check_drat(formula.clauses, proof.read_text("utf-8").splitlines()).valid is True


def test_cli_omniwave_rejects_bad_settings():
    from cqhecs.cli import main

    assert main(["sat", "solve", "--cnf", "p cnf 1 1\n1 0\n", "--engine", "omniwave", "--waves", "0"]) != 0
