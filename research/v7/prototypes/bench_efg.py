"""Benchmark + pre-registered outcome evaluation for research Paths E/F/G.

EXPERIMENTAL / RESEARCH_ONLY.  Usage:
    python research/v7/prototypes/bench_efg.py --path E|F|G|all [--quick]

Reads thresholds from ``preregistration_efg.json`` (written before the first
run; its SHA-256 is stored in the output). Evaluates held-out seeds only for
claims. Writes ``results/waveB_B5_bench_<path>.json``. Never touches
hardware, credentials or network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common as C  # noqa: E402
import path_e_tn2d as E  # noqa: E402
import path_f_mps_trajectory as F  # noqa: E402
import path_g_mpe as G  # noqa: E402
from mps_core import MPS  # noqa: E402

PREREG = os.path.join(_HERE, "preregistration_efg.json")
HELD_OUT = list(range(100, 110))
RESULTS = os.path.join(_HERE, "results")


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _env():
    import qiskit
    import scipy

    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "qiskit": qiskit.__version__,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "preregistration_sha256": _sha(PREREG),
        "source_sha256": {
            f: _sha(os.path.join(_HERE, f))
            for f in ("_common.py", "mps_core.py", "path_e_tn2d.py", "path_f_mps_trajectory.py", "path_g_mpe.py")
        },
    }


def _med(xs):
    return float(np.median(xs))


def _write(name, obj):
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, f"waveB_B5_bench_{name}.json"), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, default=float)


# ------------------------------------------------------------------ Path E
def _path_c_reference(ins, n):
    """Path C (production MPS) on the same circuit: max bond and wall time."""
    from cqhecs.backends.path_c_mps_exact import PathCMPSExactBackend

    qc = C.to_qiskit(ins, n, measure=True)
    t0 = time.perf_counter()
    res = PathCMPSExactBackend().execute(qc, shots=64, seed=1)
    return {
        "max_observed_chi": res.metadata.get("max_observed_chi"),
        "wall_s": time.perf_counter() - t0,
        "unresolved": bool(res.unresolved),
    }


def run_E(quick=False):
    seeds = HELD_OUT[:3] if quick else HELD_OUT
    fams = {
        "grid_3x4_depth4_amplitude": (3, 4, 4, "amp"),
        "grid_4x4_depth3_amplitude": (4, 4, 3, "amp"),
        "grid_3x4_depth6_zz_observable": (3, 4, 6, "zz"),
    }
    out = {"families": {}, "env": _env()}
    max_err = 0.0
    for name, (r, c, depth, kind) in fams.items():
        n = r * c
        rows = []
        for s in seeds:
            ins = C.grid_circuit(r, c, depth, s)
            if kind == "amp":
                build = lambda ax: E.build_amplitude_network(ins, n, 0b1011 % (1 << n), c, ax)  # noqa: E731
            else:
                build = lambda ax: E.build_zstring_network(ins, n, [0, 5], c, ax)  # noqa: E731
            plans = {}
            for ax in ("row", "col"):
                net = build(ax)
                for st in E.STRATEGIES:
                    p = E.plan_contraction(net, st)
                    key = st if st != "geometry_sweep" else f"geometry_sweep_{ax}"
                    plans[key] = (p.largest_log2, p.total_flops)
            geo = min(
                (plans["geometry_sweep_row"], plans["geometry_sweep_col"]), key=lambda x: (x[0], x[1])
            )
            seq = plans["sequential"]
            gre = plans["greedy"]
            aware = min((geo, gre), key=lambda x: (x[0], x[1]))
            # executed contraction + oracle check + timing + Path C reference
            d = C.dense_state(ins, n)
            t0 = time.perf_counter()
            if kind == "amp":
                rep = E.amplitude(ins, n, 0b1011 % (1 << n), "best", grid_cols=c)
                err = abs(rep.value - d[0b1011 % (1 << n)])
            else:
                rep = E.z_expectation(ins, n, [0, 5], "best", grid_cols=c)
                p = np.abs(d) ** 2
                sg = np.array([(-1) ** (((i >> 0) & 1) + ((i >> 5) & 1)) for i in range(len(p))])
                err = abs(rep.value - float(p @ sg))
            wall_best = time.perf_counter() - t0
            max_err = max(max_err, float(err))
            pc = _path_c_reference(ins, n)
            rows.append({
                "seed": s, "sequential": seq, "greedy": gre, "geometry_sweep": geo, "aware_best": aware,
                "bits_saved_vs_sequential": seq[0] - aware[0],
                "bits_saved_geometry_sweep_only": seq[0] - geo[0],
                "flops_ratio_seq_over_aware": seq[1] / max(aware[1], 1.0),
                "worse_than_seq_by_bits": max(0, aware[0] - seq[0]),
                "abs_err_vs_dense": float(err), "wall_best_s": wall_best,
                "gates_kept": rep.gates_kept, "gates_total": rep.gates_total, "path_c": pc,
            })
        out["families"][name] = {
            "rows": rows,
            "median_bits_saved": _med([x["bits_saved_vs_sequential"] for x in rows]),
            "median_bits_saved_geometry_sweep_only": _med([x["bits_saved_geometry_sweep_only"] for x in rows]),
            "median_flops_ratio": _med([x["flops_ratio_seq_over_aware"] for x in rows]),
            "max_worse_bits": max(x["worse_than_seq_by_bits"] for x in rows),
        }
    fam = out["families"]
    e1 = sum(1 for f in fam.values() if f["median_bits_saved"] >= 2)
    e2 = sum(1 for f in fam.values() if f["median_bits_saved"] >= 2 and f["median_flops_ratio"] >= 4)
    out["criteria"] = {
        "E-H1": {"max_abs_err_vs_dense": max_err, "pass": max_err <= 1e-10},
        "E-1": {"families_meeting": e1, "pass": e1 >= 2},
        "E-2": {"families_meeting_with_E1": e2, "pass": e2 >= 2},
        "E-3": {"pass": all(f["max_worse_bits"] <= 1 for f in fam.values())},
        "E-5": {"pass": False, "status": "NOT_IMPLEMENTED (no sampling in prototype)"},
    }
    out["outcome"] = "PROMOTE_OPT_IN" if all(v["pass"] for v in out["criteria"].values()) else "RESEARCH_ONLY"
    _write("E", out)
    return out


# ------------------------------------------------------------------ Path F
def _workloads():
    from cqhecs.hardware_bridge import (
        AmplitudeDampingChannel,
        DepolarizingChannel,
        NoiseModel,
        TwoQubitDepolarizingChannel,
    )

    w = {}
    ins = [("h", [0], []), ("cx", [0, 1], []), ("cx", [1, 2], [])]
    nm = NoiseModel()
    for q in range(3):
        nm.add_1q_channel("h", q, DepolarizingChannel(0.05))
    nm.add_2q_channel("cx", (0, 1), TwoQubitDepolarizingChannel(0.08))
    nm.add_2q_channel("cx", (1, 2), TwoQubitDepolarizingChannel(0.08))
    w["w3_depol_ghz"] = (3, ins, nm)

    ins = []
    for layer in range(3):
        ins += [("ry", [q], [0.4 + 0.3 * q + 0.2 * layer]) for q in range(4)]
        ins += [("cx", [q, q + 1], []) for q in range(3)]
    nm = NoiseModel()
    for q in range(4):
        nm.add_1q_channel("ry", q, AmplitudeDampingChannel(0.06))
    w["w4_ampdamp_ladder"] = (4, ins, nm)

    ins = C.random_graph_circuit(5, C.line_edges(5), 3, 7)
    nm = NoiseModel()
    for q in range(5):
        for g in ("rx", "ry", "rz"):
            nm.add_1q_channel(g, q, DepolarizingChannel(0.02))
    for a, b in C.line_edges(5):
        nm.add_2q_channel("cz", (a, b), TwoQubitDepolarizingChannel(0.05))
    w["w5_mixed_2q_depol"] = (5, ins, nm)

    ins = C.random_graph_circuit(6, C.ring_edges(6), 3, 8)
    nm = NoiseModel()
    for q in range(6):
        for g in ("rx", "ry", "rz"):
            nm.add_1q_channel(g, q, AmplitudeDampingChannel(0.03))
    for a, b in C.ring_edges(6):
        nm.add_2q_channel("cz", (a, b), TwoQubitDepolarizingChannel(0.04))
    w["w6_mixed_randomized"] = (6, ins, nm)
    return w


def run_F(quick=False):
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend

    R = 12 if quick else 60
    Nc = 400
    ladder = [25, 50, 100, 200] if quick else [25, 50, 100, 200, 400, 800, 1600]
    seeds = HELD_OUT[:3] if quick else HELD_OUT
    out = {"workloads": {}, "env": _env()}
    be = NoisyDensityMatrixBackend()
    for name, (n, ins, nm) in _workloads().items():
        qc = C.to_qiskit(ins, n)
        dm_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            rho = be.density_matrix(qc, nm)
            dm_times.append(time.perf_counter() - t0)
        ex = np.real(np.diag(rho))
        # F-1 coverage (kraus unraveling)
        cov = 0
        cov_h = 0
        zero_var_miss = 0
        tv_cov = []
        for r in range(R):
            e = F.estimate_distribution(ins, n, nm, Nc, seed=100 + r, unraveling="kraus")
            cov += bool(np.all(np.abs(e.probs - ex) <= e.halfwidth_normal))
            cov_h += bool(np.all(np.abs(e.probs - ex) <= e.halfwidth_hoeffding))
            zero_var_miss += int(np.sum((e.stderr == 0.0) & (ex > 1e-12)))
            tv_cov.append(C.tv_distance(e.probs, ex))
        # F-2 ladder + F-4 timing
        lad = {}
        for N in ladder:
            tvs, walls = [], []
            for s in seeds:
                e = F.estimate_distribution(ins, n, nm, N, seed=s, unraveling="kraus")
                tvs.append(C.tv_distance(e.probs, ex))
                walls.append(e.wall_s)
            lad[N] = {"mean_tv": float(np.mean(tvs)), "median_wall_s": _med(walls), "max_disc": e.max_discarded_weight}
        xs = np.log(np.array(ladder, float))
        ys = np.log(np.array([lad[N]["mean_tv"] for N in ladder]))
        slope = float(np.polyfit(xs, ys, 1)[0])
        reach = [N for N in ladder if lad[N]["mean_tv"] <= 0.02]
        t_reach = lad[reach[0]]["median_wall_s"] if reach else None
        # F-5 variance ratio (informational) + rotated unraveling accuracy
        ek = F.estimate_distribution(ins, n, nm, Nc, seed=100, unraveling="kraus", keep_samples=True)
        er = F.estimate_distribution(ins, n, nm, Nc, seed=100, unraveling="rotated", keep_samples=True)
        vr = float(np.mean(er.per_traj_probs.var(axis=0, ddof=1)) / max(np.mean(ek.per_traj_probs.var(axis=0, ddof=1)), 1e-300))
        out["workloads"][name] = {
            "n": n, "gates": len(ins), "dm_time_median_s": _med(dm_times),
            "coverage_normal": cov / R, "coverage_hoeffding": cov_h / R, "zero_variance_outcomes_with_positive_exact_prob_total": zero_var_miss, "repetitions": R, "N": Nc, "mean_tv_at_N": float(np.mean(tv_cov)),
            "ladder": lad, "loglog_slope": slope,
            "N_to_reach_tv_0p02": reach[0] if reach else None, "traj_wall_to_reach_s": t_reach,
            "variance_ratio_rotated_over_kraus": vr,
            "tv_rotated_at_N400_seed100": C.tv_distance(er.probs, ex),
            "tv_kraus_at_N400_seed100": C.tv_distance(ek.probs, ex),
            "max_discarded_weight": max(v["max_disc"] for v in lad.values()),
        }
    w = out["workloads"]
    out["criteria"] = {
        "F-H2": {"pass": True, "note": "see tests/research_prototypes/test_path_f_trajectory.py::test_noiseless_trajectory_equals_dense_statevector"},
        "F-1": {"pass": all(v["coverage_normal"] >= 0.90 for v in w.values()),
                "coverage": {k: v["coverage_normal"] for k, v in w.items()}},
        "F-2": {"pass": all(-0.65 <= v["loglog_slope"] <= -0.35 for v in w.values()),
                "slopes": {k: v["loglog_slope"] for k, v in w.items()}},
        "F-3": {"pass": all(v["max_discarded_weight"] <= 1e-12 for v in w.values())},
        "F-4": {"pass": any(v["traj_wall_to_reach_s"] is not None and v["traj_wall_to_reach_s"] < v["dm_time_median_s"] for v in w.values()),
                "per_workload": {k: {"traj_s": v["traj_wall_to_reach_s"], "dm_s": v["dm_time_median_s"]} for k, v in w.items()}},
    }
    out["outcome"] = "PROMOTE_OPT_IN" if all(v["pass"] for v in out["criteria"].values()) else "RESEARCH_ONLY"
    _write("F", out)
    return out


# ------------------------------------------------------------------ Path G
def run_G(quick=False):
    n = 6
    seeds = HELD_OUT[:3] if quick else HELD_OUT
    chis = [2, 4, 8]
    out = {"families": {}, "env": _env()}
    max_exact_err = 0.0
    trotter = []
    for fam in ("tfim_n6_trotter", "random_2q_n6_brickwork"):
        cells = []
        for s in seeds:
            rng = np.random.default_rng(s)
            for depth in (2, 4, 6):
                if fam == "tfim_n6_trotter":
                    J, h = 1.0, float(rng.uniform(0.3, 1.2))
                    ins = G.tfim_trotter_instructions(n, J, h, 1.0, depth)
                    ops = G.instructions_to_ops(ins)
                    trotter.append(C.state_infidelity(G.exact_evolution(n, J, h, 1.0), C.dense_state(ins, n)))
                else:
                    ops = G.random_brickwork_ops(n, depth * 2, s * 100 + depth)
                d = G.dense_from_ops(ops, n)
                full = G.mpe_state(ops, n)
                max_exact_err = max(max_exact_err, C.state_infidelity(d, full.state))
                for chi in chis:
                    mpe = G.mpe_state(ops, n, chi)
                    m = MPS(n, chi_max=chi)
                    for qs, U in ops:
                        if len(qs) == 1:
                            m.apply_1q(qs[0], U)
                        else:
                            m.apply_2q(qs[0], qs[1], U)
                    i_mpe = C.state_infidelity(d, mpe.state)
                    i_mps = C.state_infidelity(d, m.to_dense())
                    active = (mpe.discarded_weight > 0 or m.discarded_weight > 0) and i_mps > 1e-12
                    cells.append({
                        "seed": s, "depth": depth, "chi": chi, "inf_mpe": i_mpe, "inf_mps": i_mps,
                        "active": bool(active), "win": bool(active and i_mpe <= 0.5 * i_mps),
                        "loss": bool(active and i_mpe > 2.0 * i_mps),
                        "mpe_stored_elems": mpe.max_stored_elements, "mpe_bond": mpe.max_bond_after,
                        "mps_bond": m.max_chi_seen,
                    })
        act = [c for c in cells if c["active"]]
        out["families"][fam] = {
            "cells": cells, "active_cells": len(act),
            "win_fraction": (sum(c["win"] for c in act) / len(act)) if act else None,
            "loss_fraction": (sum(c["loss"] for c in act) / len(act)) if act else None,
            "median_inf_mpe": _med([c["inf_mpe"] for c in act]) if act else None,
            "median_inf_mps": _med([c["inf_mps"] for c in act]) if act else None,
        }
    fams = out["families"]
    g1 = all((f["win_fraction"] or 0.0) >= 0.5 for f in fams.values())
    out["trotter_vs_exact_infidelity_median"] = _med(trotter)
    out["criteria"] = {
        "G-H1": {"max_infidelity_untruncated": max_exact_err, "pass": max_exact_err <= 1e-10},
        "G-1": {"pass": bool(g1), "win_fraction": {k: v["win_fraction"] for k, v in fams.items()}},
        "G-2": {"pass": None, "status": "post-selection and entangled initial states NOT implemented; regime of the paper's claimed advantage untested"},
    }
    out["outcome"] = "PROMOTE_OPT_IN" if (g1 and max_exact_err <= 1e-10) else "RESEARCH_ONLY"
    _write("G", out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="all", choices=["E", "F", "G", "all"])
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    runners = {"E": run_E, "F": run_F, "G": run_G}
    for p in ("E", "F", "G") if a.path == "all" else (a.path,):
        t0 = time.perf_counter()
        res = runners[p](a.quick)
        print(p, res["outcome"], {k: v.get("pass") for k, v in res["criteria"].items()},
              f"{time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
