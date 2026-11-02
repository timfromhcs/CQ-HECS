// Circuit-level conformance: the browser parses the QASM itself and Qiskit is the oracle.
//
// `web/tests/conformance.test.ts` checks the 2x2 matrices against a NumPy reference. This
// file checks the layer above it: OpenQASM parsing, circuit compilation and gate ordering.
// The case *is* the QASM text, so the browser cannot agree by construction - it has to read
// the same source Qiskit read.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { Core } from "../src/core";
import { compile, parseQasm } from "../src/circuit";

interface Case {
  name: string;
  qasm: string;
  probabilities: number[];
}

interface Corpus {
  schema: string;
  oracle: string;
  tolerance: number;
  cases: Case[];
}

const corpus: Corpus = JSON.parse(
  readFileSync(new URL("./fixtures/circuit_conformance.json", import.meta.url), "utf8"),
);
const wasmBytes = readFileSync(new URL("../public/cqhecs_core.wasm", import.meta.url));

test("the corpus names its oracle and a usable tolerance", () => {
  assert.equal(corpus.schema, "hcs.web.circuit-conformance.v1");
  assert.match(corpus.oracle, /Qiskit \d+\.\d+/);
  assert.ok(corpus.tolerance > 0 && corpus.tolerance < 1e-9);
  assert.ok(corpus.cases.length >= 5);
});

for (const entry of corpus.cases) {
  test(`circuit conformance: ${entry.name}`, async () => {
    const circuit = parseQasm(entry.qasm);
    const core = await Core.load(wasmBytes);
    assert.ok(core.init(circuit.numQubits), `the core refused ${circuit.numQubits} qubits`);
    core.applyOps(compile(circuit));

    const probabilities = core.probabilities();
    assert.equal(probabilities.length, 1 << circuit.numQubits);
    for (let index = 0; index < probabilities.length; index += 1) {
      const expected = entry.probabilities[index];
      const actual = probabilities[index];
      assert.ok(
        Math.abs(actual - expected) <= corpus.tolerance,
        `${entry.name}: P(${index}) = ${actual}, Qiskit says ${expected}`,
      );
    }
    assert.ok(Math.abs(core.norm() - 1) <= 1e-12, `${entry.name}: norm ${core.norm()}`);
    core.free();
  });
}

test("a swapped control and target is not accepted", async () => {
  // Guard against a corpus that would pass for any circuit: reverse the CNOT of the
  // control-direction case and require a mismatch against Qiskit's answer.
  const entry = corpus.cases.find((candidate) => candidate.name === "control-direction");
  assert.ok(entry, "the corpus lost its control-direction case");
  const swapped = entry.qasm.replace("cx q[1],q[0]", "cx q[0],q[1]");
  assert.notEqual(swapped, entry.qasm, "the substitution did not change the QASM");

  const core = await Core.load(wasmBytes);
  const circuit = parseQasm(swapped);
  assert.ok(core.init(circuit.numQubits));
  core.applyOps(compile(circuit));
  const probabilities = core.probabilities();
  const matches = probabilities.every(
    (value, index) => Math.abs(value - entry.probabilities[index]) <= corpus.tolerance,
  );
  assert.equal(matches, false, "a swapped CNOT must not reproduce Qiskit's answer");
  core.free();
});
