# Wave B / B5 evidence (W7 research Paths E/F/G, prototypes only)

Files: research/v7/prototypes/{_common,mps_core,path_e_tn2d,path_f_mps_trajectory,path_g_mpe,bench_efg}.py,
preregistration_efg.json, results/waveB_B5_bench_{E,F,G}.json (+F_stdout.txt),
tests/research_prototypes/*, research/v7/QUANTUM_SIMULATION_RESEARCH.md.

Commands:
- `python -m pytest tests/research_prototypes -q` -> 85 passed in 17.9 s (E 52, F 11, G 13, router 9).
- `python research/v7/prototypes/bench_efg.py --path E|F|G` (held-out seeds 100-109, earlier run, saved JSON;
  F took 1316 s). Outcomes: E RESEARCH_ONLY (E-5 not implemented; E-1..E-3 pass with caveats), F RESEARCH_ONLY
  (F-1 and F-4 fail), G RESEARCH_ONLY (G-1 fail, 0% win).
- arXiv API lookup of 2608.03472 confirmed title/abstract (read-only call, no personal data).

NOT RUN: full pytest suite; any QPU/provider/credit action; literature re-reading beyond the arXiv abstract;
comparison of E against cotengra/opt_einsum; F/G beyond dense-oracle size; benchmark re-run in this session.
No edits outside the owned area. No git operations.
