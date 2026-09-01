# CQ-HECS v4.5: Native C-ABI & API Specification

The pure C-ABI interface for CQ-HECS is declared in [`include/cq_hecs_api.h`](file:///C:/Users/hcsme/Desktop/quanten%20emulator/include/cq_hecs_api.h) and implemented within [`bin/Release/cq_hecs.dll`](file:///C:/Users/hcsme/Desktop/quanten%20emulator/bin/Release/cq_hecs.dll). It follows strict `cdecl` calling conventions with 64-bit alignment and no external runtime dependencies.

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
- **Description**: Parses and executes an OpenQASM 2.0/3.0 circuit string on the MPS tensor chain.
- **Parameters**:
  - `ctx`: Active solver context.
  - `qasm_str`: Null-terminated OpenQASM source string.
  - `out_result`: Pointer to caller-allocated `cq_result_t` structure.
- **Return Value**:
  - `0`: Success.
  - `1`: Syntax error or execution failure.

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
- **Description**: Queries current active VRAM footprint allocated on the GPU device.
- **Return Value**: Resident memory in megabytes (guaranteed $< 120.0$ MB).

---

### 2.7 `cq_get_version`
```c
CQ_API const char* cq_get_version(void);
```
- **Description**: Queries semantic version string.
- **Return Value**: Constant string `"4.5.0"`.
