# CQ-HECS design system

Covers both UI products: **CQ-HECS Web** (`web/`, Vite + TypeScript) and **CQ-HECS
Studio** (`cqhecs/studio/static/`). The tokens below are the ones defined in
`web/src/styles.css`. The Studio uses the same palette under its own variable names.

## Principles

1. **Every number has a source.** A value on screen comes from an engine result,
   a committed dataset or the device check. No placeholder metrics and no decorative
   "live" telemetry.
2. **Status in words, not only colour.** `SAT`, `UNSAT`, `UNKNOWN`, `COUNTED`,
   `UNCERTIFIED`, `EXACT` and similar always appear as text. Colour only reinforces the word.
3. **Say what ran.** Results name the engine and its precision (WASM f64,
   WebGPU f32, DPLL, CaDiCaL), the noise model and its evidence, and what was not run.
4. **A refusal is a result.** Safe-limit refusals, `UNKNOWN` and unavailable
   backends get their own wording. They never show as an empty success.

## Tokens

| Token | Dark | Light | Use |
| :--- | :--- | :--- | :--- |
| `--bg` | `#0a0c13` | `#f4f6fc` | page background |
| `--bg-2` | `#10131d` | `#ffffff` | inputs, inner panels |
| `--panel` | `rgba(21,25,39,.72)` | `rgba(255,255,255,.86)` | cards |
| `--line` | `rgba(148,163,255,.14)` | `rgba(40,50,100,.12)` | borders, grid lines |
| `--text` | `#e9ecf8` | `#121626` | body text |
| `--muted` | `#8f97b6` | `#59617f` | secondary text (≥ 4.5:1 on `--bg`) |
| `--accent` / `--accent-2` | `#39d0ff` / `#9b6bff` | `#0a8fd1` / `#6a3df0` | primary actions, focus, chart series |
| `--good` / `--warn` / `--bad` | `#3ee6a0` / `#ffb547` / `#ff5d7a` | same | verified / caution / error, always with a text label |

Code editor (CodeMirror oneDark) overrides: comments and gutter `#a3acbf`, keywords
`#d7a1ee`, variables `#ef8a92`. They replace oneDark values that fall below 4.5:1.

## Type and spacing

- Body: Inter 400/500/600/700/800. Code and numbers: JetBrains Mono.
- Scale: `clamp()` for the hero (2–3.6 rem), h1 1.6–2.6 rem, h2 1.15 rem, body 1 rem,
  small 0.84 rem.
- Radius: cards 18 px, controls 10–12 px, chips 999 px. Gaps are 16–18 px between cards.

## Layout rules

- Grid containers declare `grid-template-columns: minmax(0, 1fr)` (or explicit
  tracks), and their children use `min-width: 0`. An implicit `auto` track lets one
  long code line push the page wider than the viewport. The E2E suite caught this twice
  in v3.5.0.
- Breakpoints: 1080 px (compact tabs), 980 px (single column), 760 px (stacked header,
  full-width run button).
- No horizontal page overflow at 360 px. This is enforced by `web/e2e/app.spec.ts`.

## States

| State | Treatment |
| :--- | :--- |
| loading | the button is disabled, with a progress bar and a text label |
| empty | an explanatory sentence ("No run yet …"), never an empty chart |
| refused / safe limit | `⚠` plus the reason in `--bad`; the run button is disabled |
| `UNKNOWN` | warn colour plus the cause (timeout, budget); never styled as success |
| `UNSAT` uncertified | warn box: "this UNSAT is the solver's verdict only" |
| error | an inline message near the control, with details in the console |

## Accessibility

- Target WCAG 2.2 AA. `web/e2e/app.spec.ts` runs axe (`wcag2a`, `wcag2aa`, `wcag21aa`,
  `wcag22aa`) on every route and fails on critical or serious violations.
- Visible `:focus-visible` outline; skip link; `role="tab"` with `aria-selected` on
  segmented controls; a labelled code editor.
- `prefers-reduced-motion` disables the animations (orbit, heart, spinners).
- Charts carry `<title>` per bar and a text table alternative (Table tab).

## Anti-patterns (do not add)

Fake live metrics, KPI cards without a source, glow for its own sake, decorative
pills, monospace for prose, and colour-only status.
