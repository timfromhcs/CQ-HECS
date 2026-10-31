import { defineConfig, devices } from "@playwright/test";

// E2E against the production build (`vite preview`), or against a deployed URL
// when E2E_BASE_URL is set (used for the Vercel preview check).
const external = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"]],
  outputDir: "e2e-results",
  use: {
    baseURL: external ?? "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: external
    ? undefined
    : { command: "npx vite preview --host 127.0.0.1 --port 4173 --strictPort", url: "http://127.0.0.1:4173", reuseExistingServer: true, timeout: 60_000 },
});
