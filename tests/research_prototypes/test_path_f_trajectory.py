"""Path F prototype: unraveling identity, estimator statistics, error separation."""
import numpy as np
import pytest

import _common as C
import path_f_mps_trajectory as F
from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
from cqhecs.hardware_bridge import (
    AmplitudeDampingChannel,
    DepolarizingChannel,
    NoiseModel,
    TwoQubitDepolarizingChannel,
)

INS = [("h", [0], []), ("cx", [0, 1], []), ("cx", [1, 2], []), ("rx", [2], [0.7])]


def _nm():
    nm = NoiseModel()
    nm.add_1q_channel("h", 0, DepolarizingChannel(0.3))
    nm.add_1q_channel("rx", 2, AmplitudeDampingChannel(0.4))
    nm.add_2q_channel("cx", (0, 1), TwoQubitDepolarizingChannel(0.2))
    nm.add_2q_channel("cx", (1, 2), TwoQubitDepolarizingChannel(0.1))
    return nm


def _exact_diag(ins, n, nm):
    rho = NoisyDensityMatrixBackend().density_matrix(C.to_qiskit(ins, n), nm)
    return np.real(np.diag(rho))


@pytest.mark.parametrize("unr", F.UNRAVELINGS)
def test_unraveling_identity_exact_enumeration_equals_density_matrix(unr):
    nm = _nm()
    got = F.exact_unraveling_average(INS, 3, nm, unr)
    assert np.max(np.abs(got - _exact_diag(INS, 3, nm))) < 1e-12


def test_non_adjacent_and_reversed_two_qubit_noise_matches_density_matrix():
    ins = [("h", [0], []), ("cx", [0, 2], []), ("cx", [2, 1], []), ("rx", [1], [1.1])]
    nm = NoiseModel()
    nm.add_2q_channel("cx", (0, 2), TwoQubitDepolarizingChannel(0.25))
    nm.add_2q_channel("cx", (2, 1), TwoQubitDepolarizingChannel(0.35))
    nm.add_1q_channel("rx", 1, AmplitudeDampingChannel(0.3))
    got = F.exact_unraveling_average(ins, 3, nm)
    assert np.max(np.abs(got - _exact_diag(ins, 3, nm))) < 1e-12


def test_rotated_kraus_is_the_same_channel():
    for ch in (DepolarizingChannel(0.2), AmplitudeDampingChannel(0.3), TwoQubitDepolarizingChannel(0.15)):
        Ks = ch.kraus_operators
        rot = F.rotate_kraus(Ks)
        assert np.max(np.abs(F.channel_superoperator(Ks) - F.channel_superoperator(rot))) < 1e-12
        assert np.max(np.abs(sum(k.conj().T @ k for k in rot) - np.eye(Ks[0].shape[0]))) < 1e-12


def test_noiseless_trajectory_equals_dense_statevector():
    ins = C.random_graph_circuit(4, C.all_to_all_edges(4), 3, 21)
    est = F.estimate_distribution(ins, 4, None, 2, seed=0)
    ref = np.abs(C.dense_state(ins, 4)) ** 2
    assert np.max(np.abs(est.probs - ref)) < 1e-10
    assert est.max_discarded_weight <= 1e-12


def test_estimate_is_deterministic_in_seed_and_covered_by_hoeffding_ci():
    nm = _nm()
    a = F.estimate_distribution(INS, 3, nm, 300, seed=5)
    b = F.estimate_distribution(INS, 3, nm, 300, seed=5)
    assert np.array_equal(a.probs, b.probs)
    c = F.estimate_distribution(INS, 3, nm, 300, seed=6)
    assert not np.array_equal(a.probs, c.probs)
    ex = _exact_diag(INS, 3, nm)
    assert np.all(np.abs(a.probs - ex) <= a.halfwidth_hoeffding)
    assert C.tv_distance(a.probs, ex) <= a.tv_bound_hoeffding()


def test_error_decreases_with_trajectory_count():
    nm = _nm()
    ex = _exact_diag(INS, 3, nm)
    lo = np.mean([C.tv_distance(F.estimate_distribution(INS, 3, nm, 25, seed=s).probs, ex) for s in range(8)])
    hi = np.mean([C.tv_distance(F.estimate_distribution(INS, 3, nm, 400, seed=s).probs, ex) for s in range(8)])
    assert hi < lo


def test_truncation_is_reported_separately_from_stochastic_error():
    ins = C.random_graph_circuit(5, C.all_to_all_edges(5), 4, 22)
    nm = NoiseModel()
    for q in range(5):
        nm.add_1q_channel("rx", q, DepolarizingChannel(0.05))
    full = F.estimate_distribution(ins, 5, nm, 3, seed=1, chi_max=None)
    cut = F.estimate_distribution(ins, 5, nm, 3, seed=1, chi_max=1)
    assert full.max_discarded_weight <= 1e-12
    assert cut.max_discarded_weight > 1e-6
    assert cut.max_chi_seen == 1


def test_branch_weights_are_trace_preserving():
    m = F.MPS(3)
    m.apply_1q(0, C.gate_1q("h"))
    m.apply_2q(0, 2, C.gate_2q("cx"))
    for ch in (DepolarizingChannel(0.4), AmplitudeDampingChannel(0.6)):
        assert abs(m.kraus_branch_norms_1q(2, ch.kraus_operators).sum() - 1.0) < 1e-12
    w2 = m.kraus_branch_norms_2q(0, 2, TwoQubitDepolarizingChannel(0.3).kraus_operators)
    assert abs(w2.sum() - 1.0) < 1e-12


def test_refusals():
    with pytest.raises(ValueError):
        F.estimate_distribution(INS, 3, None, 1)
    with pytest.raises(ValueError):
        F.run_trajectory(INS, 3, None, np.random.default_rng(0), unraveling="nope")
    with pytest.raises(C.ResourceRefusal):
        F.exact_unraveling_average(INS, 3, _nm(), max_branches=3)
    with pytest.raises(C.ResourceRefusal):
        F.MPS(20).to_dense(max_qubits=14)


def test_small_coverage_experiment_for_normal_ci():
    """30 repetitions: the simultaneous normal CI should cover the exact diag in most runs."""
    nm = _nm()
    ex = _exact_diag(INS, 3, nm)
    cover = 0
    reps = 30
    for r in range(reps):
        e = F.estimate_distribution(INS, 3, nm, 150, seed=1000 + r)
        cover += bool(np.all(np.abs(e.probs - ex) <= e.halfwidth_normal))
    assert cover / reps >= 0.8
