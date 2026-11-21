// W4-15: phone-sized, touch-enabled runs (projects mobile-360 and mobile-390 in the Playwright
// config). Desktop behaviour is covered by app.spec.ts; this file checks what only a phone
// breaks: horizontal overflow, touch input into the composer, target size, and axe at 360 px.
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ROUTES = ["", "guide", "lab", "code", "sat", "compare", "device"];

async function ready(page: Page) {
  await expect(page.locator("#limit-chip")).toHaveClass(/ok/, { timeout: 45_000 });
}

test.beforeEach(async ({ page }) => {
  page.on("pageerror", (err) => { throw err; });
});

test("the project really is a touch phone viewport", async ({ page, viewport, isMobile, hasTouch }) => {
  expect(viewport!.width).toBeLessThanOrEqual(390);
  expect(isMobile).toBe(true);
  expect(hasTouch).toBe(true);
  await page.goto("/?lang=en");
  expect(await page.evaluate(() => window.innerWidth)).toBeLessThanOrEqual(390);
});

test("no route scrolls horizontally and the console stays clean", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto("/?lang=en");
  await ready(page);
  for (const r of ROUTES) {
    await page.goto(`/?lang=en#/${r}`);
    await page.waitForTimeout(200);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `#/${r}`).toBeLessThanOrEqual(0);
  }
  expect(errors).toEqual([]);
});

test("touch targets in the lab are at least 24 x 24 CSS px (WCAG 2.2 AA 2.5.8)", async ({ page }) => {
  await page.goto("/?lang=en#/lab");
  await ready(page);
  const small = await page.evaluate(() => {
    const out: string[] = [];
    const sel = "main button, main select, main input:not([type=hidden]), main summary";
    for (const el of document.querySelectorAll<HTMLElement>(sel)) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue; // hidden
      if (r.width < 24 || r.height < 24) out.push(`${el.tagName.toLowerCase()}#${el.id || el.textContent?.trim().slice(0, 12)} ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
    return out;
  });
  expect(small).toEqual([]);
});

test("tap a Bell run: WASM result, only 00 and 11", async ({ page }) => {
  await page.goto("/?lang=en#/lab");
  await ready(page);
  await page.locator("#run").tap();
  await expect(page.locator("#stats .chip").first()).toContainText("WASM f64");
  await expect(page.locator("#res-table tbody tr td:first-child")).toHaveCount(2);
});

test("composer by touch: tap places a gate, a long press removes it", async ({ page }) => {
  await page.goto("/?lang=en#/lab");
  await ready(page);
  await page.locator("#clear").tap();
  await page.locator('#palette button[data-tool="h"]').tap();
  await page.locator("#composer .cell").first().tap();
  const placed = page.locator("#composer g.placed");
  await expect(placed).toHaveCount(1);

  // Long press (touch has no right click). Chromium DevTools input gives a real touch stream.
  await placed.first().scrollIntoViewIfNeeded();
  const box = (await placed.first().boundingBox())!;
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
  await page.waitForTimeout(800);
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await expect(placed).toHaveCount(0);
});

test("composer by touch: a short tap on a placed gate keeps it", async ({ page }) => {
  await page.goto("/?lang=en#/lab");
  await ready(page);
  await page.locator("#clear").tap();
  await page.locator('#palette button[data-tool="x"]').tap();
  await page.locator("#composer .cell").first().tap();
  await expect(page.locator("#composer g.placed")).toHaveCount(1);
  await page.locator("#composer g.placed").first().tap();
  await expect(page.locator("#composer g.placed")).toHaveCount(1);
});

test("accessibility at phone width: no critical or serious axe violations", async ({ page }) => {
  await page.goto("/?lang=en");
  await ready(page);
  for (const r of ["", "lab", "sat", "guide", "device"]) {
    await page.goto(`/?lang=en#/${r}`);
    await page.waitForTimeout(250);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    const blocking = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
    expect(blocking.map((v) => `${r}: ${v.id} (${v.nodes.length})`)).toEqual([]);
  }
});
