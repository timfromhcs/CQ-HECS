// Real-browser Studio checks (headless Chromium from web/node_modules, never the user's browser).
// Usage: node tests/studio_ui_e2e.mjs <studio-url-with-#token=...>
// Prints one JSON line {"ok": bool, "checks": N, "failures": [...]} and exits 0/1.
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "..", "web", "package.json"));
const { chromium } = require("@playwright/test");
const axeModule = require("@axe-core/playwright");
const AxeBuilder = axeModule.default ?? axeModule.AxeBuilder ?? axeModule;

const url = process.argv[2];
const checks = [];
const failures = [];
const check = (name, cond, detail = "") => {
  checks.push(name);
  if (!cond) failures.push(`${name}${detail ? `: ${detail}` : ""}`);
};

async function axeSerious(page, include, label) {
  const result = await new AxeBuilder({ page }).include(include).analyze();
  const bad = result.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  check(`axe ${label}`, bad.length === 0, bad.map((v) => `${v.id}(${v.nodes.length})`).join(","));
}

async function openCircuit(page) {
  await page.goto(url);
  await page.waitForSelector("#nav button");
  await page.click('#nav button[data-view="circuit"]');
  await page.waitForSelector("#view-circuit.active");
  await page.waitForFunction(() => document.querySelectorAll("#preset option").length > 0);
  await page.selectOption("#preset", "bell");
  await page.waitForFunction(() => document.querySelector("#qasm").value.includes("OPENQASM"));
}

const browser = await chromium.launch();
try {
  for (const [label, width, height] of [["1280", 1280, 900], ["360", 360, 740]]) {
    const page = await (await browser.newContext({ viewport: { width, height } })).newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await openCircuit(page);

    check(`[${label}] empty state`, (await page.textContent("#plan-output")).includes("No plan yet"));
    await axeSerious(page, "#plan-panel", `[${label}] plan panel empty`);

    // Plan via keyboard: focus the button, press Enter.
    await page.focus("#plan-run");
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => document.querySelector("#plan-state").textContent === "plan ready");
    const text = await page.textContent("#plan-output");
    check(`[${label}] selected path A`, /selected path\s*A/.test(text), text.slice(0, 120));
    check(`[${label}] ESTIMATE labels`, (text.match(/ESTIMATE/g) || []).length >= 4);
    check(`[${label}] digests shown`, /[0-9a-f]{64}/.test(text));
    check(`[${label}] rejected candidates listed`, text.includes("lower priority than selected Path A"));
    await axeSerious(page, "#plan-panel", `[${label}] plan panel with plan`);
    await axeSerious(page, "#view-circuit", `[${label}] circuit view`);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    check(`[${label}] no horizontal page overflow`, overflow <= 0, String(overflow));

    // Typed refusal: forced path A on a T gate.
    await page.fill("#qasm", 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\nt q[0];\ncx q[0],q[1];\n');
    await page.selectOption("#path", "A");
    await page.click("#plan-run");
    await page.waitForFunction(() => document.querySelector("#plan-state").textContent === "refused");
    const refusal = await page.textContent("#plan-output");
    check(`[${label}] refusal code shown`, refusal.includes("FORCED_PATH_UNSUPPORTED"));
    check(`[${label}] refusal is an alert`, (await page.locator('#plan-output [role="alert"]').count()) >= 1);
    await axeSerious(page, "#plan-panel", `[${label}] plan panel refusal`);

    // Typed error state: invalid source.
    await page.fill("#qasm", "OPENQASM 2.0; this is not a circuit");
    await page.selectOption("#path", "auto");
    await page.click("#plan-run");
    await page.waitForFunction(() => document.querySelector("#plan-state").textContent === "error");
    check(`[${label}] error state alert`, (await page.locator('#plan-output [role="alert"]').count()) >= 1);

    // Empty source state.
    await page.fill("#qasm", "");
    await page.click("#plan-run");
    await page.waitForFunction(() => document.querySelector("#plan-state").textContent === "empty");
    check(`[${label}] empty source message`, (await page.textContent("#plan-output")).includes("Empty circuit"));

    check(`[${label}] no page errors`, errors.filter((e) => !/status of 4\d\d/.test(e)).length === 0, errors.join(" | ").slice(0, 300));
    await page.close();
  }

  // Keyboard arrow-key tab pattern on the Quantum Gravity Lab tablist (WAI-ARIA tabs).
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await page.goto(url);
  await page.waitForSelector("#nav button");
  await page.click('#nav button[data-view="qg"]');
  await page.waitForSelector("#qgs-tab-overview");
  const tabIds = await page.$$eval('#qg-studio [role="tab"]', (n) => n.map((x) => x.id));
  check("qg tablist has 8 tabs", tabIds.length === 8, String(tabIds.length));
  await page.focus("#qgs-tab-overview");
  const activeId = () => page.evaluate(() => document.activeElement && document.activeElement.id);
  const selected = () => page.$$eval('#qg-studio [role="tab"][aria-selected="true"]', (n) => n.map((x) => x.id));
  await page.keyboard.press("ArrowRight");
  check("ArrowRight moves focus to tab 2", (await activeId()) === tabIds[1], await activeId());
  check("ArrowRight selects tab 2", JSON.stringify(await selected()) === JSON.stringify([tabIds[1]]));
  await page.keyboard.press("End");
  check("End moves to last tab", (await activeId()) === tabIds[7], await activeId());
  await page.keyboard.press("ArrowRight");
  check("ArrowRight wraps to first tab", (await activeId()) === tabIds[0], await activeId());
  await page.keyboard.press("ArrowLeft");
  check("ArrowLeft wraps to last tab", (await activeId()) === tabIds[7], await activeId());
  await page.keyboard.press("Home");
  check("Home moves to first tab", (await activeId()) === tabIds[0], await activeId());
  const tabindexes = await page.$$eval('#qg-studio [role="tab"]', (n) => n.map((x) => x.tabIndex));
  check("roving tabindex (one 0, rest -1)", tabindexes.filter((t) => t === 0).length === 1 && tabindexes.filter((t) => t === -1).length === 7, tabindexes.join(","));
  check("tabpanel labelled by selected tab", (await page.getAttribute("#qgs-panel", "aria-labelledby")) === tabIds[0]);
  await page.close();
} finally {
  await browser.close();
}

console.log(JSON.stringify({ ok: failures.length === 0, checks: checks.length, failures }));
process.exit(failures.length ? 1 : 0);
