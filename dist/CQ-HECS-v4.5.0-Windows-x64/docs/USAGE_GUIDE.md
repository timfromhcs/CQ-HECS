# CQ-HECS v4.5: User and Operator Guide

This guide provides step-by-step instructions for configuring, building, executing, and programmatically orchestrating CQ-HECS v4.5 on Windows 11.

---

### 1. Build Artifacts

Following build completion, all primary artifacts reside under `bin/Release/`:
- **Standalone Binary**: `bin/Release/cq_hecs.exe` (Single monolithic executable, zero external file dependencies; compute shaders are embedded directly as static byte arrays).
- **C-ABI Shared Library**: `bin/Release/cq_hecs.dll` and import library `cq_hecs.lib`.
- **C Header**: `include/cq_hecs_api.h`.

---

### 2. One-Click Automated Build

To compile shaders, embed them into static C++ headers, configure CMake, compile the C++ Release executable and shared library, and execute the verification suite, run:

```cmd
build.bat
```

---

### 3. CLI Command Reference & Exit Codes

```cmd
bin\Release\cq_hecs.exe <command> [options]
```

#### Exit Code Semantics:
- **`0`**: Success / Target Verified / Satisfiable (SAT).
- **`10`**: Unsatisfiable (UNSAT) / Refuted.
- **`1`**: Generic Error / Syntax Error / Out of Bounds.

#### Global Options:
- **`--json`**: Outputs strict machine-readable JSON to `stdout` with all diagnostic messages redirected to `stderr`.
- **`--help, -h`**: Displays usage and help summary.

---

### 4. OpenQASM 2.0 / 3.0 Circuit Simulation

Simulate canonical quantum circuits on the 300-qubit MPS chain with $\mathbb{Z}_8$ phase mapping and J-Space Delta residual tracking:

#### Direct File Execution:
```powershell
.\bin\Release\cq_hecs.exe qasm benchmarks\qasm\ghz_300.qasm
```

#### JSON Output & PowerShell Piping:
```powershell
Get-Content benchmarks\qasm\ghz_300.qasm | .\bin\Release\cq_hecs.exe qasm - --json | ConvertFrom-Json
```

#### Output Schema:
```json
{
  "engine": "CQ-HECS v4.5 QASM Engine",
  "status": "SUCCESS",
  "circuit": "benchmarks\\qasm\\ghz_300.qasm",
  "qubit_count": 300,
  "gate_count": 600,
  "elapsed_ms": 2.265,
  "active_vram_mb": 4.531,
  "vram_budget_mb": 120.0,
  "vram_satisfied": true,
  "lambda_res": 0.000000
}
```

---

### 5. DIMACS CNF SAT Constraint Solving

Solve standard propositional satisfiability problems with $O(1)$ Hilbert-Cuckoo cycle loop pruning:

#### Solve Unsatisfiable Benchmark (Pigeonhole 6-into-5):
```powershell
.\bin\Release\cq_hecs.exe sat benchmarks\sat\pigeonhole_6_5.cnf --json
# $LASTEXITCODE will be 10 (UNSAT)
```

#### Solve via PowerShell Pipe:
```powershell
Get-Content benchmarks\sat\uf50_hard.cnf | .\bin\Release\cq_hecs.exe sat - --json | ConvertFrom-Json
```

#### Output Schema:
```json
{
  "engine": "CQ-HECS v4.5 SAT Engine",
  "status": "UNSAT",
  "source": "benchmarks\\sat\\pigeonhole_6_5.cnf",
  "num_vars": 30,
  "num_clauses": 81,
  "decisions": 359,
  "pruned_cycles": 0,
  "elapsed_ms": 2.927,
  "verified": true
}
```

---

### 6. Real-World ARX Cryptanalysis Suite

Benchmark step-inversion, carry-shadow separation, and path pruning efficiency on symmetric cryptographic primitives:

```powershell
# BLAKE2b G-function
.\bin\Release\cq_hecs.exe arx blake2b --rounds 1000 --json

# ChaCha20 quarter-round
.\bin\Release\cq_hecs.exe arx chacha20 --rounds 1000 --json

# SHA-256 schedule expansion
.\bin\Release\cq_hecs.exe arx sha256 --rounds 1000 --json
```

---

### 7. Interactive Terminal Dashboard (Native ANSI / VT100 TUI)

Launch the live terminal dashboard displaying real-time VRAM telemetry, cross-attention heatmaps, QPC oscillator jitter oscilloscope, and throughput gauges:

```powershell
.\bin\Release\cq_hecs.exe dashboard
```

Options:
- `--cycles <N>`: Run for a fixed number of refresh cycles and exit (ideal for automated headless testing).

---

### 8. Continuous 100k-Iteration Stress & Leak Test

Execute the continuous endurance stress harness to test long-running memory stability, VRAM bound adherence (< 120 MB), and Lyapunov explosion shielding:

```powershell
.\bin\Release\cq_hecs.exe stress --cycles 100000 --json | ConvertFrom-Json
```

---

### 9. Embedded Self-Test Suite

Execute all internal subsystem unit tests:

```powershell
.\bin\Release\cq_hecs.exe test
.\bin\Release\cq_hecs.exe test --json | ConvertFrom-Json
```
