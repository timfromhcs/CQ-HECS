// Bundle budget: the browser build may not silently grow.
//
// Measured on 2026-11-02 from `dist/` with gzip level 9 (the transport encoding
// browsers actually receive):
//
//   JavaScript total   233.5 KB   (editor chunk alone 169.2 KB, it is CodeMirror)
//   WebAssembly core    15.0 KB
//   CSS total            6.6 KB
//
// The budgets below are those measurements plus ~15 % headroom, not round numbers
// picked out of the air. Raising one is a deliberate decision that needs a reason in the
// commit message; the CI build fails otherwise.
import { gzipSync } from "node:zlib";
import { readFileSync, readdirSync } from "node:fs";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const BUDGET = {
  js: 270 * 1024,
  wasm: 18 * 1024,
  css: 8 * 1024,
};

const root = fileURLToPath(new URL("../dist", import.meta.url));

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? walk(join(directory, entry.name)) : [join(directory, entry.name)],
  );
}

let files;
try {
  files = walk(root).filter((file) => [".js", ".wasm", ".css"].includes(extname(file)));
} catch {
  console.error(`bundle check: ${relative(process.cwd(), root)} is missing; run the build first`);
  process.exit(2);
}

const totals = { js: 0, wasm: 0, css: 0 };
const rows = [];
for (const file of files) {
  const kind = extname(file).slice(1);
  const bytes = gzipSync(readFileSync(file), { level: 9 }).length;
  totals[kind] += bytes;
  rows.push([relative(root, file), kind, bytes]);
}

rows.sort((a, b) => b[2] - a[2]);
for (const [name, kind, bytes] of rows) {
  console.log(`${kind.padEnd(5)} ${(bytes / 1024).toFixed(1).padStart(7)} KB gz  ${name}`);
}

let failed = false;
for (const kind of Object.keys(BUDGET)) {
  const actual = totals[kind];
  const budget = BUDGET[kind];
  const status = actual <= budget ? "ok" : "OVER BUDGET";
  console.log(`${kind.padEnd(5)} ${(actual / 1024).toFixed(1).padStart(7)} KB gz  budget ${(budget / 1024).toFixed(0)} KB  ${status}`);
  if (actual > budget) failed = true;
}

if (failed) {
  console.error("bundle budget exceeded; shrink the asset or raise the budget with a reason");
  process.exit(1);
}
console.log(`bundle size check passed (${files.length} files)`);
