// Ask the browser whether it exposes a WebGPU adapter, and say so precisely.
//
// The engine table has a WebGPU column. On 2026-11-02 the bundled Playwright Chromium did
// not expose `navigator.gpu` under any of four launch configurations, so that column is
// "not measured" rather than a guessed number. This script makes the check reproducible:
//
//     node scripts/probe_webgpu.mjs
//
// Exit codes: 0 an adapter is available (prints vendor/architecture), 3 no adapter (prints
// the launch configurations that were tried), 1 the probe itself failed.
import { chromium } from "playwright";

const CONFIGURATIONS = [
  { name: "default", args: [] },
  { name: "unsafe-webgpu+d3d11", args: ["--enable-unsafe-webgpu", "--use-angle=d3d11"] },
  { name: "unsafe-webgpu+vulkan", args: ["--enable-unsafe-webgpu", "--enable-features=Vulkan", "--use-angle=vulkan"] },
];

const results = [];
for (const configuration of CONFIGURATIONS) {
  let browser;
  try {
    browser = await chromium.launch({ args: configuration.args });
    const page = await browser.newPage();
    const probe = await page.evaluate(async () => {
      if (!navigator.gpu) return { gpu: false };
      const adapter = await navigator.gpu.requestAdapter().catch((error) => ({ error: String(error) }));
      if (!adapter) return { gpu: true, adapter: false };
      const info = adapter.info ?? {};
      return { gpu: true, adapter: true, vendor: info.vendor ?? null, architecture: info.architecture ?? null };
    });
    results.push({ ...configuration, ...probe });
  } catch (error) {
    results.push({ ...configuration, error: String(error).slice(0, 200) });
  } finally {
    if (browser) await browser.close();
  }
}

const available = results.find((entry) => entry.adapter === true);
console.log(JSON.stringify({ checked_at: new Date().toISOString(), available: Boolean(available), configurations: results }, null, 2));
process.exit(available ? 0 : 3);
