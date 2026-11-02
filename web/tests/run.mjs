// Bundle the TypeScript tests with esbuild (shipped with Vite) and run node --test.
import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const names = ["circuit_conformance", "conformance", "core", "forge", "provenance", "wasm"];
const outfiles = [];
for (const name of names) {
  const outfile = fileURLToPath(new URL(`./${name}.test.bundle.mjs`, import.meta.url));
  await build({
    entryPoints: [fileURLToPath(new URL(`./${name}.test.ts`, import.meta.url))],
    bundle: true, platform: "node", format: "esm", outfile, logLevel: "warning",
    banner: { js: "import { createRequire } from 'module'; const require = createRequire(import.meta.url);" },
  });
  outfiles.push(outfile);
}
const r = spawnSync(process.execPath, ["--test", ...outfiles], { stdio: "inherit" });
process.exit(r.status ?? 1);
