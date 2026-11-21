// W4-11: resolve the bundled WASM core against the deployment base.
//
// The loader used `fetch("/cqhecs_core.wasm")`, an absolute path that breaks when the app
// is served under a sub-path (e.g. Vercel project pages, a reverse-proxy prefix). Vite's
// BASE_URL is the deployment base, so the URL is built from it instead. Kept dependency
// free so the Node tests can load it (import.meta.env is absent there).

function baseUrl(): string {
  try {
    // vite/client types this; outside a Vite build it is undefined.
    return import.meta.env.BASE_URL || "/";
  } catch {
    return "/";
  }
}

/** Absolute URL of the bundled state-vector/SHA WASM core for the given origin. */
export function coreWasmUrl(origin: string, base: string = baseUrl()): string {
  return new URL("cqhecs_core.wasm", new URL(base, origin)).href;
}
