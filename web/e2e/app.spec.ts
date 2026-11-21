import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync } from "node:fs";

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
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^cqhecs-run-\d+\.json$/);

  // The exported card must be reproducible, not decorative: it is the shared `hcs.run.v2`
  // contract, the digest has to be the SHA-256 of the payload it carries, the seed has to
  // be there, and no device or bridge detail may leak into a file the user shares.
  const raw = readFileSync((await file.path())!, "utf8");
  const card = JSON.parse(raw);
  expect(card.schema).toBe("hcs.run.v2");
  expect(card.input.digest).toBe(createHash("sha256").update(card.input.payload, "utf8").digest("hex"));
  expect(card.engine).toEqual({ kind: "wasm", precision: "f64", mode: "SAMPLED" });
  expect(Number.isInteger(card.seed)).toBe(true);
  expect(card.result.counts).toBeTruthy();
  expect(card.limits.length).toBeGreaterThan(0);
  expect(raw).not.toMatch(/bssid|\bwallet\b|\btoken\b|bridge_url|192\.168\./i);
});

test("the editor bundle is lazy: it loads only when the code lab opens", async ({ page }) => {
  const requested: string[] = [];
  page.on("request", (request) => requested.push(request.url()));
  const editorLoaded = () => requested.some((url) => /\/assets\/editor-[^/]+\.js/.test(url));

  await page.goto("/?lang=en#/");
  await ready(page);
  await page.goto("/?lang=en#/lab");
  await ready(page);
  expect(editorLoaded(), "the editor chunk must not be part of the first visit").toBe(false);

  await page.goto("/?lang=en#/code");
  await expect(page.locator("#editor .cm-editor")).toBeVisible({ timeout: 30_000 });
  expect(editorLoaded(), "opening the code lab must load the editor chunk").toBe(true);
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
  await expect(page.locator("#sat-result .digest")).toContainText("SHA-256 input");
  await expect(page.locator("#sat-result .digest")).toContainText("canonical");
  const downloadPromise = page.waitForEvent("download");
  await page.click("#sat-export");
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("cqhecs-sat-result.json");
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

// ---------------------------------------------------------------- W4-12 keyboard composer

test("composer by keyboard: arrows move, Enter places, Delete removes, and it is announced", async ({ page }) => {
  await page.goto("/?lang=en#/lab");
  await ready(page);
  await page.click("#clear");
  await page.click('#palette button[data-tool="h"]');
  await page.locator("#composer").focus();
  await expect(page.locator("#composer .kcursor")).toHaveCount(1);
  await page.keyboard.press("Enter");
  await expect(page.locator("#composer g.placed")).toHaveCount(1);
  await expect(page.locator("#composer + [role=status]")).toContainText("placed on q0, column 1");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Space");
  await expect(page.locator("#composer g.placed")).toHaveCount(2);
  // Occupied cell is refused, not overwritten.
  await page.keyboard.press("Space");
  await expect(page.locator("#composer g.placed")).toHaveCount(2);
  await expect(page.locator("#composer + [role=status]")).toContainText("occupied");
  await page.keyboard.press("Delete");
  await expect(page.locator("#composer g.placed")).toHaveCount(1);
  await expect(page.locator("#composer + [role=status]")).toContainText("removed");
});

test("composer by keyboard: a two-qubit gate takes control then target", async ({ page }) => {
  await page.goto("/?lang=en#/lab");
  await ready(page);
  await page.click("#clear");
  await page.click('#palette button[data-tool="cx"]');
  await page.locator("#composer").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#composer + [role=status]")).toContainText("choose the next qubit");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await expect(page.locator("#composer g.placed")).toHaveCount(1);
  // The cursor stays inside the grid: far more key presses than cells.
  for (let i = 0; i < 12; i++) await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Home");
  await expect(page.locator("#composer .kcursor")).toHaveCount(1);
});

test("the composer keeps keyboard focus reachable: Tab leaves it", async ({ page }) => {
  await page.goto("/?lang=en#/lab");
  await ready(page);
  await page.locator("#composer").focus();
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.activeElement?.id)).not.toBe("composer");
});

// ---------------------------------------------------------------- W4-14 output-sink XSS

test("break: hostile text in every user-fed output sink is shown as text, never executed", async ({ page }) => {
  const evil = `<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>`;
  const dialogs: string[] = [];
  page.on("dialog", (d) => { dialogs.push(d.message()); void d.dismiss(); });
  await page.goto(`/?lang=${encodeURIComponent(evil)}#/sat`);
  await ready(page);
  const scriptsBefore = await page.evaluate(() => document.scripts.length);

  // SAT sink: parse error text and result panel.
  await page.fill("#sat-input", `p cnf 2 1\n${evil}\n`);
  await page.click("#sat-solve");
  await expect(page.locator("#sat-result")).toContainText("<img");
  await page.click("#sat-count");
  await expect(page.locator("#sat-result")).toContainText("<img");

  // Code-lab sink: QASM error shown in #code-error.
  await page.goto("/?lang=en#/code");
  await expect(page.locator("#editor .cm-editor")).toBeVisible({ timeout: 30_000 });
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type(`OPENQASM 2.0; qreg q[1]; ${evil};`);
  await page.click("#run");
  await expect(page.locator("#code-error")).toContainText("<img");

  // Share-link sink: a hostile payload in the hash must not be interpreted either.
  const b64 = Buffer.from(`OPENQASM 2.0; qreg q[2]; ${evil};`).toString("base64url");
  await page.goto(`/?lang=en#/code?qasm=${b64}`);
  await page.goto(`/?lang=en#/<img src=x onerror=window.__pwned=1>`);
  await ready(page);

  const state = await page.evaluate(() => ({
    pwned: (window as unknown as { __pwned?: number }).__pwned,
    handlers: document.querySelectorAll("[onerror], [onload], [onclick]").length,
    injectedImg: document.querySelectorAll('img[src="x"]').length,
    scripts: document.scripts.length,
  }));
  expect(state.pwned).toBeUndefined();
  expect(state.handlers).toBe(0);
  expect(state.injectedImg).toBe(0);
  expect(dialogs).toEqual([]);
  expect(state.scripts).toBeLessThanOrEqual(scriptsBefore + 1); // the SPA's own module script
});

// ---------------------------------------------------------------- T6-06 resource and cancel paths

test("worker cancellation: Stop ends a long run, shows it, and the next run works on a fresh worker", async ({ page }) => {
  // 24 qubits with ~200 entangling gates keeps the WASM core busy for several seconds.
  const lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[24];", "creg c[24];"];
  for (let i = 0; i < 24; i++) lines.push(`h q[${i}];`);
  for (let r = 0; r < 9; r++) for (let i = 0; i < 23; i++) lines.push(`cx q[${i}],q[${i + 1}];`);
  const b64 = Buffer.from(lines.join("\n")).toString("base64url");
  await page.goto(`/?lang=en#/lab?qasm=${b64}`);
  await ready(page);
  await page.click("#run");
  await expect(page.locator("#stop")).toBeVisible();
  await page.click("#stop");
  await expect(page.locator("#stats .chip")).toContainText("cancelled");
  await expect(page.locator("#stop")).toBeHidden();
  await expect(page.locator("#limit-chip")).toHaveClass(/ok/, { timeout: 45_000 });
  // Fresh worker: a Bell preset runs normally afterwards.
  await page.selectOption("#preset", "bell");
  await page.click("#run");
  await expect(page.locator("#stats .chip").first()).toContainText("WASM f64", { timeout: 30_000 });
  await expect(page.locator("#res-table tbody tr td:first-child")).toHaveCount(2);
});

test("low memory: a device that reports 0.25 GiB gets a lower qubit limit and refuses a larger circuit", async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(Navigator.prototype, "deviceMemory", { get: () => 0.25, configurable: true }); });
  await page.goto("/?lang=en#/code");
  await ready(page);
  await expect(page.locator("#limit-chip")).toContainText("22");
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type('OPENQASM 2.0; include "qelib1.inc"; qreg q[24]; h q[0];');
  await expect(page.locator("#estimate")).toContainText("safe limit");
  await expect(page.locator("#run")).toBeDisabled();
});

test("memory API absent: the page still boots with a conservative limit", async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(Navigator.prototype, "deviceMemory", { get: () => undefined, configurable: true }); });
  await page.goto("/?lang=en#/lab");
  await ready(page);
  await page.click("#run");
  await expect(page.locator("#stats .chip").first()).toContainText("WASM f64");
});
