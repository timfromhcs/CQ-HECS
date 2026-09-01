# GitHub Copilot & AI Coding Agent Instructions for CQ-HECS

## Architecture Overview
CQ-HECS is a deterministic hybrid quantum emulator and constraint solver written in C++20 and Vulkan 1.3 with zero runtime dependencies.

### Coding & Engineering Guidelines

1. **C++20 & MSVC Standards**:
   - Always use modern C++20 standard library facilities (`<concepts>`, `<chrono>`, `<ranges>`, `std::span`).
   - Maintain clean compilation under `/W4 /WX` without unreferenced variables or warnings.
   - Use `cdecl` calling convention and pure C linkage (`extern "C"`) in `include/cq_hecs_api.h`.

2. **Zero Runtime Asset Dependency**:
   - Shaders must never be loaded from external disk `.spv` files at runtime.
   - Shaders are embedded as static `uint32_t` arrays in `src/shaders_embedded.hpp` via `scripts/embed_shaders.py`.
   - Any modification to GLSL compute shaders in `shaders/` must be re-embedded into `src/shaders_embedded.hpp`.

3. **Memory Ceiling & Safety**:
   - Resident VRAM must never exceed 120.0 MB.
   - 300-qubit MPS allocations use 2 bytes per amplitude mapped into the $\mathbb{Z}_8$ phase ring.
   - Cold storage paging is managed via Win32 memory-mapped files in `src/tiered_storage.cpp`.

4. **Solver Exit Code Semantics**:
   - `0`: Success / Target Verified / Satisfiable (SAT).
   - `10`: Unsatisfiable (UNSAT) / Refuted.
   - `1`: Generic error / Syntax error / Out of bounds.

5. **JSON Streaming Standard**:
   - Any CLI command called with `--json` must write strict, machine-readable JSON to `stdout` and redirect all debug logs to `stderr`.

6. **Licensing Attribution**:
   - Any new command-line flag or user-facing view must preserve:
     `"Powered by CQ-HECS (https://github.com/timfromhcs)"`
