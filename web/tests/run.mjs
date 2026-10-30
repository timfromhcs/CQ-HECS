// Bundle the TypeScript tests with esbuild (shipped with Vite) and run node --test.
import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const outfile = fileURLToPath(new URL("./core.test.bundle.mjs", import.meta.url));
await build({
  entryPoints: [fileURLToPath(new URL("./core.test.ts", import.meta.url))],
  bundle: true, platform: "node", format: "esm", outfile, logLevel: "warning",
  banner: { js: "import { createRequire } from 'module'; const require = createRequire(import.meta.url);" },
});
const r = spawnSync(process.execPath, ["--test", outfile], { stdio: "inherit" });
process.exit(r.status ?? 1);
