# v6 plan

The supplied execution plan is `PLAN-v3.6.0.md` at the repository root. It was
read in full (1708 lines) before any code change. The historical root `PLAN.md`
(v3.5-era) and `research/v5/` are preserved unchanged.

Canonical mission summary:

1. reconcile and verify the v3.5.0 baseline;
2. reproduce local gates before cloud actions;
3. fix correctness and result contracts first;
4. add two-watched-literal propagation as an opt-in engine with differential
   evidence; only then consider CDCL;
5. audit proof trust boundaries; do not call the in-repo checker formally verified;
6. keep research transfer (ETH/tensor/GF(2)) research-only until oracles pass;
7. keep the web app Vite/TypeScript; no framework rewrite;
8. no `main` push, force push, paid QPU job, production deploy or release without
   the explicit gates and authorization.

Permanent state files live in this directory; milestone status is in `TASKS.md`.
