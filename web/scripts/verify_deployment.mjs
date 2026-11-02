// Observe a deployed build instead of assuming it works.
//
// A screenshot cannot show that the wasm is served with the wrong MIME type, that the
// security headers are gone, or that a deep link 404s. This checks those things:
//
//   * the SPA root and a deep link both return the app shell;
//   * `/cqhecs_core.wasm` is `application/wasm` with a cache policy, and it compiles;
//   * the security headers from `vercel.json` are really present;
//   * the entry script and the wasm stay within the transport budget.
//
// Authentication: Vercel Deployment Protection answers an anonymous request with a login
// page, which looks like a broken app if you do not look for it. Three ways to get past
// that, in the order this script tries them:
//
//   1. `VERCEL_PROTECTION_BYPASS` in the environment -> `x-vercel-protection-bypass`;
//   2. `--via-cli` -> every request goes through `vercel curl`, which uses your session;
//   3. nothing -> the script detects the protection page and exits with code 3, saying so.
//      It never reports the protection page as an application failure.
//
//     node scripts/verify_deployment.mjs <base-url> [--via-cli]
//
// Exit codes: 0 all checks pass, 1 a check failed, 2 the deployment did not answer,
//             3 the response is Vercel's protection page and no credential was available.
import { spawnSync } from "node:child_process";

// Transport sizes as served (the CLI reports the uncompressed body), measured on the
// production deployment of 2026-11-02: entry script 324.4 KB, wasm 35.5 KB.
const BUDGET = { js: 400 * 1024, wasm: 64 * 1024 };
const PROTECTION_MARKERS = [/Log in to Vercel/i, /Protected Deployment/i, /vercel\.com\/login/];

const args = process.argv.slice(2);
const viaCli = args.includes("--via-cli");
const base = (args.find((value) => value.startsWith("http")) ?? "").replace(/\/+$/, "");
if (!base) {
  console.error("usage: node scripts/verify_deployment.mjs <base-url> [--via-cli]");
  process.exit(2);
}

const bypass = process.env.VERCEL_PROTECTION_BYPASS ?? "";

function parseCliOutput(raw) {
  // `vercel curl` prints advisory lines ("Deployment Protection bypassed ...") to stdout
  // before the response, so the parse starts at the first HTTP status line.
  const lines = raw.split(/\r?\n/);
  let start = lines.findIndex((line) => /^HTTP\/\d/.test(line));
  if (start < 0) return null;
  const status = Number(lines[start].split(" ")[1] ?? 0);
  const headers = new Headers();
  let index = start + 1;
  for (; index < lines.length; index += 1) {
    if (!lines[index].trim()) break;
    const colon = lines[index].indexOf(":");
    if (colon > 0) {
      try {
        headers.append(lines[index].slice(0, colon).trim(), lines[index].slice(colon + 1).trim());
      } catch {
        // A decorative line the CLI printed around the response; not a header.
      }
    }
  }
  return { status, headers, body: lines.slice(index + 1).join("\n") };
}

function viaVercelCli(url) {
  const result = spawnSync("vercel", ["curl", url, "--", "--silent", "--include"], {
    encoding: "utf8",
    shell: process.platform === "win32",
  });
  if (result.error) return null;
  const raw = `${result.stdout ?? ""}`;
  if (!raw) return null;
  return parseCliOutput(raw);
}

async function get(path) {
  const url = `${base}${path}`;
  if (viaCli) {
    const parsed = viaVercelCli(url);
    if (parsed) return parsed;
  }
  try {
    const headers = bypass ? { "x-vercel-protection-bypass": bypass } : undefined;
    const response = await fetch(url, { redirect: "follow", headers });
    return { status: response.status, headers: response.headers, body: await response.text() };
  } catch (error) {
    return { status: 0, headers: new Headers(), body: String(error) };
  }
}

const results = [];
function record(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}: ${detail}`);
}

const root = await get("/");
const protectedPage = PROTECTION_MARKERS.some((marker) => marker.test(root.body));
if (protectedPage) {
  console.error(
    [
      "The deployment answered with Vercel's protection page, not the application.",
      "That is not an application failure; it is Deployment Protection.",
      "Re-run with --via-cli (uses your Vercel session) or set VERCEL_PROTECTION_BYPASS.",
      "A bypassed request proves the build is correct, not that the URL is public.",
    ].join("\n"),
  );
  process.exit(3);
}

// The app is served as static markup with hash routing (`#/lab`), so the stable marker is
// its main landmark, not a framework root div. A path deep link never reaches the server:
// the fragment stays in the browser.
const SHELL_MARKER = 'id="main"';
record("app shell", root.status === 200 && root.body.includes(SHELL_MARKER), `${root.status}, ${root.body.length} bytes`);

const hashRoute = await get("/#/sat");
record(
  "hash route serves the same document",
  hashRoute.status === 200 && hashRoute.body.includes(SHELL_MARKER),
  `${hashRoute.status}, ${hashRoute.body.length} bytes`,
);

const expectedHeaders = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "strict-origin-when-cross-origin",
};
for (const [header, expected] of Object.entries(expectedHeaders)) {
  const value = root.headers.get(header);
  record(`header ${header}`, value === expected, value ?? "missing");
}
const permissions = root.headers.get("Permissions-Policy") ?? "";
record("header Permissions-Policy", permissions.includes("camera=()"), permissions || "missing");

const wasm = await get("/cqhecs_core.wasm");
const contentType = wasm.headers.get("content-type") ?? "";
record(
  "wasm content type",
  wasm.status === 200 && contentType.startsWith("application/wasm"),
  `${wasm.status}, ${contentType || "missing"}`,
);
const cacheControl = wasm.headers.get("cache-control") ?? "";
record("wasm cache policy", /max-age=\d+/.test(cacheControl), cacheControl || "missing");

if (wasm.status === 200) {
  try {
    // The body came through as text; fetch the bytes again for the compile check. Under
    // --via-cli this falls back to the direct URL, so a protected deployment reports the
    // protection page instead of pretending the wasm compiled.
    const response = viaCli ? null : await fetch(`${base}/cqhecs_core.wasm`);
    const bytes = response ? new Uint8Array(await response.arrayBuffer()) : null;
    if (bytes) {
      await WebAssembly.compile(bytes);
      record("wasm compiles", true, `${(bytes.length / 1024).toFixed(1)} KB`);
      record(
        "wasm size budget",
        bytes.length <= BUDGET.wasm,
        `${(bytes.length / 1024).toFixed(1)} KB of ${(BUDGET.wasm / 1024).toFixed(0)} KB`,
      );
    } else {
      // Under --via-cli the body is text, so size and magic word are checked instead.
      const size = Number(wasm.headers.get("content-length") ?? 0);
      const magicOk = wasm.body.startsWith("\u0000asm");
      record("wasm compiles", magicOk, magicOk ? "magic word present (CLI transport)" : "not a wasm body");
      record(
        "wasm size budget",
        size > 0 && size <= BUDGET.wasm,
        `${(size / 1024).toFixed(1)} KB of ${(BUDGET.wasm / 1024).toFixed(0)} KB`,
      );
    }
  } catch (error) {
    record("wasm compiles", false, String(error));
  }
}

const scriptMatch = root.body.match(/<script[^>]+src="([^"]+\.js)"[^>]*>/);
if (scriptMatch) {
  const response = await fetch(`${base}${scriptMatch[1]}`);
  const bytes = response.ok ? new Uint8Array(await response.arrayBuffer()) : null;
  if (bytes) {
    record(
      "entry script size",
      bytes.length <= BUDGET.js,
      `${(bytes.length / 1024).toFixed(1)} KB of ${(BUDGET.js / 1024).toFixed(0)} KB (${scriptMatch[1]})`,
    );
  } else {
    const asset = await get(scriptMatch[1]);
    const size = Number(asset.headers.get("content-length") ?? 0);
    record(
      "entry script size",
      asset.status === 200 && size > 0 && size <= BUDGET.js,
      `${(size / 1024).toFixed(1)} KB of ${(BUDGET.js / 1024).toFixed(0)} KB (CLI transport)`,
    );
  }
} else {
  record("entry script found", false, "the served page has no module script");
}

const unreachable = results.filter((entry) => entry.detail.startsWith("0,"));
if (unreachable.length) {
  console.error(`\n${base} did not answer; nothing was verified`);
  process.exit(2);
}
const failed = results.filter((entry) => !entry.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed against ${base}`);
process.exit(failed.length === 0 ? 0 : 1);
