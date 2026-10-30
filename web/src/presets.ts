// Built-in example circuits. Each is generated for a chosen width.

import { Builder } from "./circuit";
import type { Lang } from "./i18n";

export interface Preset {
  id: string;
  title: Record<Lang, string>;
  blurb: Record<Lang, string>;
  minQubits: number;
  build: (n: number) => Builder;
}

function qft(b: Builder, n: number, offset = 0) {
  for (let j = n - 1; j >= 0; j--) {
    b.h(offset + j);
    for (let k = j - 1; k >= 0; k--) b.cp(Math.PI / 2 ** (j - k), offset + k, offset + j);
  }
  for (let i = 0; i < Math.floor(n / 2); i++) b.swap(offset + i, offset + n - 1 - i);
  return b;
}

export const PRESETS: Preset[] = [
  {
    id: "bell", minQubits: 2,
    title: { en: "Bell pair", de: "Bell-Paar", fr: "Paire de Bell" },
    blurb: { en: "Maximal entanglement: only 00 and 11, 50 % each.", de: "Maximale Verschränkung: nur 00 und 11, je 50 %.", fr: "Intrication maximale : seulement 00 et 11, 50 % chacun." },
    build: () => new Builder(2).h(0).cx(0, 1).measureAll(),
  },
  {
    id: "ghz", minQubits: 3,
    title: { en: "GHZ state", de: "GHZ-Zustand", fr: "État GHZ" },
    blurb: { en: "All qubits entangled: only 0…0 and 1…1.", de: "Alle Qubits verschränkt: nur 0…0 und 1…1.", fr: "Tous les qubits intriqués : seulement 0…0 et 1…1." },
    build: (n) => {
      const b = new Builder(n).h(0);
      for (let q = 1; q < n; q++) b.cx(q - 1, q);
      return b.measureAll();
    },
  },
  {
    id: "superposition", minQubits: 1,
    title: { en: "Uniform superposition", de: "Gleichverteilung", fr: "Superposition uniforme" },
    blurb: { en: "H on every qubit: all 2^n outcomes equally likely.", de: "H auf jedem Qubit: alle 2^n Ausgänge gleich wahrscheinlich.", fr: "H sur chaque qubit : les 2^n résultats équiprobables." },
    build: (n) => {
      const b = new Builder(n);
      for (let q = 0; q < n; q++) b.h(q);
      return b.measureAll();
    },
  },
  {
    id: "qft", minQubits: 2,
    title: { en: "Quantum Fourier transform", de: "Quanten-Fourier-Transformation", fr: "Transformée de Fourier quantique" },
    blurb: { en: "QFT of |1⟩: equal magnitudes with a phase ramp.", de: "QFT auf |1⟩: gleichverteilte Beträge mit Phasenrampe.", fr: "QFT de |1⟩ : modules égaux avec une rampe de phase." },
    build: (n) => qft(new Builder(n).x(0), n).measureAll(),
  },
  {
    id: "grover", minQubits: 2,
    title: { en: "Grover search (|11…1⟩)", de: "Grover-Suche (|11…1⟩)", fr: "Recherche de Grover (|11…1⟩)" },
    blurb: { en: "Amplitude amplification finds the marked state.", de: "Amplitudenverstärkung findet den markierten Zustand.", fr: "L'amplification d'amplitude trouve l'état marqué." },
    build: (n) => {
      const b = new Builder(n);
      const all = [...Array(n).keys()];
      const mcz = () => (n === 1 ? b.z(0) : b.mcz(...all));
      all.forEach((q) => b.h(q));
      const iterations = Math.max(1, Math.floor((Math.PI / 4) * Math.sqrt(2 ** n)));
      for (let it = 0; it < iterations; it++) {
        mcz();
        all.forEach((q) => b.h(q));
        all.forEach((q) => b.x(q));
        mcz();
        all.forEach((q) => b.x(q));
        all.forEach((q) => b.h(q));
      }
      return b.measureAll();
    },
  },
  {
    id: "bv", minQubits: 2,
    title: { en: "Bernstein–Vazirani", de: "Bernstein–Vazirani", fr: "Bernstein–Vazirani" },
    blurb: { en: "Finds a secret bit pattern with a single query.", de: "Findet ein geheimes Bitmuster mit einer einzigen Abfrage.", fr: "Trouve un motif secret en une seule requête." },
    build: (n) => {
      const b = new Builder(n);
      const data = n - 1;
      const secret = Array.from({ length: data }, (_, i) => (i % 2 === 0 ? 1 : 0));
      b.x(data).h(data);
      for (let q = 0; q < data; q++) b.h(q);
      secret.forEach((bit, q) => { if (bit) b.cx(q, data); });
      for (let q = 0; q < data; q++) b.h(q);
      for (let q = 0; q < data; q++) b.measure(q, q);
      return b;
    },
  },
  {
    id: "teleport", minQubits: 3,
    title: { en: "Teleportation", de: "Teleportation", fr: "Téléportation" },
    blurb: { en: "Moves RY(1.1)|0⟩ from q0 to q2 with corrections; q2 then reads 0.", de: "Überträgt RY(1.1)|0⟩ von q0 auf q2 mit Korrektur; q2 zeigt dann 0.", fr: "Transfère RY(1.1)|0⟩ de q0 vers q2 avec correction ; q2 lit alors 0." },
    build: () => {
      const b = new Builder(3).ry(1.1, 0).h(1).cx(1, 2).cx(0, 1).h(0);
      // Deferred-measurement form: corrections as controlled gates, exact.
      b.cx(1, 2).cz(0, 2);
      b.ry(-1.1, 2); // undo the payload: q2 must now read 0 with certainty
      return b.measure(2, 0);
    },
  },
  {
    id: "random", minQubits: 2,
    title: { en: "Random circuit (supremacy style)", de: "Zufallsschaltung (Supremacy-Stil)", fr: "Circuit aléatoire (style suprématie)" },
    blurb: { en: "Layers of √X/T/RZ and CZ bricks: hard classically, exact here.", de: "Schichten aus √X/T/RZ und CZ-Ziegeln: schwer klassisch, hier exakt.", fr: "Couches de √X/T/RZ et briques CZ : difficile classiquement, exact ici." },
    build: (n) => {
      const b = new Builder(n);
      let seed = 12345;
      const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
      const layers = Math.min(20, 2 * n);
      for (let l = 0; l < layers; l++) {
        for (let q = 0; q < n; q++) {
          const r = rnd();
          if (r < 0.33) b.sx(q); else if (r < 0.66) b.t(q); else b.rz(rnd() * 2 * Math.PI, q);
        }
        for (let q = l % 2; q + 1 < n; q += 2) b.cz(q, q + 1);
      }
      return b.measureAll();
    },
  },
];
