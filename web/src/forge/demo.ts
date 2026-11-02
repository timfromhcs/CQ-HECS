// Deterministic demo fixtures. Everything here is labelled SIMULATED; nothing is random per load.

import { GENESIS_BLOCK_HASH, GENESIS_HEADER_HEX } from "./sha";

export const DEMO_LABEL = "DEMO / SIMULATED" as const;

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface DemoSample { t_s: number; hashrate_ghs: number | null; temperature_c: number | null; power_w: number | null }
export interface DemoTelemetry {
  label: typeof DEMO_LABEL; source: "SIMULATED"; seed: number; device: string; samples: DemoSample[];
}

/** 60 samples at 30 s spacing with two explicit gaps (null), seeded and reproducible. */
export function demoTelemetry(seed = 20261101): DemoTelemetry {
  const rnd = mulberry32(seed);
  const samples: DemoSample[] = [];
  for (let i = 0; i < 60; i++) {
    if (i === 17 || i === 18 || i === 41) {
      samples.push({ t_s: i * 30, hashrate_ghs: null, temperature_c: null, power_w: null });
      continue;
    }
    samples.push({
      t_s: i * 30,
      hashrate_ghs: Math.round((400 + (rnd() - 0.5) * 20) * 10) / 10,
      temperature_c: Math.round((52 + (rnd() - 0.5) * 4) * 10) / 10,
      power_w: Math.round((12 + (rnd() - 0.5) * 1) * 100) / 100,
    });
  }
  return { label: DEMO_LABEL, source: "SIMULATED", seed, device: "demo-node (not a real device)", samples };
}

export const DEMO_HEADER = { hex: GENESIS_HEADER_HEX, expectedDisplayHash: GENESIS_BLOCK_HASH, note: "Bitcoin genesis block header (public test vector)" };

export interface DemoBenchmark { label: typeof DEMO_LABEL; rows: { workload: string; unit: string; value: number; comparable: false }[] }
/** Synthetic values to show the layout. They are not measurements of any device. */
export function demoBenchmark(): DemoBenchmark {
  return {
    label: DEMO_LABEL,
    rows: [
      { workload: "SHA-256d mining job (ASIC, synthetic)", unit: "GH/s", value: 400, comparable: false },
      { workload: "SHA-256 compressions (software, synthetic)", unit: "M compressions/s", value: 12.5, comparable: false },
    ],
  };
}
