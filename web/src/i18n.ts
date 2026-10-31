// UI strings in English, German and French. The language is chosen from the
// browser (navigator.languages) unless the visitor picked one.

export type Lang = "en" | "de" | "fr";
export const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "de", label: "Deutsch" },
  { id: "fr", label: "Français" },
];

type Dict = Record<string, string>;

const en: Dict = {
  "sat.count": "Count models (#SAT)", "sat.countResult": "{n} satisfying assignments (exact count)", "sat.countUnknown": "Budget exhausted: no count is claimed.", "sat.cert.MODEL_VERIFIED": "Evidence: the model was checked clause by clause.", "sat.cert.TREE_RESOLUTION_CHECKED": "Evidence: a tree-resolution certificate ({n} steps) was replayed by a checker that shares no code with the solver.", "sat.cert.UNCERTIFIED": "No checked certificate: this UNSAT is the solver's verdict only.", "sat.cert.NONE": "Not decided.", "res.details": "Details & export", "res.export": "Download result (JSON)", "prov.title": "What ran", "prov.engine.wasm": "Engine: WebAssembly f64 state vector. Every amplitude is kept; the only deviation is double rounding (≈1e-16 per operation).", "prov.engine.webgpu": "Engine: WebGPU f32 state vector. Single precision (≈1e-7); up to 20 qubits it is compared with the exact f64 result (TV shown).", "prov.noise.none": "Noise: none (ideal circuit).", "prov.noise.profile": "Noise: measured profile {id} (M-FIT-2, post-hoc fit), evidence in {path}.", "prov.noise.custom": "Noise: custom values set by you; not a measured device.", "prov.sampling": "Shots are random samples; the orange line in the histogram is the exact probability.", "prov.build": "Build {version} · source {sha}", "prov.not": "Not run here: the Python paths A–D, Path D certificates and real QPU jobs. They exist in the CLI and Studio, not in the browser.",
  "lab.paramPrompt": "{gate}: {n} parameter(s), e.g. pi/4, 0.3", "lab.paramBad": "Invalid parameter", "lab.aria": "Circuit with {n} qubits", "lab.erase": "Eraser: remove gates",
  "meta.title": "CQ-HECS Web · Exact quantum emulator in your browser",
  "nav.home": "Home", "nav.guide": "Guide", "nav.lab": "Lab", "nav.code": "Code", "nav.sat": "SAT",
  "nav.compare": "Devices", "nav.device": "My device", "nav.about": "About",
  "skip": "Skip to content", "theme": "Toggle light/dark", "lang": "Language",
  "chip.checking": "checking device …", "chip.limit": "exact up to {n} qubits",
  "hero.kicker": "WebAssembly f64 · WebGPU · measured QPU noise",
  "hero.title": "Quantum circuits, exactly — in your browser.",
  "hero.sub": "CQ-HECS checks your device first, then runs as many qubits as it can hold without losing a single amplitude. Add the noise of real IBM, Rigetti and IQM processors, measured on the hardware.",
  "hero.start": "Open the lab", "hero.guide": "Get started guide",
  "hero.device": "Your device", "hero.deviceWait": "Measuring CPU, memory and GPU …",
  "hero.deviceReady": "{os} · {cores} threads · {gpu}", "hero.deviceLimit": "Exact up to {n} qubits ({mem}) · {rate} M amplitude updates/s",
  "feat.title": "What it does",
  "feat.exact.t": "Exact, not approximate", "feat.exact.d": "A Rust core compiled to WebAssembly keeps all 2ⁿ amplitudes in double precision. It agrees with Qiskit to below 10⁻¹².",
  "feat.safe.t": "Safe by design", "feat.safe.d": "Your device is checked before anything runs. The qubit limit is confirmed by a real memory allocation, and runs that would take too long are refused.",
  "feat.gpu.t": "GPU when available", "feat.gpu.d": "A WebGPU compute shader runs fast single-precision simulations and is checked against the exact core every time.",
  "feat.noise.t": "Real hardware noise", "feat.noise.d": "Per-qubit readout errors, gate anomalies and two-qubit depolarizing come from runs of the same 25 circuits on real QPUs.",
  "feat.code.t": "Beginner to expert", "feat.code.d": "Build circuits by clicking, or write OpenQASM 2.0 and JavaScript. Mid-circuit measurement, reset and shareable links are included.",
  "feat.sat.t": "SAT lab", "feat.sat.d": "A sound DPLL solver with verified models, honest UNKNOWN results and a phase-transition sweep.",
  "modes.title": "Choose your mode",
  "modes.beginner": "Beginner", "modes.inter": "Intermediate", "modes.adv": "Advanced",
  "modes.lab": "Click gates onto qubit wires and watch probabilities, Bloch spheres and amplitudes.",
  "modes.guide": "A step-by-step tour from one qubit to entanglement, noise and algorithms.",
  "modes.compare": "Run one circuit on every measured device profile and compare fidelity.",
  "modes.code": "OpenQASM 2.0 and a JavaScript builder API with multi-controlled gates.",
  "modes.sat": "Solve DIMACS CNF instances and explore the 3-SAT phase transition.",
  "honest.title": "Honest by default",
  "honest.body": "This is a classical simulation, not a quantum computer. Each extra qubit doubles the memory: 27 qubits need 2 GiB, 30 would need 16 GiB. Instead of promising more with lossy tricks, the page shows the exact maximum your device can hold. Noise profiles are fitted from real runs; qubits beyond the measured ones reuse the average, and that extrapolation is marked.",
  "boot.title": "Checking your device", "boot.sub": "Before anything runs, CQ-HECS measures what your device can compute exactly.",
  "boot.os": "Operating system & browser", "boot.mem": "CPU & memory", "boot.gpu": "Graphics & WebGPU",
  "boot.wasm": "Load & benchmark the WebAssembly core", "boot.probe": "Confirm the exact limit with a memory probe",
  "boot.noWebgpu": "no WebGPU → WASM only", "boot.ramUnknown": "RAM unknown", "boot.failed": "failed",
  "lab.qubits": "Qubits", "lab.preset": "Example", "lab.empty": "— empty —", "lab.clear": "Clear",
  "lab.hint": "Pick a gate, then tap a cell. Multi-qubit gates: tap control(s) first, then the target. Right-click or the eraser removes a gate.",
  "code.toLab": "Open in lab", "code.share": "Share link", "code.copied": "Link copied ✓", "code.download": "Download .qasm",
  "code.loading": "Loading editor …", "code.api": "API reference",
  "run.shots": "Shots", "run.engine": "Engine", "run.wasm": "WebAssembly f64 · exact", "run.gpu": "WebGPU f32 · fast",
  "run.gpuNo": "WebGPU · not available", "run.noise": "Noise", "run.noise.none": "Ideal (no noise)",
  "run.noise.custom": "Custom values", "run.noise.measured": "measured",
  "run.run": "▶ Run", "run.stop": "Stop", "run.p1": "1-qubit error", "run.p2": "2-qubit error", "run.ro": "Readout error",
  "run.profileInfo": "{label}: CX depolarizing {cx} · mean readout P(1|0) {p01}, P(0|1) {p10} · H-V3-8 {verdict} · {shots} shots/circuit.",
  "run.extrap": "Qubits {from}–{to} use the average measured readout (extrapolated).",
  "run.gpuNoise": "WebGPU runs circuits without mid-circuit measurement, reset or gate noise only. Please choose WebAssembly.",
  "run.refused": "refused: {reason}", "run.cancelled": "cancelled", "run.starting": "starting …",
  "est.ok": "{n} qubits · {mem} · ≈{t}", "est.limit": "{n} qubits exceed the safe limit of {max} on this device",
  "est.time": "estimated runtime {t} s > 90 s",
  "res.hist": "Histogram", "res.table": "Table", "res.bloch": "Bloch", "res.state": "State",
  "res.empty": "No run yet. Choose an example or build a circuit and press ▶.",
  "res.measured": "measured ({n} shots)", "res.ideal": "ideal probability (exact)", "res.shown": "{a} of {b} outcomes shown",
  "res.outcome": "Outcome", "res.count": "Shots", "res.freq": "Frequency", "res.idealCol": "ideal", "res.bitorder": "Bit order: bit 0 is on the right (as in Qiskit).",
  "res.blochNone": "Bloch vectors are shown for the exact WebAssembly engine (up to 16 qubits).",
  "res.blochMixed": "entangled/mixed", "res.blochShown": "Showing {a} of {b} qubits.",
  "res.stateTop": "With {n} qubits there are 2^{n} amplitudes; the {k} most likely basis states are shown (exact).",
  "res.stateNone": "At this size no probability table is built (shots only).",
  "res.traj": "{n} trajectories", "res.tv": "TV to f64: {v}", "res.extrap": "{n} qubits extrapolated",
  "sat.title": "SAT lab", "sat.intro": "Paste a DIMACS CNF or generate one. SAT comes with a model checked clause by clause. UNSAT comes with a tree-resolution certificate that a separate checker replays. A timeout is UNKNOWN, never UNSAT. Counting models (#SAT) is a separate problem with its own exact result.",
  "sat.solve": "Solve", "sat.random": "Random 3-SAT", "sat.php": "Pigeonhole (UNSAT)", "sat.vars": "Variables", "sat.ratio": "Clauses/variable",
  "sat.timeout": "Timeout (ms)", "sat.sweep": "Phase-transition sweep", "sat.sweepNote": "Median decisions per ratio. The peak near 4.26 is the classic hardness peak. This is a finite experiment, not a complexity bound.",
  "sat.status": "Status", "sat.model": "Model", "sat.stats": "{d} decisions · {p} propagations · {c} conflicts · {t} ms",
  "cmp.title": "Device comparison", "cmp.intro": "Runs the lab circuit ideally and with every measured profile. TV is the total-variation distance to the ideal distribution: 0 is perfect, 1 is completely different.",
  "cmp.run": "Compare all devices", "cmp.device": "Device", "cmp.tv": "TV to ideal", "cmp.top": "Most likely outcome", "cmp.limit": "Comparison runs up to 14 qubits.",
  "dev.title": "Your device", "dev.limits": "Safe limits", "dev.profiles": "Measured QPU profiles",
  "dev.profilesNote": "Extracted from runs of the pinned 25-circuit r-io-7 suite (model M-FIT-2, post-hoc). H-V3-8 asks whether the fitted noise model predicts unseen circuits better than the ideal simulation.",
  "dev.reprobe": "Re-check limit", "dev.limitsNote": "An exact n-qubit state needs 16 · 2ⁿ bytes (f64). At most a quarter of reported RAM and 2 GiB of WebAssembly heap are used, and the limit is confirmed by a real allocation. Runs estimated over 90 s are refused.",
  "dev.os": "Operating system", "dev.browser": "Browser", "dev.arch": "Architecture", "dev.cores": "CPU threads",
  "dev.ram": "Memory", "dev.gpu": "GPU", "dev.webgpu": "WebGPU", "dev.webgl": "WebGL 2", "dev.simd": "WASM SIMD128", "dev.core": "WASM core",
  "dev.budget": "Memory budget", "dev.exact": "Exact (WASM f64)", "dev.fast": "Fast (WebGPU f32)", "dev.time": "Runtime limit",
  "dev.verified": "confirmed by allocation", "dev.computed": "computed", "dev.yes": "yes", "dev.no": "no", "dev.backend": "likely backend {b}",
  "dev.qubit": "qubit", "dev.p01": "P(1|0)", "dev.p10": "P(0|1)", "dev.xflip": "X flip",
  "foot.love": "Made with {heart} by {a} & {b}", "foot.sub": "Exact classical simulation · not a quantum computer",
  "err.boot": "Start failed: {e}", "err.wasm": "WebAssembly could not be loaded: {e}",
};

const de: Dict = {
  "sat.count": "Modelle zählen (#SAT)", "sat.countResult": "{n} erfüllende Belegungen (exakte Zählung)", "sat.countUnknown": "Budget erschöpft: Es wird keine Anzahl behauptet.", "sat.cert.MODEL_VERIFIED": "Beleg: Das Modell wurde Klausel für Klausel geprüft.", "sat.cert.TREE_RESOLUTION_CHECKED": "Beleg: Ein Tree-Resolution-Zertifikat ({n} Schritte) wurde von einem Prüfer nachgespielt, der keinen Code mit dem Solver teilt.", "sat.cert.UNCERTIFIED": "Kein geprüftes Zertifikat: Dieses UNSAT ist nur das Urteil des Solvers.", "sat.cert.NONE": "Nicht entschieden.", "res.details": "Details & Export", "res.export": "Ergebnis laden (JSON)", "prov.title": "Was gerechnet wurde", "prov.engine.wasm": "Engine: WebAssembly-f64-Zustandsvektor. Jede Amplitude bleibt erhalten; einzige Abweichung ist die f64-Rundung (≈1e-16 pro Operation).", "prov.engine.webgpu": "Engine: WebGPU-f32-Zustandsvektor. Einfache Genauigkeit (≈1e-7); bis 20 Qubits wird gegen das exakte f64-Ergebnis verglichen (TV angezeigt).", "prov.noise.none": "Rauschen: keins (ideale Schaltung).", "prov.noise.profile": "Rauschen: gemessenes Profil {id} (M-FIT-2, post-hoc gefittet), Evidenz in {path}.", "prov.noise.custom": "Rauschen: eigene Werte; kein gemessenes Gerät.", "prov.sampling": "Shots sind Zufallsstichproben; die orange Linie im Histogramm ist die exakte Wahrscheinlichkeit.", "prov.build": "Build {version} · Quellstand {sha}", "prov.not": "Hier nicht gerechnet: die Python-Pfade A–D, Path-D-Zertifikate und echte QPU-Jobs. Die gibt es in CLI und Studio, nicht im Browser.",
  "lab.paramPrompt": "{gate}: {n} Parameter (z. B. pi/4, 0.3)", "lab.paramBad": "Ungültiger Parameter", "lab.aria": "Schaltung mit {n} Qubits", "lab.erase": "Radierer: Gatter löschen",
  "meta.title": "CQ-HECS Web · Exakter Quanten-Emulator im Browser",
  "nav.home": "Start", "nav.guide": "Anleitung", "nav.lab": "Labor", "nav.code": "Code", "nav.sat": "SAT",
  "nav.compare": "Geräte", "nav.device": "Mein Gerät", "nav.about": "Über",
  "skip": "Zum Inhalt springen", "theme": "Hell/Dunkel umschalten", "lang": "Sprache",
  "chip.checking": "prüfe Gerät …", "chip.limit": "exakt bis {n} Qubits",
  "hero.kicker": "WebAssembly f64 · WebGPU · gemessenes QPU-Rauschen",
  "hero.title": "Quantenschaltungen, exakt – im Browser.",
  "hero.sub": "CQ-HECS prüft zuerst dein Gerät und rechnet dann so viele Qubits, wie es ohne Verlust einer einzigen Amplitude halten kann. Dazu kommt das Rauschen echter IBM-, Rigetti- und IQM-Prozessoren, gemessen auf der Hardware.",
  "hero.start": "Labor öffnen", "hero.guide": "Einstiegsanleitung",
  "hero.device": "Dein Gerät", "hero.deviceWait": "Messe CPU, Speicher und GPU …",
  "hero.deviceReady": "{os} · {cores} Threads · {gpu}", "hero.deviceLimit": "Exakt bis {n} Qubits ({mem}) · {rate} Mio. Amplituden-Updates/s",
  "feat.title": "Was es kann",
  "feat.exact.t": "Exakt statt genähert", "feat.exact.d": "Ein Rust-Kern als WebAssembly hält alle 2ⁿ Amplituden in doppelter Genauigkeit. Er stimmt mit Qiskit auf unter 10⁻¹² überein.",
  "feat.safe.t": "Sicher by Design", "feat.safe.d": "Dein Gerät wird vor jedem Lauf geprüft. Das Qubit-Limit wird durch eine echte Speicherreservierung bestätigt; zu lange Läufe werden abgelehnt.",
  "feat.gpu.t": "GPU, wenn vorhanden", "feat.gpu.d": "Ein WebGPU-Compute-Shader rechnet schnell in einfacher Genauigkeit und wird jedes Mal gegen den exakten Kern geprüft.",
  "feat.noise.t": "Echtes Hardware-Rauschen", "feat.noise.d": "Ausleseraten pro Qubit, Gatter-Anomalien und Zwei-Qubit-Depolarisierung stammen aus Läufen derselben 25 Schaltungen auf echten QPUs.",
  "feat.code.t": "Vom Einstieg bis zum Profi", "feat.code.d": "Schaltungen per Klick bauen oder OpenQASM 2.0 und JavaScript schreiben. Messung mitten in der Schaltung, Reset und Teilen per Link sind dabei.",
  "feat.sat.t": "SAT-Labor", "feat.sat.d": "Ein solider DPLL-Solver mit verifizierten Modellen, ehrlichem UNKNOWN und Phasenübergangs-Sweep.",
  "modes.title": "Wähle deinen Modus",
  "modes.beginner": "Einsteiger", "modes.inter": "Fortgeschritten", "modes.adv": "Profi",
  "modes.lab": "Gatter auf Qubit-Leitungen klicken und Wahrscheinlichkeiten, Bloch-Kugeln und Amplituden beobachten.",
  "modes.guide": "Schritt für Schritt vom einzelnen Qubit zu Verschränkung, Rauschen und Algorithmen.",
  "modes.compare": "Eine Schaltung auf allen gemessenen Geräteprofilen laufen lassen und die Treue vergleichen.",
  "modes.code": "OpenQASM 2.0 und eine JavaScript-API mit mehrfach kontrollierten Gattern.",
  "modes.sat": "DIMACS-CNF-Instanzen lösen und den 3-SAT-Phasenübergang erkunden.",
  "honest.title": "Ehrlich von Anfang an",
  "honest.body": "Das ist eine klassische Simulation, kein Quantencomputer. Jedes weitere Qubit verdoppelt den Speicher: 27 Qubits brauchen 2 GiB, 30 bräuchten 16 GiB. Statt mit verlustbehafteten Tricks mehr zu versprechen, zeigt die Seite das exakte Maximum deines Geräts. Die Rauschprofile sind aus echten Läufen gefittet; Qubits jenseits der gemessenen nutzen den Mittelwert, und diese Extrapolation wird angezeigt.",
  "boot.title": "Gerät wird geprüft", "boot.sub": "Bevor etwas läuft, misst CQ-HECS, was dein Gerät exakt rechnen kann.",
  "boot.os": "Betriebssystem & Browser", "boot.mem": "CPU & Arbeitsspeicher", "boot.gpu": "Grafikkarte & WebGPU",
  "boot.wasm": "WebAssembly-Kern laden & messen", "boot.probe": "Exaktes Limit per Speicher-Probe bestätigen",
  "boot.noWebgpu": "kein WebGPU → nur WASM", "boot.ramUnknown": "RAM unbekannt", "boot.failed": "fehlgeschlagen",
  "lab.qubits": "Qubits", "lab.preset": "Beispiel", "lab.empty": "— leer —", "lab.clear": "Leeren",
  "lab.hint": "Gatter wählen, dann auf eine Zelle tippen. Mehr-Qubit-Gatter: zuerst Kontrolle(n), dann Ziel. Rechtsklick oder Radierer löscht.",
  "code.toLab": "Ins Labor laden", "code.share": "Link teilen", "code.copied": "Link kopiert ✓", "code.download": ".qasm laden",
  "code.loading": "Editor wird geladen …", "code.api": "API-Referenz",
  "run.shots": "Shots", "run.engine": "Engine", "run.wasm": "WebAssembly f64 · exakt", "run.gpu": "WebGPU f32 · schnell",
  "run.gpuNo": "WebGPU · nicht verfügbar", "run.noise": "Rauschen", "run.noise.none": "Ideal (ohne Rauschen)",
  "run.noise.custom": "Eigene Werte", "run.noise.measured": "gemessen",
  "run.run": "▶ Ausführen", "run.stop": "Stopp", "run.p1": "1-Qubit-Fehler", "run.p2": "2-Qubit-Fehler", "run.ro": "Auslesefehler",
  "run.profileInfo": "{label}: CX-Depolarisierung {cx} · mittleres Auslesen P(1|0) {p01}, P(0|1) {p10} · H-V3-8 {verdict} · {shots} Shots/Schaltung.",
  "run.extrap": "Qubits {from}–{to} nutzen das mittlere gemessene Auslesen (extrapoliert).",
  "run.gpuNoise": "WebGPU rechnet nur Schaltungen ohne Mitte-Messung, Reset und Gatter-Rauschen. Bitte WebAssembly wählen.",
  "run.refused": "abgelehnt: {reason}", "run.cancelled": "abgebrochen", "run.starting": "starte …",
  "est.ok": "{n} Qubits · {mem} · ≈{t}", "est.limit": "{n} Qubits überschreiten das sichere Limit von {max} auf diesem Gerät",
  "est.time": "geschätzte Laufzeit {t} s > 90 s",
  "res.hist": "Histogramm", "res.table": "Tabelle", "res.bloch": "Bloch", "res.state": "Zustand",
  "res.empty": "Noch kein Lauf. Wähle ein Beispiel oder baue eine Schaltung und drücke ▶.",
  "res.measured": "gemessen ({n} Shots)", "res.ideal": "ideale Wahrscheinlichkeit (exakt)", "res.shown": "{a} von {b} Ausgängen gezeigt",
  "res.outcome": "Ausgang", "res.count": "Shots", "res.freq": "Häufigkeit", "res.idealCol": "ideal", "res.bitorder": "Bitreihenfolge: rechts steht Bit 0 (wie Qiskit).",
  "res.blochNone": "Bloch-Vektoren gibt es im exakten WebAssembly-Modus (bis 16 Qubits angezeigt).",
  "res.blochMixed": "verschränkt/gemischt", "res.blochShown": "Gezeigt: {a} von {b} Qubits.",
  "res.stateTop": "Bei {n} Qubits gibt es 2^{n} Amplituden; gezeigt sind die {k} wahrscheinlichsten Basiszustände (exakt).",
  "res.stateNone": "Bei dieser Größe wird keine Wahrscheinlichkeitstabelle gebaut (nur Shots).",
  "res.traj": "{n} Trajektorien", "res.tv": "TV zu f64: {v}", "res.extrap": "{n} Qubits extrapoliert",
  "sat.title": "SAT-Labor", "sat.intro": "DIMACS-CNF einfügen oder erzeugen. SAT kommt mit einem Klausel für Klausel geprüften Modell. UNSAT kommt mit einem Tree-Resolution-Zertifikat, das ein separater Prüfer nachspielt. Ein Timeout ist UNKNOWN, nie UNSAT. Modellzählen (#SAT) ist ein eigenes Problem mit eigenem exaktem Ergebnis.",
  "sat.solve": "Lösen", "sat.random": "Zufalls-3-SAT", "sat.php": "Schubfach (UNSAT)", "sat.vars": "Variablen", "sat.ratio": "Klauseln/Variable",
  "sat.timeout": "Timeout (ms)", "sat.sweep": "Phasenübergangs-Sweep", "sat.sweepNote": "Median der Entscheidungen pro Verhältnis. Die Spitze nahe 4,26 ist das klassische Härtemaximum. Ein endliches Experiment, keine Komplexitätsschranke.",
  "sat.status": "Status", "sat.model": "Modell", "sat.stats": "{d} Entscheidungen · {p} Propagationen · {c} Konflikte · {t} ms",
  "cmp.title": "Gerätevergleich", "cmp.intro": "Rechnet die Labor-Schaltung ideal und mit jedem gemessenen Profil. TV ist der Totalvariationsabstand zur idealen Verteilung: 0 ist perfekt, 1 völlig verschieden.",
  "cmp.run": "Alle Geräte vergleichen", "cmp.device": "Gerät", "cmp.tv": "TV zu ideal", "cmp.top": "Häufigster Ausgang", "cmp.limit": "Der Vergleich läuft bis 14 Qubits.",
  "dev.title": "Dein Gerät", "dev.limits": "Sichere Limits", "dev.profiles": "Gemessene QPU-Profile",
  "dev.profilesNote": "Extrahiert aus Läufen der festgelegten 25-Schaltungen-Suite r-io-7 (Modell M-FIT-2, post-hoc). H-V3-8 fragt, ob das gefittete Rauschmodell ungesehene Schaltungen besser vorhersagt als die ideale Simulation.",
  "dev.reprobe": "Limit erneut prüfen", "dev.limitsNote": "Ein exakter Zustand mit n Qubits braucht 16 · 2ⁿ Byte (f64). Genutzt wird höchstens ein Viertel des gemeldeten RAMs und 2 GiB WebAssembly-Heap; das Limit wird durch eine echte Reservierung bestätigt. Läufe über 90 s geschätzt werden abgelehnt.",
  "dev.os": "Betriebssystem", "dev.browser": "Browser", "dev.arch": "Architektur", "dev.cores": "CPU-Threads",
  "dev.ram": "Arbeitsspeicher", "dev.gpu": "GPU", "dev.webgpu": "WebGPU", "dev.webgl": "WebGL 2", "dev.simd": "WASM SIMD128", "dev.core": "WASM-Kern",
  "dev.budget": "Speicherbudget", "dev.exact": "Exakt (WASM f64)", "dev.fast": "Schnell (WebGPU f32)", "dev.time": "Laufzeit-Grenze",
  "dev.verified": "durch Reservierung bestätigt", "dev.computed": "berechnet", "dev.yes": "ja", "dev.no": "nein", "dev.backend": "Backend wahrscheinlich {b}",
  "dev.qubit": "Qubit", "dev.p01": "P(1|0)", "dev.p10": "P(0|1)", "dev.xflip": "X-Flip",
  "foot.love": "Made with {heart} by {a} & {b}", "foot.sub": "Exakte klassische Simulation · kein Quantencomputer",
  "err.boot": "Start fehlgeschlagen: {e}", "err.wasm": "WebAssembly konnte nicht geladen werden: {e}",
};

const fr: Dict = {
  "sat.count": "Compter les modèles (#SAT)", "sat.countResult": "{n} affectations satisfaisantes (comptage exact)", "sat.countUnknown": "Budget épuisé : aucun nombre n'est affirmé.", "sat.cert.MODEL_VERIFIED": "Preuve : le modèle a été vérifié clause par clause.", "sat.cert.TREE_RESOLUTION_CHECKED": "Preuve : un certificat de résolution en arbre ({n} étapes) a été rejoué par un vérificateur qui ne partage aucun code avec le solveur.", "sat.cert.UNCERTIFIED": "Aucun certificat vérifié : cet UNSAT n'est que le verdict du solveur.", "sat.cert.NONE": "Non décidé.", "res.details": "Détails et export", "res.export": "Télécharger le résultat (JSON)", "prov.title": "Ce qui a été calculé", "prov.engine.wasm": "Moteur : vecteur d'état WebAssembly f64. Chaque amplitude est conservée ; seul l'arrondi double (≈1e-16 par opération) s'écarte.", "prov.engine.webgpu": "Moteur : vecteur d'état WebGPU f32. Simple précision (≈1e-7) ; jusqu'à 20 qubits il est comparé au résultat f64 exact (TV affiché).", "prov.noise.none": "Bruit : aucun (circuit idéal).", "prov.noise.profile": "Bruit : profil mesuré {id} (M-FIT-2, ajusté a posteriori), données dans {path}.", "prov.noise.custom": "Bruit : valeurs personnalisées ; pas un appareil mesuré.", "prov.sampling": "Les tirs sont des échantillons aléatoires ; la ligne orange de l'histogramme est la probabilité exacte.", "prov.build": "Build {version} · source {sha}", "prov.not": "Non calculé ici : les chemins Python A–D, les certificats du chemin D et les vrais jobs QPU. Ils existent dans la CLI et le Studio, pas dans le navigateur.",
  "lab.paramPrompt": "{gate} : {n} paramètre(s), ex. pi/4, 0.3", "lab.paramBad": "Paramètre invalide", "lab.aria": "Circuit à {n} qubits", "lab.erase": "Gomme : supprimer des portes",
  "meta.title": "CQ-HECS Web · Émulateur quantique exact dans le navigateur",
  "nav.home": "Accueil", "nav.guide": "Guide", "nav.lab": "Labo", "nav.code": "Code", "nav.sat": "SAT",
  "nav.compare": "Appareils", "nav.device": "Mon appareil", "nav.about": "À propos",
  "skip": "Aller au contenu", "theme": "Mode clair/sombre", "lang": "Langue",
  "chip.checking": "analyse de l'appareil …", "chip.limit": "exact jusqu'à {n} qubits",
  "hero.kicker": "WebAssembly f64 · WebGPU · bruit QPU mesuré",
  "hero.title": "Des circuits quantiques, exactement — dans votre navigateur.",
  "hero.sub": "CQ-HECS analyse d'abord votre appareil, puis simule autant de qubits qu'il peut contenir sans perdre une seule amplitude. Ajoutez le bruit de vrais processeurs IBM, Rigetti et IQM, mesuré sur le matériel.",
  "hero.start": "Ouvrir le labo", "hero.guide": "Guide de démarrage",
  "hero.device": "Votre appareil", "hero.deviceWait": "Mesure du CPU, de la mémoire et du GPU …",
  "hero.deviceReady": "{os} · {cores} threads · {gpu}", "hero.deviceLimit": "Exact jusqu'à {n} qubits ({mem}) · {rate} M mises à jour d'amplitude/s",
  "feat.title": "Ce qu'il fait",
  "feat.exact.t": "Exact, pas approché", "feat.exact.d": "Un cœur Rust compilé en WebAssembly conserve les 2ⁿ amplitudes en double précision. Il concorde avec Qiskit à moins de 10⁻¹².",
  "feat.safe.t": "Sûr par conception", "feat.safe.d": "Votre appareil est vérifié avant chaque exécution. La limite de qubits est confirmée par une vraie allocation mémoire ; les calculs trop longs sont refusés.",
  "feat.gpu.t": "GPU si disponible", "feat.gpu.d": "Un shader de calcul WebGPU simule rapidement en simple précision et est vérifié à chaque fois par le cœur exact.",
  "feat.noise.t": "Bruit matériel réel", "feat.noise.d": "Erreurs de lecture par qubit, anomalies de porte et dépolarisation à deux qubits proviennent des 25 mêmes circuits exécutés sur de vrais QPU.",
  "feat.code.t": "Du débutant à l'expert", "feat.code.d": "Construisez des circuits en cliquant, ou écrivez de l'OpenQASM 2.0 et du JavaScript. Mesure en cours de circuit, reset et liens partageables inclus.",
  "feat.sat.t": "Labo SAT", "feat.sat.d": "Un solveur DPLL correct avec modèles vérifiés, UNKNOWN honnête et balayage de la transition de phase.",
  "modes.title": "Choisissez votre mode",
  "modes.beginner": "Débutant", "modes.inter": "Intermédiaire", "modes.adv": "Avancé",
  "modes.lab": "Placez des portes sur les fils et observez probabilités, sphères de Bloch et amplitudes.",
  "modes.guide": "Une visite pas à pas, d'un qubit à l'intrication, au bruit et aux algorithmes.",
  "modes.compare": "Exécutez un circuit sur chaque profil d'appareil mesuré et comparez la fidélité.",
  "modes.code": "OpenQASM 2.0 et une API JavaScript avec portes multi-contrôlées.",
  "modes.sat": "Résolvez des CNF DIMACS et explorez la transition de phase de 3-SAT.",
  "honest.title": "Honnête par défaut",
  "honest.body": "Ceci est une simulation classique, pas un ordinateur quantique. Chaque qubit supplémentaire double la mémoire : 27 qubits demandent 2 Gio, 30 en demanderaient 16. Plutôt que de promettre plus avec des astuces avec perte, la page affiche le maximum exact de votre appareil. Les profils de bruit sont ajustés sur de vraies exécutions ; les qubits au-delà de ceux mesurés reprennent la moyenne, et cette extrapolation est signalée.",
  "boot.title": "Analyse de l'appareil", "boot.sub": "Avant toute exécution, CQ-HECS mesure ce que votre appareil peut calculer exactement.",
  "boot.os": "Système et navigateur", "boot.mem": "CPU et mémoire", "boot.gpu": "Carte graphique et WebGPU",
  "boot.wasm": "Charger et mesurer le cœur WebAssembly", "boot.probe": "Confirmer la limite exacte par allocation",
  "boot.noWebgpu": "pas de WebGPU → WASM seul", "boot.ramUnknown": "RAM inconnue", "boot.failed": "échec",
  "lab.qubits": "Qubits", "lab.preset": "Exemple", "lab.empty": "— vide —", "lab.clear": "Effacer",
  "lab.hint": "Choisissez une porte puis touchez une case. Portes multi-qubits : contrôle(s) d'abord, puis la cible. Clic droit ou gomme pour supprimer.",
  "code.toLab": "Ouvrir dans le labo", "code.share": "Partager le lien", "code.copied": "Lien copié ✓", "code.download": "Télécharger .qasm",
  "code.loading": "Chargement de l'éditeur …", "code.api": "Référence API",
  "run.shots": "Tirs", "run.engine": "Moteur", "run.wasm": "WebAssembly f64 · exact", "run.gpu": "WebGPU f32 · rapide",
  "run.gpuNo": "WebGPU · indisponible", "run.noise": "Bruit", "run.noise.none": "Idéal (sans bruit)",
  "run.noise.custom": "Valeurs personnalisées", "run.noise.measured": "mesuré",
  "run.run": "▶ Exécuter", "run.stop": "Arrêter", "run.p1": "Erreur 1 qubit", "run.p2": "Erreur 2 qubits", "run.ro": "Erreur de lecture",
  "run.profileInfo": "{label} : dépolarisation CX {cx} · lecture moyenne P(1|0) {p01}, P(0|1) {p10} · H-V3-8 {verdict} · {shots} tirs/circuit.",
  "run.extrap": "Les qubits {from}–{to} utilisent la lecture moyenne mesurée (extrapolée).",
  "run.gpuNoise": "WebGPU n'exécute que des circuits sans mesure intermédiaire, reset ni bruit de porte. Choisissez WebAssembly.",
  "run.refused": "refusé : {reason}", "run.cancelled": "annulé", "run.starting": "démarrage …",
  "est.ok": "{n} qubits · {mem} · ≈{t}", "est.limit": "{n} qubits dépassent la limite sûre de {max} sur cet appareil",
  "est.time": "durée estimée {t} s > 90 s",
  "res.hist": "Histogramme", "res.table": "Tableau", "res.bloch": "Bloch", "res.state": "État",
  "res.empty": "Aucune exécution. Choisissez un exemple ou construisez un circuit et appuyez sur ▶.",
  "res.measured": "mesuré ({n} tirs)", "res.ideal": "probabilité idéale (exacte)", "res.shown": "{a} sur {b} résultats affichés",
  "res.outcome": "Résultat", "res.count": "Tirs", "res.freq": "Fréquence", "res.idealCol": "idéal", "res.bitorder": "Ordre des bits : le bit 0 est à droite (comme Qiskit).",
  "res.blochNone": "Les vecteurs de Bloch sont affichés avec le moteur WebAssembly exact (jusqu'à 16 qubits).",
  "res.blochMixed": "intriqué/mixte", "res.blochShown": "{a} qubits affichés sur {b}.",
  "res.stateTop": "Avec {n} qubits il y a 2^{n} amplitudes ; les {k} états de base les plus probables sont affichés (exact).",
  "res.stateNone": "À cette taille, aucun tableau de probabilités n'est construit (tirs uniquement).",
  "res.traj": "{n} trajectoires", "res.tv": "TV vs f64 : {v}", "res.extrap": "{n} qubits extrapolés",
  "sat.title": "Labo SAT", "sat.intro": "Collez une CNF DIMACS ou générez-en une. SAT est accompagné d'un modèle vérifié clause par clause. UNSAT est accompagné d'un certificat de résolution en arbre rejoué par un vérificateur séparé. Un délai dépassé donne UNKNOWN, jamais UNSAT. Le comptage de modèles (#SAT) est un problème à part avec son propre résultat exact.",
  "sat.solve": "Résoudre", "sat.random": "3-SAT aléatoire", "sat.php": "Tiroirs (UNSAT)", "sat.vars": "Variables", "sat.ratio": "Clauses/variable",
  "sat.timeout": "Délai (ms)", "sat.sweep": "Balayage de transition de phase", "sat.sweepNote": "Médiane des décisions par ratio. Le pic près de 4,26 est le pic de difficulté classique. Une expérience finie, pas une borne de complexité.",
  "sat.status": "Statut", "sat.model": "Modèle", "sat.stats": "{d} décisions · {p} propagations · {c} conflits · {t} ms",
  "cmp.title": "Comparaison d'appareils", "cmp.intro": "Exécute le circuit du labo en idéal et avec chaque profil mesuré. TV est la distance de variation totale à la distribution idéale : 0 est parfait, 1 totalement différent.",
  "cmp.run": "Comparer tous les appareils", "cmp.device": "Appareil", "cmp.tv": "TV vs idéal", "cmp.top": "Résultat le plus probable", "cmp.limit": "La comparaison va jusqu'à 14 qubits.",
  "dev.title": "Votre appareil", "dev.limits": "Limites sûres", "dev.profiles": "Profils QPU mesurés",
  "dev.profilesNote": "Extraits des exécutions de la suite figée r-io-7 de 25 circuits (modèle M-FIT-2, a posteriori). H-V3-8 demande si le modèle de bruit ajusté prédit mieux des circuits non vus que la simulation idéale.",
  "dev.reprobe": "Revérifier la limite", "dev.limitsNote": "Un état exact de n qubits demande 16 · 2ⁿ octets (f64). Au plus un quart de la RAM signalée et 2 Gio de tas WebAssembly sont utilisés ; la limite est confirmée par une vraie allocation. Les exécutions estimées à plus de 90 s sont refusées.",
  "dev.os": "Système", "dev.browser": "Navigateur", "dev.arch": "Architecture", "dev.cores": "Threads CPU",
  "dev.ram": "Mémoire", "dev.gpu": "GPU", "dev.webgpu": "WebGPU", "dev.webgl": "WebGL 2", "dev.simd": "WASM SIMD128", "dev.core": "Cœur WASM",
  "dev.budget": "Budget mémoire", "dev.exact": "Exact (WASM f64)", "dev.fast": "Rapide (WebGPU f32)", "dev.time": "Limite de durée",
  "dev.verified": "confirmé par allocation", "dev.computed": "calculé", "dev.yes": "oui", "dev.no": "non", "dev.backend": "backend probable {b}",
  "dev.qubit": "qubit", "dev.p01": "P(1|0)", "dev.p10": "P(0|1)", "dev.xflip": "Flip X",
  "foot.love": "Made with {heart} by {a} & {b}", "foot.sub": "Simulation classique exacte · pas un ordinateur quantique",
  "err.boot": "Échec du démarrage : {e}", "err.wasm": "Impossible de charger WebAssembly : {e}",
};

const DICTS: Record<Lang, Dict> = { en, de, fr };
let lang: Lang = "en";
const listeners: (() => void)[] = [];

export function detectLang(): Lang {
  try {
    const stored = localStorage.getItem("lang");
    if (stored === "en" || stored === "de" || stored === "fr") return stored;
  } catch { /* storage blocked */ }
  for (const l of navigator.languages ?? [navigator.language]) {
    const base = l.slice(0, 2).toLowerCase();
    if (base === "de" || base === "fr" || base === "en") return base;
  }
  return "en";
}

export function getLang(): Lang { return lang; }

export function setLang(next: Lang) {
  lang = next;
  document.documentElement.lang = next;
  try { localStorage.setItem("lang", next); } catch { /* storage blocked */ }
  document.title = t("meta.title");
  applyI18n(document);
  listeners.forEach((fn) => fn());
}

export function onLangChange(fn: () => void) { listeners.push(fn); }

export function t(key: string, vars: Record<string, string | number> = {}): string {
  const s = DICTS[lang][key] ?? en[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
}

/** Fill every [data-i18n] element (text) and [data-i18n-attr="attr:key"] attribute. */
export function applyI18n(root: ParentNode) {
  root.querySelectorAll<HTMLElement>("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n!); });
  root.querySelectorAll<HTMLElement>("[data-i18n-attr]").forEach((el) => {
    for (const pair of el.dataset.i18nAttr!.split(";")) {
      const [attr, key] = pair.split(":");
      el.setAttribute(attr, t(key));
    }
  });
}

/** Every key must exist in every language (checked by the test suite). */
export function missingKeys(): string[] {
  const keys = new Set([...Object.keys(en), ...Object.keys(de), ...Object.keys(fr)]);
  const missing: string[] = [];
  for (const k of keys) for (const l of ["en", "de", "fr"] as Lang[]) if (!(k in DICTS[l])) missing.push(`${l}:${k}`);
  return missing;
}
