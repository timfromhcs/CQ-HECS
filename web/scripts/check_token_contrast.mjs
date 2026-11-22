// W4-13: compute WCAG contrast for the design tokens in both themes.
//
// Reads the hex tokens straight from web/src/styles.css (dark `:root` and
// `:root[data-theme="light"]`) so the check cannot drift from the stylesheet. Fails when
// body text is below AA (4.5:1) or secondary/decorative text is below the stated target.
//
//   node scripts/check_token_contrast.mjs
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const css = readFileSync(fileURLToPath(new URL("../src/styles.css", import.meta.url)), "utf8");

function tokens(selector) {
  const block = css.match(new RegExp(selector + "\\s*\\{([^}]*)\\}"));
  if (!block) throw new Error(`missing token block for ${selector}`);
  const out = {};
  for (const m of block[1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\b/g)) out[m[1]] = m[2];
  return out;
}

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [la, lb] = [luminance(a), luminance(b)];
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

// [foreground, background, minimum] -- text and muted on both surfaces are AA normal
// text (4.5:1); accent is used for large text/links/decoration (3:1).
const PAIRS = [
  ["text", "bg", 4.5],
  ["text", "bg-2", 4.5],
  ["muted", "bg", 4.5],
  ["muted", "bg-2", 4.5],
  ["accent", "bg", 3.0],
];

const themes = {
  dark: tokens(":root"),
  light: tokens(":root\\[data-theme=\"light\"\\]"),
};

let failed = 0;
for (const [name, t] of Object.entries(themes)) {
  console.log(`theme ${name}:`);
  for (const [fg, bg, min] of PAIRS) {
    if (!t[fg] || !t[bg]) {
      console.log(`  MISSING ${fg}/${bg}`);
      failed += 1;
      continue;
    }
    const r = ratio(t[fg], t[bg]);
    const ok = r >= min;
    if (!ok) failed += 1;
    console.log(`  ${ok ? "ok  " : "FAIL"} ${fg} on ${bg}: ${r.toFixed(2)} (min ${min})`);
  }
}

if (failed) {
  console.error(`\ntoken contrast FAILED (${failed} pair(s))`);
  process.exit(1);
}
console.log("\ntoken contrast OK");