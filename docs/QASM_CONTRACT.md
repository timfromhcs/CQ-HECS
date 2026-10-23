# QASM parser contract

This document describes the **native C++ parser** (`QASMParserCPP`) used by
`cq_hecs qasm` and the C ABI. The Python CLI uses its own Qiskit-based loader for
`cq-hecs run`; the two entry points do not share the C++ parser.

## What the native parser does

The parser reads a strict subset of OpenQASM 2.0 and a few OpenQASM 3 register
declarations. It produces a validated instruction list for the legacy Z8 phase
ledger. It is **not** a statevector simulator and does not return measurement
counts.

The JSON result always identifies this boundary:

```json
{
  "engine": "CQ-HECS <version> QASM Phase-Ledger",
  "engine_class": "legacy_z8_phase_ledger",
  "statevector_simulation": false
}
```

Use the Python four-path backends (`cq-hecs run`) for statevector, stabilizer,
MPS or sparse-Pauli results.

## Accepted syntax

- `OPENQASM 2.0;` or `OPENQASM 3.0;`
- `include "file.inc";`
- `qreg name[size];` / `creg name[size];`
- `qubit[size] name;` / `bit[size] name;`
- one statement per `;`
- `//` line comments
- gate names are case-insensitive
- gate arguments may be indexed (`q[0]`) or whole-register
  (`q[0], q[1]` or `q` where the gate arity permits expansion)
- angle expressions accepted by the shared evaluator: decimal/scientific
  literals, `pi`, unary `+`/`-`, parentheses and binary `+`, `-`, `*`, `/`.
  Expressions must consume the whole token and evaluate to a finite value.

Supported gate set for the legacy executor:

| Gate | Qubits | Parameters |
| :--- | :--- | :--- |
| `h`, `s`, `sdg`, `t`, `tdg`, `x`, `y`, `z` | 1 | 0 |
| `rx`, `ry`, `rz` | 1 | 1 |
| `cx`, `cnot`, `cz`, `swap` | 2 | 0 |
| `cp` | 2 | 1 |
| `measure` | 1 | 0 |

Anything outside this table is rejected with `unsupported_gate`. It is never
executed as the identity.

## Rejected input

The parser fails closed. It does not repair or partially interpret malformed
input. Rejections include:

- missing statement semicolons (`missing_semicolon`)
- unknown gates (`unsupported_gate`)
- invalid or non-finite angle expressions (`invalid_parameter`)
- wrong parameter or qubit counts (`parameter_count_mismatch` /
  `syntax_error`)
- unknown or duplicate registers (`undeclared_register` / `duplicate_register`)
- malformed operands or out-of-range indices (`invalid_operand` /
  `index_out_of_range`)
- malformed declarations or invalid register sizes (`syntax_error` /
  `invalid_register_size`)
- whole-register expansion that does not match the gate arity (`syntax_error`)
- block comments (`unsupported_syntax`)
- unsupported version strings (`unsupported_version`)
- input larger than 16 MiB or a line larger than 1 MiB (`input_too_large` /
  `line_too_long`)
- a circuit wider than the explicit CLI `--qubits` cap
  (`qubit_budget_exceeded`)

Each error has the shape:

```json
{"line": 3, "category": "unsupported_gate", "message": "unsupported or unknown gate: not_a_gate"}
```

The executor refuses any circuit whose `errors` list is non-empty. There is no
partial execution path.

## Exit codes and streams

For `cq_hecs qasm`:

| Exit code | Meaning |
| :--- | :--- |
| `0` | valid input, execution completed |
| `1` | runtime/environment failure (for example Vulkan unavailable) |
| `2` | valid invocation, invalid circuit input (parse error or `--qubits` cap exceeded) |

With `--json`, the error document is written to **stdout** and human-readable
diagnostics to **stderr**. Text mode writes diagnostics only.

## C ABI

`cq_parse_qasm_buffer()` / `cq_parse_qasm_file()` fill the same structured error
list. `cq_execute_qasm()` returns `-3` when the supplied circuit has parse
errors, and never executes a partially valid circuit.

## Regression evidence

- CTest: `test_qasm_contract`
- Python: `tests/test_fuzz_qasm.py`, `tests/test_cli_powershell.py`,
  `tests/test_qasm_circuits.py`, `tests/test_c_api.py`
- Source mutation: `scripts/run_mutation_tests.py`
