import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";

const ROUTES = ["", "guide", "lab", "code", "sat", "compare", "device"];
const VIEWPORTS = [
  { name: "mobile-360", width: 360, height: 800 },
  { name: "mobile-390", width: 390, height: 844 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "desktop-1280", width: 1280, height: 800 },
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1920", width: 1920, height: 1080 },
];
const SHOTS = "e2e-results/screenshots";

async function ready(page: Page) {
  await expect(page.locator("#limit-chip")).toHaveClass(/ok/, { timeout: 45_000 });
}

test.beforeEach(async ({ page }) => {
  page.on("pageerror", (err) => { throw err; });
});

test("every route renders, deep links survive a reload, and the console stays clean", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto("/?lang=en");
  await ready(page);
  for (const r of ROUTES) {
    await page.goto(`/?lang=en#/${r}`);
    await page.reload();
    await expect(page.locator(`.page:not([hidden])`).first()).toBeVisible();
  }
  expect(errors).toEqual([]);
});

test("language switch EN/DE/FR changes the interface", async ({ page }) => {
  await page.goto("/?lang=en");
  await expect(page.locator(".hero h1")).toContainText("Quantum circuits");
  await page.selectOption("#lang", "de");
  await expect(page.locator(".hero h1")).toContainText("Quantenschaltungen");
  await page.selectOption("#lang", "fr");
  await expect(page.locator(".hero h1")).toContainText("circuits quantiques");
});

test("Bell run: only 00/11, provenance shown, JSON export downloads", async ({ page }) => {
  await page.goto("/?lang=en#/lab");
  await ready(page);
  await page.click("#run");
  await expect(page.locator("#stats .chip").first()).toContainText("WASM f64");
  const rows = page.locator("#res-table tbody tr td:first-child");
  await expect(rows).toHaveCount(2);
  await expect(page.locator("#prov-list li").first()).toContainText("WebAssembly f64");
  await page.locator("#res-details summary").click();
  const download = page.waitForEvent("download");
  await page.click("#res-export");
  expect((await download).suggestedFilename()).toMatch(/^cqhecs-run-\d+\.json$/);
});

test("WebGPU-unavailable fallback: the option is disabled, WASM still runs", async ({ page }) => {
  // navigator.gpu is a getter on Navigator.prototype; hide it for the page.
  await page.addInitScript(() => { Object.defineProperty(Navigator.prototype, "gpu", { get: () => undefined, configurable: true }); });
  await page.goto("/?lang=en#/lab");
  await ready(page);
  // toBeDisabled() does not evaluate a single <option>; read the DOM property.
  expect(await page.locator('#engine option[value="webgpu"]').evaluate((o) => (o as HTMLOptionElement).disabled)).toBe(true);
  await page.click("#run");
  await expect(page.locator("#stats .chip").first()).toContainText("WASM f64");
});

test("safe limits refuse an oversized circuit instead of running it", async ({ page }) => {
  await page.goto("/?lang=en#/code");
  await ready(page);
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type('OPENQASM 2.0; include "qelib1.inc"; qreg q[30]; h q[0];');
  await expect(page.locator("#estimate")).toContainText("safe limit");
  await expect(page.locator("#run")).toBeDisabled();
});

test("SAT lab: UNSAT carries a checked certificate, SAT a verified model, #SAT an exact count", async ({ page }) => {
  await page.goto("/?lang=en#/sat");
  await ready(page);
  await page.click("#sat-php");
  await page.click("#sat-solve");
  await expect(page.locator("#sat-result .status")).toHaveText("UNSAT", { timeout: 30_000 });
  await expect(page.locator("#sat-result .cert")).toContainText("tree-resolution certificate");
  await page.fill("#sat-input", "p cnf 3 1\n1 2 0\n");
  await page.click("#sat-solve");
  await expect(page.locator("#sat-result .status")).toHaveText("SAT");
  await expect(page.locator("#sat-result .cert")).toContainText("checked clause by clause");
  await page.click("#sat-count");
  await expect(page.locator(".count-value")).toContainText("6 satisfying assignments");
});

for (const vp of VIEWPORTS) {
  test(`layout ${vp.name}: no horizontal overflow, screenshots retained`, async ({ page }) => {
    mkdirSync(SHOTS, { recursive: true });
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/?lang=en");
    await ready(page);
    for (const r of ["", "lab", "sat", "guide"]) {
      await page.goto(`/?lang=en#/${r}`);
      await page.waitForTimeout(250);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `${vp.name} #/${r}`).toBeLessThanOrEqual(0);
      await page.screenshot({ path: `${SHOTS}/${vp.name}-${r || "home"}.png`, fullPage: false });
    }
  });
}

test("accessibility: no critical or serious axe violations on the main views", async ({ page }) => {
  await page.goto("/?lang=en");
  await ready(page);
  for (const r of ROUTES) {
    await page.goto(`/?lang=en#/${r}`);
    await page.waitForTimeout(250);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking.map((v) => `${r}: ${v.id} (${v.nodes.length})`)).toEqual([]);
  }
});
