// W4-11: the WASM core URL must follow the deployment base, not the domain root.
import { test } from "node:test";
import assert from "node:assert/strict";

import { coreWasmUrl } from "../src/wasm_url";

test("the core URL is rooted at the deployment base", () => {
  assert.equal(coreWasmUrl("https://example.com", "/"), "https://example.com/cqhecs_core.wasm");
});

test("a sub-path deployment keeps the core under that path", () => {
  assert.equal(coreWasmUrl("https://example.com", "/app/"), "https://example.com/app/cqhecs_core.wasm");
  assert.equal(coreWasmUrl("https://example.com", "/preview/team/"), "https://example.com/preview/team/cqhecs_core.wasm");
});

test("the URL is never protocol-relative or doubled", () => {
  const url = coreWasmUrl("https://example.com", "/app/");
  assert.ok(url.startsWith("https://example.com/app/"));
  assert.ok(!url.includes("//cqhecs_core.wasm"));
});
