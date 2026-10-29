# Benchmark protocol

Status: **PREREGISTERED / NO NEW PERFORMANCE RESULTS YET**.

1. Correctness and identical output contracts precede timing. Exact, approximate, and sampled results are not compared as interchangeable outputs.
2. Pin CQ-HECS SHA, comparator versions/options, dtype, shots/seeds, approximation settings, OS, CPU/device, memory, and native/Vulkan configuration in machine-readable output.
3. Use named circuit families: low-entanglement chain/GHZ, random Clifford, Clifford+T, brickwork/entanglement growth, long-range/2D-local, QFT/arithmetic, selected-observable and refusal/resource cases. No broad SOTA claim from GHZ alone.
4. Hold out entire circuit families from any routing/cost-model calibration. Do not tune on the final validation families.
5. Separate planning/setup/compile, execution, upload/readback, and end-to-end wall time. Record retained tensors, temporary workspace, peak RSS, disk and GPU memory separately where available.
6. Run warmups plus repeated measured runs; preserve every raw run and report median and dispersion. Never manually type timings into public tables.
7. Performance feature initial acceptance bar: at least 15% end-to-end improvement on a preregistered named family, equal correctness/output semantics, no budget violation, and no large regression on comparable families. This is a heuristic project bar, not a scientific law.
8. A microkernel improvement is not an end-to-end win. Physical-GPU, software-ICD, shader compilation, and full simulator acceleration are separate evidence levels.
9. Benchmark smoke must fail on missing required cases or unexpected `UNRESOLVED` results. Historical JSON remains historical and is never presented as a fresh run.
