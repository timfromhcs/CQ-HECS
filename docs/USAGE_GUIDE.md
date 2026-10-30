# CQ-HECS: User and Operator Guide

There are **two** command-line interfaces in this project. They are different
programs with different purposes; do not mix their commands.

| | `cq-hecs` (Python CLI) | `cq_hecs` (native C++ binary) |
| :--- | :--- | :--- |
| Installed by | `pip install cqhecs` | built from source |
| Purpose | Four-path circuit simulation | QASM execution, SAT solving, ARX inversion, self-test |
| Requires Vulkan | **No** | Yes (build-time) |
| Documented below | §1–§4 | §5 |

---

## 1. Install

### Python only (no Vulkan, no compiler)

```bash
pip install cqhecs
```

This gives you the package, the `cq-hecs` CLI, and all four classical
simulation paths. They run entirely on the CPU.

Verify:

```bash
cq-hecs doctor
```

`doctor` distinguishes `available`, `not_installed` and `not_available` rather
than collapsing them. It also reports that the Python paths are CPU-only, and
makes no physical-GPU claim.

### Native component (adds the C++ binary and bindings)

Requires the Vulkan SDK, because the native headers include `vulkan/vulkan.h`
unconditionally.

```powershell
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

Artifacts land in `${CMAKE_BINARY_DIR}/bin/Release` — i.e. `build/bin/Release`
for an out-of-source build, **not** in the source tree.

---

## 2. `cq-hecs` — circuit simulation

```bash
cq-hecs version
cq-hecs doctor
cq-hecs backend list          # capabilities of Paths A–D
cq-hecs analyze name:ghz8     # static analysis + path recommendation
cq-hecs run name:bell --shots 1000 --seed 42
cq-hecs verify name:bell --reference aer
cq-hecs benchmark smoke
```

### Real-data reference evaluation (experimental)

`reference` compares a noisy CQ-HECS prediction with *measured* bitstrings from
a pinned public dataset. It is not a claim that the emulator matches a QPU.

```bash
cq-hecs reference list
cq-hecs --format json reference run --bootstrap 5000
```

The default record is R-IO-5 (Quantum Noise Transfer, MIT): real 2–5 qubit
counts from `ibm_fez` and `ibm_marrakesh` plus run-time calibration. Bell, GHZ
and QFT circuits are reconstructed; the 40 random circuits are excluded because
their gate sequences are not published. The published layout is missing, so the
model is a device-mean model. The preregistered pooled H-V3-1 result on
2026-10-30 is `INCONCLUSIVE` (median ΔTV −0.015660, 95 % CI
[−0.032546, 0.000000]); the Bell+GHZ subset is exploratory `SUPPORTED`. See
`research/v3/HYPOTHESES.md`.

### Metamorphic self-test

`selftest` runs twelve relations that must hold for any correct engine, without
comparing against a stored expected output:

```bash
cq-hecs selftest --cases 8
cq-hecs --format json selftest --cases 8
```

It checks normalization, `C†C = I`, qubit-permutation equivariance, the
`p(θ)`/`rz(θ)` global-phase relation, exact MPS vs dense parity, finite-shot
sampling within a Bonferroni-corrected Hoeffding bound, Kraus/readout
invariants, noisy-output permutation equivariance, zero-noise identity,
channel-composition order, the full MPS/dense unitary modulo one global phase,
and the dense expectation oracle. It is a fast
installation check, not a proof of correctness; the Qiskit/Aer differential
suite remains the independent oracle.

### Circuits

A circuit argument is one of:

* `path/to/circuit.qasm` — OpenQASM 2.0 source
* `name:<builtin>` — a library circuit, listed below
* `module.py:NAME` — import `NAME` from a Python module

Builtins: `ghz8`, `ghz16`, `bell`, `clifford6`, `low_t_rank4`, `mps6`,
`sparse_pauli4`, `ghz8_measured`, `bell_measured`, `toffoli_adder`
(CCX full adder, measured), `qft4` (controlled-phase QFT), `ising6`
(RZZ/RX Trotter steps).

### Output contract

`--format json` writes **exactly one** JSON document to stdout. All
diagnostics go to stderr, never stdout.

```bash
cq-hecs --format json run name:bell --shots 1000 | jq '.result.path'
```

Exit codes:

| Code | Meaning |
| ---: | :--- |
| 0 | success |
| 1 | unexpected error |
| 2 | usage error (bad file, invalid shots, unsupported forced backend) |
| 3 | circuit unresolved / verification failed |
| 4 | environment unavailable |

Verbosity: `--quiet`, `-v`, `-vv`. Errors are logged to stderr via the
`logging` module, never printed to stdout.

---

## 3. Reading the result

Every result separates three error sources:

| Field | Meaning |
| :--- | :--- |
| `error_bound` | Deliberate approximation. `0.0` = nothing was deliberately approximated. |
| `numerical_error_bound` | Measured float roundoff, **or `null`** if not derivable. |
| `sampling_error_bound` | Finite-shot confidence bound, support-size dependent. |
| `total_error_bound` | Sum of the above, **only when they share a metric**; `null` otherwise. |

`state` is `EXACT`, `CERTIFIED`, `UNRESOLVED` or `FAILED`. `EXACT` requires
`exact = true` **and** `error_bound = 0.0`.

### Path-specific expectations

* **A / B / C** return `counts`. Bitstrings use the Qiskit convention: qubit 0
  is **rightmost**.
* **D** returns `expectation_values`, not `counts`. Its error bound certifies
  observables, not a bitstring distribution. If you need counts, force A, B or
  C.
* **C** samples natively from the MPS up to 500 qubits (subject to the RAM
  budget and a `shots × qubits` batch ceiling) and refuses counts above that
  routing ceiling rather than inventing a result. The separate 20-qubit cap
  applies only to dense statevector conversion (`to_statevector()`), not to
  MPS-native sampling.

### Forces

```bash
cq-hecs run name:low_t_rank4 --backend B
```

A forced path never silently reroutes. If the circuit uses a gate that path
cannot execute, the command exits 2 and names the offending gate.

Forcing Path D on a circuit it *can* evolve is allowed even when a cheaper path
exists — it reports `CERTIFIED` and prints `expectation_values` rather than
counts. Forcing it on a circuit it cannot evolve at all (unsupported gate) exits
2.

---

### Pauli expectation values

```bash
cq-hecs expect name:bell -o ZZ -o XX -o YY
cq-hecs --format json expect name:ising6 -o "X0 X1" --method dense
```

`expect` evaluates `<psi|P|psi>` for Pauli strings: a dense Qiskit label
(`IZX`, rightmost character = qubit 0, length = qubit count) or a sparse list
(`X0 Z2`, `X[0]Z[2]`). Every qubit may appear once. Engines:

* `stabilizer` - Clifford circuits up to 4096 qubits; exact `-1/0/+1` from the
  tableau, no sampling.
* `dense` - exact float64 statevector up to 22 qubits (library ceiling 26).
* `sparse_pauli` - wider non-Clifford circuits through Path D. Its certified
  bound covers the expectation values only; a value that cannot be certified
  inside `--error-tolerance` is printed as `UNRESOLVED` (JSON `null`) and the
  command exits 3. Path D keeps its gate set, so `cp`/`crx`/... circuits are
  refused here instead of approximated.

`--method auto` (default) uses the first engine that applies. Mid-circuit
measurement and `reset` are refused (exit 2). The JSON document has the same
`schema_version` as the other commands; `result.values` maps each requested
name to its value.

### Hardware profiles and noisy emulation

```bash
cq-hecs profile list
cq-hecs profile show fake_manila
cq-hecs --format json run name:bell --profile fake_manila --shots 1000
cq-hecs --format json run name:bell --profile fake_manila --no-noisy
```

`--profile` runs the circuit on the exact float64 density-matrix backend
(at most 10 qubits) after checking every two-qubit gate against the profile's
coupling map. The result carries `execution_mode` (`NOISY_CLASSICAL`, or
`IDEAL_CLASSICAL` with `--no-noisy`), `backend_profile_id` and
`noise_model_id`; it is never `REAL_HARDWARE`. Bitstrings follow the same
convention as `run` without a profile: qubit 0 rightmost, measured qubits only.

* A noise channel applies after each gate *as written* on the qubits the model
  names. The circuit is not transpiled to the profile's basis gates, so a gate
  the profile does not calibrate (for example `h` on `fake_manila`) stays
  noiseless.
* `gate_errors` in a profile are average gate infidelities `r = 1 - F_avg`
  (the value Qiskit's `InstructionProperties.error` and IBM calibration data
  report). Each becomes the depolarizing channel with that infidelity,
  `p = d r / (d - 1)` for a gate on `d = 2^k` levels
  (`cqhecs.depolarizing_parameter_from_infidelity`); an `r` above
  `(d - 1)/d` is refused. T1/T2 relaxation is validated (`T2 <= 2 T1`) but not
  modelled. Before v2.5.2 `r` was used as `p`, which halved one-qubit noise.
* `fake_manila` and `linear_5q` are **synthetic**: `fake_manila` copies only
  the Manila coupling topology, not IBM's calibration values. A
  `BackendProfile` that claims real data (`is_synthetic=False`) must carry
  `capture_timestamp` and `provenance_uri`.
* An unknown profile name or a gate on a missing coupling edge exits with `2`.

#### Real calibration snapshots (unreleased, v3 work)

```python
from cqhecs.calibration_import import load_qiskit_ibm_runtime_snapshot
from cqhecs.hardware_bridge import FakeHardwareBackend

profile = load_qiskit_ibm_runtime_snapshot("manila")    # needs qiskit-ibm-runtime
backend = FakeHardwareBackend(profile, relaxation=True)  # depolarizing + T1/T2
result = backend.run([("h", [0], []), ("cx", [0, 1], []),
                      ("measure", [0], []), ("measure", [1], [])], shots=1000, seed=7)
```

The profile is `is_synthetic=False` with the snapshot's `last_update_date`,
a `pypi:qiskit-ibm-runtime==<version>#...` provenance URI and the SHA-256 of
the source file. It describes the device on that date, not today. Data the
model cannot use is listed in `profile.calibration_flags`; a circuit that
touches such a qubit or pair raises `OutOfModelError`. With `relaxation=True`
the noise per gate is Qiskit Aer's device model; the result is still
`NOISY_CLASSICAL` (a model), not a hardware measurement.

Noisy expectation values work beyond the 10-qubit density-matrix limit:

```python
res = backend.expectation_values(circuit, ["Z[20]", "Z[19]Z[20]"],
                                 prune_threshold=1e-6, error_tolerance=0.01)
res.values, res.method, res.error_bound   # 'noisy_pauli_propagation' above 10 qubits
```

`error_bound` is the 1-norm of the Pauli terms dropped during propagation. It
bounds the difference to the exact value *of the noise model* for this circuit
and the |0…0⟩ input; it does not bound the distance to real hardware. Values
whose bound exceeds `error_tolerance` are `None`.

## 4. Python API

```python
from qiskit import QuantumCircuit
from cqhecs import FourPathRouter

qc = QuantumCircuit(3)
qc.h(0); qc.cx(0, 1); qc.t(1)

result = FourPathRouter().route_and_execute(qc, shots=1000, seed=42)

print(result.path, result.state.value)
print(result.error_bound, result.sampling_error_bound)
print(result.to_dict())        # JSON-serialisable
```

Qiskit `BackendV2`:

```python
from cqhecs import CQHecsBackend
from qiskit import transpile

backend = CQHecsBackend(num_qubits=8)
compiled = transpile(qc, backend)
counts = backend.run(compiled, shots=1000, seed_simulator=42).result().get_counts()
```

Measurement mapping follows the circuit's own `measure` instructions, so
`measure_all()` circuits produce the same keys as Aer.

---

## 5. Native C++ binary

The native executable is a separate program. Its commands are **not** the
`cq-hecs` commands.

```cmd
bin\Release\cq_hecs.exe --help
```

Exit codes differ from the Python CLI:

| Code | Meaning |
| ---: | :--- |
| 0 | success / verified / SAT |
| 1 | generic error |
| 10 | UNSAT / refuted |

Global options: `--json` (strict JSON on stdout, diagnostics on stderr) and
`--help`.

```powershell
.\build\bin\Release\cq_hecs.exe qasm benchmarks\qasm\ghz_300.qasm --json
```

---

## 6. Troubleshooting

**`cq-hecs: command not found`** — the console script directory is not on
`PATH`. Use `python -m cqhecs.cli` or add the scripts directory.

**`doctor` reports `native_binding: not_available`** — expected for a
Python-only install. The classical backends work without it.

**Exit 2 with "does not support the following gate(s)"** — a forced path cannot
run that circuit. Drop `--backend` to let the router choose.

**Exit 3 `unresolved`** — the circuit exceeded a resource budget or the
certified bound exceeded the tolerance. This is a real refusal, not a failure.
Raise `--error-tolerance` or reduce the circuit width.

**Counts look wrong for a wide circuit** — Path C produces no counts above 20
measured qubits, and Path D produces none at all. Check `result.state` and
`result.path` before trusting `counts`.

---

## 7. Verifying the claims in this guide

Every command above was executed on the environment recorded in
`research/v2/METHOD_CATALOG.md` §5. If a command in this document does not work,
that is a documentation bug — please report it rather than working around it
silently.