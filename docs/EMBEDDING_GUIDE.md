# CQ-HECS v4.5: Foreign Function Interface & Programmatic Embedding Guide

CQ-HECS v4.5 provides a pure, zero-dependency C-ABI shared library (`bin/Release/cq_hecs.dll`) with declaration header [`include/cq_hecs_api.h`](file:///C:/Users/hcsme/Desktop/quanten%20emulator/include/cq_hecs_api.h) for embedding into C, C++, Python, C#, Rust, and Node.js.

---

## 1. C-ABI Specification & Data Structures

```c
#include "cq_hecs_api.h"

// Types
typedef struct cq_context cq_context_t;

typedef struct {
    uint32_t gate_count;
    uint32_t qubit_count;
    double elapsed_ms;
    double active_vram_mb;
    double lambda_res;
    int success;
} cq_result_t;

typedef struct {
    int satisfiable;       // 1 = SAT, 0 = UNSAT
    uint32_t num_vars;
    uint32_t num_clauses;
    uint32_t decisions;
    uint32_t pruned_cycles;
    double elapsed_ms;
    int verified;
    int8_t assignment[1024]; // 1 = True, 0 = False, -1 = Unassigned
} cq_sat_result_t;

// Function Exports
CQ_API cq_context_t* cq_create_context(uint32_t num_qubits, uint32_t bond_dim);
CQ_API int cq_execute_qasm(cq_context_t* ctx, const char* qasm_str, cq_result_t* out_result);
CQ_API int cq_solve_sat(const char* cnf_str, cq_sat_result_t* out_result);
CQ_API int cq_invert_arx(const char* primitive, uint32_t rounds, const uint64_t* target, uint64_t* out_preimage);
CQ_API void cq_destroy_context(cq_context_t* ctx);
CQ_API const char* cq_get_version(void);
CQ_API double cq_get_active_vram_mb(cq_context_t* ctx);
```

---

## 2. C / C++ Integration

Link against `bin/Release/cq_hecs.lib` and include `include/cq_hecs_api.h`:

```cpp
#include <iostream>
#include "cq_hecs_api.h"

int main() {
    std::cout << "CQ-HECS Version: " << cq_get_version() << std::endl;

    // 1. Create 300-Qubit Engine Context
    cq_context_t* ctx = cq_create_context(300, 64);
    std::cout << "Active VRAM: " << cq_get_active_vram_mb(ctx) << " MB" << std::endl;

    // 2. Execute OpenQASM Circuit
    const char* qasm = 
        "OPENQASM 2.0;\n"
        "include \"qelib1.inc\";\n"
        "qreg q[300];\n"
        "h q[0];\n"
        "cx q[0], q[1];\n"
        "measure q[0];\n";

    cq_result_t qasm_res;
    if (cq_execute_qasm(ctx, qasm, &qasm_res) == 0) {
        std::cout << "Executed " << qasm_res.gate_count << " gates in " 
                  << qasm_res.elapsed_ms << " ms. VRAM: " 
                  << qasm_res.active_vram_mb << " MB\n";
    }

    // 3. Solve Propositional SAT Formula
    const char* cnf = "p cnf 3 2\n1 2 0\n-1 3 0\n";
    cq_sat_result_t sat_res;
    int sat_code = cq_solve_sat(cnf, &sat_res);
    if (sat_code == 0) {
        std::cout << "SATISFIABLE (Decisions: " << sat_res.decisions << ")\n";
    } else if (sat_code == 10) {
        std::cout << "UNSATISFIABLE\n";
    }

    // 4. Destroy Context
    cq_destroy_context(ctx);
    return 0;
}
```

---

## 3. Python Integration via `ctypes`

Zero-overhead foreign function calling from standard Python:

```python
import ctypes
from pathlib import Path

class CQResult(ctypes.Structure):
    _fields_ = [
        ("gate_count", ctypes.c_uint32),
        ("qubit_count", ctypes.c_uint32),
        ("elapsed_ms", ctypes.c_double),
        ("active_vram_mb", ctypes.c_double),
        ("lambda_res", ctypes.c_double),
        ("success", ctypes.c_int),
    ]

class CQSATResult(ctypes.Structure):
    _fields_ = [
        ("satisfiable", ctypes.c_int),
        ("num_vars", ctypes.c_uint32),
        ("num_clauses", ctypes.c_uint32),
        ("decisions", ctypes.c_uint32),
        ("pruned_cycles", ctypes.c_uint32),
        ("elapsed_ms", ctypes.c_double),
        ("verified", ctypes.c_int),
        ("assignment", ctypes.c_int8 * 1024),
    ]

# Load DLL
dll = ctypes.CDLL(str(Path("bin/Release/cq_hecs.dll").resolve()))

# Initialize context
ctx = dll.cq_create_context(300, 64)
print("Active VRAM:", dll.cq_get_active_vram_mb(ctx), "MB")

# Execute circuit
qasm_str = b'OPENQASM 2.0; qreg q[300]; h q[0]; cx q[0], q[1];'
res = CQResult()
dll.cq_execute_qasm(ctx, qasm_str, ctypes.byref(res))
print(f"Executed {res.gate_count} gates in {res.elapsed_ms:.2f} ms")

dll.cq_destroy_context(ctx)
```

---

## 4. C# / .NET via P/Invoke

```csharp
using System;
using System.Runtime.InteropServices;

public class Program {
    [StructLayout(LayoutKind.Sequential)]
    public struct CQResult {
        public uint GateCount;
        public uint QubitCount;
        public double ElapsedMs;
        public double ActiveVramMb;
        public double LambdaRes;
        public int Success;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct CQSATResult {
        public int Satisfiable;
        public uint NumVars;
        public uint NumClauses;
        public uint Decisions;
        public uint PrunedCycles;
        public double ElapsedMs;
        public int Verified;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 1024)]
        public sbyte[] Assignment;
    }

    [DllImport("cq_hecs.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr cq_create_context(uint numQubits, uint bondDim);

    [DllImport("cq_hecs.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern int cq_execute_qasm(IntPtr ctx, string qasmStr, ref CQResult outResult);

    [DllImport("cq_hecs.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern int cq_solve_sat(string cnfStr, ref CQSATResult outResult);

    [DllImport("cq_hecs.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern void cq_destroy_context(IntPtr ctx);

    public static void Main() {
        IntPtr ctx = cq_create_context(300, 64);
        var res = new CQResult();
        string qasm = "OPENQASM 2.0; qreg q[300]; h q[0]; cx q[0], q[1];";
        cq_execute_qasm(ctx, qasm, ref res);
        Console.WriteLine($"Executed {res.GateCount} gates in {res.ElapsedMs:F2} ms");
        cq_destroy_context(ctx);
    }
}
```

---

## 5. Rust Integration

```rust
use std::os::raw::{c_char, c_int};
use std::ffi::CString;

#[repr(C)]
pub struct CQResult {
    pub gate_count: u32,
    pub qubit_count: u32,
    pub elapsed_ms: f64,
    pub active_vram_mb: f64,
    pub lambda_res: f64,
    pub success: c_int,
}

#[link(name = "cq_hecs")]
extern "C" {
    fn cq_create_context(num_qubits: u32, bond_dim: u32) -> *mut std::ffi::c_void;
    fn cq_execute_qasm(ctx: *mut std::ffi::c_void, qasm: *const c_char, res: *mut CQResult) -> c_int;
    fn cq_destroy_context(ctx: *mut std::ffi::c_void);
}

fn main() {
    unsafe {
        let ctx = cq_create_context(300, 64);
        let qasm = CString::new("OPENQASM 2.0; qreg q[300]; h q[0]; cx q[0], q[1];").unwrap();
        let mut res = std::mem::zeroed::<CQResult>();
        cq_execute_qasm(ctx, qasm.as_ptr(), &mut res);
        println!("Executed {} gates in {:.2} ms", res.gate_count, res.elapsed_ms);
        cq_destroy_context(ctx);
    }
}
```
