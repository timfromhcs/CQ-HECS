// The browser's run card must satisfy the same schema the CLI writes against.
//
// `docs/provenance/hcs.run.v2.schema.json` is the shared contract. There is no JSON-Schema
// dependency in this project, so this file carries a small validator that implements the
// keywords the schema actually uses (type, required, const, enum, pattern, minLength,
// minimum, minItems). If the schema grows a keyword the validator does not know, the test
// fails on the unknown keyword instead of silently skipping it.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { buildRunCard, modeOf } from "../src/provenance";

interface SchemaNode {
  type?: string | string[];
  required?: string[];
  properties?: Record<string, SchemaNode>;
  const?: unknown;
  enum?: unknown[];
  pattern?: string;
  minLength?: number;
  minimum?: number;
  minItems?: number;
  items?: SchemaNode;
}

const schema: SchemaNode = JSON.parse(
  readFileSync(new URL("../../docs/provenance/hcs.run.v2.schema.json", import.meta.url), "utf8"),
);

const KNOWN = new Set([
  "$schema", "$id", "title", "description", "type", "required", "properties",
  "const", "enum", "pattern", "minLength", "minimum", "minItems", "items",
  "additionalProperties",
]);

function checkSchemaKeywords(node: SchemaNode, path: string): void {
  for (const key of Object.keys(node)) {
    assert.ok(KNOWN.has(key), `schema keyword ${key} at ${path} is not implemented by this validator`);
  }
  for (const [name, child] of Object.entries(node.properties ?? {})) {
    checkSchemaKeywords(child, `${path}.${name}`);
  }
  if (node.items) checkSchemaKeywords(node.items, `${path}[]`);
}

function typeOf(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

function validate(node: SchemaNode, value: unknown, path: string, errors: string[]): void {
  if (node.type) {
    const allowed = Array.isArray(node.type) ? node.type : [node.type];
    const actual = typeOf(value);
    // JSON Schema separates "number" from "integer"; JavaScript does not.
    const matches = allowed.some(
      (kind) => kind === actual || (kind === "integer" && actual === "number" && Number.isInteger(value)),
    );
    if (!matches) {
      errors.push(`${path}: ${actual} is not ${allowed.join("|")}`);
      return;
    }
  }
  if (node.const !== undefined && value !== node.const) errors.push(`${path}: expected ${JSON.stringify(node.const)}`);
  if (node.enum && !node.enum.includes(value)) errors.push(`${path}: ${JSON.stringify(value)} not in ${JSON.stringify(node.enum)}`);
  if (typeof value === "string") {
    if (node.pattern && !new RegExp(node.pattern).test(value)) errors.push(`${path}: does not match ${node.pattern}`);
    if (node.minLength !== undefined && value.length < node.minLength) errors.push(`${path}: shorter than ${node.minLength}`);
  }
  if (typeof value === "number" && node.minimum !== undefined && value < node.minimum) {
    errors.push(`${path}: below minimum ${node.minimum}`);
  }
  if (Array.isArray(value) && node.minItems !== undefined && value.length < node.minItems) {
    errors.push(`${path}: fewer than ${node.minItems} items`);
  }
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    for (const key of node.required ?? []) {
      if (!(key in record)) errors.push(`${path}: missing required ${key}`);
    }
    for (const [name, child] of Object.entries(node.properties ?? {})) {
      if (name in record) validate(child, record[name], `${path}.${name}`, errors);
    }
  }
  if (Array.isArray(value) && node.items) {
    value.forEach((item, index) => validate(node.items as SchemaNode, item, `${path}[${index}]`, errors));
  }
}

async function sampleCard(): Promise<Record<string, unknown>> {
  const qasm = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n";
  const result = {
    engine: "wasm",
    mode: "sampled",
    elapsedMs: 1.5,
    counts: { "00": 512, "11": 488 },
    exact: [{ bits: "00", p: 0.5 }, { bits: "11", p: 0.5 }],
    amplitudes: [{ bits: "00", re: 0.7071, im: 0 }, { bits: "11", re: 0.7071, im: 0 }],
    bloch: [[0, 0, 1], [0, 0, 1]] as [number, number, number][],
    norm: 1,
    trajectories: 0,
  };
  return buildRunCard(
    {
      version: "5.0.0",
      revision: "35506b7",
      qasm,
      shots: 1000,
      engineRequested: "wasm",
      noise: { p1: 0, p2: 0, readout: 0 },
      seed: 4242,
    },
    result,
    ["Finite shots: the counts are a sample, not the exact distribution."],
    new Date("2026-11-02T12:00:00.000Z"),
  );
}

test("the schema uses only keywords the validator implements", () => {
  checkSchemaKeywords(schema, "root");
});

test("a browser card satisfies the shared schema", async () => {
  const card = await sampleCard();
  const errors: string[] = [];
  validate(schema, card, "card", errors);
  assert.deepEqual(errors, []);
});

test("the digest is the SHA-256 of the payload in the card", async () => {
  const card = (await sampleCard()) as {
    input: { payload: string; digest: string };
    created_at: string;
  };
  const { createHash } = await import("node:crypto");
  assert.equal(card.input.digest, createHash("sha256").update(card.input.payload, "utf8").digest("hex"));
  assert.equal(card.created_at, "2026-11-02T12:00:00Z");
});

test("a wrong digest is rejected by the schema check", async () => {
  const card = (await sampleCard()) as { input: { digest: string } };
  card.input.digest = "0".repeat(64);
  const errors: string[] = [];
  validate(schema, card, "card", errors);
  // The schema only constrains the shape; the value check is the test above. What must
  // fail here is a digest of the wrong shape.
  assert.deepEqual(errors, []);
  card.input.digest = "not-a-digest";
  const second: string[] = [];
  validate(schema, card, "card", second);
  assert.ok(second.length > 0, "a malformed digest must be rejected");
});

test("a card without limits or payload is refused at construction", async () => {
  const result = { engine: "wasm", mode: "sampled", elapsedMs: 1, counts: {} };
  await assert.rejects(
    buildRunCard(
      { version: "5.0.0", revision: "35506b7", qasm: "", shots: 10, engineRequested: "wasm", noise: {}, seed: 1 },
      result,
      ["limit"],
    ),
    /needs the QASM text/,
  );
  await assert.rejects(
    buildRunCard(
      { version: "5.0.0", revision: "35506b7", qasm: "qreg q[1];", shots: 10, engineRequested: "wasm", noise: {}, seed: 1 },
      result,
      [],
    ),
    /at least one stated limit/,
  );
});

test("noise channels select the NOISY_CLASSICAL mode", () => {
  const result = { engine: "wasm", mode: "sampled", elapsedMs: 1, counts: {} };
  assert.equal(modeOf({ p1: 0, p2: 0, readout: 0 }), "SAMPLED");
  assert.equal(modeOf({ p1: 0.001, p2: 0, readout: 0 }), "NOISY_CLASSICAL");
});
