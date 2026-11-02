// Measure the WASM core on increasing widths, separately for setup, execution and readout.
//
// The browser engine has two paths: the exact f64 WebAssembly core and the f32 WebGPU
// path. This measures the one that runs everywhere and writes a machine-readable record.
// The WebGPU column is filled by `e2e/engine-benchmark.spec.ts` when a headless browser
// actually provides an adapter; otherwise it stays "not measured" instead of guessed.
//
// Deterministic workload per width: H on every qubit, a CNOT ladder, then an rz layer.
// Every repetition is kept in the record; the summary is the median plus min/max.
import { readFileSync, writeFileSync } from "node:fs";

import { Builder, compile } from "../src/circuit";
import { Core } from "../src/core";

const WIDTHS = [12, 16, 20];
const REPETITIONS = 5;

function ladder(n: number) {
  const circuit = new Builder(n);
  for (let q = 0; q < n; q += 1) circuit.h(q);
  for (let q = 0; q + 1 < n; q += 1) circuit.cx(q, q + 1);
  for (let q = 0; q < n; q += 1) circuit.rz(0.37 + 0.01 * q, q);
  return circuit;
}

async function main(): Promise<number> {
  const bytes = new Uint8Array(readFileSync(new URL("../public/cqhecs_core.wasm", import.meta.url)));
  const results = [];

  for (const width of WIDTHS) {
    const ops = compile(ladder(width));
    const samples: number[] = [];
    let setupMs = 0;
    let readoutMs = 0;

    for (let run = 0; run < REPETITIONS; run += 1) {
      const setupStart = performance.now();
      const core = await Core.load(bytes);
      if (!core.init(width)) throw new Error(`the core refused ${width} qubits`);
      setupMs = performance.now() - setupStart;

      const started = performance.now();
      core.applyOps(ops);
      const elapsed = performance.now() - started;

      const readStart = performance.now();
      const probabilities = core.probabilities();
      readoutMs = performance.now() - readStart;

      const total = probabilities.reduce((sum, value) => sum + value, 0);
      if (Math.abs(total - 1) > 1e-9) throw new Error(`width ${width}: norm ${total}`);
      samples.push(elapsed);
      core.free();
    }

    const sorted = [...samples].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    results.push({
      width,
      gates: ops.length,
      engine: "wasm",
      precision: "f64",
      repetitions: REPETITIONS,
      setup_ms: Number(setupMs.toFixed(3)),
      readout_ms: Number(readoutMs.toFixed(3)),
      samples_ms: samples.map((value) => Number(value.toFixed(3))),
      median_ms: Number(median.toFixed(3)),
      min_ms: Number(sorted[0].toFixed(3)),
      max_ms: Number(sorted[sorted.length - 1].toFixed(3)),
      amplitudes_per_second: Math.round((ops.length * 2 ** (width + 1)) / (median / 1000)),
    });
    console.log(`${width} qubits: ${ops.length} ops, median ${median.toFixed(2)} ms, norm ok`);
  }

  const outIndex = process.argv.indexOf("--out");
  const target = outIndex >= 0 ? process.argv[outIndex + 1] : "e2e-results/engine-benchmark.json";
  const document = {
    schema: "hcs.web.engine-benchmark.v1",
    measured_at: new Date().toISOString(),
    environment: {
      runtime: `node ${process.version}`,
      platform: process.platform,
      circuit: "h on every qubit, CNOT ladder, rz layer",
    },
    gpu: {
      status: "not measured",
      reason: "the WebGPU path needs a browser with an adapter; see e2e/engine-benchmark.spec.ts",
    },
    results,
  };
  writeFileSync(target, `${JSON.stringify(document, null, 2)}\n`);
  console.log(`written: ${target}`);
  return 0;
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error(error);
  process.exit(1);
});
