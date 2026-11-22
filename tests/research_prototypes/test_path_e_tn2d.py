"""Path E prototype: exactness against independent oracles, planner honesty, refusals."""
import numpy as np
import pytest

import _common as C
import path_e_tn2d as E

TOL = 1e-10


def _cases():
    out = []
    out.append(("grid2x3", 6, C.grid_circuit(2, 3, 3, 1), 3))
    out.append(("grid3x3", 9, C.grid_circuit(3, 3, 3, 2), 3))
    out.append(("line6", 6, C.random_graph_circuit(6, C.line_edges(6), 4, 3), None))
    out.append(("ring8", 8, C.random_graph_circuit(8, C.ring_edges(8), 3, 4), None))
    out.append(("star6", 6, C.random_graph_circuit(6, C.star_edges(6), 3, 5), None))
    out.append(("a2a5", 5, C.random_graph_circuit(5, C.all_to_all_edges(5), 3, 6), None))
    out.append(("rand7", 7, C.random_graph_circuit(7, C.random_sparse_edges(7, 9, 7), 3, 8), None))
    return out


@pytest.mark.parametrize("name,n,ins,cols", _cases())
@pytest.mark.parametrize("strategy", E.STRATEGIES + ("best",))
def test_amplitudes_match_dense_oracle(name, n, ins, cols, strategy):
    d = C.dense_state(ins, n)
    for x in (0, 1, (1 << n) - 1, 5 % (1 << n), 37 % (1 << n)):
        rep = E.amplitude(ins, n, x, strategy, grid_cols=cols)
        assert abs(rep.value - d[x]) <= TOL, (name, strategy, x)


def test_amplitudes_match_qiskit_independent_engine():
    count = 0
    for name, n, ins, cols in _cases():
        q = C.qiskit_state(ins, n)
        for x in (0, 3 % (1 << n), (1 << n) - 2):
            rep = E.amplitude(ins, n, x, "best", grid_cols=cols)
            assert abs(rep.value - q[x]) <= TOL
            count += 1
    assert count >= 20


def _z_exp(state, support):
    p = np.abs(state) ** 2
    s = np.array([(-1) ** sum((i >> q) & 1 for q in support) for i in range(len(p))])
    return float(p @ s)


@pytest.mark.parametrize("support", [[0], [0, 5], [2, 3], [1, 4, 5]])
@pytest.mark.parametrize("strategy", E.STRATEGIES + ("best",))
def test_z_string_expectation_with_lightcone_matches_dense(support, strategy):
    ins = C.grid_circuit(2, 3, 4, 11)
    d = C.dense_state(ins, 6)
    rep = E.z_expectation(ins, 6, support, strategy, grid_cols=3)
    assert abs(rep.value.real - _z_exp(d, support)) <= TOL
    assert abs(rep.value.imag) <= TOL


def test_lightcone_prunes_gates_and_is_exact():
    ins = C.grid_circuit(3, 4, 6, 12)
    kept = E.lightcone(ins, [0])
    assert len(kept) < len(ins)
    d = C.dense_state(ins, 12)
    rep = E.z_expectation(ins, 12, [0], "greedy", grid_cols=4)
    assert rep.gates_kept == len(kept) and rep.gates_total == len(ins)
    assert abs(rep.value.real - _z_exp(d, [0])) <= TOL


def test_planner_largest_tensor_matches_executed_contraction(monkeypatch):
    ins = C.grid_circuit(2, 3, 3, 13)
    net = E.build_amplitude_network(ins, 6, 5, grid_cols=3)
    seen = []
    orig = E._contract_pair

    def spy(a, b):
        out = orig(a, b)
        seen.append(max(len(a.legs), len(b.legs), len(out.legs)))
        return out

    monkeypatch.setattr(E, "_contract_pair", spy)
    for s in E.STRATEGIES:
        seen.clear()
        plan = E.plan_contraction(net, s)
        E.contract(net, plan)
        assert max(seen) <= plan.largest_log2  # plan also counts input tensors


def test_best_plan_never_worse_than_sequential_baseline():
    for _, n, ins, cols in _cases():
        def build(ax, ins=ins, n=n, cols=cols):
            return E.build_amplitude_network(ins, n, 1, cols, ax)

        _, best, _ = E.best_plan(build)
        seq = E.plan_contraction(build("row"), "sequential")
        assert best.largest_log2 <= seq.largest_log2


def test_budget_refusal_happens_before_any_contraction(monkeypatch):
    ins = C.grid_circuit(3, 3, 4, 14)
    called = []
    monkeypatch.setattr(E, "_contract_pair", lambda a, b: called.append(1))
    with pytest.raises(C.ResourceRefusal):
        E.amplitude(ins, 9, 0, "sequential", grid_cols=3, max_elements=4)
    assert called == []


def test_typed_refusals_for_bad_input():
    with pytest.raises(C.UnsupportedPrototypeInput):
        E.plan_contraction(E.build_amplitude_network([("h", [0], [])], 1, 0), "nope")
    with pytest.raises(C.UnsupportedPrototypeInput):
        E.build_amplitude_network([("ccx", [0, 1, 2], [])], 3, 0)


def test_deliberate_gate_error_is_detected():
    """Mutation probe: replacing cz by cx must change amplitudes (the test has teeth)."""
    ins = C.grid_circuit(2, 2, 3, 15)
    bad = [("cx", q, p) if g == "cz" else (g, q, p) for g, q, p in ins]
    d = C.dense_state(ins, 4)
    diffs = [abs(E.amplitude(bad, 4, x, "best", grid_cols=2).value - d[x]) for x in range(16)]
    assert max(diffs) > 1e-3


def test_idle_qubit_amplitude_is_zero_when_bit_set():
    ins = [("h", [0], [])]
    assert E.amplitude(ins, 2, 0b10, "best").value == 0
    assert abs(E.amplitude(ins, 2, 0b01, "best").value - 2 ** -0.5) < TOL
