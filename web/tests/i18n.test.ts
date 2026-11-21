// W4-14: every UI key must exist in all three languages. `missingKeys()` is the
// module's own parity probe; this test makes it a gate instead of a comment.
import { test } from "node:test";
import assert from "node:assert/strict";

import { missingKeys, LANGS } from "../src/i18n";

test("every i18n key exists in English, German and French", () => {
  assert.deepEqual(missingKeys(), []);
});

test("the three languages are declared in order", () => {
  assert.deepEqual(
    LANGS.map((l) => l.id),
    ["en", "de", "fr"],
  );
});