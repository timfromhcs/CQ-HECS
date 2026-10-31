"""Exhaustive oracle tests for the research-only GF(2) prototype (not a cqhecs feature)."""

from __future__ import annotations

import importlib.util
import itertools
import random
import sys
from pathlib import Path

import pytest

from cqhecs.sat import CNF, count_models

PATH = Path(__file__).resolve().parent.parent / "research" / "v5" / "prototypes" / "gf2_counting.py"
spec = importlib.util.spec_from_file_location("gf2_counting", PATH)
gf2 = importlib.util.module_from_spec(spec)
sys.modules["gf2_counting"] = gf2  # dataclasses resolve their module through sys.modules
spec.loader.exec_module(gf2)


def random_instance(rng, n):
    clauses = []
    for _ in range(rng.randint(0, 3 * n)):
        vars_ = rng.sample(range(1, n + 1), min(3, n))
        clauses.append(tuple(v if rng.random() < 0.5 else -v for v in vars_))
    masks = [rng.randrange(1, 1 << n) for _ in range(rng.randint(1, 4))]
    return clauses, masks


@pytest.mark.parametrize("seed", range(150))
def test_parity_partition_is_disjoint_and_preserves_the_count(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 9)
    clauses, masks = random_instance(rng, n)
    parts = gf2.parity_partition(n, clauses, masks)
    total = gf2.brute_count(n, clauses)
    assert sum(parts.values()) == total
    # Cross-check against the shipped exact counter (independent implementation).
    assert int(count_models(CNF(num_vars=n, clauses=tuple(clauses)))["count"]) == total
    # Each part equals the count of F ∧ (Ax = b).
    for syndrome, value in parts.items():
        xor = gf2.XorSystem(n, tuple(zip(masks, syndrome)))
        assert gf2.brute_count(n, clauses, xor) == value


@pytest.mark.parametrize("seed", range(150))
def test_gaussian_elimination_counts_xor_solutions_exactly(seed):
    rng = random.Random(1000 + seed)
    n = rng.randint(1, 10)
    rows = tuple((rng.randrange(0, 1 << n), rng.randint(0, 1)) for _ in range(rng.randint(1, 8)))
    system = gf2.XorSystem(n, rows)
    brute = sum(system.satisfied(bits) for bits in itertools.product((False, True), repeat=n))
    assert system.count_solutions() == brute


def test_prototype_is_not_wired_into_the_package():
    import cqhecs

    package = Path(cqhecs.__file__).parent
    assert not any("gf2_counting" in p.read_text("utf-8", "ignore") for p in package.rglob("*.py"))
