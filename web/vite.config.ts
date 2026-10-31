import { defineConfig } from "vite";
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

// Build provenance shown in the result details: the CQ-HECS version from the single
// source of truth and the exact source commit (Vercel sets VERCEL_GIT_COMMIT_SHA).
function version(): string {
  try {
    const text = readFileSync(new URL("../scripts/version.py", import.meta.url), "utf-8");
    return /^VERSION = "([^"]+)"/m.exec(text)?.[1] ?? "unknown";
  } catch {
    return "unknown";
  }
}

function sourceSha(): string {
  if (process.env.VERCEL_GIT_COMMIT_SHA) return process.env.VERCEL_GIT_COMMIT_SHA;
  try {
    return execSync("git rev-parse HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return "unknown";
  }
}

export default defineConfig({
  worker: { format: "es" },
  define: {
    __APP_VERSION__: JSON.stringify(version()),
    __SOURCE_SHA__: JSON.stringify(sourceSha()),
  },
  build: { target: "es2022", sourcemap: false, chunkSizeWarningLimit: 800 },
});
