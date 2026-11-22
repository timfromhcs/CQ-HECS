# Wave D / D1 evidence

## C1-FIND-01 (repeated operand) -- FIXED at the shared layer
- `cqhecs/gate_manifest.py`: new `repeated_operands()`; `signature_errors()` now reports repeated operands (covers `gate_lowering`).
- `cqhecs/circuit_parsing.py`: QASM reader refuses with `QASMParseError(category="repeated_operand", line=N)` per arity-sized chunk (so `cx q,q` broadcast chunks are also checked); `_sort_terminal_measurements` (shared by Qiskit, list and QASM inputs) refuses any non-barrier instruction with a repeated operand with `UnsupportedCircuitInputError`. Refusal happens in parsing, before routing or any backend allocation.
- New `tests/test_circuit_repeated_operands.py`: every multi-qubit gate in MANIFEST x every repeated-operand tuple pattern, via QASM and via instruction list, plus distinct operands still accepted, plus router on auto/A/B/C.
- `tests/test_web_shared_conformance.py`: expectedFailure removed (now a normal refusal test); the "divergence is recorded" test and the `known_divergence` skip removed.
- NEEDED OUTSIDE MY AREA (web/): delete the `DIVERGENCES` entry in `web/scripts/export_shared_conformance.py` and regenerate `web/tests/fixtures/shared_conformance.json` (`python web/scripts/export_shared_conformance.py`). Until then `FixtureIntegrity::test_committed_fixture_is_what_the_generator_produces` fails with "stale corpus" (the generator now sees Python refusing, so `known_divergence` disappears from the output).

## SEC-M2 (eval in python_bridge) -- FIXED
- `QASMParser._eval_param_expr` now calls `parse_angle_expression`. Differential old-vs-new on 25 legal expressions: bit-identical. Behaviour change (deliberate, fail-closed): non-grammar text (`pi**2`, `2^3`, `sqrt(2)`, `1/0`, empty) previously evaluated (or silently returned 0.0); now raises ValueError.
- strict xfail removed; the test now asserts ValueError. Added parity + refusal tests. `KNOWN_CODE_FINDINGS` in tests/test_property_security_audit.py emptied.

## eval/exec/pickle grep (cqhecs, python_bridge, scripts, web/src)
- No remaining `eval`/`exec`/pickle/marshal in Python product code (`np.load(..., allow_pickle=False)` in path_c; `ast.literal_eval` in scripts/sbom_cyclonedx.py is safe; `model.eval()` in omniwave/learned.py is torch).
- `web/src/main.ts:423` `new Function("circuit","PI", text)`: runs user-authored JS circuit-builder code in the browser; by design but is code execution of user text (outside my area; report only).
- `cqhecs/service.py:577` `__import__(module)` dynamic import of a module name; not examined further (outside owned area).

## Test status
- Targeted: tests/test_circuit_repeated_operands.py, test_fuzz_qasm_parser.py, test_qasm_circuits.py pass.
- Failing, not caused by D1: test_property_security_audit.py::test_tracked_files_contain_no_secret_shaped_strings (flags positive-control strings at tests/test_packaging.py:143 and tests/test_property_security_audit.py:31,33; those files belong to other owners / the audit's own fixtures).
- Failing, needs web regeneration: test_web_shared_conformance FixtureIntegrity (see above).
