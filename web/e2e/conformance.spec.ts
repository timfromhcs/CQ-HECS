// T6-05 / W13: the shared conformance corpus through the REAL page (UI -> worker -> engine).
//
// `tests/fixtures/shared_conformance.json` is the same file the Python test and the Node test
// read. Here every case is typed into the code lab, run on WebAssembly f64 and, when this
// machine exposes a WebGPU adapter, on WebGPU f32; the run card the page exports is compared
// with the corpus. WebGPU deviations are measured and written to
// `e2e-results/webgpu_conformance.json`; without an adapter that column is NOT_RUN, never green.
import { test, expect, type Page } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

interface Case {
  name: string;
  qasm: string;
  num_qubits: number;
  num_clbits: number;
  probabilities_sparse: Record<string, number>;
  classical_distribution: Record<string, number>;
  deterministic_counts: boolean;
  webgpu: { in_declared_range: boolean };
}
const corpus = JSON.parse(readFileSync(new URL("../tests/fixtures/shared_conformance.json", import.meta.url), "utf8")) as {
  tolerance_f64: number;
  webgpu: { declared_max_qubits: number; tolerance: { max_abs_probability_diff: number; total_variation: number } };
  cases: Case[];
};
const OUT = new URL("../e2e-results/", import.meta.url);
const gpuReport: Record<string, unknown> = {};

const b64 = (s: string) => Buffer.from(s).toString("base64url");

async function ready(page: Page) {
  await expect(page.locator("#limit-chip")).toHaveClass(/ok/, { timeout: 45_000 });
}

async function runCase(page: Page, c: Case, engine: "wasm" | "webgpu") {
  await page.goto(`/?lang=en#/code?qasm=${b64(c.qasm)}`);
  await page.reload();
  await ready(page);
  await page.selectOption("#engine", engine);
  await page.click("#run");
  await expect(page.locator("#stats .chip").first()).toContainText(engine === "wasm" ? "WASM f64" : /WebGPU|WASM/, { timeout: 45_000 });
  await page.locator("#res-details summary").click();
  const download = page.waitForEvent("download");
  await page.click("#res-export");
  const card = JSON.parse(readFileSync((await (await download).path())!, "utf8"));
  return card;
}

function compareExact(card: any, c: Case) {
  const rows: { bits: string; p: number }[] = card.result.exact;
  let maxAbs = 0, seen = 0;
  for (const row of rows) {
    const expected = c.probabilities_sparse[String(parseInt(row.bits, 2))] ?? 0;
    maxAbs = Math.max(maxAbs, Math.abs(row.p - expected));
    seen += expected;
  }
  const support = Object.keys(c.probabilities_sparse).length;
  // The card lists at most 64 basis states; when the support is larger the rest is not compared.
  const complete = support <= 64;
  if (complete) expect(seen).toBeCloseTo(1, 9);
  return { maxAbs, complete, rows: rows.length };
}

for (const c of corpus.cases) {
  test(`page, WebAssembly f64: ${c.name}`, async ({ page }) => {
    const card = await runCase(page, c, "wasm");
    expect(card.engine.kind).toBe("wasm");
    expect(card.engine.precision).toBe("f64");
    const { maxAbs } = compareExact(card, c);
    expect(maxAbs).toBeLessThanOrEqual(corpus.tolerance_f64);
    expect(Math.abs(card.result.norm - 1)).toBeLessThanOrEqual(corpus.tolerance_f64);
    const counts: Record<string, number> = card.result.counts;
    expect(Object.values(counts).reduce((a, b) => a + b, 0)).toBe(card.input.shots);
    for (const key of Object.keys(counts)) expect(key).toHaveLength(c.num_clbits);
    if (c.deterministic_counts) expect(counts).toEqual({ [Object.keys(c.classical_distribution)[0]]: card.input.shots });
  });
}

test.describe.serial("page, WebGPU f32 (needs an adapter)", () => {
  let adapterNote = "";
  test.beforeAll(() => mkdirSync(OUT, { recursive: true }));

  test("the WebGPU column is measured when an adapter exists and NOT_RUN otherwise", async ({ page }) => {
    await page.goto("/?lang=en#/code");
    await ready(page);
    const gpuOption = await page.locator('#engine option[value="webgpu"]').evaluate((o) => (o as HTMLOptionElement).disabled);
    if (gpuOption) {
      adapterNote = "no WebGPU adapter in this browser: option disabled by the page";
      writeFileSync(new URL("webgpu_conformance.json", OUT), JSON.stringify({ status: "NOT_RUN", reason: adapterNote }, null, 2));
      // Reported as skipped (NOT_RUN), not as a pass. The unavailable state itself is tested in
      // app.spec.ts ("WebGPU-unavailable fallback").
      test.skip(true, `NOT_RUN: ${adapterNote}`);
      return;
    }
    const tolerance = corpus.webgpu.tolerance;
    let worst = 0;
    for (const c of corpus.cases.filter((x) => x.webgpu.in_declared_range)) {
      const card = await runCase(page, c, "webgpu");
      if (card.engine.kind !== "webgpu") { gpuReport[c.name] = { status: "FELL_BACK", engine: card.engine.kind }; continue; }
      const { maxAbs, complete } = compareExact(card, c);
      gpuReport[c.name] = { max_abs_probability_diff: maxAbs, complete_support: complete, cross_check_tv: card.engine.cross_check_tv };
      worst = Math.max(worst, maxAbs);
      expect(maxAbs, `${c.name} WebGPU f32 deviation`).toBeLessThanOrEqual(tolerance.max_abs_probability_diff);
    }
    writeFileSync(new URL("webgpu_conformance.json", OUT), JSON.stringify({ status: "RUN", worst_max_abs: worst, tolerance, cases: gpuReport }, null, 2));
  });
});
