# Roadmap to v4.0.0

v4.0.0 is a major release only if the evidence supports one: a noise model
validated across vendors, and a SAT engine and simulators whose claims are
checked by independent oracles. Each milestone ends in a gated minor release.

## v3.3: UNSAT certificates (shipped)

Replay-checked tree-resolution refutations for `cqhecs.sat` (PR #33).

## v3.4: third vendor, device profiles, web (shipped)

- **Run:** `r-iqm-1`, the full r-io-7 suite on IQM Garnet, 500 shots
  (`PREREG_IQM_GARNET.md`).
- **Test:** H-V3-8 verdict on a third vendor; M-FIT-2 vs M-FIT; readout/X
  anomaly scan; a `tests/test_iqm_garnet.py` integrity test (digests, shots,
  bit order, reproducible verdict), same as `test_ibm_10k.py`.
- **Ship:** Studio Hardware lab and MCP list the row; the web emulator gets a
  "device profile" preset fitted from the measured Garnet/IBM/Rigetti readout and
  CX error, labelled as measured on a given date.
- **Gate:** CI 8/8 green; verdict published whatever it is.
- **Result:** H-V3-8 SUPPORTED on IQM Garnet (16/20). Profiles ship in the CLI,
  Studio, MCP, the Windows build and the web emulator, which also gained the
  guide, EN/DE/FR, the SAT lab and the device comparison.

## v3.5: emulator fidelity

- **Measured-counts regression:** the web and Python profile models are
  scored directly against each vendor's measured counts. Test: per vendor,
  the median TV must be ≤ the committed M-FIT-2 value from the evaluation
  JSON.
- **Web:** WASM threads (SharedArrayBuffer + COOP/COEP) for a 2–8× speedup on
  many-core CPUs. Test: bitwise-identical state vs the single-thread core on
  200 random circuits.
- **Web:** a WebGPU f32 path with a Kahan-compensated norm. Test: TV ≤ 1e-5
  on the Qiskit fixtures.
- **Noise:** T1/T2 relaxation once a provider delivers calibration snapshots.
  Until then it is not modelled, and the profiles say so.

## v3.6: SAT engine (handoff §6)

- CDCL (watched literals, VSIDS, restarts, learning), with DPLL kept as the
  oracle. Test: agreement with brute force on ≥ 5000 random formulas;
  every SAT model verified.
- DRAT proof emission for the CDCL engine, alongside the tree-resolution
  certificates from v3.3. Test: `drat-trim` verifies every UNSAT in CI.
- Weighted partial MaxSAT (core-guided). Test: the ≤ 20-variable brute force
  as oracle.

## v4.0.0: release criteria

1. H-V3-8 evaluated on ≥ 3 vendors: **done** (Rigetti ✓, IBM ✓, IQM ✓, all
   SUPPORTED).
2. Either M-FIT-2 is confirmed on a fresh preregistered run, or it is
   retired in favour of M-FIT. Both outcomes are acceptable; an unresolved
   status is not.
3. CDCL + DRAT shipped, with every UNSAT checked in CI.
4. Web emulator: exact limit, cross-checks and measured device profiles,
   with a Playwright smoke test in CI.
5. Release audit as for v3.2.0: hashes, clean-venv smoke, credential scan.

## Non-goals

No P = NP or ETH claim; no "lossless for arbitrary states"; no GPU speedup
claim without before/after numbers on the same workload.
