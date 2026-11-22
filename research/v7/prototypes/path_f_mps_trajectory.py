"""Path F research prototype: MPS quantum-trajectory sampler for noisy circuits.

EXPERIMENTAL / RESEARCH_ONLY. Not imported by the router or any stable module.

Target (the exact object): the final density matrix rho of the circuit with
Markovian CPTP channels (given as Kraus sets of a ``cqhecs.hardware_bridge``
``NoiseModel``) attached after each gate exactly as written, i.e. what
``NoisyDensityMatrixBackend.density_matrix`` computes.

Unraveling: every channel E(rho) = sum_k K_k rho K_k^dag is unravelled into
pure-state trajectories; a branch k is drawn with probability
p_k = ||K_k psi||^2 and the state is renormalised. The ensemble mean of
|psi><psi| equals E(rho) exactly (standard Kraus-jump unraveling, Dalibard-
Castin-Moelmer / Dum-Zoller-Ritsch; see the literature pins). Two unravelings
of the SAME channel are provided:

  * ``kraus``   - the Kraus set as supplied;
  * ``rotated`` - K'_j = sum_k V_jk K_k with a fixed seeded unitary V; the
                  channel is unchanged (verified by test), only the trajectory
                  statistics differ.

Error story (kept separate):
  * stochastic error: finite number N of trajectories; reported with a
    simultaneous normal-approximation CI (asymptotic) and a Hoeffding CI
    (finite-sample, rigorous for [0,1]-valued per-trajectory probabilities);
  * MPS truncation error: ``chi_max`` cap; ``discarded_weight`` is a
    DIAGNOSTIC and the CIs do NOT cover it (they cover only the stochastic
    error of the truncated process);
  * floating-point error: not bounded here.
Noise model scope: Markovian channels attached to gates; no non-Markovian
effects, no readout error, no mid-circuit measurement.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from _common import Instruction, instruction_tensor
from mps_core import MPS

UNRAVELINGS = ("kraus", "rotated")


def _haar_unitary(m: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(m, m)) + 1j * rng.normal(size=(m, m))
    q, r = np.linalg.qr(z)
    return q * (np.diag(r) / np.abs(np.diag(r)))


def rotate_kraus(Ks: Sequence[np.ndarray], seed: int = 12345) -> List[np.ndarray]:
    """Unitary mixing of a Kraus set: same channel, different unraveling."""
    m = len(Ks)
    V = _haar_unitary(m, seed + m)
    return [sum(V[j, k] * Ks[k] for k in range(m)) for j in range(m)]


def channel_superoperator(Ks: Sequence[np.ndarray]) -> np.ndarray:
    """sum_k K (x) conj(K): equal for two Kraus sets iff the channels are equal."""
    return sum(np.kron(K, K.conj()) for K in Ks)


def kraus_sets(noise_model, name: str, qubits: Sequence[int]) -> List[List[np.ndarray]]:
    """Kraus sets of the channels attached to this gate (as written), in order."""
    gate = name.lower()
    if noise_model is None:
        return []
    if len(qubits) == 1:
        chans = noise_model.channels_1q.get(gate, {}).get(qubits[0], ())
    elif len(qubits) == 2:
        chans = noise_model.channels_2q.get(gate, {}).get((qubits[0], qubits[1]), ())
    else:
        chans = ()
    return [list(ch.kraus_operators) for ch in chans]


def run_trajectory(
    instructions: Sequence[Instruction],
    n: int,
    noise_model,
    rng: np.random.Generator,
    unraveling: str = "kraus",
    chi_max: Optional[int] = None,
) -> MPS:
    if unraveling not in UNRAVELINGS:
        raise ValueError(f"unknown unraveling {unraveling!r}")
    m = MPS(n, chi_max=chi_max)
    for inst in instructions:
        name, qs, _ps = inst
        U = instruction_tensor(inst)
        if len(qs) == 1:
            m.apply_1q(qs[0], U)
        else:
            m.apply_2q(qs[0], qs[1], U)
        for Ks in kraus_sets(noise_model, name, qs):
            if unraveling == "rotated":
                Ks = rotate_kraus(Ks)
            if len(Ks) == 1:
                # a single Kraus operator is deterministic; apply and renormalise
                _apply(m, qs, Ks[0])
                continue
            if len(qs) == 1:
                w = m.kraus_branch_norms_1q(qs[0], Ks)
            else:
                w = m.kraus_branch_norms_2q(qs[0], qs[1], Ks)
            tot = float(w.sum())
            if not math.isfinite(tot) or abs(tot - 1.0) > 1e-8:
                raise RuntimeError(f"Kraus branch weights sum to {tot}, expected 1 (trace preservation)")
            k = int(rng.choice(len(Ks), p=w / tot))
            _apply(m, qs, Ks[k])
    return m


def _apply(m: MPS, qs: Sequence[int], K: np.ndarray) -> None:
    if len(qs) == 1:
        m.apply_kraus_1q(qs[0], K)
    else:
        m.apply_kraus_2q(qs[0], qs[1], K)


@dataclass
class TrajectoryEstimate:
    n: int
    trajectories: int
    unraveling: str
    chi_max: Optional[int]
    probs: np.ndarray                 # estimated diag(rho), little-endian index
    stderr: np.ndarray                # per-outcome standard error
    halfwidth_normal: np.ndarray      # simultaneous (Bonferroni) normal-approx half width
    halfwidth_hoeffding: float        # simultaneous Hoeffding half width (same for all outcomes)
    alpha: float
    max_discarded_weight: float
    max_chi_seen: int
    wall_s: float
    per_traj_probs: Optional[np.ndarray] = field(default=None, repr=False)

    def tv_bound_normal(self) -> float:
        return 0.5 * float(np.sum(self.halfwidth_normal))

    def tv_bound_hoeffding(self) -> float:
        return 0.5 * self.halfwidth_hoeffding * len(self.probs)


def _z_two_sided(p: float) -> float:
    """Inverse standard-normal survival: z with P(|Z|>z) = p (Acklam-free: bisection on erfc)."""
    lo, hi = 0.0, 40.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if math.erfc(mid / math.sqrt(2.0)) > p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def estimate_distribution(
    instructions: Sequence[Instruction],
    n: int,
    noise_model,
    trajectories: int,
    seed: int = 0,
    unraveling: str = "kraus",
    chi_max: Optional[int] = None,
    alpha: float = 0.05,
    keep_samples: bool = False,
) -> TrajectoryEstimate:
    """Monte-Carlo estimate of diag(rho). Deterministic given ``seed``.

    Each trajectory draws from its own child of ``SeedSequence(seed)``, so the
    result does not depend on evaluation order.
    """
    if trajectories < 2:
        raise ValueError("need >= 2 trajectories for a variance estimate")
    t0 = time.perf_counter()
    children = np.random.SeedSequence(seed).spawn(trajectories)
    dim = 1 << n
    acc = np.empty((trajectories, dim))
    max_disc = 0.0
    max_chi = 1
    for i, ss in enumerate(children):
        m = run_trajectory(instructions, n, noise_model, np.random.default_rng(ss), unraveling, chi_max)
        psi = m.to_dense()
        acc[i] = np.abs(psi) ** 2 / float(np.sum(np.abs(psi) ** 2))
        max_disc = max(max_disc, m.discarded_weight)
        max_chi = max(max_chi, m.max_chi_seen)
    mean = acc.mean(axis=0)
    se = acc.std(axis=0, ddof=1) / math.sqrt(trajectories)
    z = _z_two_sided(alpha / dim)
    hh = math.sqrt(math.log(2.0 * dim / alpha) / (2.0 * trajectories))
    return TrajectoryEstimate(
        n, trajectories, unraveling, chi_max, mean, se, z * se, hh, alpha,
        max_disc, max_chi, time.perf_counter() - t0, acc if keep_samples else None,
    )


def exact_unraveling_average(
    instructions: Sequence[Instruction],
    n: int,
    noise_model,
    unraveling: str = "kraus",
    max_branches: int = 20000,
) -> np.ndarray:
    """Probability-weighted average of |psi_branch|^2 over ALL trajectory branches.

    No Monte-Carlo noise: this evaluates the unraveling identity
    E[ |psi><psi| ] = rho exactly (up to float) on small circuits, which is the
    mathematical content the sampler relies on. Refuses when the branch tree
    exceeds ``max_branches``.
    """
    from _common import ResourceRefusal

    events = []
    for inst in instructions:
        name, qs, _ = inst
        for Ks in kraus_sets(noise_model, name, qs):
            events.append(len(Ks))
    total = 1
    for m in events:
        total *= m
        if total > max_branches:
            raise ResourceRefusal(f"branch tree {total}+ exceeds max_branches={max_branches}")

    out = np.zeros(1 << n)

    def walk(i: int, c: int, m: MPS, weight: float) -> None:
        nonlocal out
        while i < len(instructions):
            name, qs, _ = instructions[i]
            sets = kraus_sets(noise_model, name, qs)
            if c == 0:
                U = instruction_tensor(instructions[i])
                if len(qs) == 1:
                    m.apply_1q(qs[0], U)
                else:
                    m.apply_2q(qs[0], qs[1], U)
            if c < len(sets):
                Ks = rotate_kraus(sets[c]) if unraveling == "rotated" else sets[c]
                if len(qs) == 1:
                    w = m.kraus_branch_norms_1q(qs[0], Ks)
                else:
                    w = m.kraus_branch_norms_2q(qs[0], qs[1], Ks)
                for k, wk in enumerate(w):
                    if wk <= 1e-15:
                        continue
                    child = m.copy()
                    _apply(child, qs, Ks[k])
                    walk(i, c + 1, child, weight * float(wk) / float(w.sum()))
                return
            i += 1
            c = 0
        psi = m.to_dense()
        out += weight * np.abs(psi) ** 2 / float(np.sum(np.abs(psi) ** 2))

    walk(0, 0, MPS(n), 1.0)
    return out
