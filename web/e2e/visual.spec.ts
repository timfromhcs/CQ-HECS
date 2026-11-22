// W13: visual-regression snapshots on the key routes, light and dark, phone (360) and desktop.
//
// Pixel baselines depend on the OS font rasteriser, so they are stored per platform
// (`e2e/__snapshots__/visual.spec.ts/<name>-<platform>.png`, see `snapshotPathTemplate` in
// playwright.config.ts). A platform without committed baselines does NOT fail: the tests are
// reported as skipped (NOT_RUN) with the reason. Create or refresh baselines on a platform with
//
//     UPDATE_VISUAL=1 npx playwright test e2e/visual.spec.ts --update-snapshots
//
// Device-dependent text (qubit limit, GPU name, timings) is masked: the snapshot checks layout,
// colour and typography, not the numbers of the machine it runs on. External fonts are blocked
// so a missing network cannot change the rendering.
import { test, expect, type Page } from "@playwright/test";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const ROUTES = ["lab", "code", "sat", "guide"];
const SCHEMES = ["light", "dark"] as const;
const VIEWPORTS = [
  { name: "360", width: 360, height: 800 },
  { name: "desktop", width: 1280, height: 800 },
];

function baseline(route: string, scheme: string, vp: string): string {
  return fileURLToPath(new URL(`./__snapshots__/visual.spec.ts/${route}-${scheme}-${vp}-${process.platform}.png`, import.meta.url));
}

async function settle(page: Page) {
  await expect(page.locator("#limit-chip")).toHaveClass(/ok/, { timeout: 45_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
}

for (const route of ROUTES) {
  for (const scheme of SCHEMES) {
    for (const vp of VIEWPORTS) {
      test(`visual: ${route} / ${scheme} / ${vp.name}`, async ({ page }) => {
        const file = baseline(route, scheme, vp.name);
        test.skip(!existsSync(file) && !process.env.UPDATE_VISUAL, `NOT_RUN: no ${process.platform} baseline committed for this view`);
        await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());
        await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.goto(`/?lang=en#/${route}`);
        await settle(page);
        await expect(page).toHaveScreenshot(`${route}-${scheme}-${vp.name}.png`, {
          animations: "disabled",
          caret: "hide",
          maxDiffPixelRatio: 0.01,
          mask: [page.locator("#limit-chip"), page.locator("#hero-limit"), page.locator("#estimate"), page.locator(".cm-content")],
        });
      });
    }
  }
}
