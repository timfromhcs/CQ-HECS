// Measure what Chrome actually allows: a page served from loopback fetching the
// miner's API on the LAN. Run from the web/ directory (Playwright is installed
// there); the result is printed as JSON so it can be quoted verbatim.
//
//   node E:/qCSHA/sha_forge_results/measure_lan_access.mjs http://192.168.178.61
//
// Nothing is written to the device: it asks for /api/system/info (read-only) and
// /api/research/status (read-only).
import { chromium } from "playwright";

const device = process.argv[2];
if (!device) {
  console.error("usage: node measure_lan_access.mjs <device-origin>");
  process.exit(2);
}

const origin = process.argv[3] ?? "http://127.0.0.1:4173";
const page_html = `<!doctype html><meta charset="utf-8"><title>lna probe</title><body>probe</body>`;

const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
const events = [];
page.on("console", (m) => events.push(m.text()));
page.on("requestfailed", (r) => events.push(`requestfailed ${r.url()} :: ${r.failure()?.errorText}`));

// Serve the probe page from loopback without a server: intercept the navigation.
await page.route(`${origin}/`, (route) => route.fulfill({ status: 200, contentType: "text/html", body: page_html }));
await page.goto(`${origin}/`);

const results = {};
for (const path of ["/api/system/info", "/api/research/status"]) {
  const started = Date.now();
  results[path] = await page.evaluate(async ({ base, p }) => {
    try {
      const response = await fetch(base + p, { mode: "cors", cache: "no-store" });
      const text = await response.text();
      return { ok: response.ok, status: response.status, bytes: text.length, error: null };
    } catch (error) {
      return { ok: false, status: 0, bytes: 0, error: String(error) };
    }
  }, { base: device, p: path });
  results[path].ms = Date.now() - started;
}

// A private-network request from a loopback page is exactly the case Chrome's
// Local Network Access policy covers; report the permission state if exposed.
results.permissions = await page.evaluate(async () => {
  const out = {};
  for (const name of ["local-network-access", "local-network"]) {
    try {
      out[name] = (await navigator.permissions.query({ name })).state;
    } catch (error) {
      out[name] = `unavailable: ${String(error).slice(0, 60)}`;
    }
  }
  return out;
});

console.log(JSON.stringify({ chromium: browser.version(), origin, device, results, events: events.slice(0, 10) }, null, 2));
await browser.close();
