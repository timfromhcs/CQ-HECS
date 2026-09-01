# CQ-HECS: 300-Qubit Quantum MPS Emulator & ARX Constraint Solver

<div align="center">

[![CI Build](https://github.com/timfromhcs/CQ-HECS/actions/workflows/ci.yml/badge.svg)](https://github.com/timfromhcs/CQ-HECS/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/timfromhcs/CQ-HECS?color=blue&label=Release)](https://github.com/timfromhcs/CQ-HECS/releases/latest)
[![License: Fair-Core Tiered](https://img.shields.io/badge/License-Tiered%20Commercial%20(%3C$100k%20Free)-orange.svg)](LICENSE)
[![MSVC C++20](https://img.shields.io/badge/Language-C%2B%2B20%20%2F%20MSVC-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![Vulkan 1.3](https://img.shields.io/badge/Vulkan-1.3%20Embedded%20SPIR--V-red.svg)](https://www.vulkan.org/)
[![Qubits](https://img.shields.io/badge/Capacity-300%20Qubits-purple.svg)](#1-matrix-product-state-mps-300-qubit-quantum-emulation)
[![Active VRAM](https://img.shields.io/badge/VRAM-4.5%20MB%20%3C%20120%20MB-brightgreen.svg)](#memory-model--tiered-paging)
[![Throughput](https://img.shields.io/badge/Throughput-646%2C000%20cycles%2Fsec-blueviolet.svg)](#benchmarks--telemetry)
[![Tests](https://img.shields.io/badge/Tests-62%2F62%20Passing%20(100%25)-success.svg)](#automated-test-matrix-62--62-passing)

<p align="center">
  <b>Deterministic 300-qubit quantum state emulator and ARX constraint satisfaction solver.</b><br>
  Powered by Matrix Product State (MPS) tensor networks, $\mathbb{Z}_8$ cyclotomic phase rings, Global Workspace Theory (GWT) cognitive metacognition, and NVMe tiered cold swap paging.
</p>

[Quickstart](#quickstart) •
[Architecture](#architectural-overview) •
[C-ABI API](#c-abi-shared-library-cq_hecsdll) •
[PowerShell Interop](#powershell-pipeline-orchestration) •
[Benchmarks](#benchmarks--telemetry) •
[License](#licensing--commercial-tier)

</div>

---

## Highlights

- **300-Qubit Deterministic Emulation**: High-fidelity OpenQASM 2.0/3.0 circuit execution via 1D Matrix Product State (MPS) tensor contractions with bond dimension $\chi = 64$.
- **Sub-120 MB VRAM Budget**: Operates strictly within **4.531 MB** active VRAM, with transparent Win32 memory-mapped cold paging.
- **Exact Cyclotomic Phase Ring ($\mathbb{Z}_8$)**: Universal Clifford + T phase representation with zero floating-point accumulation drift and exact anti-math unitary inversion ($U^\dagger U = \mathbb{I}$).
- **ARX Carry-Shadow Separation**: Linearizes modular arithmetic over $\mathbb{Z}_{2^{64}}$, enabling $> 270\text{M}$ ops/sec step-inversion benchmarks for BLAKE2b, ChaCha20, and SHA-256.
- **DIMACS CNF SAT Engine**: Accelerated with an $O(1)$ Hilbert-Cuckoo cycle loop pruner running Murmur3 state signatures.
- **Zero Runtime Dependencies**: Shaders (`cq_hecs_core.comp`, `explosion_shield.comp`, `cuckoo_prune.comp`) are compiled directly into static byte arrays (`src/shaders_embedded.hpp`). No external `.spv`, `.py`, or `.dll` assets required.
- **Universal C-ABI Export**: Public C header ([`include/cq_hecs_api.h`](include/cq_hecs_api.h)) and shared library (`cq_hecs.dll`) for integration into C++, Python, C#, Rust, and Node.js.

---

## Architectural Overview

```
                              +-------------------------------------------+
                              |    Global Workspace Meta-Layer (GWT)     |
                              |    - Softmax Cross-Attention Across Spaces|
                              |    - Hardware Entropy Nudge Controller    |
                              +---------------------+---------------------+
                                                    |
          +-------------------+---------------------+---------------------+-------------------+
          |                   |                     |                     |                   |
+---------v---------+ +-------v---------+ +---------v---------+ +---------v---------+ +-------v---------+
|  J-Space Alpha    | |  J-Space Beta   | |  J-Space Gamma    | |  J-Space Delta    | |  J-Space Epsilon  |
|  (ARX Modulo)     | |  (Phase Ring)   | |  (SAT & Cuckoo)   | |  (Residual SVD)   | | (Explosion Shield)|
|  A + B Linearize  | |  Exact Z_8 Ring | |  DIMACS CNF Solve | |  MPS 300 Qubits   | |  Lyapunov Monitor |
|  Carry Shadow     | |  Clifford + T   | |  O(1) Loop Prune  | |  OpenQASM 2.0/3.0 | |  3-Number Compres |
|  Overflow Reverse | |  Destruct Interf| |  Hilbert Mix      | |  Re-Inflation     | |  0-Bit Loss Round |
+-------------------+ +-----------------+ +-------------------+ +-------------------+ +-----------------+
                                                    |
                              +---------------------v---------------------+
                              |   Vulkan 1.3 Compute & Tiered Memory      |
                              |   - Embedded SPIR-V Shaders in Binary     |
                              |   - 300 MPS Nodes (chi=64, 2B/amplitude)  |
                              |   - Active VRAM strictly < 120 MB         |
                              |   - Win32 Memory-Mapped Cold Swap Pool    |
                              |   - Top Non-Master Isolated Validator     |
                              +-------------------------------------------+
                                                    |
                              +---------------------v---------------------+
                              |          Unified Entrypoints              |
                              |   - Standalone CLI: bin/Release/cq_hecs.exe|
                              |   - Shared DLL:     bin/Release/cq_hecs.dll|
                              |   - C-ABI Header:   include/cq_hecs_api.h |
                              +-------------------------------------------+
```

---

## Quickstart

### 1. Download Pre-Built Release
Grab the latest portable standalone distribution from [Releases](https://github.com/timfromhcs/CQ-HECS/releases):
```powershell
# Extract release bundle
Expand-Archive -Path CQ-HECS-v4.5.0-Windows-x64.zip -DestinationPath .\CQ-HECS\
cd .\CQ-HECS\
```

### 2. Run CLI Subcommands
```powershell
# Display version and mandatory attribution
.\bin\cq_hecs.exe --version

# Simulate 300-Qubit OpenQASM circuit
.\bin\cq_hecs.exe qasm benchmarks\qasm\ghz_300.qasm --json

# Solve Propositional SAT (Exit code 10 on UNSAT, 0 on SAT)
.\bin\cq_hecs.exe sat benchmarks\sat\pigeonhole_6_5.cnf --json
$LASTEXITCODE # Returns 10

# Benchmark ARX step-inversion
.\bin\cq_hecs.exe arx blake2b --rounds 1000 --json

# Launch interactive ANSI/VT100 TUI Monitor
.\bin\cq_hecs.exe dashboard

# Run embedded self-test suite
.\bin\cq_hecs.exe test --json
```

---

## PowerShell Pipeline Orchestration

Every CLI command supports stdin streaming via `-` and outputs strict, machine-readable JSON to `stdout`:

```powershell
# Stream circuit directly through PowerShell pipeline
Get-Content benchmarks\qasm\ghz_300.qasm | .\bin\cq_hecs.exe qasm - --json | ConvertFrom-Json

# Pipe SAT problem and inspect solver decisions
$sat = Get-Content benchmarks\sat\uf50_hard.cnf | .\bin\cq_hecs.exe sat - --json | ConvertFrom-Json
Write-Host "Satisfiable: $($sat.status) in $($sat.elapsed_ms) ms (Decisions: $($sat.decisions))"
```

---

## C-ABI Shared Library (`cq_hecs.dll`)

Include [`include/cq_hecs_api.h`](include/cq_hecs_api.h) and link against `cq_hecs.lib`:

```cpp
#include <iostream>
#include "cq_hecs_api.h"

int main() {
    std::cout << "Version: " << cq_get_version() << std::endl;

    // Create 300-qubit engine context
    cq_context_t* ctx = cq_create_context(300, 64);
    std::cout << "Resident VRAM: " << cq_get_active_vram_mb(ctx) << " MB\n";

    // Solve propositional SAT
    cq_sat_result_t sat_res;
    int code = cq_solve_sat("p cnf 3 2\n1 2 0\n-1 3 0\n", &sat_res);
    if (code == 0) std::cout << "SATISFIABLE!\n";

    cq_destroy_context(ctx);
    return 0;
}
```

*For C#, Rust, and Python (`ctypes`) integration examples, see [`docs/EMBEDDING_GUIDE.md`](docs/EMBEDDING_GUIDE.md).*

---

## Benchmarks & Telemetry

| Domain | Benchmark Instance | Metric | Measured Value | Theoretical Contract | Status |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **QASM Simulation** | GHZ-300 (`ghz_300.qasm`) | Execution Time | **2.26 ms** | $< 100.0\text{ ms}$ | **PASS** |
| **QASM Simulation** | QFT-300 (`qft_300.qasm`) | Execution Time | **14.10 ms** | $< 500.0\text{ ms}$ | **PASS** |
| **Memory Footprint** | 300 Qubits ($\chi = 64$) | Active VRAM | **4.531 MB** | $< 120.0\text{ MB}$ | **PASS** |
| **SAT Constraint** | Pigeonhole 6-into-5 | Solving Time | **2.92 ms** | Exit Code 10 (UNSAT) | **PASS** |
| **SAT Constraint** | 3-SAT Phase Transition | Branching Decisions | 1,240 | Oracle Certified | **PASS** |
| **ARX Cryptanalysis** | BLAKE2b $G$-Function | Inversion Rate | **270,270,000 ops/s** | $100\%$ Bit-Exact | **PASS** |
| **ARX Cryptanalysis** | ChaCha20 Quarter-Round | Inversion Rate | **344,827,000 ops/s** | $100\%$ Bit-Exact | **PASS** |
| **ARX Cryptanalysis** | SHA-256 Schedule Exp. | Inversion Rate | **75,757,000 ops/s** | $100\%$ Bit-Exact | **PASS** |
| **Endurance Sweep** | Continuous Solver Loops | Throughput | **646,486 cycles/s** | Zero Leaks | **PASS** |

---

## Automated Test Matrix (62 / 62 Passing)

The test harness spans both native C++ CTest harnesses and comprehensive Python test suites:

- `test_fuzz_qasm.py` (7 tests): QASM parser edge-case and boundary robustness.
- `test_fuzz_sat.py` (6 tests): DIMACS CNF degenerate formula and contradiction tests.
- `test_svd_precision.py` (1 test): 10,000 SVD truncate-reinflate iterations ($< 10^{-10}$ drift).
- `test_concurrency.py` (1 test): 16 concurrent threads with zero data races.
- `test_cli_powershell.py` (10 tests): Standalone CLI subcommands and exit code verification.
- `test_c_api.py` (5 tests): C-ABI shared library foreign function interface verification.
- `test_qasm_circuits.py` (3 tests): GHZ-300, QFT-300, and surface code stabilizers.
- `test_sat_solver.py` (3 tests): Pigeonhole principle and 50-variable hard instances.
- `test_arx_cryptanalysis.py` (3 tests): Exact carry-shadow separation and step-inversions.
- `test_long_running_stress.py` (3 tests): 100k cycles endurance with Lyapunov growth monitor.
- `test_z8_phases.py` (4 tests): Cyclotomic phase ring and anti-math unitary inversion.
- `test_compression_lossless.py` (4 tests): 0-bit loss tensor roundtrips.
- `test_carry_protection.py` (5 tests): 64-bit integer overflow reverse calculations.
- `test_mps_300qbits.py` (4 tests): 300 tensor sites under 120 MB active VRAM.
- `test_end_to_end_solver.py` (3 tests): End-to-end multi-round preimage recovery.

---

## Documentation

- [`docs/USAGE_GUIDE.md`](docs/USAGE_GUIDE.md): CLI command reference, PowerShell pipeline integration, exit codes.
- [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md): Pure C-ABI function signatures, struct layouts, and thread safety contracts.
- [`docs/EMBEDDING_GUIDE.md`](docs/EMBEDDING_GUIDE.md): Code examples for C++, Python, C#, Rust, and Node.js.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Mathematical formulations for the 5 J-Spaces, phase ring, and Lyapunov stability.
- [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md): Empirical throughput, memory measurements, and pruning ratios.
- [`CHANGELOG.md`](CHANGELOG.md): Release version history and milestone logs.
- [`llms.txt`](llms.txt): Structured summary for LLM context ingestion.

---

## Licensing & Commercial Tier

CQ-HECS is published under the **Fair-Core Tiered Commercial License**:

1. **Free Personal & Academic Use**: Completely free for research, hobbyists, and academic study.
2. **Free Startup & Small Business Tier (< $100,000 USD)**: Free commercial deployment for organizations with under $100,000 USD in annual gross revenue and aggregate funding.
3. **Attribution Requirement**: All applications, CLI utilities, and services utilizing CQ-HECS must display:
   > `"Powered by CQ-HECS (https://github.com/timfromhcs)"`
4. **Enterprise Commercial License (>= $100,000 USD)**: Entities exceeding $100,000 USD in revenue or funding must acquire an Enterprise License.

For commercial licensing agreements, custom algorithms, or dedicated HPC support:
- **Contact**: `timfromhcs@gmail.com`
- **GitHub**: [@timfromhcs](https://github.com/timfromhcs)
