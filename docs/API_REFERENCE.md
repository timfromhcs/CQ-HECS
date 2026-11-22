# CQ-HECS: Native C-ABI & API Specification

The pure C-ABI interface for CQ-HECS is declared in [`include/cq_hecs_api.h`](../include/cq_hecs_api.h) and implemented within `bin/Release/cq_hecs.dll`. It follows strict `cdecl` calling conventions with 64-bit alignment and no external runtime dependencies.

---

## 1. Type Definitions & Struct Layouts

### 1.1 `cq_context_t`
```c
typedef struct cq_context cq_context_t;
```
Opaque handle representing an isolated simulation and constraint solving instance, including:
- 300-qubit MPS state tensor chain with bond dimension $\chi \le 64$.
- Vulkan 1.3 compute pipeline & descriptor sets with embedded SPIR-V shaders.
- Tiered memory governor with Win32 memory-mapped cold swap pool.
- Hardware entropy harvester with high-resolution QPC drift monitoring.

### 1.2 `cq_result_t` (Quantum Execution Telemetry)
```c
typedef struct {
    uint32_t gate_count;     // Total quantum gates executed
    uint32_t qubit_count;    // Active qubit lattice width (up to 300)
    double   elapsed_ms;     // Wall-clock execution time in milliseconds
    double   active_vram_mb; // Active resident VRAM allocated (< 120.0 MB)
    double   lambda_res;     // Residual Frobenius truncation error (\Lambda_res)
    int      success;        // 1 if simulation succeeded, 0 on failure
} cq_result_t;
```

### 1.3 `cq_sat_result_t` (DIMACS SAT Solver Telemetry)
```c
typedef struct {
    int      satisfiable;       // 1 = SAT, 0 = UNSAT
    uint32_t num_vars;          // Number of distinct propositional variables
    uint32_t num_clauses;       // Total clause count
    uint32_t decisions;         // Total branching decisions explored
    uint32_t pruned_cycles;     // Cycle loops pruned via Hilbert-Cuckoo table
    double   elapsed_ms;        // Wall-clock solving time in milliseconds
    int      verified;          // 1 if certified by isolated oracle, 0 otherwise
    int8_t   assignment[1024];  // Variable assignments: 1 = True, 0 = False, -1 = Unassigned
} cq_sat_result_t;
```

---

## 2. Exported Functions

### 2.1 `cq_create_context`
```c
CQ_API cq_context_t* cq_create_context(uint32_t num_qubits, uint32_t bond_dim);
```
- **Description**: Allocates and initializes a new CQ-HECS solver context.
- **Parameters**:
  - `num_qubits`: Number of qubits in the 1D lattice (default: `300`).
  - `bond_dim`: Maximum bond dimension $\chi$ (default: `64`).
- **Return Value**: Non-null pointer to opaque `cq_context_t` on success; `NULL` on initialization failure.
- **Thread Safety**: Contexts are fully isolated. Multiple threads may safely allocate and operate on independent contexts concurrently.

---

### 2.2 `cq_destroy_context`
```c
CQ_API void cq_destroy_context(cq_context_t* ctx);
```
- **Description**: Waits for all device operations to complete, frees all GPU MPS nodes, unmaps and closes Win32 swap files, and releases the context handle.
- **Parameters**:
  - `ctx`: Pointer returned by `cq_create_context`. Safe to pass `NULL` (no-op).

---

### 2.3 `cq_execute_qasm`
```c
CQ_API int cq_execute_qasm(cq_context_t* ctx, const char* qasm_str, cq_result_t* out_result);
```
- **Description**: Parses and executes the documented OpenQASM 2.0 subset on the
  native legacy engine (`legacy_z8_phase_ledger`). This is not a general
  statevector simulator.
- **Parameters**:
  - `ctx`: Active solver context.
  - `qasm_str`: Null-terminated OpenQASM source string.
  - `out_result`: Pointer to caller-allocated `cq_result_t` structure.
- **Return Value**:
  - `0`: Success.
  - `-3`: Parse/validation error. `out_result` is zeroed; no circuit is executed.
  - `-5`: QASM longer than 64 MiB (the core library caps at 16 MiB).
  - `-7`: Internal error. Every entry point is exception-fenced; nothing throws
    across the C boundary.
  - `1`: NULL argument or execution failure after successful parsing.
  `out_result` is zeroed on every failure. The core library (`include/cq/cq_c_api.h`)
  additionally refuses non-Clifford gates (T, Tdg, RZ) on a simulator wider than 16
  qubits before any gate runs (`CQ_CORE_ERR_UNSUPPORTED`, read with
  `cq_core_last_error()`), instead of returning a 16-bit bitstring; it also range-checks
  qubit indices and rejects non-finite angles. Evidence: `research/v7/evidence/waveA_A2.md`.

---

### 2.4 `cq_solve_sat`
```c
CQ_API int cq_solve_sat(const char* cnf_str, cq_sat_result_t* out_result);
```
- **Description**: Solves a propositional satisfiability problem encoded in standard DIMACS CNF format using DPLL accelerated by $O(1)$ Hilbert-Cuckoo cycle loop pruning.
- **Parameters**:
  - `cnf_str`: Null-terminated DIMACS CNF source string.
  - `out_result`: Pointer to caller-allocated `cq_sat_result_t` structure.
- **Return Value**:
  - `0`: Formula is **Satisfiable (SAT)**.
  - `10`: Formula is **Unsatisfiable (UNSAT)**.
  - `3`: Time budget exhausted. **No verdict**: `satisfiable == -1`. Treat it as
    unknown, never as UNSAT (before ABI 1.1 a timeout surfaced as `10`).
  - `1`: Syntax error or malformed input.
  - `-5`: Input longer than 64 MiB. `-7`: internal error.

---

### 2.5 `cq_invert_arx`
```c
CQ_API int cq_invert_arx(const char* primitive, uint32_t rounds, const uint64_t* target, uint64_t* out_preimage);
```
- **Description**: Performs step-inversion and carry-shadow separation on symmetric ARX cryptographic functions.
- **Parameters**:
  - `primitive`: Primitive name (`"blake2b"`, `"chacha20"`, or `"sha256"`).
  - `rounds`: Iteration rounds count.
  - `target`: Pointer to 4-word 64-bit target state vector ($4 \times 64$ bits).
  - `out_preimage`: Caller-allocated 4-word output array for recovered preimage.
- **Return Value**:
  - `0`: Target verified and inverted.
  - `1`: Invalid arguments or unsupported primitive.

---

### 2.6 `cq_get_active_vram_mb`
```c
CQ_API double cq_get_active_vram_mb(cq_context_t* ctx);
```
- **Description**: Queries the allocation accounted against the 120 MiB governor
  ceiling. This is an internal budget figure; it is not a physical GPU
  measurement.
- **Return Value**: Accounted resident memory in megabytes (enforced $< 120.0$ MB).

---

### 2.7 `cq_get_version`
```c
CQ_API const char* cq_get_version(void);
```
- **Description**: Queries semantic version string.
- **Return Value**: Constant string `"7.0.0"`, derived from the package
  version (`scripts/version.py`); it must not drift.

---

### 2.8 `cq_omniwave_device_name` (3.5.0)
```c
CQ_API int cq_omniwave_device_name(char* out, uint32_t capacity);
```
- **Description**: Writes the Vulkan device name used by the OMNIWAVE kernel
  (NUL-terminated, truncated to `capacity`). The device is created lazily once.
- **Return Value**: `0` on success, `-2` when no Vulkan device is available.

### 2.9 `cq_omniwave_bcp_eval` (3.5.0)
```c
CQ_API int cq_omniwave_bcp_eval(const uint32_t* offsets, const uint32_t* codes, uint32_t num_clauses,
                                const uint32_t* assigned, const uint32_t* values, uint32_t num_fronts,
                                uint32_t words, uint32_t* out_status);
```
- **Description**: One batched clause-evaluation pass of OMNIWAVE on the GPU
  (`shaders/compute/omniwave_bcp.comp`). Clauses are CSR (`offsets`, literal
  codes `2(v-1)+neg`); each front is `words` 32-bit words of assigned bits and
  value bits. `out_status[f*num_clauses+c]` is `0` SAT, `1` CONFLICT,
  `2|(code<<2)` UNIT or `3` OPEN, identical to `cqhecs.omniwave.bcp.evaluate_batch`.
- **Return Value**: `0`, `-2` (no device), `1`/`2`/`4` (NULL argument, size limit,
  malformed clause data; all validated on the host before any device work),
  `-3` (allocation), `-4` (dispatch), `-5` (device lost: the context is dropped and
  the next call re-creates it; use the CPU reference), `-6` (readback failed:
  `out_status` is **not** written) or `-7` (internal). Python verifies every pass
  against the CPU reference unless told otherwise.

### 2.10 `cq_omniwave_shutdown` (3.6.0)
```c
CQ_API void cq_omniwave_shutdown(void);
```
- **Description**: Releases the lazily created OMNIWAVE Vulkan context. Safe to
  call repeatedly; a later call may initialize a new context. `cqhecs.omniwave.gpu`
  registers it through `atexit`, so Vulkan objects are destroyed while the loader
  and driver are still mapped (fixes a Windows DLL-unload abort).
- **Return Value**: none.

---

## 3. Python surfaces added in 3.1.0

These are not C-ABI symbols. They are documented here because the C ABI's
`cq_solve_sat` remains the native bridge.

| Command | Purpose |
| :--- | :--- |
| `cq-hecs noise-fit` | Fit `M-FIT-2` from measured `r-io-7` counts; records the `OQ-02` X-gate anomaly and the fitted X bit-flip. |
| `cq-hecs sat solve` | Standalone sound DIMACS DPLL. `SAT` carries a verified model; `UNSAT` is exhaustive and, by default, carries a replay-checked tree-resolution certificate (`certified`); `UNKNOWN` is a timeout or node budget. |
| `cq-hecs sat sweep` | Empirical random-3-SAT phase-transition sweep. Not an ETH proof. |
| `cq-hecs sat solve --engine cadical` | Optional CaDiCaL backend (`pip install cqhecs[sat]`). The SAT model is re-checked; the UNSAT DRAT proof is checked by `cqhecs.drat`; a missing backend is an error, never a fallback. (3.5.0) |
| `cq-hecs sat count` | Exact model count (#SAT): `COUNTED` with an exact integer string, or `UNKNOWN` on budget. (3.5.0) |
| `cq-hecs sat solve --engine watched` | Built-in DPLL with two-watched-literal unit propagation. Same decision order, polarity and pure-literal rule as the default scan engine; UNSAT certificates still come from the independent scan-based certifying search. (3.6.0, opt-in) |
| `cq-hecs sat solve --engine omniwave` | Experimental multi-front search (`--waves`, `--workers`, `--bcp scalar|batch|vulkan`, `--branch auto|jw|bfs`, `--batch-size`, `--proof-out`). UNSAT only with a DRAT proof accepted by `cqhecs.drat`; JSON output adds an `omniwave` stats object. (3.6.0) |
| `cq-hecs studio` | Local experiment UI; see [`STUDIO.md`](STUDIO.md). |

SAT result dictionaries carry `contract_version` `1.2` (3.6.0), which adds `formula_original_sha256` and the `dpll-watched` engine label. `1.1` (3.5.0) added `certification`, `proof_system` and `engine`; no field was removed.

Python API (3.5.0, experimental): `cqhecs.omniwave.solve_omniwave(cnf, **config)`
returns a `SATResult`; `OmniwaveEngine(cnf, OmniwaveConfig(...))` adds `run(on_tick)`,
`snapshot()`, `proof()`, `pause()`, `resume()` and `cancel()`. The representation
modules (`field`, `gf2`, `quadratic`, `boundary`, `bcp`, `gpu`) are research APIs
and may change in a minor release.

The `cq_solve_sat` C entry point and `python_bridge.sat_engine` use the v3.0.0
`SAT_VERIFIED`/`UNSAT_PROVEN`/`TIMEOUT_UNKNOWN` vocabulary. The standalone
`cqhecs.sat` surface uses `SAT`/`UNSAT`/`UNKNOWN`.

---

## 4. ABI version contract

Both native libraries export an ABI version (`CQ_HECS_ABI_MAJOR`/`MINOR`, currently
1.1): `cq_abi_version()` returns `(major << 16) | minor` and `cq_check_abi(major, minor)`
returns `0` when the loaded library is compatible with the caller's build, else `-1`.
MAJOR changes are incompatible, MINOR changes are additions. The 1.1 additions are
listed in `include/cq_hecs_api.h`: `cq_create_context` returns `NULL` for absurd sizes
(qubits above 4096, bond dimension above 65536), input-size limits, the device-lost and
readback codes above, and status `3` for `cq_solve_sat`. The core's own capability JSON
(`cq_core_build_capabilities()`) is unchanged.

## 5. Shared service layer and the plan document

`cqhecs/service.py` is the one place that turns a request into an `ExecutionPlan`
(`plan_document(source, force_path=..., require_counts=..., max_memory_bytes=...)`; `plan_object` returns the `ExecutionPlan` itself). Four
surfaces call it and `tests/test_cross_surface_parity.py` asserts they return the same
document on a six-circuit corpus (including a forced-path refusal and `require_counts`):

| Surface | Entry |
| :--- | :--- |
| Python | `cqhecs.service.plan_document(...)` |
| CLI | `cq-hecs plan <circuit> [--force-path A..D] [--require-counts] [--max-memory-mb N]` |
| MCP | tool `cqhecs_plan` |
| Studio | `POST /api/plan` (also `/api/v1/plan`) |

Quantum Gravity experiments have their own envelope (`qg_plan` plus a `digest`, built by
`cqhecs.service.qg_plan_document`), exposed the same way: `cq-hecs qg plan`, MCP
`cqhecs_qg_plan` and Studio `POST /api/qg/v1/experiments/plan`;
`tests/test_qg_surface_parity.py` asserts they are identical. It never plans a QPU job.

The document schema is `cqhecs.execution_plan/1` (`docs/schemas/execution_plan.schema.json`).
Envelope keys differ by surface and only those (CLI adds `schema_version` and `version`,
Studio adds `schema_version`). A refusal (`FORCED_PATH_UNSUPPORTED`, `COUNTS_UNAVAILABLE`,
`RESOURCE_BUDGET`) is part of a successful plan document (`selected_path: null`,
`would_execute: false`, a `refusal` object); it is not an HTTP or process error.
Estimates in the plan are heuristics; `estimate_quality` says so.

Not migrated to the service: `cq-hecs analyze --explain` still calls
`build_execution_plan` directly (same function, same output).

## 6. Studio HTTP API: OpenAPI 3.1 and `/api/v1`

`schemas/studio.openapi.json` is generated by `python -m cqhecs.studio.openapi` and
served at `GET /api/openapi.json`. Every `/api/<x>` route also answers at
`/api/v1/<x>` with the same guard and the same body; the original paths are unchanged.
Every `/api` route needs the per-launch bearer token (or `CQ_HECS_STUDIO_TOKEN` /
`CQ_HECS_STUDIO_TOKEN_FILE`), an allowed Host, no foreign Origin and `application/json`
POST bodies. The Quantum Gravity routes are a separately versioned family under
`/api/qg/v1` and are not in the OpenAPI document (see [`QUANTUM_GRAVITY_LAB.md`](QUANTUM_GRAVITY_LAB.md)).
A drift test fails if a route literal in `cqhecs/studio/app.py` is undocumented or if the
committed JSON differs from the generator. `openapi_spec_validator` is not installed in the
reference environment, so full-spec validation is NOT RUN; structural checks are tested.

## 7. MCP server (`cq-hecs mcp`)

Stdio JSON-RPC. `initialize` negotiates `protocolVersion` among `2025-06-18`,
`2025-03-26` and `2024-11-05` (an absent version selects the legacy shape, which is
byte-for-byte the old behaviour). `2025-03-26` adds tool `annotations`; `2025-06-18`
adds `title`, `outputSchema` and `structuredContent` (with a JSON text mirror in
`content`). Checked against the 2025-06-18 tools text only; newer revisions are not
claimed.

Tools: `cqhecs_run`, `cqhecs_analyze`, `cqhecs_plan`, `cqhecs_doctor`,
`cqhecs_sat_solve`, `cqhecs_sat_count`, `cqhecs_sat_models`, `cqhecs_devices`,
`cqhecs_hardware`, and the Quantum Gravity family `cqhecs_qg_catalog`,
`cqhecs_qg_circuit_preview`, `cqhecs_qg_run_local`, `cqhecs_qg_plan`,
`cqhecs_qg_model_validate`, `cqhecs_qg_compare`, `cqhecs_qg_export`. Five more tools,
`cqhecs_qg_openquantum_discover`, `cqhecs_qg_openquantum_quote`,
`cqhecs_qg_openquantum_submit`, `cqhecs_qg_openquantum_status` and
`cqhecs_qg_openquantum_results`, exist only to refuse: each returns the typed document
`cqhecs.qg.paid_refusal.v1` (`status: UNAVAILABLE`, `code: QG_PAID_PATH_UNAVAILABLE`,
`network: none`, `spend_credits: 0.0`). No tool contacts a provider or spends credits.

Execution and cancellation: `tools/call` runs on a worker thread and the read loop stays
live (`ping` is answered mid-call). `notifications/cancelled` answers the call once with
`status: CANCELLED`, `verdict: null`; the late result is discarded. This deviates from the
spec's "SHOULD NOT respond" and is recorded as a deviation. Pure-Python compute is
**abandoned, not stopped**. At most 8 calls run concurrently (`SERVER_BUSY` otherwise,
reported as `UNKNOWN`, never a verdict). Numeric inputs (`timeout`, `waves`, `workers`,
`limit`, `node_budget`) are bounded to the Studio's ranges. Evidence:
`research/v7/evidence/waveA_A1.md`.

## 8. Typed MaxSAT

`cq-hecs sat maxsat` and `cqhecs.sat.max_sat_checked` return contract `hcs.sat.maxsat.v1`:
`status` is `OPTIMAL` only when exhaustive enumeration ran (at most 20 variables) and the
optimum was re-verified from the returned assignment; above the limit the status is
`UNKNOWN` with `limit_reached: true`, `assignment: null` and `trust: "NONE"`. The optimality
claim rests on enumeration, so `optimality_certificate` is always `null`. The older
`cqhecs.sat.max_sat` still raises `ValueError` above the limit. See
[`../MIGRATION_V7.md`](../MIGRATION_V7.md) for a verified example.
