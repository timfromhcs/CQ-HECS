# LITERATURE_MAP.md — Quantum Gravity research map (campaign `qg-2026-01`)

Maintained per `QGRAVITY.md` §2.6 and §4.1. Each source records: date, type, DOI/URL,
assumptions, system size, method, observable, main result, limitations, and a transfer
decision: `DIRECT_TRANSFER | ADAPTABLE | VALIDATION_ONLY | CONTEXT_ONLY | DEFERRED |
NOT_REPRODUCIBLE`.

> Verification status: all entries below are **SOURCE_CLAIM** as of 2026-11-21 — read from
> the mission's primary-reference table and standard bibliographic memory, not yet
> re-fetched page-by-page. Re-verify every DOI, publication date and correction before the
> release gate (M13). Do not summarise a preprint as peer-reviewed.

## Track A — Gravity-mediated entanglement / BMV interferometry

| ID | Reference | Type | Date | Transfer |
|---|---|---|---|---|
| L-A1 | Marletto & Vedral, "Quantum-information methods for quantum gravity laboratory-based tests", Rev. Mod. Phys. 97, 015006. DOI 10.1103/RevModPhys.97.015006 | Review | 2025-03-14 | ADAPTABLE — witness + assumptions for the two-probe/single-probe proposals |
| L-A2 | Bose et al., "Massive quantum systems as interfaces of quantum mechanics and gravity", Rev. Mod. Phys. 97, 015003. DOI 10.1103/RevModPhys.97.015003 | Review | 2025-02-13 | CONTEXT_ONLY — physical requirements, decoherence, platform landscape |
| L-A3 | Aziz & Howl, "Classical theories of gravity produce entanglement", Nature 646, 813–817 | Research | 2025-10-22 | VALIDATION_ONLY — a positive entanglement signal may not separate all classical-gravity models |
| L-A4 | Di Biagio, "Gravity-induced entanglement is not a theory-independent witness of nonclassicality of the gravitational field", Phys. Rev. D 114, 084050 | Critique | 2026-10-19 | VALIDATION_ONLY — track assumptions; no theory-independent claim |
| L-A5 | Feng, Vedral & Marletto, "Collapse-based models for gravity do not violate the entanglement-based witness of nonclassicality", Phys. Rev. D 113, 104055. DOI 10.1103/83rl-nygv | Research | 2026-05-26 | ADAPTABLE — collapse/decoherence alternative included as a competing model |
| L-A6 | Mitrakos et al., "When does entanglement through gravity imply gravitons?", Phys. Rev. D 114, 025019. DOI 10.1103/lq47-1hfg | Research | 2026-07-24 | VALIDATION_ONLY — no graviton inference without stated conditions |
| L-A7 | Howl, Cooper & Hackermüller, "Gravitationally induced entanglement in atom interferometry", Phys. Rev. A 114, 023306. DOI 10.1103/l62d-gz5c | Proposal | 2026-08-05 | ADAPTABLE — extra observables/route |

## Track B — SYK, JT, holography, traversable-wormhole-inspired circuits

| ID | Reference | Type | Date | Transfer |
|---|---|---|---|---|
| L-B1 | "Traversable wormhole dynamics on a quantum processor", Nature 2022. DOI 10.1038/s41586-022-05424-3 (author correction 2025-04-04) | Experiment | 2022 | DIRECT_TRANSFER (historical reference corpus) — 9-qubit, 164 2-qubit-gate sparsified-SYK protocol |
| L-B2 | Granet et al., "Simulating sparse SYK model with a randomized algorithm on a trapped-ion quantum computer", npj Quantum Inf. 12, 43 | Experiment | 2026-02-23 | DIRECT_TRANSFER (model + method) — 24 Majorana dof, sparse q=4 SYK, TETRIS randomised evolution, Loschmidt/mirror |

**Track B model fact:** SYK has random all-to-all q-body Majorana interactions with a
low-energy 2D-gravity description *in a specified regime*. A finite digital circuit is a
finite-N **model** experiment, not a physical spacetime wormhole.

## Track C — Lattice gauge theory bridge

| ID | Reference | Type | Date | Transfer |
|---|---|---|---|---|
| L-C1 | "Simulating two-dimensional lattice gauge theories on a qudit quantum computer", Nature Physics 21, 570–576 | Experiment | 2025-03-25 | VALIDATION_ONLY — gauge/matter encoding and discretisation; a tool, not a gravity result |

## Competing / null models (mandatory for analysis)

- `M-QMED`: quantum-mediated entangling interaction (the effective `U_ZZ(θ)` model).
- `M-CLASSICAL-FIELD`: local classical field; under stated assumptions can entangle
  (L-A3), so a positive witness alone does not exclude it.
- `M-COLLAPSE`: collapse/decoherence alternatives (L-A5).
- `M-LOCC`: local operations + classical communication only — must stay separable.
- `M-DECOHERENCE`: declared dephasing / amplitude damping / readout assignment noise.

## Standing limitations (apply to all CQ-HECS results)

1. A processor running `U_ZZ(θ)` **emulates** a model; the device is not coupling two test
   masses through gravity.
2. A witness is only as informative as its premises; a real GIE experiment has mass,
   separation, isolation, phase-accumulation and systematic-error parameters absent from a
   toy gate circuit. No silent mapping from circuit `θ` to a physical mass–distance claim.
3. Finite-N SYK, Trotter/randomisation error run separately from hardware noise.
4. No inference of `P=NP/NP`, graviton detection, or "quantum gravity discovered".
