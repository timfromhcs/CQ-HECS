// Bundle the TypeScript benchmark with esbuild and run it with node.
//
// The benchmark imports the real engine code (`src/circuit.ts`, `src/core.ts`), so it has
// to go through the same bundler the test suite uses; node cannot import the TypeScript
// sources directly.
import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { rmSync } from "node:fs";
import { fileURLToPath } from "node:url";

const outfile = fileURLToPath(new URL("./.engine_benchmark.bundle.mjs", import.meta.url));
await build({
  entryPoints: [fileURLToPath(new URL("./engine_benchmark.ts", import.meta.url))],
  bundle: true,
  platform: "node",
  format: "esm",
  outfile,
  logLevel: "warning",
});
const result = spawnSync(process.execPath, [outfile, ...process.argv.slice(2)], { stdio: "inherit" });
rmSync(outfile, { force: true });
process.exit(result.status ?? 1);
