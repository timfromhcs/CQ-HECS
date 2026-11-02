# Conformance and engine measurement

Two questions, answered by files rather than adjectives: *does the browser compute what the
reference computes?* and *how fast is it, measured?*

## 1. Matrix-level corpus (WebAssembly core vs NumPy)

- Generator: `scripts/export_web_conformance.py`
- Fixture: `web/tests/fixtures/quantum_conformance.json`
- Test: `web/tests/conformance.test.ts`

Six circuits (Bell, GHZ-3, phase interference, a `u3` rotation, a controlled phase, a
control-direction case) are expressed as operation lists with explicit 2×2 matrices. The
reference is a dense NumPy statevector written from the same matrices, not the Python
simulator, so the comparison is between two independent implementations.

Semantics recorded in the file: qubit `q` is bit `q` of the basis index, `ctrl` is a bitmask
with `0` meaning no control, matrices are row-major
`[re00, im00, re01, im01, re10, im10, re11, im11]`. Amplitudes are compared, not only
probabilities, at `1e-12`. One test breaks a matrix entry on purpose and must fail.

## 2. Circuit-level corpus (WebAssembly core vs Qiskit)

- Generator: `scripts/export_web_circuit_conformance.py`
- Fixture: `web/tests/fixtures/circuit_conformance.json`
- Test: `web/tests/circuit_conformance.test.ts`

Here the case *is* the OpenQASM 2 text. The browser parses it with its own parser
(`src/circuit.ts`), compiles it, and runs it through the core; the oracle is Qiskit's
statevector simulator. That covers the layer the matrix corpus cannot: parsing, gate
compilation and operand order.

| Case | QASM body (after the register) |
|---|---|
| `bell` | `h q[0]; cx q[0],q[1]` |
| `ghz-3` | `h q[0]; cx q[0],q[1]; cx q[1],q[2]` |
| `s-interference` | `h q[0]; s q[0]; h q[0]` |
| `rx-rz` | `rx(0.7) q[0]; rz(0.4) q[0]` |
| `controlled-phase` | `h q[0]; h q[1]; cp(1.047…) q[0],q[1]; h q[0]; h q[1]` |
| `control-direction` | `x q[0]; cx q[1],q[0]` |

Oracle: **Qiskit 2.5.1 Statevector**, recorded in the fixture. Tolerance `1e-12`.
A negative test swaps the CNOT of `control-direction` and requires a mismatch.

Regenerate both corpora after changing a gate definition:

```bash
python scripts/export_web_conformance.py
python scripts/export_web_circuit_conformance.py
cd web && npm test
```

## 3. Engine measurement (2026-11-02)

- Script: `web/scripts/measure_engines.mjs` (bundles `engine_benchmark.ts` with esbuild and
  runs it under Node 22.23.1).
- Workload: `h` on every qubit, a CNOT ladder, an `rz` layer. Five repetitions per width;
  every sample is kept in `web/e2e-results/engine-benchmark.json` (git-ignored, like the
  other raw evidence; the table below is its summary).
- Environment: Windows 11, AMD Ryzen 7 7735HS, Node v22.23.1, the committed
  `cqhecs_core.wasm` (35.5 KB).

| Qubits | Gates | Setup | Execution (median) | min–max | Readout | Amplitude updates/s |
|---:|---:|---:|---:|---|---:|---:|
| 12 | 35 | 0.26 ms | **0.20 ms** | 0.20–0.52 | 0.03 ms | 1.43 × 10⁹ |
| 16 | 47 | 0.43 ms | **4.08 ms** | 4.02–5.58 | 0.24 ms | 1.51 × 10⁹ |
| 20 | 59 | 3.61 ms | **111.5 ms** | 106.8–114.2 | 5.35 ms | 1.11 × 10⁹ |

Reading: the cost grows with `2^n`, as it must for a dense statevector; the per-update rate
stays in the same order of magnitude up to 20 qubits. This is a single-machine measurement,
not a benchmark against other simulators.

### WebGPU: NOT RUN, and why

`web/scripts/probe_webgpu.mjs` asks the Playwright Chromium for an adapter under three
launch configurations (`default`, `--enable-unsafe-webgpu --use-angle=d3d11`,
`--enable-unsafe-webgpu --enable-features=Vulkan --use-angle=vulkan`) and a fourth headed
run. Result on 2026-11-02: **`navigator.gpu` is absent in all of them**, exit code 3.

So the WebGPU column has no number. Writing one from the f32 pipeline on another machine
would be a different measurement on different hardware; the honest entry is `NOT RUN` with
the command that reproduces the conclusion. The `gpu` field in the benchmark JSON says
exactly that.

## 4. What is not claimed

- The browser engine is **not** the Python engine; the claim is agreement on these two
  corpora, on this hardware, at these tolerances.
- No WebGPU speed claim, in either direction.
- No claim that 20 qubits is a ceiling; it is simply where the measurement stopped.
- No cross-simulator benchmark (Qiskit Aer, Stim, quimb) is implied by the Qiskit oracle
  above - Qiskit is used for small reference states, not as a performance baseline.

## 5. Status against `PLAN_HORIZON_8_V5.md`

| Stage | Package | Status |
|---|---|---|
| A | V1 circuit corpus (Qiskit oracle) | **done** |
| A | V2 engine measurement (WASM measured, WebGPU NOT RUN) | **done, with the GPU column honestly empty** |
| A | V3 documentation | **done** (this file, `docs/WEB_ENGINES.md`, CHANGELOG, README) |
| B | V4 `hcs.run.v2` provenance across CLI/Studio/Web | **done** (5.0.0, `docs/PROVENANCE.md`, `MIGRATION_V5.md`) |
| C | V6–V8 version 5.0.0, migration notes, release | **done** (5.0.0 on every surface, CI, merge) |

Stage A shipped as 4.2.0; stage B/C as 5.0.0. The remaining gap in the contract is the
circuit-simulation CLI path, which does not write cards yet - stated, not hidden.
