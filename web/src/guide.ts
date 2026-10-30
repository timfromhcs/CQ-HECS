// The get-started guide: beginner → advanced, in English, German and French.
// Each section may offer a "try it" action that opens a preset or a view.

import type { Lang } from "./i18n";

export type Level = "beginner" | "inter" | "adv";
export interface GuideAction { preset?: string; qubits?: number; noise?: string; view?: string }
export interface GuideSection { id: string; level: Level; action?: GuideAction; title: Record<Lang, string>; body: Record<Lang, string> }

export const GUIDE_UI: Record<Lang, { title: string; intro: string; tryIt: string; levels: Record<Level, string>; toc: string }> = {
  en: { title: "Get started", intro: "Ten short chapters, from your first qubit to real hardware noise and the limits of computation. Every chapter has a button that sets up the lab for you.", tryIt: "Try it", toc: "Contents", levels: { beginner: "Beginner", inter: "Intermediate", adv: "Advanced" } },
  de: { title: "Erste Schritte", intro: "Zehn kurze Kapitel, vom ersten Qubit bis zu echtem Hardware-Rauschen und den Grenzen des Berechenbaren. Jedes Kapitel hat einen Button, der das Labor für dich vorbereitet.", tryIt: "Ausprobieren", toc: "Inhalt", levels: { beginner: "Einsteiger", inter: "Fortgeschritten", adv: "Profi" } },
  fr: { title: "Bien démarrer", intro: "Dix chapitres courts, de votre premier qubit au bruit matériel réel et aux limites du calcul. Chaque chapitre propose un bouton qui prépare le labo pour vous.", tryIt: "Essayer", toc: "Sommaire", levels: { beginner: "Débutant", inter: "Intermédiaire", adv: "Avancé" } },
};

export const GUIDE: GuideSection[] = [
  {
    id: "qubit", level: "beginner", action: { preset: "superposition", qubits: 1 },
    title: { en: "1 · What is a qubit?", de: "1 · Was ist ein Qubit?", fr: "1 · Qu'est-ce qu'un qubit ?" },
    body: {
      en: `<p>A classical bit is 0 or 1. A qubit has two <b>amplitudes</b>, complex numbers <i>a</i> for |0⟩ and <i>b</i> for |1⟩, with |a|² + |b|² = 1. Measuring it gives 0 with probability |a|² and 1 with probability |b|².</p><p>The <b>Hadamard</b> gate H turns |0⟩ into an equal superposition: measure it many times and you get 0 and 1 about half the time each. On the <b>Bloch sphere</b> |0⟩ is the north pole and |1⟩ the south pole. H moves the arrow to the equator.</p>`,
      de: `<p>Ein klassisches Bit ist 0 oder 1. Ein Qubit hat zwei <b>Amplituden</b>, komplexe Zahlen <i>a</i> für |0⟩ und <i>b</i> für |1⟩, mit |a|² + |b|² = 1. Eine Messung liefert 0 mit Wahrscheinlichkeit |a|² und 1 mit |b|².</p><p>Das <b>Hadamard</b>-Gatter H macht aus |0⟩ eine gleichmäßige Überlagerung: Misst du oft, kommt etwa je zur Hälfte 0 und 1. Auf der <b>Bloch-Kugel</b> ist |0⟩ der Nordpol und |1⟩ der Südpol. H dreht den Pfeil auf den Äquator.</p>`,
      fr: `<p>Un bit classique vaut 0 ou 1. Un qubit possède deux <b>amplitudes</b>, des nombres complexes <i>a</i> pour |0⟩ et <i>b</i> pour |1⟩, avec |a|² + |b|² = 1. Une mesure donne 0 avec probabilité |a|² et 1 avec |b|².</p><p>La porte de <b>Hadamard</b> H transforme |0⟩ en superposition équilibrée : en mesurant souvent, on obtient 0 et 1 environ moitié-moitié. Sur la <b>sphère de Bloch</b>, |0⟩ est le pôle nord et |1⟩ le pôle sud. H amène la flèche sur l'équateur.</p>`,
    },
  },
  {
    id: "bell", level: "beginner", action: { preset: "bell" },
    title: { en: "2 · Your first circuit: a Bell pair", de: "2 · Deine erste Schaltung: ein Bell-Paar", fr: "2 · Votre premier circuit : une paire de Bell" },
    body: {
      en: `<p>Place H on q0, then a <b>CNOT</b> (CX) with control q0 and target q1. The result is (|00⟩ + |11⟩)/√2: the two qubits are <b>entangled</b>. You only ever see 00 or 11, never 01 or 10. Each qubit alone looks random, but the two always agree.</p><p>In the lab, pick CX, tap q0 (control) and then q1 (target) in the same column. Press ▶ and look at the histogram. The Bloch arrows shrink to the centre: an entangled qubit has no pure state of its own.</p>`,
      de: `<p>Setze H auf q0, dann ein <b>CNOT</b> (CX) mit Kontrolle q0 und Ziel q1. Ergebnis ist (|00⟩ + |11⟩)/√2: Die Qubits sind <b>verschränkt</b>. Du siehst nur 00 oder 11, nie 01 oder 10. Jedes Qubit allein wirkt zufällig, aber beide stimmen immer überein.</p><p>Im Labor: CX wählen, erst q0 (Kontrolle), dann q1 (Ziel) in derselben Spalte antippen. ▶ drücken und das Histogramm ansehen. Die Bloch-Pfeile schrumpfen in die Mitte: Ein verschränktes Qubit hat keinen eigenen reinen Zustand.</p>`,
      fr: `<p>Placez H sur q0, puis un <b>CNOT</b> (CX) avec contrôle q0 et cible q1. Le résultat est (|00⟩ + |11⟩)/√2 : les qubits sont <b>intriqués</b>. On ne voit que 00 ou 11, jamais 01 ni 10. Chaque qubit seul paraît aléatoire, mais les deux concordent toujours.</p><p>Dans le labo : choisissez CX, touchez q0 (contrôle) puis q1 (cible) dans la même colonne. Appuyez sur ▶ et regardez l'histogramme. Les flèches de Bloch se réduisent au centre : un qubit intriqué n'a pas d'état pur propre.</p>`,
    },
  },
  {
    id: "shots", level: "beginner", action: { preset: "bell" },
    title: { en: "3 · Shots, probabilities and statistics", de: "3 · Shots, Wahrscheinlichkeiten und Statistik", fr: "3 · Tirs, probabilités et statistiques" },
    body: {
      en: `<p>A real quantum computer only gives samples. Each run of the circuit is a <b>shot</b> that returns one bit string. The emulator does the same, and also shows the <b>exact probability</b> as an orange line, because it knows the full state.</p><p>With 100 shots the bars wobble around 50 %. With 100 000 they sit on the line. The statistical error shrinks like 1/√shots. That is why hardware experiments use thousands of shots.</p>`,
      de: `<p>Ein echter Quantencomputer liefert nur Stichproben. Jeder Durchlauf ist ein <b>Shot</b> und ergibt einen Bitstring. Der Emulator macht dasselbe und zeigt zusätzlich die <b>exakte Wahrscheinlichkeit</b> als orange Linie, weil er den ganzen Zustand kennt.</p><p>Mit 100 Shots wackeln die Balken um 50 %, mit 100 000 liegen sie auf der Linie. Der statistische Fehler schrumpft wie 1/√Shots. Deshalb nutzen Hardware-Experimente Tausende Shots.</p>`,
      fr: `<p>Un vrai ordinateur quantique ne fournit que des échantillons. Chaque exécution est un <b>tir</b> qui renvoie une chaîne de bits. L'émulateur fait de même et affiche aussi la <b>probabilité exacte</b> en ligne orange, car il connaît l'état complet.</p><p>Avec 100 tirs, les barres oscillent autour de 50 %. Avec 100 000, elles se posent sur la ligne. L'erreur statistique décroît en 1/√tirs. C'est pourquoi les expériences matérielles utilisent des milliers de tirs.</p>`,
    },
  },
  {
    id: "ghz", level: "inter", action: { preset: "ghz", qubits: 8 },
    title: { en: "4 · Entanglement at scale: GHZ", de: "4 · Verschränkung im Großen: GHZ", fr: "4 · L'intrication à grande échelle : GHZ" },
    body: {
      en: `<p>A chain of CNOTs after one H entangles all n qubits: (|0…0⟩ + |1…1⟩)/√2. Only two of the 2ⁿ outcomes appear. With 20 qubits the state vector already holds over a million amplitudes, and the exact engine still tracks each one.</p><p>GHZ states are fragile. On hardware, every CNOT adds a little error and the two peaks leak into many small bars. Chapter 5 shows this with measured noise.</p>`,
      de: `<p>Eine Kette von CNOTs nach einem H verschränkt alle n Qubits: (|0…0⟩ + |1…1⟩)/√2. Von 2ⁿ Ausgängen erscheinen nur zwei. Bei 20 Qubits hält der Zustandsvektor schon über eine Million Amplituden, und der exakte Kern verfolgt jede einzelne.</p><p>GHZ-Zustände sind empfindlich. Auf Hardware fügt jedes CNOT etwas Fehler hinzu, und die zwei Spitzen zerfließen in viele kleine Balken. Kapitel 5 zeigt das mit gemessenem Rauschen.</p>`,
      fr: `<p>Une chaîne de CNOT après un H intrique les n qubits : (|0…0⟩ + |1…1⟩)/√2. Seuls deux des 2ⁿ résultats apparaissent. À 20 qubits, le vecteur d'état contient déjà plus d'un million d'amplitudes, et le moteur exact les suit toutes.</p><p>Les états GHZ sont fragiles. Sur le matériel, chaque CNOT ajoute un peu d'erreur et les deux pics se diluent en nombreuses petites barres. Le chapitre 5 le montre avec du bruit mesuré.</p>`,
    },
  },
  {
    id: "noise", level: "inter", action: { preset: "ghz", qubits: 5, noise: "rigetti_cepheus" },
    title: { en: "5 · Real hardware noise, measured", de: "5 · Echtes Hardware-Rauschen, gemessen", fr: "5 · Le bruit matériel réel, mesuré" },
    body: {
      en: `<p>The <b>Noise</b> menu offers profiles fitted from runs of the same 25 circuits on IBM, Rigetti and IQM processors. Each profile has three ingredients:</p><ul><li><b>Readout error</b> per qubit: P(1|0) and P(0|1), usually asymmetric because |1⟩ decays during measurement.</li><li><b>Two-qubit depolarizing</b> after every CNOT: with probability p the pair is replaced by a random Pauli error.</li><li><b>Gate anomalies</b>: on Rigetti, qubit 0's X gate flipped with probability ≈ 0.54 on the measurement day.</li></ul><p>Run a GHZ-5 with the Rigetti profile, then with an IBM profile, and compare the "impossible" outcomes. On the <b>Devices</b> page you can run one circuit on every profile at once.</p>`,
      de: `<p>Das Menü <b>Rauschen</b> bietet Profile, gefittet aus Läufen derselben 25 Schaltungen auf IBM-, Rigetti- und IQM-Prozessoren. Jedes Profil hat drei Zutaten:</p><ul><li><b>Auslesefehler</b> pro Qubit: P(1|0) und P(0|1), meist asymmetrisch, weil |1⟩ während der Messung zerfällt.</li><li><b>Zwei-Qubit-Depolarisierung</b> nach jedem CNOT: Mit Wahrscheinlichkeit p wird das Paar durch einen zufälligen Pauli-Fehler ersetzt.</li><li><b>Gatter-Anomalien</b>: Bei Rigetti kippte am Messtag das X-Gatter von Qubit 0 mit Wahrscheinlichkeit ≈ 0,54.</li></ul><p>Lass GHZ-5 mit dem Rigetti-Profil laufen, dann mit einem IBM-Profil, und vergleiche die „unmöglichen“ Ausgänge. Auf der Seite <b>Geräte</b> läuft eine Schaltung auf allen Profilen gleichzeitig.</p>`,
      fr: `<p>Le menu <b>Bruit</b> propose des profils ajustés sur les mêmes 25 circuits exécutés sur des processeurs IBM, Rigetti et IQM. Chaque profil a trois ingrédients :</p><ul><li><b>Erreur de lecture</b> par qubit : P(1|0) et P(0|1), souvent asymétriques car |1⟩ se relaxe pendant la mesure.</li><li><b>Dépolarisation à deux qubits</b> après chaque CNOT : avec probabilité p la paire subit une erreur de Pauli aléatoire.</li><li><b>Anomalies de porte</b> : chez Rigetti, la porte X du qubit 0 s'inversait avec une probabilité ≈ 0,54 le jour de la mesure.</li></ul><p>Lancez un GHZ-5 avec le profil Rigetti, puis avec un profil IBM, et comparez les résultats « impossibles ». La page <b>Appareils</b> exécute un circuit sur tous les profils à la fois.</p>`,
    },
  },
  {
    id: "algorithms", level: "inter", action: { preset: "grover", qubits: 6 },
    title: { en: "6 · Algorithms: Grover, Bernstein–Vazirani, QFT", de: "6 · Algorithmen: Grover, Bernstein–Vazirani, QFT", fr: "6 · Algorithmes : Grover, Bernstein–Vazirani, QFT" },
    body: {
      en: `<p><b>Grover search</b> amplifies the amplitude of a marked state. After about (π/4)·√(2ⁿ) rounds the marked string dominates: with 6 qubits, 6 rounds give 99.7 %. That is a quadratic speed-up for unstructured search, not an exponential one.</p><p><b>Bernstein–Vazirani</b> finds a hidden bit string in one query where a classical algorithm needs n. The <b>QFT</b> is the Fourier transform on amplitudes and the core of phase estimation and Shor's algorithm.</p>`,
      de: `<p><b>Grover-Suche</b> verstärkt die Amplitude eines markierten Zustands. Nach etwa (π/4)·√(2ⁿ) Runden dominiert der markierte String: bei 6 Qubits ergeben 6 Runden 99,7 %. Das ist ein quadratischer Vorteil für unstrukturierte Suche, kein exponentieller.</p><p><b>Bernstein–Vazirani</b> findet einen versteckten Bitstring mit einer Abfrage, wo klassisch n nötig sind. Die <b>QFT</b> ist die Fourier-Transformation auf Amplituden und das Herz von Phasenschätzung und Shor-Algorithmus.</p>`,
      fr: `<p>La <b>recherche de Grover</b> amplifie l'amplitude d'un état marqué. Après environ (π/4)·√(2ⁿ) itérations, la chaîne marquée domine : avec 6 qubits, 6 itérations donnent 99,7 %. C'est une accélération quadratique pour la recherche non structurée, pas exponentielle.</p><p><b>Bernstein–Vazirani</b> trouve une chaîne cachée en une seule requête là où un algorithme classique en demande n. La <b>QFT</b> est la transformée de Fourier sur les amplitudes, au cœur de l'estimation de phase et de l'algorithme de Shor.</p>`,
    },
  },
  {
    id: "code", level: "adv", action: { view: "code" },
    title: { en: "7 · Code: OpenQASM 2.0 and the JavaScript API", de: "7 · Code: OpenQASM 2.0 und die JavaScript-API", fr: "7 · Code : OpenQASM 2.0 et l'API JavaScript" },
    body: {
      en: `<p>The <b>Code</b> mode accepts OpenQASM 2.0 with the qelib1 gates, register broadcasting (<code>h q;</code>), <code>measure</code>, <code>reset</code> and <code>barrier</code>. Parameters may use <code>pi</code>. As an extension, <code>mcx</code>/<code>mcz</code> take any number of controls.</p><p>The <b>JavaScript</b> tab builds circuits in code:</p><pre><code>const qc = circuit(5);
for (let q = 0; q &lt; 5; q++) qc.h(q);
qc.mcz(0, 1, 2, 3, 4);
return qc.measureAll();</code></pre><p>Press Ctrl/⌘+Enter to run. "Share link" puts the circuit into the URL.</p>`,
      de: `<p>Der <b>Code</b>-Modus versteht OpenQASM 2.0 mit den qelib1-Gattern, Register-Broadcast (<code>h q;</code>), <code>measure</code>, <code>reset</code> und <code>barrier</code>. Parameter dürfen <code>pi</code> enthalten. Als Erweiterung nehmen <code>mcx</code>/<code>mcz</code> beliebig viele Kontrollen.</p><p>Der Tab <b>JavaScript</b> baut Schaltungen per Code:</p><pre><code>const qc = circuit(5);
for (let q = 0; q &lt; 5; q++) qc.h(q);
qc.mcz(0, 1, 2, 3, 4);
return qc.measureAll();</code></pre><p>Strg/⌘+Enter startet. „Link teilen“ legt die Schaltung in die URL.</p>`,
      fr: `<p>Le mode <b>Code</b> accepte OpenQASM 2.0 avec les portes qelib1, la diffusion de registre (<code>h q;</code>), <code>measure</code>, <code>reset</code> et <code>barrier</code>. Les paramètres peuvent utiliser <code>pi</code>. En extension, <code>mcx</code>/<code>mcz</code> acceptent un nombre quelconque de contrôles.</p><p>L'onglet <b>JavaScript</b> construit des circuits par code :</p><pre><code>const qc = circuit(5);
for (let q = 0; q &lt; 5; q++) qc.h(q);
qc.mcz(0, 1, 2, 3, 4);
return qc.measureAll();</code></pre><p>Ctrl/⌘+Entrée exécute. « Partager le lien » place le circuit dans l'URL.</p>`,
    },
  },
  {
    id: "midcircuit", level: "adv", action: { preset: "teleport" },
    title: { en: "8 · Mid-circuit measurement, reset, teleportation", de: "8 · Messung mitten in der Schaltung, Reset, Teleportation", fr: "8 · Mesure en cours de circuit, reset, téléportation" },
    body: {
      en: `<p>When a measurement or reset happens before the end, the result of each shot depends on earlier random outcomes. The emulator then replays the circuit once per shot as a <b>quantum trajectory</b>: it collapses the state at every measurement and keeps going. The statistics are exact.</p><p>The teleportation example moves the state RY(1.1)|0⟩ from q0 to q2 and then undoes it, so q2 must read 0 every time. Any 1 is a bug, or with noise switched on, a physical error.</p>`,
      de: `<p>Passiert eine Messung oder ein Reset vor dem Ende, hängt jeder Shot von früheren Zufallsergebnissen ab. Der Emulator spielt die Schaltung dann pro Shot als <b>Quanten-Trajektorie</b> ab: Er kollabiert den Zustand bei jeder Messung und rechnet weiter. Die Statistik ist exakt.</p><p>Das Teleportations-Beispiel überträgt RY(1.1)|0⟩ von q0 auf q2 und macht es dort rückgängig, also muss q2 immer 0 zeigen. Jede 1 ist ein Bug oder, mit Rauschen, ein physikalischer Fehler.</p>`,
      fr: `<p>Quand une mesure ou un reset a lieu avant la fin, chaque tir dépend de résultats aléatoires antérieurs. L'émulateur rejoue alors le circuit à chaque tir comme une <b>trajectoire quantique</b> : il effondre l'état à chaque mesure et continue. Les statistiques sont exactes.</p><p>L'exemple de téléportation transfère RY(1.1)|0⟩ de q0 vers q2 puis l'annule, donc q2 doit toujours lire 0. Tout 1 est un bug ou, avec le bruit, une erreur physique.</p>`,
    },
  },
  {
    id: "limits", level: "adv", action: { view: "device" },
    title: { en: "9 · Exactness, memory and the GPU", de: "9 · Exaktheit, Speicher und die GPU", fr: "9 · Exactitude, mémoire et GPU" },
    body: {
      en: `<p>An n-qubit state has 2ⁿ complex amplitudes at 16 bytes each: 20 qubits are 16 MiB, 26 are 1 GiB, 30 would be 16 GiB. The WebAssembly heap is at most 4 GiB, so the exact engine stops at 27 qubits. Your device may allow less, and the page checks that with a real allocation.</p><p><b>WebGPU</b> runs the same gate kernel on your graphics card in 32-bit floats. That is fast, but only accurate to about 10⁻⁷. For circuits up to 20 qubits every GPU run is compared with the exact result (the "TV to f64" chip). Browsers expose no Vulkan; WebGPU uses Vulkan, Direct3D 12 or Metal under the hood.</p>`,
      de: `<p>Ein n-Qubit-Zustand hat 2ⁿ komplexe Amplituden zu je 16 Byte: 20 Qubits sind 16 MiB, 26 sind 1 GiB, 30 wären 16 GiB. Der WebAssembly-Heap fasst höchstens 4 GiB, darum endet der exakte Kern bei 27 Qubits. Dein Gerät erlaubt vielleicht weniger; die Seite prüft das mit einer echten Reservierung.</p><p><b>WebGPU</b> rechnet denselben Gatter-Kernel auf der Grafikkarte in 32-Bit-Gleitkomma. Das ist schnell, aber nur auf etwa 10⁻⁷ genau. Bis 20 Qubits wird jeder GPU-Lauf mit dem exakten Ergebnis verglichen (Chip „TV zu f64“). Browser bieten kein Vulkan; WebGPU nutzt intern Vulkan, Direct3D 12 oder Metal.</p>`,
      fr: `<p>Un état à n qubits a 2ⁿ amplitudes complexes de 16 octets : 20 qubits font 16 Mio, 26 font 1 Gio, 30 feraient 16 Gio. Le tas WebAssembly est limité à 4 Gio, donc le moteur exact s'arrête à 27 qubits. Votre appareil peut en permettre moins ; la page le vérifie par une vraie allocation.</p><p><b>WebGPU</b> exécute le même noyau sur votre carte graphique en flottants 32 bits. C'est rapide, mais précis seulement à environ 10⁻⁷. Jusqu'à 20 qubits, chaque exécution GPU est comparée au résultat exact (pastille « TV vs f64 »). Les navigateurs n'exposent pas Vulkan ; WebGPU s'appuie sur Vulkan, Direct3D 12 ou Metal.</p>`,
    },
  },
  {
    id: "sat", level: "adv", action: { view: "sat" },
    title: { en: "10 · SAT, NP and what quantum computers do not do", de: "10 · SAT, NP und was Quantencomputer nicht können", fr: "10 · SAT, NP et ce que les ordinateurs quantiques ne font pas" },
    body: {
      en: `<p><b>SAT</b> asks whether a Boolean formula has a satisfying assignment. It is NP-complete. Checking a solution is easy; finding one seems to need exponential time in the worst case (the Exponential Time Hypothesis). <b>P versus NP is open</b>.</p><p>Grover search solves SAT in about √(2ⁿ) steps instead of 2ⁿ. That is a real speed-up, but it is still exponential. The SAT lab runs a classical DPLL solver. Its "phase transition" sweep shows how random 3-SAT gets hardest near 4.26 clauses per variable. That is a finite experiment, not a proof.</p>`,
      de: `<p><b>SAT</b> fragt, ob eine Boolesche Formel eine erfüllende Belegung hat. Das Problem ist NP-vollständig. Eine Lösung zu prüfen ist leicht; eine zu finden scheint im schlimmsten Fall exponentiell lange zu dauern (Exponentialzeit-Hypothese). <b>P gegen NP ist offen</b>.</p><p>Grover löst SAT in etwa √(2ⁿ) statt 2ⁿ Schritten. Das ist ein echter Vorteil, bleibt aber exponentiell. Das SAT-Labor rechnet mit einem klassischen DPLL-Solver. Sein Phasenübergangs-Sweep zeigt, dass Zufalls-3-SAT nahe 4,26 Klauseln pro Variable am schwersten ist. Das ist ein endliches Experiment, kein Beweis.</p>`,
      fr: `<p><b>SAT</b> demande si une formule booléenne admet une affectation qui la satisfait. Le problème est NP-complet. Vérifier une solution est facile ; en trouver une semble demander un temps exponentiel dans le pire cas (hypothèse du temps exponentiel). <b>P contre NP reste ouvert</b>.</p><p>Grover résout SAT en environ √(2ⁿ) étapes au lieu de 2ⁿ. C'est une vraie accélération, mais qui reste exponentielle. Le labo SAT utilise un solveur DPLL classique. Son balayage de transition de phase montre que le 3-SAT aléatoire est le plus difficile vers 4,26 clauses par variable. C'est une expérience finie, pas une preuve.</p>`,
    },
  },
];
