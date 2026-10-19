# CQ-HECS von aktuellem Stand zu v2.0.0 — Audit und Roadmap

**Repository:** https://github.com/timfromhcs/CQ-HECS  
**Audierter Main-Commit:** `dd59c0c4e60e0ba7b95194798dccba288786db53` (19. Oktober 2026)  
**Bestehender Release:** `v0.2.0`  
**Ziel:** fachlich belastbares v2.0.0, mit neuen klassischen Quantensimulationsmethoden, vollständigen Korrektheitsprüfungen, lokalem und Cloud-CI/CD, geprüften Release-Artefakten und abschließend aktualisierter README.

> Diese Bewertung basiert auf dem sichtbaren GitHub-Quellcode, Commit-/PR-Historie, Workflows und CI-Ergebnissen. Es wurde keine Ausführung auf deiner lokalen Hardware vorgenommen. Ein grüner CI-Lauf belegt nur die eingerichteten Tests, nicht automatisch alle mathematischen Aussagen.

## 1. Wo das Repository heute steht

Am 19. Oktober 2026 wurde PR #1 — **„fix: eliminate fabricated results, silent truncation and fail-open routing“** — in `main` gemergt. Der CI-Lauf zum Merge-Commit bestand unter Ubuntu und Windows: https://github.com/timfromhcs/CQ-HECS/actions/runs/39242815214.

Der Merge ist eine echte Verbesserung: Die Änderungen haben Fälle angefasst, in denen Backends Ergebnisse erfunden oder falsch interpretiert hatten, unbekannte Gates ignorierten, Qiskit-Bitstrings falsch abbildeten oder bei nativer Nichtverfügbarkeit plausibel aussehende Fake-Counts ausgaben. Zusätzlich gibt es jetzt eine `cq-hecs`-CLI, gemeinsame Parsing-Infrastruktur, bessere Versionsprüfungen und Correctness-Contract-Tests.

Das ist eine brauchbare Basis für v2 — aber nicht das Ende des Audits.

### Was gut ist

- Getrennte Python-Simulationspfade und ein eigenständiger C++20/Vulkan-Core.
- Qiskit BackendV2-Integration und gemeinsame Parser-/CLI-Richtung.
- Automatisierte Linux- und Windows-CI mit Python-Tests, CMake, CTest und Shader-Validierung.
- Explizite Zustände und erste Trennung zwischen Approximation, numerischem Fehler und Sampling.
- Mehrere frühere Fehler wurden im Changelog benannt und Regressionstests hinzugefügt, statt sie nur in der Doku zu kaschieren.
- Release-Version, SBOM und Checksums werden zunehmend aus einer gemeinsamen Version abgeleitet.

### Noch klar offene Themen

1. Der Samplingfehler-Helper in `cqhecs/result.py` nennt eine dimensionfreie Hoeffding-Formel eine TV-Distanz-Schranke für eine beliebige kategoriale Verteilung. Eine solche Schranke ist für beliebig große Support-Mengen nicht allgemein gültig; die Garantie muss korrekt hergeleitet und support-/metrikspezifisch gemacht werden.
2. Der Mutation-Harness in `scripts/run_mutation_tests.py` zählt in mehreren Fällen einen defekten Baselinezustand als „killed“ und beendet `main()` auch bei überlebenden Mutanten mit Code 0. Der Harness muss selbst fail-closed werden, bevor sein Score ein Release-Kriterium ist.
3. Path C nutzt numerische SVD und entfernt Werte unter einer relativen Rundungsschwelle. Die gemeldete Summe der verworfenen Singulärwerte muss auf die tatsächlich zugesicherte Fehlergröße abgebildet werden; andernfalls ist sie eine Diagnose/Schätzung, keine universelle Zertifizierung.
4. Path B rechnet in Python mit komplexer Gleitkommaarithmetik und hat eine enge Statevector-Grenze. „Exakt“ muss mathematisch und numerisch sauber unterschieden werden.
5. Path D kann bestimmte Erwartungswerte mit einer Pauli-Trunkierungsgrenze absichern; das zertifiziert nicht automatisch eine gemeinsame Messverteilung.
6. `README.md` enthält weiterhin nicht belegte Hardware-/Exaktheits-/VRAM-Aussagen, die dem aktuellen Changelog und der Hardwarematrix widersprechen. Gemäß Anforderung soll sie erst am Ende bearbeitet werden.
7. `RELEASE_NOTES.md` ist historisch auf v0.1.0 ausgerichtet; der aktuelle Release-Workflow kopiert den Inhalt in eine versionierte Datei. Für v2 muss der Inhalt selbst stimmen, nicht nur der Dateiname.
8. `docs/USAGE_GUIDE.md` beschreibt teilweise alte native CLI-Aufrufe und Telemetrie. Sie muss auf die tatsächlich unterstützte Oberfläche angepasst werden.
9. Historische Benchmarks in `docs/BENCHMARKS.md` sind sinnvollerweise als STALE markiert; keine alten Tabellen als v2-Messwerte übernehmen.
10. CPU-Python, Software-Vulkan, Vulkan-Loader und physische GPU-Ausführung sind unterschiedliche Verifikationsstufen. Shader-Kompilierung allein beweist keine physische GPU-Beschleunigung.

## 2. Reihenfolge bis v2.0.0

### Phase A — Baseline sichern

- Live-`main`, neueste Commits, PRs, Tags, Releases und Cloud-CI erneut abrufen.
- Sauberen Git-Status und genaue Start-SHA sichern.
- Vollständige lokale Baseline laufen lassen: pytest, CTest, CMake, Shader-Audit, Version-Audit, Trunkierungs-/Fabrication-Audit, Mutation-Harness und Installations-Smoke-Test.
- Alle Ergebnisse als pass/fail/skip/not-run und mit Kommandos/Versionen festhalten.

**Gate:** Baseline ist reproduzierbar; alle fehlgeschlagenen oder übersprungenen Prüfungen sind erklärt.

### Phase B — Resultate und mathematische Korrektheit reparieren

- Samplingfehler formal korrekt machen; TV-Verteilungsgrenzen berücksichtigen den Support/Anzahl möglicher Ausgänge oder die API liefert pro Observable gültige Konzentrationsgrenzen.
- Fehlerfelder nur addieren, wenn sie dieselbe Zielmetrik mit gültiger Komposition beschreiben.
- `exact`, floating-point, approximation, sampling error, state und output kind voneinander trennen.
- Mutationtest so umbauen, dass ein kaputter Baselinezustand das Harness fehlschlagen lässt und jeder überlebende Mutant einen non-zero Exit erzeugt.
- Path A/B/C/D gegen Qiskit Statevector/Aer bzw. Stim testen; unbekannte Gates müssen abgelehnt werden; nie Fake-Counts erzeugen.
- MPS-Paging, temporäre Dateien, Budgets, Ausnahmen, teilweise mutierte Zustände und konkurrierende Runs testen.
- Qiskit BackendV2-Job-/Result-Semantik und klassische Register-Mappings prüfen.

**Gate:** Jede bekannte Klasse früherer Falschresultate hat einen eigenständigen Verhaltenstest. Ergebnisverträge versprechen nur, was wirklich belegt ist.

### Phase C — Methodenkatalog und Forschung

Untersuche, prototypisiere und bewerte alle für CQ-HECS relevanten Verfahren. Für jedes Verfahren Ergebnis dokumentieren: Implementieren, integrieren, experimentell lassen, später verschieben oder ablehnen — jeweils mit Begründung und Vergleichsmessung.

| Methode | Warum prüfen? | Was sie nicht verspricht |
|---|---|---|
| Dense Statevector | Referenz für kleine Schaltungen, einfache korrekte Baseline | Keine effiziente Lösung beliebig großer Zustände |
| Stabilizer Tableau | Sehr effizient für geeignete Clifford-Schaltungen | Kein universeller Simulator |
| Stabilizer Rank/Extent | Nutzt kleine Nicht-Clifford-Ressourcen aus | Skaliert bei zunehmender Nicht-Clifford-Komplexität schlecht |
| MPS / Tensor Trains | Komprimiert Strukturen mit begrenzter Bond-Dimension | Volume-Law-/dichte Schaltungen können teuer werden |
| Allgemeine Tensor-Netzwerke | Unterschiedliche Graph-Topologien und Kontraktionsreihenfolgen | Gute Kontraktion ist nicht für jeden Graphen günstig |
| Schrödinger–Feynman / Circuit Partitioning | RAM gegen Laufzeit über Schaltungsschnitte tauschen | Schnittkosten können exponentiell wachsen |
| Decision Diagrams (QMDD/QuIDD) | Komprimieren wiederholte/regelmäßige Amplitudenstruktur | Vorteil stark problemabhängig; Lizenz und Wartung prüfen |
| Feynman Path Sum | Vorteil bei günstiger Pfadstruktur möglich | Anzahl relevanter Pfade kann explodieren |
| Heisenberg-/Sparse-Pauli | Berechnet Observablen ohne vollständige Wellenfunktion | Lokale Observable-Schranke ist keine Gesamtverteilungsgarantie |
| Symmetrie-/Subraumreduktion | Reduziert Dimension, wenn Invarianten sicher erkannt werden | Unsichere Symmetrieannahmen verfälschen Ergebnisse |
| ZX-/Graph-State-Rewrites | Hilfreich bei geeigneten graph-/stabilisatorlastigen Aufgaben | Kein universeller Ersatz für Simulation |
| Monte Carlo/Quasiprobability | Kann große Zustände statistisch behandeln | Varianz/Sample-Anforderungen müssen berichtet werden |
| Noisy trajectories / Density matrix / MPO | Relevanz für verrauschte/mixed-state Schaltungen | Dichtematrizen sind ressourcenintensiv; Genauigkeit bleibt zu prüfen |
| Circuit Cutting | Parallelisiert oder partitioniert Schaltungen | Overhead und kombinierte Schätzfehler dürfen nicht verschwiegen werden |
| CPU-SIMD/Threading/GPU | Reale Laufzeitoptimierung nach Korrektheit | Ein einzelner Benchmark beweist keinen allgemeinen Vorteil |

OpenAI Math (`https://github.com/openai/math`) ist eine Quelle für Hypothesen und Beweismethoden, kein fertiger Simulator. Kataloge und Paper-Zahlen ändern sich; am Live-Stand orientieren. Für jeden Treffer präzise Aussage, Voraussetzungen, Komplexitätsmodell, Formalisierungsstatus, Primärquelle und Anwendbarkeit dokumentieren. Ein unformalisiertes Manuskript nicht als bewiesen übernehmen; ein formalisiertes Lemma muss genau die benötigte Aussage treffen.

**Gate:** `research/v2/METHOD_CATALOG.md`, Literaturkarte, Hypothesen und Testprotokolle sind vorhanden. Jede implementierte neue Methode hat klaren Nutzwert und Tests; verworfene Methoden haben nachvollziehbare Gründe.

### Phase D — Gemeinsame Architektur und UX

- Einheitliche IR und Capability-API für Parser, Router und Backend.
- Keine Default-Route für unbekannte Circuit-Typen, keine stillen Fallbacks, keine generischen Exceptions als normale Eskalation.
- Backend muss Fähigkeit, Ressourcenschätzung und Output-/Fehlervertrag liefern.
- `cq-hecs`-CLI und native C++-CLI klar unterscheiden; JSON/Exit-Code-Verträge stabilisieren.
- CPU-only Installation und Vulkan-native Funktion separat bauen/testen; native Beschleunigung nur behaupten, wenn der entsprechende Code tatsächlich dispatcht.
- Kein großes Frontend vor stabilem API-Vertrag; GUI ist optional, nicht v2-Blocker.

### Phase E — Benchmarks, Fuzzing und Zuverlässigkeit

Testfamilien: Bell/GHZ, random Clifford, Clifford+T, QFT/controlled phase, 1D/2D cluster, brickwork, low/high entanglement, circuit partitions, symmetrische Schaltungen, verrauschte Fälle für tatsächlich implementierte Methoden, unsupported gates und malformed QASM.

Jeder Benchmark enthält Commit, Version, OS, CPU/GPU/Driver, Compiler/Flags, Python-Dependencies, Methode, Circuit/Seed, Qubits/Gates/Shots/Toleranz, Outputart, Zeit/RSS/VRAM nur wenn wirklich gemessen, Error-/Confidence-Metrik und Status. Small exact tests gegen Qiskit Statevector/Aer; Stabilizer-Fälle gegen Stim. Tests von zufälligem Sampling nutzen statistisch korrekte Akzeptanzbereiche statt identische Stichproben zu verlangen.

**Gate:** Vollständige pytest- und CTest-Suite, Fehler-/Property-/Fuzz-Regressions, validierte Mutationstests und Clean-Install funktionieren. Kein stilles Überspringen nativer Tests, wenn CI Native ausdrücklich prüfen soll.

### Phase F — Paketierung und Release-Härtung

- Eine Version als Quelle; checkerweit mindestens `cqhecs/__init__.py`, `pyproject.toml`, CMake, Citation, CLI, SBOM, Release Notes, Security Policy und README prüfen.
- Build-artifact-Verzeichnis sauber neu erzeugen, damit alte `.whl`/`.tar.gz` nicht in `dist` verbleiben.
- Wheel und sdist aus sauberem Checkout bauen, in frischer venv installieren und wirklich ausführen.
- Wenn native Downloadpakete versprochen sind: Windows/Linux jeweils bauen, auspacken und auf unterstützter Runner-Umgebung ausführen; sonst nur Python-Artefakte veröffentlichen.
- SBOM aus echten Abhängigkeiten erzeugen, Release-Hashes für alle Assets generieren, Herkunft auf exakten Commit referenzieren, echte Attestierung implementieren, falls behauptet.
- Release Notes, Security-Support, Benutzungsanleitung und Beispiele auf tatsächlichen v2-Stand korrigieren.

### Phase G — README ganz zuletzt

Erst wenn Code, Methodenkatalog, Testmatrix, CMake, Package und alle anderen Dokumente stabil sind, die README als letzte Source-/Dokumentationsdatei aktualisieren. Die README muss nur verifizierte Methoden, Benchmarks, Hardwarestufen, Installationswege und CLI-Kommandos präsentieren. Danach vollständige Tests und Cloud-CI nochmals starten; jede README-Änderung vor dem Tag geht durch die finale Validierung.

### Phase H — Tag und Release

- Canonical version auf `2.0.0` setzen; Releases dürfen keine veralteten v0.1.0 Notes oder Artefakte enthalten.
- Letzte Windows- und Ubuntu-Checks abwarten und deren tatsächlichen Erfolg prüfen.
- Releasecommit pushen, Tag `v2.0.0` exakt auf den geprüften Commit setzen und pushen.
- Release-Workflow beobachten; tatsächliche Dateien, Checksums, SBOM und Notes gegenprüfen. Wheel/sdist und ggf. native Archives aus sauberer Umgebung herunterladen und Smoke-Test wiederholen.
- Kein Tag/Release, wenn irgendein Mandatory Gate scheitert, Artifakte fehlen oder die Funktionen nur Stub/Marketing sind.

## 3. Qualitätstore

| Gate | Pflichtnachweis |
|---|---|
| Correctness | Backend-Verträge, differential tests, Mess-/Bitorder-/Gate-Tests, keine Fake-Counts |
| Numerical | gültige und passend beschriebene Error-/Confidence bounds |
| Router | capability-first, fail-closed, typed errors, keine stille erzwungene Umschaltung |
| Mutation | Baseline muss bestehen; überlebender Mutant/Harness-Fehler ergibt non-zero |
| Build | Out-of-tree CMake build, CTest, Python package build |
| Platforms | Windows + Ubuntu CI grün; hardware claims jeweils belegt |
| Install | frische venv, `cq-hecs --help`, `version`, `doctor`, JSON-Run und Referenzcheck |
| Docs | Commands in Docs verifiziert; historische Benchmarks gekennzeichnet; README zuletzt editiert |
| Release | korrekter Tag, Artefakte, SBOM, vollständige Hashes, release notes, clean-download smoke test |

## 4. Releaseziel und Scopegrenze

v2.0.0 soll alle nützlichen und innerhalb der Projektgrenzen verantwortbar implementierbaren Verfahren umfassen — nicht jede denkbare Forschungsrichtung als unfertige Funktion. Eine Methode wird übernommen, wenn sie korrekt umgesetzt, getestet, dokumentiert und gegenüber bestehenden Verfahren sinnvoll ist. Andernfalls wird sie im Forschungskatalog mit Bedingungen und Grund zurückgestellt.

Das Projekt soll durch v2 größere Bereiche effizient klassisch simulierbarer Aufgaben erschließen, aber kein universelles Aufheben des Quantenvorteils beanspruchen. Ein reproduzierbarer, begrenzter und mathematisch ehrlich beschriebener Fortschritt ist ein gültiges Ergebnis.
