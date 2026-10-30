// Measured device noise profiles (M-FIT-2), extracted from real QPU runs by
// scripts/export_device_profiles.py and shared with the Python package.

import type { Noise } from "./protocol";

export interface DeviceProfile {
  id: string;
  vendor: string;
  label: string;
  backend: string;
  shots_per_circuit: number;
  measured_qubits: number;
  p01: number[];
  p10: number[];
  x_bitflip: number[];
  cx_depolarizing: number;
  anomalies: unknown[];
  validation: {
    h_v3_8: string;
    median_delta_tv_m_fit: number;
    ci95: [number, number];
    m_fit_2_vs_ideal_median: number;
    m_fit_2_vs_ideal_ci95: [number, number];
    n_eval: number;
    status: string;
  };
  evidence: string;
}

export interface ProfileDocument {
  schema: string;
  model: string;
  note: string;
  profiles: DeviceProfile[];
}

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

/**
 * The noise model of a profile for an n-qubit circuit. Qubits beyond the measured
 * ones reuse the mean measured readout (an extrapolation, flagged in the UI); X
 * anomalies belong to specific physical qubits and are not extrapolated. This is
 * the same rule as cqhecs.device_profiles.readout_for.
 */
export function profileNoise(profile: DeviceProfile, numQubits: number): Noise & { extrapolated: number } {
  const m01 = mean(profile.p01), m10 = mean(profile.p10);
  const fill = (xs: number[], v: number) => Array.from({ length: numQubits }, (_, q) => (q < xs.length ? xs[q] : v));
  return {
    p1: 0,
    p2: profile.cx_depolarizing,
    readout: 0,
    p01: fill(profile.p01, m01),
    p10: fill(profile.p10, m10),
    xflip: fill(profile.x_bitflip, 0),
    profile: profile.id,
    extrapolated: Math.max(0, numQubits - profile.measured_qubits),
  };
}

let cache: Promise<ProfileDocument> | null = null;

export function loadProfiles(): Promise<ProfileDocument> {
  cache ??= fetch("/device_profiles.json").then((r) => {
    if (!r.ok) throw new Error(`device_profiles.json: HTTP ${r.status}`);
    return r.json() as Promise<ProfileDocument>;
  });
  return cache;
}
