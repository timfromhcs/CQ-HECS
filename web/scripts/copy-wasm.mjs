// Copy the release build of the Rust core into public/ so Vite serves it as-is.
import { copyFileSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const from = new URL("../wasm/target/wasm32-unknown-unknown/release/cqhecs_web_core.wasm", import.meta.url);
const to = new URL("../public/cqhecs_core.wasm", import.meta.url);
copyFileSync(from, to);
const digest = createHash("sha256").update(readFileSync(to)).digest("hex");
console.log(`public/cqhecs_core.wasm ${statSync(to).size} bytes sha256 ${digest}`);
