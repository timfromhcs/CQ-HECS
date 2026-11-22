"""Path G prototype: exactness before truncation, error separation, refusals."""
import numpy as np
import pytest

import _common as C
import path_g_mpe as G
from mps_core import MPS


def test_generic_dense_simulator_agrees_with_reference():
    ins = C.random_graph_circuit(4, C.line_edges(4), 3, 31)
    ref = C.dense_state(ins, 4)
    assert np.max(np.abs(G.dense_from_ops(G.instructions_to_ops(ins), 4) - ref)) < 1e-12


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_mpe_exact_on_standard_gates_without_truncation(seed):
    ins = C.random_graph_circuit(5, C.line_edges(5), 4, seed)
    r = G.mpe_state(G.instructions_to_ops(ins), 5)
    assert C.state_infidelity(C.dense_state(ins, 5), r.state) < 1e-10
    assert r.discarded_weight < 1e-12


@pytest.mark.parametrize("seed", [4, 5])
def test_mpe_exact_on_random_two_qubit_unitaries(seed):
    ops = G.random_brickwork_ops(6, 6, seed)
    r = G.mpe_state(ops, 6)
    assert C.state_infidelity(G.dense_from_ops(ops, 6), r.state) < 1e-10


def test_mpe_phase_and_norm_preserved_not_just_fidelity():
    ops = G.random_brickwork_ops(4, 4, 6)
    r = G.mpe_state(ops, 4)
    d = G.dense_from_ops(ops, 4)
    assert np.max(np.abs(r.state - d)) < 1e-10  # includes the global phase


def test_reversed_operand_order_two_qubit_gate():
    ins = [("h", [1], []), ("cx", [1, 0], [])]
    r = G.mpe_state(G.instructions_to_ops(ins), 2)
    assert np.max(np.abs(r.state - C.dense_state(ins, 2))) < 1e-12


def test_truncation_is_reported_and_infidelity_falls_with_chi():
    ops = G.random_brickwork_ops(6, 6, 7)
    d = G.dense_from_ops(ops, 6)
    inf = {}
    for chi in (2, 4, 8, 64):
        r = G.mpe_state(ops, 6, chi)
        inf[chi] = C.state_infidelity(d, r.state)
        if chi < 64:
            assert r.discarded_weight > 0
    assert inf[64] < 1e-10
    assert inf[2] > inf[8] > inf[64] - 1e-12


def test_trotter_error_separated_from_mpe_error():
    n, J, h, t = 5, 1.0, 0.7, 1.0
    ex = G.exact_evolution(n, J, h, t)
    errs = []
    for steps in (2, 4, 8, 16):
        ins = G.tfim_trotter_instructions(n, J, h, t, steps)
        tro = C.dense_state(ins, n)
        mpe = G.mpe_state(G.instructions_to_ops(ins), n)
        assert C.state_infidelity(tro, mpe.state) < 1e-10  # MPE error alone ~ 0 untruncated
        errs.append(C.state_infidelity(ex, tro))  # Trotter error alone
    assert errs[0] > errs[1] > errs[2] > errs[3]


def test_tfim_hamiltonian_is_hermitian_and_known_two_site_spectrum():
    H = G.tfim_hamiltonian(2, 1.0, 0.0)
    assert np.allclose(H, H.conj().T)
    assert sorted(np.round(np.linalg.eigvalsh(H), 10)) == [-1.0, -1.0, 1.0, 1.0]


def test_refusals():
    with pytest.raises(C.UnsupportedPrototypeInput):
        G.mpe_state(G.instructions_to_ops([("cz", [0, 2], [])]), 3)
    with pytest.raises(C.ResourceRefusal):
        G.mpe_state([], 13)
    with pytest.raises(C.ResourceRefusal):
        G.mpe_state(G.random_brickwork_ops(8, 8, 1), 8, max_elements=8)


def test_site_oriented_mps_baseline_exact_and_truncating():
    ops = G.random_brickwork_ops(6, 6, 8)
    d = G.dense_from_ops(ops, 6)
    m = MPS(6)
    for qs, U in ops:
        m.apply_2q(qs[0], qs[1], U)
    assert C.state_infidelity(d, m.to_dense()) < 1e-10
    m2 = MPS(6, chi_max=2)
    for qs, U in ops:
        m2.apply_2q(qs[0], qs[1], U)
    assert C.state_infidelity(d, m2.to_dense()) > 1e-3 and m2.max_chi_seen <= 2
