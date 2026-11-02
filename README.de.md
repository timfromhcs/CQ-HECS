<!-- Language selector: keep the three files in sync (tests/test_readme_languages.py) -->
<p align="right"><a href="README.md">English</a> · <b>Deutsch</b> · <a href="README.fr.md">Français</a></p>

<div align="center">

# CQ-HECS

**Klassische Quantensimulation mit nachweisbaren Ergebnissen — und ein SHA-256-Forschungslabor für echte Hardware.**

</div>

> **Hinweis zur Sprache:** `README.md` (Englisch) ist die maßgebliche Fassung. Diese
> Übersetzung deckt die produktrelevanten Teile vollständig ab; die Forschungsprotokolle
> unter `research/` und `docs/` sind aus Gründen der Nachvollziehbarkeit nur auf Englisch
> gepflegt. Die Zahlen unten sind mit der englischen Fassung identisch und werden durch
> einen Test geprüft.

---

## Was CQ-HECS ist

CQ-HECS ist ein routerbasierter klassischer Simulator für Quantenschaltungen. Er
versucht nicht, ein Algorithmus für alles zu sein: Er analysiert die Schaltung, wählt
den passenden Pfad und liefert ein typisiertes Ergebnis, das sagt, was berechnet wurde —
und was nicht.

Dazu kommt **HCS SHA Forge**: eine begrenzte, evidenzbasierte Forschungsoberfläche rund
um SHA-256, die drei Implementierungen und einen physischen Miner verbindet.

## Was es nicht ist

- Kein Beweis zu P vs NP, keine Aussage über die Sicherheit von SHA-256.
- Kein „ASIC-Rundenanalysator": Der BM1366 rechnet intern und liefert Nonces, keinen
  Rundenstatus.
- Kein Ersatz für CaDiCaL oder Kissat; die eingebauten Solver sind Referenzimplementierungen.
- Kein automatischer Hardware-Zugriff: Der Browser kann den Miner nicht direkt erreichen
  (gemessen, siehe unten).

## Unified Solver

Ein Einstiegspunkt über vier Engines — eingebauter DPLL (scan und watched), OMNIWAVE und
CaDiCaL, sofern `python-sat` installiert ist — mit einem Ergebnisschema und einem
Evidenzsatz: welche Engine entschieden hat, jeder Versuch mit Budget, und der
Proof-Status jeder Engine.

- `unified.solve_unified(formula)` liefert `hcs.sat.unified.v1`: Status, Engine,
  Reihenfolge, Budgetanteile, Versuche, verifizierte Belegung, Zertifikatsgröße,
  Formel-Digest.
- Das Portfolio prüft jedes SAT-Modell erneut gegen die Original-CNF und stuft einen
  UNSAT-Proof-Status niemals hoch; ein fehlendes optionales Backend wird als
  `unavailable` gemeldet, nicht übersprungen.
- CLI: `cq-hecs sat solve --cnf ... --engine unified`.
- Gemessen auf fünf Familien, zweimal: **null Abweichungen**, einmal ohne optionales
  Backend (Python 3.14 hier ohne `python-sat`) und einmal mit **CaDiCaL 1.9.5** in einer
  Python-3.12-Umgebung. Mit CaDiCaL war `watched` auf drei Familien am schnellsten und
  `cadical` auf zwei; die deklarierte Reihenfolge kostet dort 0,12 s und 0,16 s — das steht
  da, statt versteckt zu werden. Tabellen und Rohdaten:
  [`docs/UNIFIED_SOLVER.md`](docs/UNIFIED_SOLVER.md).

## Herkunft (`hcs.run.v2`)

Ein Herkunftsschein pro Lauf, gemeinsam für CLI, Studio und Browser: exakter Eingabetext
und sein SHA-256, Engine-Art/Präzision/Modus, Seed, Softwareversion und Quellrevision, die
drei getrennten Fehlerarten (Approximation, Gleitkomma, Sampling) und die genannten
Grenzen. Der Digest liegt immer über der im Schein gespeicherten Nutzlast — ein Schein ist
ohne weitere Datei prüfbar.

- CLI: `cq-hecs sat solve --cnf … --provenance card.json`
- Browser: Export im Labor schreibt dasselbe Schema
- Alte v1-Karten (`cqhecs.web.run/1.1`) werden **abgelehnt** mit Hinweis auf Neuerzeugung,
  nicht stillschweigend umgedeutet.

Details: [`docs/PROVENANCE.md`](docs/PROVENANCE.md), Migration:
[`MIGRATION_V5.md`](MIGRATION_V5.md).

## Browser-Engines (Vercel, WebAssembly, WebGPU)

Dieselben Schaltungen laufen im Browser über drei Engines: einen Rust/WebAssembly-Kern in
f64 (exakter Pfad), einen WGSL/WebGPU-Pfad in f32 (schneller Pfad, nur mit Adapter) und
einen TypeScript-CPU-Fallback. Sie sind eine unabhängige Implementierung, nicht die
Python-Engine; behauptet wird nur Übereinstimmung auf einem erklärten Korpus.

- **Konformitätskorpus:** sechs Schaltungen mit einer dichten NumPy-Referenz werden durch
  den WASM-Kern gespielt; verglichen werden Amplituden (nicht nur Wahrscheinlichkeiten)
  mit `1e-12`. Ein Test verfälscht absichtlich einen Matrixeintrag und muss fehlschlagen.
- **Bundle-Budget:** `npm run build` schlägt über 270 KB gzip JavaScript, 18 KB WASM und
  8 KB CSS fehl; gemessen am 2026-11-02: 233,5 / 15,0 / 6,6 KB.
- **Delivery-Check:** `npm run verify:deploy -- <url>` prüft Shell, Security-Header,
  WASM-MIME-Typ und Cache-Policy. Das Production-Deployment von `1d38df2` bestand 10/10 -
  über `vercel curl`, weil das Deployment durch Vercel Deployment Protection geschützt ist;
  das Skript sagt das, statt eine öffentliche URL zu behaupten.

- **Korpus mit unabhängigem Orakel:** sechs OpenQASM-Fälle werden vom Browser-Parser
  gelesen und mit **Qiskit 2.5.1 Statevector** bei `1e-12` verglichen; ein Test vertauscht
  ein CNOT und muss fehlschlagen. Messung auf 12/16/20 Qubits: 0,20 / 4,08 / 111,5 ms
  Median. WebGPU hat hier **keine** Zahl — das mitgelieferte Chromium liefert keinen
  Adapter, also steht dort `NOT RUN` statt einer geratenen Zahl.
  [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md).

Details: [`docs/WEB_ENGINES.md`](docs/WEB_ENGINES.md).

## OMNIWAVE

Erschöpfende Cube-Suche mit geprüften UNSAT-Beweisen, plus eine optionale gelernte
Branch-Heuristik. Unterstützt mit klarem Umfang:

- `SAT` nur mit einem gegen die Original-CNF geprüften Modell, `UNSAT` nur mit einem von
  `cqhecs.drat` akzeptierten Beweis, sonst `UNKNOWN`.
- Propaganations-Neufassung am 2026-11-02: SHA-256-Instanz W=16 r=8 von 0,26 s auf
  0,11 s (2,4×), Pigeonhole praktisch unverändert (die Kosten liegen dort in der Zahl der
  Fronts).
- Gelernte Branch-Heuristik ist eingebaut, **standardmäßig aus** und wird nicht beworben:
  auf der zurückgehaltenen Pigeonhole-Instanz braucht sie 157 973 Fronts statt 10 079.
- Referenz: [`docs/OMNIWAVE.md`](docs/OMNIWAVE.md).

## Verifikation (exakter Stand `c854560` und danach)

| Prüfung | Ergebnis |
|---|---|
| Python-Suite, Linux / Python 3.11 | 2786 bestanden, 7 übersprungen |
| Python-Suite, Windows / Python 3.11 | 2690 bestanden, 53 übersprungen |
| CTest (nativ, Release) | 21/21 |
| Mutationstests | 60/60 getötet |
| Web-Unit-Tests | 39/39 |
| Playwright + axe | 41/41 |
| Einheitlicher Solver | 0 Abweichungen zwischen vier Engines auf fünf Familien |
| Geräte-Kampagne | 8 Blöcke, 512 Runden, alle vom Python-Replay und vom Host-C bestätigt |
| OTA über WLAN | HTTP 200 in 23,2 s, Gerät lief wieder auf `ota_0`, Mining automatisch fortgesetzt |

## Schnellstart

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
python -m pip install -e ".[dev]"

cq-hecs selftest --cases 4
cq-hecs sat solve --random 40 --engine unified
python -m pytest tests/ -q
```

## Grenzen

- Die vier Simulationspfade A–D sind klassische Emulation, keine QPU-Ausführung.
- Noise-Modelle sind mathematische Modelle; gemessene Kalibrierung ist als solche markiert.
- Der Browser läuft nicht die Python-Engine; die Web-Seite dokumentiert die gemessenen
  Ergebnisse, sie behauptet keinen Client-seitigen OMNIWAVE.
- Der Miner ist ein einzelnes, ausdrücklich freigegebenes Gerät; andere Geräte im Netz
  werden nicht kontaktiert.

## Dokumentation

| Thema | Datei |
|---|---|
| Einheitlicher Solver | [`docs/UNIFIED_SOLVER.md`](docs/UNIFIED_SOLVER.md) |
| OMNIWAVE | [`docs/OMNIWAVE.md`](docs/OMNIWAVE.md) |
| Lokale Bridge | [`docs/LOCAL_BRIDGE.md`](docs/LOCAL_BRIDGE.md) |
| SHA-Rundenanalyse | [`docs/SHA_ROUND_ANALYZER.md`](docs/SHA_ROUND_ANALYZER.md) |
| Forschungsakte | [`research/sha_forge/`](research/sha_forge/) (Englisch) |

## Lizenz

Apache-2.0. Siehe [`LICENSE`](LICENSE).
