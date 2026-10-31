# v6 research ledger — adopted and rejected methods

| Topic | Method / claim | Decision | Reason | Revisit when |
| :--- | :--- | :--- | :--- | :--- |
| SAT propagation | Two-watched literals, trail + qhead, watch relocation | ADOPTED (opt-in) | Standard sound invariant; differential tests pass; measured improvement is being established | H-SAT-01 full benchmark |
| SAT propagation | Full-clause rescans + pure-literal scan | KEPT as reference | Readable oracle and certificate search; needed for differential tests | Never remove without an equivalent independent oracle |
| SAT search | CDCL with 1-UIP, VSIDS, restarts, clause reduction | DEFERRED | High defect risk; must follow proof-awareness and benchmark gates | After M4/M5 |
| UNSAT evidence | Tree-resolution certificate replayed by `check_refutation` | KEPT | Independent of search and already tested against tampering | Add external LRAT/CakeLPR cross-check |
| UNSAT evidence | DRAT checker in `cqhecs.drat` | KEPT | Independent of solver code, budget-fail closed | Audit against external vectors |
| UNSAT evidence | Claim “formally verified” | REJECTED | The in-repo checker is not formally verified; no cake_lpr/LRAT run here | Only after a verified checker runs |
| #SAT | Exact DPLL counting with component cache | KEPT | Exact integer contract; budget yields `UNKNOWN` | Separator/treewidth prototype |
| #SAT | Approximate counting in `count_models` | REJECTED | Different probabilistic contract | Separate `approx_count` API |
| ETH transfer | Use OpenAI/Anthropic algorithm as a runtime SAT solver | NOT_TRANSFERABLE | Asymptotic existence results with impractical constants | Never as a direct claim |
| ETH transfer | Parity/GF(2) extraction with a checkable contradiction witness | RESEARCH_ONLY | Sound extraction is the hard part; v3.5 prototype only | M7 audit |
| Tensor transfer | Anthropic contraction recurrence → MPS path | RESEARCH_ONLY (analogy) | #3-SAT tensor networks are not quantum-circuit MPS | Only with a proof or explicit analogy |
| Quantum | New 2D tensor backend | DEFERRED | No demonstrated workload gap in current router | H-QUANT-01 preflight |
| GPU | More parallelism/threads before CPU BCP | REJECTED for now | v3.5 report: GIL contention, GPU slower end-to-end | After CPU engine evidence |
| UI | Framework migration | REJECTED | No architectural case; Vite app is testable | Only with measured need |
| Release | Push `main` to “see CI” | REJECTED | Main push can trigger release/production | Never; feature branch + PR only |

## Non-claims

- No P = NP or P ≠ NP claim.
- No claim that the ETH artifacts are independently verified.
- No universal SAT speedup claim from the watched engine.
- No GPU acceleration claim from shader compilation or a single kernel parity test.
- No claim that external QPU data is a live provider integration.
