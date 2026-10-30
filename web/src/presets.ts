// Built-in example circuits. Each is generated for a chosen width.

import { Builder } from "./circuit";

export interface Preset {
  id: string;
  title: string;
  blurb: string;
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
    id: "bell", title: "Bell-Paar", minQubits: 2,
    blurb: "Maximale Verschränkung: nur 00 und 11, je 50 %.",
    build: () => new Builder(2).h(0).cx(0, 1).measureAll(),
  },
  {
    id: "ghz", title: "GHZ-Zustand", minQubits: 3,
    blurb: "Alle Qubits verschränkt: nur 0…0 und 1…1.",
    build: (n) => {
      const b = new Builder(n).h(0);
      for (let q = 1; q < n; q++) b.cx(q - 1, q);
      return b.measureAll();
    },
  },
  {
    id: "superposition", title: "Gleichverteilung", minQubits: 1,
    blurb: "H auf jedem Qubit: alle 2^n Ausgänge gleich wahrscheinlich.",
    build: (n) => {
      const b = new Builder(n);
      for (let q = 0; q < n; q++) b.h(q);
      return b.measureAll();
    },
  },
  {
    id: "qft", title: "Quanten-Fourier-Transformation", minQubits: 2,
    blurb: "QFT auf |1⟩: gleichverteilte Beträge mit Phasenrampe.",
    build: (n) => qft(new Builder(n).x(0), n).measureAll(),
  },
  {
    id: "grover", title: "Grover-Suche (|11…1⟩)", minQubits: 2,
    blurb: "Amplitudenverstärkung findet den markierten Zustand.",
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
    id: "bv", title: "Bernstein–Vazirani", minQubits: 2,
    blurb: "Findet ein geheimes Bitmuster mit einer einzigen Abfrage.",
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
    id: "teleport", title: "Teleportation", minQubits: 3,
    blurb: "Überträgt RY(1.1)|0⟩ von q0 auf q2 mit Mitte-Messung und Korrektur.",
    build: () => {
      const b = new Builder(3).ry(1.1, 0).h(1).cx(1, 2).cx(0, 1).h(0);
      // Deferred-measurement form: corrections as controlled gates, exact.
      b.cx(1, 2).cz(0, 2);
      b.ry(-1.1, 2); // undo the payload: q2 must now read 0 with certainty
      return b.measure(2, 0);
    },
  },
  {
    id: "random", title: "Zufallsschaltung (Supremacy-Stil)", minQubits: 2,
    blurb: "Schichten aus √X/T/RZ und CZ-Ziegeln: schwer klassisch, hier exakt.",
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
