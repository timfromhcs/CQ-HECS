// T6-02: Quantum Gravity Lab (#/qg). Keyboard, axe, 360 px, reduced motion, i18n, no network,
// honest empty/unavailable states.
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";

const TABS = ["overview", "theories", "model", "circuit", "design", "backends", "analysis", "evidence"];
const oracle = JSON.parse(readFileSync(new URL("../tests/fixtures/qg_oracle.json", import.meta.url), "utf8")).points as { theta: number; qasm_sha256: string; qasm: string }[];

test.beforeEach(async ({ page }) => {
  page.on("pageerror", (err) => { throw err; });
});

async function open(page: Page, lang = "en") {
  await page.goto(`/?lang=${lang}#/qg`);
  await expect(page.locator("#qg-panel")).toBeVisible();
}
const tab = (page: Page, name: string) => page.locator(`#qg-tab-${name}`);

test("every workspace renders, the console is clean and nothing leaves the origin", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const external: string[] = [];
  const base = new URL(process.env.E2E_BASE_URL ?? "http://127.0.0.1:4173").origin;
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.protocol.startsWith("http") && u.origin !== base && !/fonts\.(googleapis|gstatic)\.com$/.test(u.hostname)) external.push(r.url());
  });
  await open(page);
  await expect(page.locator("#qg-root h1")).toContainText("Quantum Gravity Lab");
  for (const name of TABS) {
    await tab(page, name).click();
    await expect(tab(page, name)).toHaveAttribute("aria-selected", "true");
    await expect(page.locator("#qg-panel h2")).toBeVisible();
  }
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("tabs follow the keyboard pattern (arrows, Home, End) and the panel is labelled by its tab", async ({ page }) => {
  await open(page);
  await tab(page, "overview").focus();
  await page.keyboard.press("ArrowRight");
  await expect(tab(page, "theories")).toBeFocused();
  await expect(tab(page, "theories")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#qg-panel")).toHaveAttribute("aria-labelledby", "qg-tab-theories");
  await page.keyboard.press("End");
  await expect(tab(page, "evidence")).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(tab(page, "overview")).toBeFocused();
  await page.keyboard.press("ArrowLeft");
  await expect(tab(page, "evidence")).toBeFocused();
  await page.keyboard.press("Home");
  await expect(tab(page, "overview")).toBeFocused();
});

test("theory catalog shows assumptions and limits before anything runs", async ({ page }) => {
  await open(page);
  await tab(page, "theories").click();
  const card = page.locator("article", { hasText: "Two-probe gravity-mediated effective interaction" });
  await expect(card).toContainText("theta is a model parameter");
  await expect(card).toContainText("What it cannot establish");
  await expect(card).toContainText("that any gravitational field is quantum");
  await expect(page.locator("article", { hasText: "Small-N sparse q=4" })).toContainText("No browser model");
});

test("model builder: assumptions are visible, run needs confirmation, results carry units and the surface", async ({ page }) => {
  await open(page);
  await tab(page, "model").click();
  await expect(page.locator("#qg-panel")).toContainText("Interaction is U_ZZ(theta)");
  await expect(page.locator("#qg-run")).toBeDisabled();
  await page.fill("#qg-theta", "pi/2");
  await page.check("#qg-ack");
  await expect(page.locator("#qg-run")).toBeEnabled();
  await page.click("#qg-run");
  const res = page.locator("#qg-mb-result");
  await expect(res).toContainText("Simulator");
  await expect(res).toContainText("f64");
  await expect(res).toContainText("not QPU");
  await expect(res.locator("tr", { hasText: "Concurrence" })).toContainText("1.000000");
  await expect(res.locator("tr", { hasText: "CHSH maximum" })).toContainText("2.828427");
  await expect(res.locator("tr", { hasText: "Entanglement entropy" })).toContainText("bits");
  await expect(res).toContainText("0.250000");
});

test("model builder: an invalid number is refused with a message, nothing is computed", async ({ page }) => {
  await open(page);
  await tab(page, "model").click();
  await page.fill("#qg-theta", "banana");
  await page.check("#qg-ack");
  await page.click("#qg-run");
  await expect(page.locator("#qg-mb-err")).toContainText("Invalid value for theta");
  await expect(page.locator("#qg-mb-result")).toContainText("No run yet");
  await page.fill("#qg-theta", "101");
  await page.click("#qg-run");
  await expect(page.locator("#qg-mb-err")).toContainText("between -100 and 100");
});

test("circuit preview shows exact QASM and the SHA-256 the Python reference computes", async ({ page }) => {
  await open(page);
  await tab(page, "model").click();
  await page.fill("#qg-theta", "pi/2");
  await tab(page, "circuit").click();
  const o = oracle.find((x) => Math.abs(x.theta - Math.PI / 2) < 1e-12)!;
  await expect(page.locator("#qg-qasm")).toHaveText(o.qasm.trimEnd());
  await expect(page.locator("#qg-digest")).toHaveText(o.qasm_sha256);
  await expect(page.locator("#qg-panel")).toContainText("NOT performed");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#qg-dl-qasm")]);
  expect(dl.suggestedFilename()).toBe("qg-bmv.qasm");
});

test("experiment designer: validation, plan with no credit estimate, typed refusal, no request sent", async ({ page }) => {
  const posts: string[] = [];
  page.on("request", (r) => { if (r.method() !== "GET") posts.push(`${r.method()} ${r.url()}`); });
  await open(page);
  await tab(page, "design").click();
  await expect(page.locator("#qg-panel")).toContainText("UNAVAILABLE");
  await expect(page.locator("#qg-panel")).toContainText("Run Monitor");
  await page.fill("#qg-shots", "0");
  await page.click("#qg-form button[type=submit]");
  await expect(page.locator("#qg-design-err")).toContainText("shots (1 to 100000)");
  await page.fill("#qg-shots", "2000");
  await page.click("#qg-form button[type=submit]");
  await expect(page.locator("#qg-plan pre")).toContainText('"credit_estimate": null');
  await expect(page.locator("#qg-plan pre")).toContainText('"shots": 2000');
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#qg-dl-plan")]);
  expect(dl.suggestedFilename()).toBe("qg-experiment-design.json");
  await page.click("#qg-try");
  await expect(page.locator("#qg-refusal")).toContainText("WEB_NO_PROVIDER_SUBMISSION");
  await expect(page.locator("#qg-refusal")).toContainText('"spend_credits": 0');
  expect(posts).toEqual([]);
});

test("backend lab: explicit type chips, text status, time-stamped probe, nothing invented", async ({ page }) => {
  await open(page);
  await tab(page, "backends").click();
  const table = page.locator("#qg-panel table");
  for (const chip of ["QPU", "Simulator", "CPU", "Vulkan", "WASM", "WebGPU", "f32", "f64"]) {
    await expect(table.locator(".qg-chip", { hasText: new RegExp(`^${chip}$`) }).first()).toBeVisible();
  }
  await expect(table.locator("tr", { hasText: "Open Quantum QPU" })).toContainText("NOT QUERIED");
  await expect(table.locator("tr", { hasText: "Browser WASM" })).toContainText(/AVAILABLE · checked \d{4}-\d\d-\d\dT/);
  await expect(table.locator("tr", { hasText: "Browser WebGPU" })).toContainText(/(AVAILABLE|UNAVAILABLE) · checked/);
  await expect(page.locator("#qg-panel")).not.toContainText(/queue\W+\d|score\W+\d/i);
});

test("analysis: chart has title, axes with units, legend, error scope and a full text table", async ({ page }) => {
  await open(page);
  await tab(page, "analysis").click();
  const svg = page.locator("#qg-panel svg[role=img]").first();
  await expect(svg).toHaveAttribute("aria-labelledby", "qg-ch-t qg-ch-d");
  await expect(svg).toContainText("theta (rad)");
  await expect(svg).toContainText("dimensionless");
  await expect(page.locator(".qg-leg")).toContainText("QPU measured: Y⊗Z");
  await expect(page.locator("#qg-panel")).toContainText("one standard error");
  await expect(page.locator("#qg-panel")).toContainText("rigetti:cepheus-1-108q");
  await expect(page.locator("details table tbody tr")).toHaveCount(13);
  await expect(page.locator("#qg-panel")).toContainText("INCONCLUSIVE");
  await expect(page.locator("#qg-panel")).toContainText("Not available");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#qg-csv")]);
  expect(dl.suggestedFilename()).toBe("qg-bmv-scan.csv");
});

test("evidence ledger lists real hashes, excludes raw data and explains what is missing", async ({ page }) => {
  await open(page);
  await tab(page, "evidence").click();
  const rows = page.locator("#qg-panel tbody tr");
  expect(await rows.count()).toBeGreaterThanOrEqual(8);
  const text = await page.locator("#qg-panel").innerText();
  expect(text).toMatch(/[0-9a-f]{64}/);
  expect(text).not.toMatch(/JOB_LEDGER|\/raw\//);
  expect(text).toContain("Not shown or bundled: raw job files");
});

test("German and French labels are used", async ({ page }) => {
  await open(page, "de");
  await expect(tab(page, "overview")).toHaveText("Übersicht");
  await expect(page.locator("#qg-root h1")).toContainText("Quantengravitations-Labor");
  await open(page, "fr");
  await expect(tab(page, "evidence")).toHaveText("Registre des preuves");
});

test("axe: no critical or serious violations in any workspace, dark and light", async ({ page }) => {
  await open(page);
  for (const theme of ["dark", "light"]) {
    await page.evaluate((t) => { document.documentElement.dataset.theme = t; }, theme);
    for (const name of TABS) {
      await tab(page, name).click();
      if (name === "model") { await page.check("#qg-ack"); await page.click("#qg-run"); }
      if (name === "backends") await expect(page.locator("#qg-panel table")).toContainText(/checked/);
      const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
      const bad = r.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
      expect(bad.map((v) => `${theme}/${name}: ${v.id} ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
    }
  }
});

test.describe("phone width 360 px", () => {
  test.use({ viewport: { width: 360, height: 740 } });
  test("no workspace scrolls the page horizontally and controls are at least 24 px", async ({ page }) => {
    await open(page);
    for (const name of TABS) {
      await tab(page, name).click();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, name).toBeLessThanOrEqual(0);
    }
    for (const name of ["model", "design", "analysis"]) {
      await tab(page, name).click();
      const small = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>("#qg-panel button, #qg-panel input:not([type=checkbox]), #qg-panel select")]
        .filter((e) => e.offsetParent).map((e) => e.getBoundingClientRect()).filter((r) => r.height < 24 || r.width < 24).length);
      expect(small, name).toBe(0);
    }
  });
});

test("reduced motion: the lab states the preference and animates nothing", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page);
  const css = await page.evaluate(() => document.getElementById("qg-style")?.textContent ?? "");
  expect(css).toContain("prefers-reduced-motion:reduce");
  const animated = await page.evaluate(() => [...document.querySelectorAll<HTMLElement>(".qg *")].filter((e) => getComputedStyle(e).animationName !== "none").length);
  expect(animated).toBe(0);
});
