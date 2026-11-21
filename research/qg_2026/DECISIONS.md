# DECISIONS.md — design decisions (ADR-lite)

## D-01 — Add a specialist package, do not fork existing contracts
- Decision: create `cqhecs/quantum_gravity/` with a narrow interface, adapted to the
  existing `SimulationResult`/`provenance` layers. No second result type, no second parser.
- Rationale: QGRAVITY.md §1.3/§6.2 forbid parallel generic infrastructure.

## D-02 — New experiment envelope schema `cqhecs.qg.experiment.v1`
- Decision: add an experiment-level envelope that *links* the `hcs.run.v2` card rather than
  duplicating it; nullable, separate uncertainty classes; reject unknown major versions.
- Rationale: needs model/hypothesis/backend classification the run card does not carry.

## D-03 — Credentials via environment only; key is a Client ID + Secret pair
- Decision: never persist credentials in the repo; read
  `OPENQUANTUM_CLIENT_ID` + `OPENQUANTUM_CLIENT_SECRET`. The supplied `s_…` value is the
  Client ID; the secret is pending (B-1).
- Rationale: official docs; §4.2.

## D-04 — Campaign-scoped, exclusion-based numerical oracles for the first slice
- Decision: BMV and SYK correctness is proven against **closed-form / independent dense**
  oracles on small systems before any cloud work.
- Rationale: §5.1 requires independent oracles before simulator/QPU submission.

## D-05 — Deterministic, exclusion-free bootstrap seed for statistics
- Decision: all estimators use an explicit integer seed stored in the manifest.
- Rationale: reproducibility of every reported interval.

## D-06 — Historical `r-io-7` and `research/v3` evidence is read-only
- Decision: new campaign lives in `research/qg_2026/`; old paths are never rewritten.
- Rationale: §0.3/§15.
