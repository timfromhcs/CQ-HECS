# v6 live architecture and capability matrix

Captured from the current tree, not from historical hand-offs. “Engine” means
the code path that actually executes; a UI label is not evidence.

| Surface | Code | What runs | Trust / evidence boundary |
| :--- | :--- | :--- | :--- |
| Python library | `cqhecs/` | Circuit router + paths A–D, noise bridge, SAT, #SAT, MaxSAT | Primary API; additive contracts; `SimulationResult` states `EXACT`/`CERTIFIED`/`UNRESOLVED`/`FAILED` |
| Built-in SAT | `cqhecs/sat.py` | DPLL with scan propagation (default) or watched propagation (opt-in), tree-resolution certificates | SAT model verified clause by clause; UNSAT certificate replayed by `check_refutation`; `UNKNOWN` on budget |
| External SAT | `cqhecs/sat_external.py` | CaDiCaL 1.9.5 via `python-sat` | Model re-checked; DRAT proof checked by `cqhecs.drat`; missing backend is an error |
| DRAT checker | `cqhecs/drat.py` | RUP/RAT forward check with budgets | Independent of solvers, **not formally verified** |
| OMNIWAVE | `cqhecs/omniwave/` | Multi-front exact search; scalar/batch/Vulkan BCP | Experimental; UNSAT only with DRAT; no speedup/complexity claim |
| Quantum backends | `cqhecs/backends/` | Stabilizer, stabilizer rank, exact MPS, sparse Pauli, noisy density matrix | Path-specific limits; no universal simulation claim |
| Hardware bridge | `cqhecs/hardware_bridge.py` | Noise profiles, Kraus channels, calibration metadata | Measured profile ≠ live QPU run; `REAL_HARDWARE` is fail-closed |
| Native core | `src/`, `include/`, `shaders/`, `CMakeLists.txt` | C++20 kernels, C ABI, Vulkan BCP pass | Shader/primitive parity ≠ end-to-end GPU speedup |
| Local Studio | `cqhecs/studio/` | Loopback HTTP UI: Circuit, Noise, SAT, Evidence, Research, Hardware, OMNIWAVE | Local-only default; `engine` accepts `dpll`, `watched`, `cadical`, `omniwave` |
| Web app | `web/` | Vite/TypeScript, worker, Rust/WASM f64, WebGPU f32, browser SAT | Own engine, **not** Python paths A–D; no CaDiCaL/QPU |
| CLI | `cqhecs/cli.py` | Batch and JSON surfaces | `cq-hecs sat solve --engine watched` additive; exit codes unchanged |
| MCP | `cqhecs/mcp_server.py` | Local stdio JSON-RPC tools | Same SAT engine enum including `watched`; no network listener |
| CI / release | `.github/workflows/` | Linux/Windows Python, native, sanitizers, web, Playwright/axe; release on tag | Release requires green CI on the exact SHA |

## Precision and status vocabulary

- Python paths A–D run on CPU (README); native Vulkan is a kernel/primitive layer.
- Browser WASM is f64; browser WebGPU is f32 and must be cross-checked against
  WASM/dense within a stated tolerance.
- SAT: `SAT` (verified model), `UNSAT` (exhaustive), `UNKNOWN` (budget). Evidence is
  a separate field (`certification`), not a new truth value.
- #SAT: `COUNTED` with an exact integer string, or `UNKNOWN`.
- MaxSAT: `OPTIMAL` only for the bounded exhaustive solver; do not extend the label
  to a heuristic result.

## Known gaps

- No formally verified SAT proof checker installed here.
- No Lean build of the ETH artifacts in this environment.
- No end-to-end GPU circuit simulator or physical-device performance claim.
- Vercel project state is not re-verified in this session.
