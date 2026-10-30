# CQ-HECS Web

An exact quantum-circuit emulator that runs in the browser. Made with ♥ by
timfromhcs & hcsmedia.

**Live:** https://cq-hecs-web.vercel.app

- **WebAssembly f64 (exact):** a Rust state-vector core (`wasm/src/lib.rs`)
  compiled with SIMD128. It runs in a Web Worker. Every one of the 2^n
  amplitudes is kept in double precision; nothing is truncated or compressed.
- **WebGPU f32 (fast):** a WGSL compute kernel (`src/gpu.ts`). WGSL has no f64,
  so for circuits up to 20 qubits each run is cross-checked against the exact
  core and the TV distance is shown. The browser maps WebGPU to Vulkan, D3D12 or
  Metal; browsers expose no direct Vulkan API.
- **Safe runs only:** on start the page detects the OS, CPU threads, RAM and
  GPU/WebGPU limits, benchmarks the kernel, and confirms the largest exact
  width with a real allocation. That width is at most a quarter of the
  reported RAM and at most 2 GiB in the wasm32 heap, so at most 27 qubits.
  Runs whose estimated time exceeds 90 s are refused.
- **Like real hardware, statistically:** shots, mid-circuit measurement, reset,
  and optional depolarizing and readout noise via Monte-Carlo trajectories.
  This is still a classical simulation, not a quantum computer.
- **Simple and advanced:** a visual composer with presets (Bell, GHZ, QFT,
  Grover, Bernstein–Vazirani, teleportation, random circuits), and a code mode
  with OpenQASM 2.0 and a JavaScript builder API (CodeMirror, lazy-loaded),
  shareable links and `.qasm` export.

## Develop

```bash
npm ci
npm run dev        # http://localhost:5173
npm test           # WASM core vs Qiskit fixtures + independent reference
npm run build
npm run wasm       # rebuild the Rust core (needs the wasm32-unknown-unknown target)
```

`scripts/qiskit_fixtures.py` regenerates `tests/fixtures/qiskit_statevectors.json`
with Qiskit `Statevector`. The tests require agreement below 1e-12 with no
global-phase allowance.

## Deploy

Vercel project `cq-hecs-web` (team hcsmediagroup), linked to this repository with
`web/` as the root directory (`vercel.json`: Vite, `dist/`). Every push to `main`
deploys to production; pull requests get preview deployments.
