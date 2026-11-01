import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const TABS = ["overview", "analyzer", "miner", "bench", "evidence"];

test.beforeEach(async ({ page }) => {
  page.on("pageerror", (err) => { throw err; });
});

test("demo is the default, every tab renders and the console stays clean", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const external: string[] = [];
  const origin = new URL(page.url() === "about:blank" ? "http://127.0.0.1:4173" : page.url()).origin;
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.protocol.startsWith("http") && u.origin !== new URL(process.env.E2E_BASE_URL ?? origin).origin && !/fonts\.(googleapis|gstatic)\.com$/.test(u.hostname)) external.push(r.url());
  });
  await page.goto("/forge.html?lang=en");
  await expect(page.locator("#env-badge")).toHaveText("DEMO");
  for (const tab of TABS) {
    await page.click(`[data-tab=${tab}]`);
    await expect(page.locator(`[data-panel=${tab}]`)).toBeVisible();
  }
  expect(errors).toEqual([]);
  expect(external, "demo mode must not make any LAN or third-party request").toEqual([]);
});

test("analyzer: abc digest, 64 rounds, genesis header, input validation", async ({ page }) => {
  await page.goto("/forge.html?lang=en#analyzer");
  await expect(page.locator("#an-summary")).toContainText("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  await expect(page.locator("#an-summary")).toContainText("Web Crypto agrees");
  await expect(page.locator("#an-table tbody tr")).toHaveCount(64);
  await page.click("#an-genesis");
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-summary")).toContainText("000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f");
  await expect(page.locator("#an-summary")).toContainText("genesis check");
  await expect(page.locator("#an-block option")).toHaveCount(3);
  await page.selectOption("#an-mode", "hex");
  await page.fill("#an-input", "zz");
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-error")).toBeVisible();
  await page.fill("#an-input", "616263");
  await page.fill("#an-rounds", "20");
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-summary")).toContainText("not standard SHA-256");
  await expect(page.locator("#an-table tbody tr")).toHaveCount(20);
  await page.fill("#an-rounds", "65");
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-error")).toBeVisible();
});

test("analyzer export produces a replayable trace file", async ({ page }) => {
  await page.goto("/forge.html?lang=en#analyzer");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#an-export")]);
  expect(dl.suggestedFilename()).toBe("sha-trace.json");
});

test("miner lab: demo is labelled, actions stay locked, unreachable bridge fails clearly", async ({ page }) => {
  await page.goto("/forge.html?lang=en#miner");
  await expect(page.locator("#mi-src")).toContainText("DEMO / SIMULATED");
  for (const b of await page.locator(".locked button").all()) await expect(b).toBeDisabled();
  await page.fill("#mi-url", "http://192.168.1.50:80");
  await page.click("#mi-connect");
  await expect(page.locator("#mi-msg")).toContainText("127.0.0.1 or localhost");
  await page.fill("#mi-url", "http://127.0.0.1:9");
  await page.click("#mi-connect");
  await expect(page.locator("#mi-msg")).toContainText("Bridge not reachable", { timeout: 10_000 });
  await expect(page.locator("#env-badge")).toHaveText("DEMO");
  await expect(page.locator("#mi-table tbody tr")).toHaveCount(60);
});

test("engine probe selects a software engine and explains every rejection", async ({ page }) => {
  await page.goto("/forge.html?lang=en#bench");
  await page.click("#be-run");
  await expect(page.locator("#be-selected")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("#be-decisions tbody tr")).toHaveCount(7);
  await expect(page.locator("#be-decisions tbody tr", { hasText: "BROWSER_CPU" })).toContainText("available");
  for (const row of await page.locator("#be-decisions tbody tr", { hasText: "not available" }).all()) {
    expect((await row.locator("td").last().innerText()).length).toBeGreaterThan(5);
  }
});

test("without WebGPU the probe falls back visibly to the CPU", async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(navigator, "gpu", { value: undefined, configurable: true }); delete (navigator as unknown as Record<string, unknown>).gpu; });
  await page.goto("/forge.html?lang=en#bench");
  await page.click("#be-run");
  await expect(page.locator("#be-selected")).toContainText("BROWSER_CPU", { timeout: 30_000 });
  await expect(page.locator("#be-decisions tbody tr", { hasText: "WEBGPU" })).toContainText("not available");
});

test("language switch EN/DE/FR", async ({ page }) => {
  await page.goto("/forge.html?lang=en");
  await expect(page.locator("[data-tab=analyzer]")).toHaveText("Round Analyzer");
  await page.selectOption("#lang", "de");
  await expect(page.locator("[data-tab=analyzer]")).toHaveText("Runden-Analyse");
  await page.selectOption("#lang", "fr");
  await expect(page.locator("[data-tab=analyzer]")).toHaveText("Analyseur de tours");
});

test("keyboard: arrow keys move between tabs", async ({ page }) => {
  await page.goto("/forge.html?lang=en");
  await page.focus("[data-tab=overview]");
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("[data-panel=analyzer]")).toBeVisible();
});

for (const tab of TABS) {
  test(`axe: ${tab} has no violations`, async ({ page }) => {
    await page.goto(`/forge.html?lang=en#${tab}`);
    if (tab === "bench") { await page.click("#be-run"); await expect(page.locator("#be-selected")).toBeVisible({ timeout: 30_000 }); }
    const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(res.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
  });
}

for (const [w, h] of [[360, 800], [768, 1024], [1280, 800], [1920, 1080]]) {
  test(`no horizontal page scroll at ${w}px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    for (const tab of TABS) {
      await page.goto(`/forge.html?lang=en#${tab}`);
      const over = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
      expect(over, `${tab} @${w}`).toBe(false);
    }
  });
}

// ---------------------------------------------------------------- break attempts

test("break: a huge input is refused quickly and the page stays responsive", async ({ page }) => {
  await page.goto("/forge.html?lang=en#analyzer");
  await page.fill("#an-input", "A".repeat(1_000_000));
  const t0 = Date.now();
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-error")).toBeVisible({ timeout: 5000 });
  expect(Date.now() - t0).toBeLessThan(4000);
  await expect(page.locator("#an-error")).toContainText("too large");
  await page.fill("#an-input", "abc");
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-summary")).toContainText("ba7816bf");
});

test("break: hostile text is never interpreted as HTML and unicode hashes correctly", async ({ page }) => {
  await page.goto("/forge.html?lang=en#analyzer");
  const evil = `<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>`;
  await page.fill("#an-input", evil);
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-summary")).toContainText("Web Crypto agrees");
  await page.fill("#an-input", "😀 Größe 日本語 \u0000 ‮");
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-summary")).toContainText("Web Crypto agrees");
  expect(await page.evaluate(() => (window as unknown as { __pwned?: number }).__pwned)).toBeUndefined();
});

test("break: odd, empty and whitespace hex input", async ({ page }) => {
  await page.goto("/forge.html?lang=en#analyzer");
  await page.selectOption("#an-mode", "hex");
  for (const bad of ["abc", "0x61", "6 1 6", "61\n62", "gg", ""]) {
    await page.fill("#an-input", bad);
    await page.click("#an-form button[type=submit]");
    if (bad === "6 1 6" || bad === "61\n62" || bad === "") {
      // whitespace is stripped; empty is the valid empty message; odd length after stripping is invalid
      if (bad === "6 1 6") await expect(page.locator("#an-error")).toBeVisible();
      else await expect(page.locator("#an-error")).toBeHidden();
    } else {
      await expect(page.locator("#an-error")).toBeVisible();
    }
  }
});

test("break: header mode rejects 79 and 81 bytes and reduced rounds", async ({ page }) => {
  await page.goto("/forge.html?lang=en#analyzer");
  await page.selectOption("#an-mode", "header");
  for (const n of [79, 81, 0]) {
    await page.fill("#an-input", "00".repeat(n));
    await page.click("#an-form button[type=submit]");
    await expect(page.locator("#an-error")).toBeVisible();
  }
  await page.fill("#an-input", "00".repeat(80));
  await page.fill("#an-rounds", "20");
  await page.click("#an-form button[type=submit]");
  await expect(page.locator("#an-error")).toBeVisible();
});

test("break: 30 rapid submissions leave a consistent result and no console error", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto("/forge.html?lang=en#analyzer");
  await page.evaluate(() => { for (let i = 0; i < 30; i++) (document.getElementById("an-form") as HTMLFormElement).requestSubmit(); });
  await expect(page.locator("#an-summary")).toContainText("ba7816bf");
  await expect(page.locator("#an-table tbody tr")).toHaveCount(64);
  expect(errors).toEqual([]);
});

test("break: blocked localStorage does not break the page", async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(window, "localStorage", { get() { throw new Error("blocked"); } }); });
  await page.goto("/forge.html?lang=en");
  await page.selectOption("#lang", "de");
  await expect(page.locator("[data-tab=analyzer]")).toHaveText("Runden-Analyse");
});

test("break: WebGPU device loss mid-session leaves the CPU path working", async ({ page }) => {
  await page.addInitScript(() => {
    const real = navigator.gpu;
    if (!real) return;
    const orig = real.requestAdapter.bind(real);
    real.requestAdapter = async (...a) => {
      const ad = await orig(...a);
      if (!ad) return ad;
      const rd = ad.requestDevice.bind(ad);
      ad.requestDevice = async (...b) => { const d = await rd(...b); setTimeout(() => d.destroy(), 0); return d; };
      return ad;
    };
  });
  await page.goto("/forge.html?lang=en#bench");
  await page.click("#be-run");
  await expect(page.locator("#be-selected")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator("#be-decisions tbody tr", { hasText: "BROWSER_CPU" })).toContainText("available");
  await expect(page.locator("#be-results tbody tr").first()).toContainText("BROWSER_CPU");
});

test("break: the bridge URL field refuses every non-loopback address form", async ({ page }) => {
  await page.goto("/forge.html?lang=en#miner");
  for (const u of ["http://192.168.1.5", "http://127.0.0.1.evil.com", "http://user:pw@127.0.0.1:8765", "https://127.0.0.1:8765", "http://[::1]x", "file:///etc/passwd", "javascript:alert(1)", "//127.0.0.1", ""]) {
    await page.fill("#mi-url", u);
    await page.click("#mi-connect");
    await expect(page.locator("#mi-msg")).toContainText("127.0.0.1 or localhost");
  }
});

test("miner lab: the measured baseline is shown, labelled MEASURED and kept apart from the demo", async ({ page }) => {
  await page.goto("/forge.html?lang=en#miner");
  await expect(page.locator("#mi-meas-badge")).toContainText("MEASURED");
  await expect(page.locator("#mi-meas-kv")).toContainText("v4.0.2-rc1-timsminer");
  await expect(page.locator("#mi-meas-kv")).toContainText("OK");
  expect(await page.locator("#mi-meas-table tbody tr").count()).toBeGreaterThan(10);
  await expect(page.locator("#mi-src")).toContainText("DEMO / SIMULATED");
  const text = (await page.locator("main").innerText()).replaceAll("127.0.0.1", ""); // loopback appears in help text only
  expect(text).not.toMatch(/\b\d{1,3}(\.\d{1,3}){3}\b/); // no other IPv4 address on the page
  expect(text).not.toMatch(/([0-9a-f]{2}:){5}[0-9a-f]{2}/i);
});

test("evidence export contains the measured bundle", async ({ page }) => {
  await page.goto("/forge.html?lang=en#miner");
  await expect(page.locator("#mi-meas-badge")).toContainText("MEASURED");
  await page.click("[data-tab=evidence]");
  await expect(page.locator("#ev-pre")).toContainText("hcs.sha.forge.baseline.v1");
});
