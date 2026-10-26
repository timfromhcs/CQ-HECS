# QASM parser contract (v2.2.2)

CQ-HECS has two parsers that share one **fail-closed** contract:

| Surface | Entry point | Result |
| :--- | :--- | :--- |
| Python four-path simulator | `cqhecs.circuit_parsing.parse_circuit()` / `cq-hecs run` | normalised instruction list plus qubit count |
| Native legacy executor | `cq_hecs qasm`, `cq_parse_qasm_buffer()` / `cq_parse_qasm_file()` | validated instruction list for the Z8 phase ledger |

Neither parser repairs input, skips an unknown statement or executes a
partially interpreted circuit. Both report a structured error with a
machine-readable `category` and a 1-based `line`, so their behaviour can be
compared differentially. The categories are the same even where the accepted
gate tables deliberately differ (§6).

The native path is **not** a statevector simulator: it reports
`engine_class = legacy_z8_phase_ledger` and `statevector_simulation = false`.
Use the Python paths for statevector, stabilizer, MPS or sparse-Pauli results.

## 1. Accepted syntax

- `OPENQASM 2.0;` or `OPENQASM 3.0;` — the keyword is uppercase, as required by
  the OpenQASM grammar. A missing header is accepted (the native parser is
  lenient here); a malformed version is rejected with `unsupported_version`.
- One or more `;`-terminated statements per line. A statement may not continue
  on the next line; a line without a terminating `;` is `missing_semicolon`.
- `qreg name[size];` / `creg name[size];` (OpenQASM 2.0) and
  `qubit[size] name;` / `bit[size] name;` (OpenQASM 3 style).
- `include "file.inc";` is validated syntactically and otherwise ignored.
- `//` line comments and blank lines.
- Gate names are matched case-insensitively and normalised to lowercase.
- Operands are `register[index]`, or a bare register name. Bare registers are
  expanded in declaration order (see §3).
- Angle expressions are decimal/scientific literals, `pi`, unary `+`/`-`,
  parentheses and binary `+`, `-`, `*`, `/`. The entire token must be consumed
  and must evaluate to a finite value. `nan`, `inf`, division by zero,
  unbalanced parentheses, operators in the wrong position and over-long/tightly
  nested expressions are `invalid_parameter`. The Python parser uses a bounded
  recursive-descent evaluator (`_MAX_ANGLE_LENGTH = 512`,
  `_MAX_ANGLE_DEPTH = 200`) and **never** Python `eval()`.
- A measurement is `measure <qubit> -> <clbit>;`.

Block comments (`/* ... */`) are not part of the contract and are rejected with
`unsupported_syntax`.

## 2. Register mapping

Registers keep their identity and receive disjoint global qubit offsets in
declaration order:

```text
qreg a[2];   # a[0] -> 0, a[1] -> 1
qreg b[3];   # b[0] -> 2, b[1] -> 3, b[2] -> 4
```

The circuit width is the **sum** of all register sizes, not
`max(register_size)`. Classical registers are mapped the same way. This is
identical in the Python and native parsers and is covered by a differential test.

## 3. Whole-register expansion

A bare register expands to all of its indices, in declaration order. As in the
native parser, the flattened operand list must be a whole multiple of the gate
arity and is consumed in arity-sized chunks:

```text
qreg a[2];
qreg b[3];
h b;                        # h applied to b[0], b[1], b[2]
cx a[0], b[0], a[1], b[2];  # cx applied to (a[0], b[0]) and (a[1], b[2])
```

The second statement flattens to four qubits and is consumed in arity-sized
chunks. A flattened list whose length is not a multiple of the arity is
rejected with `operand_count_mismatch`. Colon ranges (`q[0:2]`) are not part of
this grammar.

## 4. Measurement placement and classical bits

Measurements stay at the **source position**. The Python parser sorts only a
terminal measurement suffix by qubit (so that qubit 0 is rendered rightmost);
it never moves a measurement past a unitary gate. The native parser records
measurements in source order.

The four-path simulator supports only the identity classical mapping:

```text
measure q[i] -> c[i];   # accepted
measure q -> c;         # accepted only when the widths match and q[i] -> c[i]
measure q[i] -> c[j];   # rejected (unsupported_syntax)
```

Silently dropping a classical target would produce wrong counts, so remapping
is refused rather than approximated.

Mid-circuit measurement, `reset` and classically conditioned gates are
semantically distinct from terminal measurement. The Python parser preserves
them in the instruction list; the analyzer/router/backend reject them **before
execution**:

- mid-circuit measurement → refused (no path implements the changed state),
- `reset` → refused (non-unitary; no path implements it),
- `if (...) ...` / Qiskit control flow → `unsupported_syntax` at parse time for
  QASM, `UnsupportedCircuitError` before execution for Qiskit circuits.

## 5. Native legacy gate table

The native executor implements exactly:

| Gate | Qubits | Parameters |
| :--- | :--- | :--- |
| `h`, `s`, `sdg`, `t`, `tdg`, `x`, `y`, `z` | 1 | 0 |
| `rx`, `ry`, `rz` | 1 | 1 |
| `cx`, `cnot`, `cz`, `swap` | 2 | 0 |
| `cp` | 2 | 1 |
| `measure` | 1 | 0 |

Anything else is `unsupported_gate` and is never executed as the identity.

## 6. Python gate table and the documented divergence

The Python parser validates syntax and signature against
`cqhecs/gate_manifest.py`, the single capability source shared with the
analyzer, router and backends. It accepts these names so that the refusal
happens at the **capability** layer with a precise message:

- implemented somewhere: `h, x, y, z, s, sdg, t, tdg, id, rx, ry, rz, p, u1,
  cx, cnot, cz, swap, cp, cu1, crx, cry, crz, measure, barrier`
- known but not implemented by any path: `u, u2, u3, ccx, toffoli, ch, cs,
  csdg, reset`

The deliberate difference is therefore only the **layer** at which the two
parsers refuse `u/u2/u3/ccx/toffoli/ch/cs/csdg` (and the additional implemented
Path-C gates `p/u1/cu1/crx/cry/crz`):

| Input | Python parser | Native parser | Execution |
| :--- | :--- | :--- | :--- |
| `u`, `u2`, `u3`, `ccx`, `toffoli`, `ch`, `cs`, `csdg` | parses, then capability refusal | `unsupported_gate` at parse time | refused by both |
| `p`, `u1`, `cu1`, `crx`, `cry`, `crz` | parses, executes on Path C | `unsupported_gate` at parse time | Python only |
| unknown name | `unsupported_gate` | `unsupported_gate` | refused by both |

No input is accepted by one parser and silently executed with different
semantics by the other. The divergence is an acceptance *ceiling*, not a
semantic difference, and `tests/test_hardening_v221.py::TestPythonNativeQASMDifferential`
asserts it.

## 7. Rejection categories

| Category | Examples |
| :--- | :--- |
| `missing_semicolon` | a statement line without `;` |
| `unsupported_gate` | unknown gate name, or a native gate outside §5 |
| `parameter_count_mismatch` | `rx q[0];`, `rx() q[0];` |
| `operand_count_mismatch` | `cx q;` where the flattened width is not a multiple of 2 |
| `invalid_parameter` | `sin(pi)`, `nan`, `inf`, `1/0`, `2**3`, unbalanced parentheses |
| `undeclared_register` | `h phantom[0];` |
| `duplicate_register` | two declarations of `q` |
| `invalid_register_size` | size `0`, negative, or above `1 << 20` |
| `index_out_of_range` | `h q[2]` for `qreg q[2];` |
| `invalid_operand` | malformed operand list |
| `width_mismatch` | `measure q -> c;` with different widths |
| `unsupported_syntax` | block comments, classical-bit remapping, `if`/`for`/`while`/`def` |
| `unsupported_version` | `OPENQASM 4.0;`, bare `OPENQASM;` |
| `input_too_large` / `line_too_long` | source > 16 MiB or line > 1 MiB |
| `syntax_error` | malformed declarations, duplicate header, other malformed statements |
| `qubit_budget_exceeded` | native `--qubits` cap exceeded |

Every error has the shape:

```json
{"line": 3, "category": "unsupported_gate", "message": "unsupported or unknown gate: not_a_gate"}
```

## 8. Exit codes and streams (native `cq_hecs qasm`)

| Exit code | Meaning |
| :--- | :--- |
| `0` | valid input, execution completed |
| `1` | runtime/environment failure |
| `2` | valid invocation, invalid circuit input |

With `--json`, the error document is written to **stdout** and human-readable
diagnostics to **stderr**. `cq_execute_qasm()` returns `-3` on parse errors and
zeroes the result; it never executes a partially valid circuit.

## 9. Regression evidence

- CTest: `test_qasm_contract`, `cq_hecs_cpp_hardening`
- Python: `tests/test_fuzz_qasm.py`, `tests/test_qasm_circuits.py`,
  `tests/test_cli_powershell.py`, `tests/test_c_api.py`,
  `tests/test_hardening_v221.py`
- Differential: `TestPythonNativeQASMDifferential` (same categories for shared
  rejections, register offsets, whole-register expansion, documented divergence)
- Source mutation: `scripts/run_mutation_tests.py`
