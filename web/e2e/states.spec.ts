// W13: every user-visible run state has a test: empty, busy, failed, cancelled, unsupported,
// timeout, worker failure. Plus run-card export and import (round trip and refusals).
import { test, expect, type Page } from "@playwright/test";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const b64 = (s: string) => Buffer.from(s).toString("base64url");
const BELL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\nmeasure q -> c;\n';

async function ready(page: Page) {
  await expect(page.locator("#limit-chip")).toHaveClass(/ok/, { timeout: 45_000 });
}

async function typeQasm(page: Page, text: string) {
  await page.locator(".cm-content").click();
  await page.keyboard.press("Control+A");
  await page.keyboard.type(text);
}

function longRunQasm(): string {
  const lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', "qreg q[24];", "creg c[24];"];
  for (let i = 0; i < 24; i++) lines.push(`h q[${i}];`);
  for (let r = 0; r < 9; r++) for (let i = 0; i < 23; i++) lines.push(`cx q[${i}],q[${i + 1}];`);
  return lines.join("\n");
}

test.describe("states", () => {
  test("empty: no run yet shows guidance, no details, no stale numbers", async ({ page }) => {
    await page.goto("/?lang=en#/lab");
    await ready(page);
    await expect(page.locator("#res-hist")).toContainText("No run yet");
    await expect(page.locator("#res-details")).toBeHidden();
    await expect(page.locator("#stats .chip")).toHaveCount(0);
    await expect(page.locator("#import-status")).toBeHidden();
  });

  test("empty input: an empty QASM text is refused with a message, nothing runs", async ({ page }) => {
    await page.goto("/?lang=en#/code");
    await ready(page);
    await typeQasm(page, "// nothing here");
    await page.click("#run");
    await expect(page.locator("#code-error")).toBeVisible();
    await expect(page.locator("#code-error")).toContainText("no qreg");
    await expect(page.locator("#stats .chip")).toHaveCount(0);
  });

  test("failed: an unknown gate is reported as an error and no result appears", async ({ page }) => {
    await page.goto("/?lang=en#/code");
    await ready(page);
    await typeQasm(page, 'OPENQASM 2.0; include "qelib1.inc"; qreg q[1]; frobnicate q[0];');
    await page.click("#run");
    await expect(page.locator("#code-error")).toContainText("unsupported gate");
    await expect(page.locator("#res-details")).toBeHidden();
    await expect(page.locator("#run")).toBeEnabled();
  });

  test("unsupported: classical control (if) is refused, never silently dropped", async ({ page }) => {
    await page.goto("/?lang=en#/code");
    await ready(page);
    await typeQasm(page, 'OPENQASM 2.0; include "qelib1.inc"; qreg q[1]; creg c[1]; if(c==1) x q[0];');
    await page.click("#run");
    await expect(page.locator("#code-error")).toBeVisible();
    await expect(page.locator("#stats .chip")).toHaveCount(0);
  });

  test("busy: while a long run is active the run button is off, Stop and progress are shown", async ({ page }) => {
    await page.goto(`/?lang=en#/lab?qasm=${b64(longRunQasm())}`);
    await ready(page);
    await page.click("#run");
    await expect(page.locator("#stop")).toBeVisible();
    await expect(page.locator("#progress")).toBeVisible();
    await expect(page.locator("#run")).toBeDisabled();
    await page.click("#stop");
    await expect(page.locator("#stats .chip")).toContainText("cancelled");
    await expect(page.locator("#run")).toBeEnabled();
    await expect(page.locator("#progress")).toBeHidden();
  });

  test("timeout: a SAT budget that is too small gives UNKNOWN and no certificate or count", async ({ page }) => {
    await page.goto("/?lang=en#/sat");
    await ready(page);
    // Pigeonhole 10 pigeons into 9 holes: far beyond a 100 ms DPLL budget.
    const holes = 9, pigeons = 10;
    const v = (p: number, h: number) => p * holes + h + 1;
    const clauses: string[] = [];
    for (let p = 0; p < pigeons; p++) clauses.push(Array.from({ length: holes }, (_, h) => v(p, h)).join(" ") + " 0");
    for (let h = 0; h < holes; h++) for (let a = 0; a < pigeons; a++) for (let b = a + 1; b < pigeons; b++) clauses.push(`-${v(a, h)} -${v(b, h)} 0`);
    await page.fill("#sat-input", `p cnf ${pigeons * holes} ${clauses.length}\n${clauses.join("\n")}\n`);
    await page.fill("#sat-timeout", "100");
    await page.click("#sat-solve");
    await expect(page.locator("#sat-result .status")).toHaveText("UNKNOWN", { timeout: 30_000 });
    await expect(page.locator("#sat-result .cert")).toContainText("Not decided");
    await page.click("#sat-count");
    await expect(page.locator("#sat-result")).toContainText("no count is claimed", { timeout: 30_000 });
    await expect(page.locator(".count-value")).toHaveCount(0);
  });

  test("worker failure at boot: a worker script that cannot load is reported, not an endless spinner", async ({ page }) => {
    await page.route(/\/assets\/engine\.worker-[^/]*\.js/, (route) => route.abort());
    await page.goto("/?lang=en#/lab");
    await expect(page.locator("#hero-limit")).toContainText(/WebAssembly could not be loaded|Start failed/, { timeout: 30_000 });
    await expect(page.locator("#limit-chip")).not.toHaveClass(/ok/);
  });

  test("worker failure during a run: the run settles with an error, the worker restarts, the next run works", async ({ page }) => {
    // A crashing worker delivers an `error` event to the page. Simulated by dispatching that same
    // ErrorEvent for the first run request; the page-side recovery is what is under test.
    await page.addInitScript(() => {
      const Original = window.Worker;
      (window as any).__crashNext = true;
      window.Worker = class extends Original {
        postMessage(message: any, ...rest: any[]) {
          if (message && message.type === "run" && (window as any).__crashNext) {
            (window as any).__crashNext = false;
            setTimeout(() => this.dispatchEvent(new ErrorEvent("error", { message: "simulated worker crash" })), 30);
            return;
          }
          (super.postMessage as any)(message, ...rest);
        }
      } as typeof Worker;
    });
    await page.goto("/?lang=en#/code");
    await ready(page);
    await page.click("#run");
    await expect(page.locator("#code-error")).toContainText("engine worker stopped unexpectedly");
    await expect(page.locator("#run")).toBeEnabled();
    await expect(page.locator("#progress")).toBeHidden();
    await expect(page.locator("#limit-chip")).toHaveClass(/ok/, { timeout: 45_000 });
    await page.click("#run");
    await expect(page.locator("#stats .chip").first()).toContainText("WASM f64", { timeout: 30_000 });
  });
});

test.describe("run card export and import", () => {
  async function exportCard(page: Page): Promise<string> {
    await page.locator("#res-details summary").click();
    const download = page.waitForEvent("download");
    await page.click("#res-export");
    return readFileSync((await (await download).path())!, "utf8");
  }

  async function importText(page: Page, name: string, text: string) {
    mkdirSync("e2e-results/imports", { recursive: true });
    // One file per parallel worker: tests that share a path race when run with --repeat-each / workers.
    const path = `e2e-results/imports/w${test.info().parallelIndex}-${name}`;
    writeFileSync(path, text);
    await page.setInputFiles("#res-import-file", path);
  }

  test("round trip: export a Bell run, import it, the circuit, shots and digest come back", async ({ page }) => {
    await page.goto(`/?lang=en#/code?qasm=${b64(BELL)}`);
    await ready(page);
    await page.fill("#shots", "333");
    await page.click("#run");
    await expect(page.locator("#stats .chip").first()).toContainText("WASM f64");
    const raw = await exportCard(page);
    const card = JSON.parse(raw);

    await page.goto("/?lang=en#/lab");
    await page.reload();
    await ready(page);
    await expect(page.locator("#shots")).toHaveValue("1024");
    await importText(page, "good.json", raw);
    await expect(page.locator("#import-status")).toContainText("Imported");
    await expect(page.locator("#import-status")).toContainText(card.input.digest.slice(0, 12));
    await expect(page.locator("#import-status")).toContainText(`seed ${card.seed}`);
    await expect(page.locator("#shots")).toHaveValue("333");
    // The stored counts are not shown as a result of this page: still no run here.
    await expect(page.locator("#stats .chip")).toHaveCount(0);
    await page.click("#run");
    await expect(page.locator("#stats .chip").first()).toContainText("WASM f64");
    await expect(page.locator("#res-table tbody tr td:first-child")).toHaveCount(2);
  });

  const refusals: [string, (c: any) => string, string][] = [
    ["tampered circuit text", (c) => { c.input.payload += "// x\n"; return JSON.stringify(c); }, "digest does not match"],
    ["wrong schema", (c) => { c.schema = "hcs.run.v1"; return JSON.stringify(c); }, "not an hcs.run.v2 card"],
    ["not JSON", () => "{not json", "not a JSON object"],
    ["bad shots", (c) => { c.input.shots = 0; return JSON.stringify(c); }, "shot count"],
  ];
  for (const [name, mutate, message] of refusals) {
    test(`import refused: ${name}`, async ({ page }) => {
      await page.goto(`/?lang=en#/code?qasm=${b64(BELL)}`);
      await ready(page);
      await page.click("#run");
      await expect(page.locator("#stats .chip").first()).toContainText("WASM f64");
      const card = JSON.parse(await exportCard(page));
      await page.fill("#shots", "77");
      await importText(page, "bad.json", mutate(card));
      await expect(page.locator("#import-status")).toContainText("Import refused");
      await expect(page.locator("#import-status")).toContainText(message);
      await expect(page.locator("#import-status")).toHaveClass(/bad/);
      await expect(page.locator("#shots")).toHaveValue("77"); // nothing was applied
    });
  }

  test("import messages are localized (de)", async ({ page }) => {
    await page.goto("/?lang=de#/lab");
    await ready(page);
    await importText(page, "bad.json", "{nope");
    await expect(page.locator("#import-status")).toContainText("Import abgelehnt");
    await expect(page.locator("#import-status")).toContainText("kein JSON-Objekt");
  });
});
