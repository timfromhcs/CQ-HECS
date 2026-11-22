# W7 Quantum-simulation research: candidate Paths E / F / G (B5)

Status: RESEARCH_ONLY for all three. Nothing here is imported by `cqhecs`; the default router (A-D) is unchanged
and a test enforces that. Prototypes live in `research/v7/prototypes/`, tests in `tests/research_prototypes/`,
raw results in `research/v7/prototypes/results/waveB_B5_bench_{E,F,G}.json` (each embeds the preregistration
SHA-256 `9bf43e07...f39d0`, the source SHA-256 of every prototype file, and the environment).

## 1. Protocol
- Criteria were written in `research/v7/prototypes/preregistration_efg.json` before `bench_efg.py` was first run.
  Default outcome is RESEARCH_ONLY; PROMOTE_OPT_IN would require every criterion of a path to be met.
- Development seeds 0-4 (debugging only); claims use held-out seeds 100-109 only.
- Oracles: dense statevector (own), Qiskit Statevector (E), existing `NoisyDensityMatrixBackend` (F), exact dense
  evolution (G). Path C max bond chi is reported next to E for the identical circuits.
- No hardware, no provider, no network use in the benchmarks, no credentials. Toy models; nothing here measures
  anything physical.
- Preregistration amendments: none after the first run.

## 2. Literature pins (honest read status)
| Source | Used for | Read status |
|---|---|---|
| Kawabe et al., arXiv:2608.03472 (preprint, 2026-08-04), "Matrix Product Evolution: A Method for Simulating Quantum Circuits Using Tensor Networks" | Path G structure | Title and abstract confirmed against the arXiv API in this session. The prototype docstring records sections I-III.2 as read in the earlier prototype session; that was not re-verified now. Sec. II.3 (identity-block compression), zip-up contraction and the post-selection regime are NOT implemented and NOT independently reproduced. Preprint, not peer reviewed. |
| Dalibard-Castin-Moelmer (1992); Dum-Zoller-Ritsch (1992), quantum-jump / Monte-Carlo wave-function method | Path F unraveling | Standard result, cited from knowledge, NOT re-read. Correctness is checked numerically (sum K^dag K = I; N to infinity vs density matrix). |
| Rudolph-Tindall-type boundary-MPS contraction of 2D circuit networks; Gray-Kourtis (cotengra) contraction orders; Markov-Shi (tensor networks and treewidth) | Path E framing | NOT read. Prior art only; Path E implements none of their algorithms beyond a greedy / sweep order study. No novelty claim. |
| Vidal 2003/2004 (MPS/TEBD); Schollwoeck 2011 | MPS core, baseline | Standard; NOT re-read. |

No novelty is claimed for E, F or G; they are small exact-network studies and reimplementations.

## 3. Path E: 2D geometry-aware tensor-network contraction
Prototype `path_e_tn2d.py`: circuit to closed network (amplitude, or doubled network with light-cone pruning for a
Z-string); orders `sequential` (time-order baseline), `greedy`, `geometry_sweep`; a symbolic cost planner run before
allocation with a typed refusal over an element budget. Exact contractions only: no truncation, sampling or slicing.

Held-out results (10 seeds, median):

| family | seq largest-tensor log2 | bits saved (best of greedy/sweep) | bits saved, geometry_sweep only | FLOPs ratio seq/best |
|---|---|---|---|---|
| grid_3x4_depth4_amplitude | 12 | 6 | +1 | 366x |
| grid_4x4_depth3_amplitude | 16 | 12 | +7 | 6977x |
| grid_3x4_depth6_zz_observable | 24 | 12 | -2 | 28924x |

Hard correctness: max abs error vs dense 2.4e-16 (E-H1 pass); Qiskit cross-check in `test_path_e_tn2d.py`.
Path C max chi on the same circuits: 16 / 16 / 32 (reported, not gated).
Criteria: E-1 pass, E-2 pass, E-3 pass (never worse than sequential), E-5 (sampling convergence) NOT_IMPLEMENTED.
**Outcome: RESEARCH_ONLY** (E-5 not implemented caps it).

Caveats so the pass is not over-read:
1. The preregistered E-1/E-2 rule let `greedy` count as "geometry-aware". The wins come mostly from the generic
   greedy order; the geometry sweep alone saves +1 bit on 3x4 amplitude and is 2 bits worse than sequential on the
   observable family (it would pass E-1 on only 1 of 3 families).
2. The baseline is a weak time-ordered contraction, not a state-of-the-art optimiser (no cotengra/opt_einsum run).
   Large ratios against it do not transfer to a mature contractor.
3. Sizes are 12-16 qubits where the dense oracle is cheap: a contraction-order study, not a scaling result.

## 4. Path F: MPS quantum-trajectory open-system sampler
Prototype `path_f_mps_trajectory.py`: Kraus-jump unraveling (plus a rotated unraveling for variance study) on an MPS,
per-trajectory discarded weight, normal-approximation and Hoeffding intervals on the output distribution, compared
with `NoisyDensityMatrixBackend` for n <= 6 (workloads w3..w6; N=400, R=60 repetitions).

| criterion | result |
|---|---|
| F-H2 noiseless equals dense statevector | pass |
| F-1 simultaneous normal-CI coverage >= 0.90 | FAIL: 0.88 / 0.88 / 0.72 / 0.32 (ghz / ladder / mixed 2q / randomized) |
| F-2 TV slope in [-0.65, -0.35] | pass: -0.44 / -0.51 / -0.48 / -0.49 |
| F-3 discarded weight <= 1e-12 (chi_max=None) | pass (0.0) |
| F-4 wall-time advantage over density matrix, n <= 6 | FAIL: DM 1-15 ms vs trajectories 0.4-19.7 s to reach TV 0.02 |
| F-5 informational variance ratio rotated/kraus | 0.53 on the GHZ workload |

Interpretation: 1/sqrt(N) convergence is observed, but the Bonferroni normal-approximation interval under-covers on
larger-support workloads (many near-zero-probability outcomes). The Hoeffding interval over-covers (1.0 on w3) and is
the only one that should be shown to a user until a better per-outcome interval (e.g. Wilson/Clopper-Pearson) is
preregistered and tested. For n <= 6 the exact density matrix is roughly 10^2-10^3 times faster; any trajectory
advantage would only appear at n where 4^n density matrices are infeasible, which was not tested (the density-matrix
oracle limits the comparison). **Outcome: RESEARCH_ONLY.** The F-1 and F-4 failures are recorded negative results.

## 5. Path G: Matrix Product Evolution
Prototype `path_g_mpe.py`: depth-oriented tensor train per qubit row, merge-then-compress (not zip-up), product
initial state, nearest-neighbour two-qubit gates only (others give a typed refusal), versus the standard MPS at equal
chi on tiny Hamiltonian circuits (TFIM Trotter n=6, random brickwork n=6).
- G-H1: untruncated MPE equals dense, max infidelity 2.2e-16 (pass).
- G-H2: Trotter error versus exact expm(-iHt) is reported separately (median infidelity 0.060 on the TFIM family at
  the benchmark parameters), never mixed with truncation error.
- G-1 FAIL: MPE met "<= 0.5x MPS infidelity" in 0% of active truncation cells in both families. Examples: TFIM depth 4,
  chi 2: MPE 0.030 vs MPS 0.00036; brickwork depth 2, chi 4: MPE 0.041 vs MPS 0.0053.
- G-2: the paper's advantage regime (post-selection, entangled initial states) is not implemented, so this is a loss on
  the tested regime, not a refutation of the preprint.
**Outcome: RESEARCH_ONLY.**

## 6. Router and scope guarantees
`tests/research_prototypes/test_router_unchanged.py`: `VALID_PATHS == (A, B, C, D)`, no plan candidate or executed path
is E/F/G on a grid of circuits, and no `cqhecs` module imports the prototypes. Prototypes carry an EXPERIMENTAL banner.

## 7. Next steps (not commitments)
- E: preregister a comparison against a real optimiser; add boundary-MPS truncation and sampling before any promotion.
- F: preregister a better interval; test at n where density matrices are infeasible before any advantage claim.
- G: implement the post-selection / entangled-input regime and zip-up before the paper's claim can be tested.
