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
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] }, testIgnore: /mobile\.spec\.ts/ },
    // W4-15: phone-sized, touch-enabled projects. They run only the mobile spec so the suite
    // time does not triple; the desktop project already walks the shared behaviour specs.
    // Chromium emulation of phone viewports (WebKit/Firefox are not installed in CI).
    { name: "mobile-360", testMatch: /mobile\.spec\.ts/, use: { ...devices["Pixel 7"], viewport: { width: 360, height: 740 } } },
    { name: "mobile-390", testMatch: /mobile\.spec\.ts/, use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } } },
  ],
  webServer: external
    ? undefined
    : { command: "npx vite preview --host 127.0.0.1 --port 4173 --strictPort", url: "http://127.0.0.1:4173", reuseExistingServer: true, timeout: 60_000 },
});
