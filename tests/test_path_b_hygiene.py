"""D10 (W3-02): Path B must report the mass it drops, not claim "no dropped terms".

``StabilizerRankSimulator`` skips a branch whose complex weight magnitude is <= 1e-15
(a numerical-zero policy), but the backend metadata claimed
``truncation_applied: False`` and "algebraically exact (no dropped terms)". These tests
pin that a negligible branch is reported (with a bounded ``error_bound``) and that a
normal circuit drops nothing.
"""
import math

from cqhecs.backends.path_b_stabilizer_rank import PathBStabilizerRankBackend


def test_a_normal_circuit_drops_nothing():
    backend = PathBStabilizerRankBackend()
    res = backend.execute([("h", [0], []), ("t", [0], []), ("cx", [0, 1], [])], shots=256, seed=1)
    assert res.metadata["discarded_branch_weight_mass"] == 0.0
    assert res.metadata["truncation_applied"] is False
    assert res.error_bound == 0.0


def test_a_negligible_branch_is_reported_with_a_bounded_error():
    # Each rotation has a branch weight of ~sin(theta/2) = 5e-7; the all-"one" branch
    # (three of them) has weight ~1.25e-19 <= 1e-15 and is dropped.
    theta = 1e-6
    circuit = [("rz", [0], [theta]), ("rz", [0], [theta]), ("rz", [0], [theta])]
    res = PathBStabilizerRankBackend().execute(circuit, shots=128, seed=1)

    discarded = res.metadata["discarded_branch_weight_mass"]
    assert discarded > 0.0, "the dropped branch must be visible"
    assert res.metadata["truncation_applied"] is True
    # The discarded amplitude mass bounds the deliberate approximation error.
    assert res.error_bound == discarded
    assert math.isclose(discarded, math.sin(theta / 2.0) ** 3, rel_tol=1e-6)


def test_two_small_rotations_are_above_the_numerical_zero():
    theta = 1e-6
    res = PathBStabilizerRankBackend().execute(
        [("rz", [0], [theta]), ("rz", [0], [theta])], shots=64, seed=1
    )
    # |c1|^2 ~ 2.5e-13 > 1e-15, so nothing is dropped and error_bound stays 0.
    assert res.metadata["discarded_branch_weight_mass"] == 0.0
    assert res.error_bound == 0.0
