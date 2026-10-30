# CQ-HECS v2.5.2 Literature and Source Map

Only sources actually used for this cycle's decisions are listed. A live
refresh of the OpenAI Math repository and of the emulator landscape
(GEMINI.md §5.1, §5.3) was **NOT RUN** this cycle: no feature was selected, so
no transfer decision depended on it. `research/v2_5/LITERATURE_MAP.md` remains
the latest such map (historical, 2026-10-29).

| Source | Revision / version | Used for | Transfer decision |
|---|---|---|---|
| M. A. Nielsen, "A simple formula for the average gate fidelity of a quantum dynamical operation", Phys. Lett. A 303, 249 (2002), arXiv:quant-ph/0205035 | published | `F_avg` of the depolarizing channel: `F = 1 − p (d−1)/d` → `p = d r/(d−1)` | DIRECT_TRANSFER (closed form; implemented in `depolarizing_parameter_from_infidelity`) |
| M. Horodecki, P. Horodecki, R. Horodecki, Phys. Rev. A 60, 1888 (1999) | published | `F_avg = (Σ_k |Tr K_k|² + d)/(d(d+1))` as an independent check in mutant 22 | VALIDATION_ONLY |
| Qiskit `qiskit.transpiler.InstructionProperties` docstring | qiskit 2.6.1 (installed) | `error` is "the average error rate for the instruction" (i.e. `1 − F_avg`) | Defines the meaning of the exported value |
| Qiskit Aer `qiskit_aer/noise/device/models.py::_device_depolarizing_error` | qiskit-aer 0.18.2 (installed source) | Aer's conversion `p = d (r − r_relax)/(d F_relax − 1)`; reduces to ours without relaxation; Aer clips unphysical `r`, CQ-HECS refuses it | VALIDATION_ONLY (cross-check of convention) |
| `qiskit.quantum_info.average_gate_fidelity`, `Statevector`, `DensityMatrix` | qiskit 2.6.1 / 2.5.1 (pinned lane) | Independent test oracles | VALIDATION_ONLY |
| Bravyi, Smith, Smolin, "Trading classical and quantum computational resources", PRX 6, 021043 (2016) | published | Path B decomposition `T = c0 I + c1 Z`; the fix follows from the matrix identity, not from the paper | VALIDATION_ONLY |
| Physical constraint `T2 ≤ 2 T1` (`1/T2 = 1/(2T1) + 1/T_φ`) | textbook | Profile validation | DIRECT_TRANSFER |
