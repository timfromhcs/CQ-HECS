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
  - `1`: Execution failure after successful parsing.

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
  - `1`: Syntax error or malformed input.

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
- **Return Value**: Constant string `"3.6.0"`, derived from the package
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
- **Return Value**: `0`, `-2` (no device), `-3` (allocation) or `-4` (dispatch).
  Python verifies every pass against the CPU reference unless told otherwise.

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
| `cq-hecs sat solve --engine omniwave` | Experimental multi-front search (`--waves`, `--workers`, `--bcp scalar|batch|vulkan`, `--batch-size`, `--proof-out`). UNSAT only with a DRAT proof accepted by `cqhecs.drat`; JSON output adds an `omniwave` stats object. (3.5.0) |
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
