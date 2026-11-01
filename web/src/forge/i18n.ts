// EN/DE/FR strings for the SHA Forge page. Missing keys fall back to English.

export type Lang = "en" | "de" | "fr";
type Dict = Record<string, string>;

const en: Dict = {
  skip: "Skip to content", lang: "Language", back: "CQ-HECS Web",
  tagline: "Real Silicon. Reproducible Science.", credit: "Made with love by timfromhcs & hcsmedia.",
  "tab.overview": "Overview", "tab.analyzer": "Round Analyzer", "tab.miner": "Miner Lab", "tab.bench": "Engine Benchmarks", "tab.evidence": "Evidence",
  "ov.title": "SHA-256, step by step — and an optional physical node.",
  "ov.lead": "Watch every one of the 64 SHA-256 rounds computed in your browser, replay Bitcoin-style SHA-256d headers, and — only if you run the local bridge on your own network — look at a physical BM1366 research node. Without hardware, everything here is a deterministic demo.",
  "ov.c1.t": "Round Analyzer", "ov.c1.d": "Padding, message schedule, all 64 rounds, registers a–h, Ch, Maj, Σ0, Σ1 and the final digest, cross-checked against Web Crypto.",
  "ov.c2.t": "Miner Lab", "ov.c2.d": "Demo telemetry is simulated and labelled. A live view needs the loopback bridge you start yourself; this page never scans your network.",
  "ov.c3.t": "Engine Benchmarks", "ov.c3.d": "WebGPU, WebAssembly and CPU are probed with self-tests against the reference. Failures fall back visibly.",
  "ov.bound.t": "What is measured, and what is not", "ov.th.source": "Source", "ov.th.what": "What it shows", "ov.th.not": "What it never shows",
  "ov.row.asic": "BM1366 ASIC", "ov.row.asic.w": "Throughput of SHA-256d mining-style work, returned nonce candidates, chip telemetry — each candidate re-hashed on the host.", "ov.row.asic.n": "Arbitrary SHA-256 inputs, internal round states or per-round traces.",
  "ov.row.sw": "Round Analyzer", "ov.row.sw.w": "FIPS 180-4 computed in software: padding, schedule, 64 rounds, digest.", "ov.row.sw.n": "Anything read from the ASIC silicon.",
  "ov.row.demo": "Demo", "ov.row.demo.w": "Seeded, deterministic fixtures marked DEMO / SIMULATED.", "ov.row.demo.n": "Live hardware data.",
  "an.title": "SHA Round Analyzer", "an.note": "Computed in your browser with exact 32-bit arithmetic. This is not a trace read from the BM1366.",
  "an.mode": "Input", "an.mode.text": "Text message", "an.mode.hex": "Hex bytes", "an.mode.header": "Bitcoin 80-byte header (SHA-256d)",
  "an.input": "Message", "an.rounds": "Rounds (1–64)", "an.run": "Compute trace", "an.genesis": "Load genesis header", "an.export": "Export trace JSON",
  "an.src": "SOFTWARE_REPLAY — computed in your browser, not read from any ASIC.", "an.pad": "Padding", "an.block": "Block", "an.rounds.t": "Rounds", "an.pick": "Round",
  "an.err.hex": "Not valid hex.", "an.err.header": "A Bitcoin header is exactly 80 bytes (160 hex characters).", "an.err.rounds": "Rounds must be between 1 and 64.", "an.reduced": "Reduced-round experiment: this is not standard SHA-256.",
  "an.webcrypto.ok": "Web Crypto agrees with the reference digest.", "an.webcrypto.bad": "Web Crypto DISAGREES with the reference digest.", "an.webcrypto.na": "Web Crypto unavailable here; digest not cross-checked.",
  "mi.title": "Miner Lab · TimsMiner / BM1366 Research Node", "mi.note": "Only the unit named timsminer is allowlisted. Other devices are refused. The bridge runs on your computer (127.0.0.1); this page never contacts your miner directly.",
  "mi.id": "Device identity", "mi.state": "Connection state", "mi.url": "Local bridge address", "mi.connect": "Connect local TimsMiner",
  "mi.tele": "Telemetry", "mi.table": "Chart as table", "mi.arm": "Arm research", "mi.start": "Start bounded test", "mi.restore": "Restore original firmware",
  "mi.locked": "Arming, work and firmware actions are unavailable in demo mode and in this read-only release.",
  "mi.demo.id": "No device. Demo node only.", "mi.demo.state": "DEMO — no LAN requests are made.", "mi.src.demo": "DEMO / SIMULATED — seeded fixture, not hardware.",
  "mi.err.url": "The bridge must be on this computer (127.0.0.1 or localhost).", "mi.err.net": "Bridge not reachable. Start it on this computer, or the browser blocked the local connection (check the site permission for local network access).",
  "mi.ok": "Bridge reachable: read-only mode. No work can be sent and no firmware can be written.", "mi.gap": "Gaps mark missing samples; nothing is interpolated.",
  "be.title": "Engine Benchmarks", "be.note": "Each engine must pass a self-test against the reference before it is selected. Results are only compared when the workload is identical.",
  "be.run": "Probe engines & run small benchmark", "be.reason": "Reason", "be.workload": "Workload", "be.unit": "Unit", "be.value": "Value",
  "be.units": "SHA-256 compressions per second (software) and GH/s of SHA-256d mining work (ASIC) are different units. They are never plotted on one axis without a documented conversion.",
  "be.running": "Running…", "be.selected": "Selected software engine", "be.ok": "available", "be.no": "not available",
  "ev.title": "Evidence Ledger", "ev.note": "Everything on this page that you compute can be exported with its inputs, engine and software version. Nothing is uploaded.", "ev.export": "Export session JSON",
};

const de: Dict = {
  skip: "Zum Inhalt springen", lang: "Sprache", tagline: "Echtes Silizium. Reproduzierbare Wissenschaft.", credit: "Mit Liebe gemacht von timfromhcs & hcsmedia.",
  "tab.overview": "Übersicht", "tab.analyzer": "Runden-Analyse", "tab.miner": "Miner-Labor", "tab.bench": "Engine-Benchmarks", "tab.evidence": "Nachweise",
  "ov.title": "SHA-256 Schritt für Schritt – und ein optionaler physischer Knoten.",
  "ov.lead": "Sieh alle 64 SHA-256-Runden im Browser, spiele Bitcoin-SHA-256d-Header nach und – nur wenn du die lokale Bridge im eigenen Netz startest – einen physischen BM1366-Forschungsknoten. Ohne Hardware ist hier alles eine deterministische Demo.",
  "ov.c1.t": "Runden-Analyse", "ov.c1.d": "Padding, Nachrichtenplan, alle 64 Runden, Register a–h, Ch, Maj, Σ0, Σ1 und Digest – gegen Web Crypto geprüft.",
  "ov.c2.t": "Miner-Labor", "ov.c2.d": "Demo-Telemetrie ist simuliert und gekennzeichnet. Live braucht die Loopback-Bridge, die du selbst startest; diese Seite scannt dein Netzwerk nie.",
  "ov.c3.t": "Engine-Benchmarks", "ov.c3.d": "WebGPU, WebAssembly und CPU werden mit Selbsttests gegen die Referenz geprüft. Ausfälle fallen sichtbar zurück.",
  "ov.bound.t": "Was gemessen wird – und was nicht", "ov.th.source": "Quelle", "ov.th.what": "Was sie zeigt", "ov.th.not": "Was sie nie zeigt",
  "ov.row.asic": "BM1366-ASIC", "ov.row.asic.w": "Durchsatz von SHA-256d-Mining-Arbeit, zurückgegebene Nonce-Kandidaten, Chip-Telemetrie – jeder Kandidat wird auf dem Host neu gehasht.", "ov.row.asic.n": "Beliebige SHA-256-Eingaben, interne Rundenzustände oder Rundenspuren.",
  "ov.row.sw": "Runden-Analyse", "ov.row.sw.w": "FIPS 180-4 in Software: Padding, Plan, 64 Runden, Digest.", "ov.row.sw.n": "Alles, was aus dem ASIC gelesen wurde.",
  "ov.row.demo": "Demo", "ov.row.demo.w": "Deterministische Fixtures mit Kennzeichnung DEMO / SIMULIERT.", "ov.row.demo.n": "Live-Hardwaredaten.",
  "an.title": "SHA-Runden-Analyse", "an.note": "Im Browser mit exakter 32-Bit-Arithmetik berechnet. Das ist keine vom BM1366 gelesene Spur.",
  "an.mode": "Eingabe", "an.mode.text": "Textnachricht", "an.mode.hex": "Hex-Bytes", "an.mode.header": "Bitcoin-Header, 80 Byte (SHA-256d)",
  "an.input": "Nachricht", "an.rounds": "Runden (1–64)", "an.run": "Spur berechnen", "an.genesis": "Genesis-Header laden", "an.export": "Spur als JSON exportieren",
  "an.src": "SOFTWARE_REPLAY – im Browser berechnet, von keinem ASIC gelesen.", "an.pad": "Padding", "an.block": "Block", "an.rounds.t": "Runden", "an.pick": "Runde",
  "an.err.hex": "Kein gültiges Hex.", "an.err.header": "Ein Bitcoin-Header hat genau 80 Byte (160 Hex-Zeichen).", "an.err.rounds": "Runden müssen zwischen 1 und 64 liegen.", "an.reduced": "Reduzierte Runden: Das ist kein Standard-SHA-256.",
  "an.webcrypto.ok": "Web Crypto stimmt mit dem Referenz-Digest überein.", "an.webcrypto.bad": "Web Crypto WIDERSPRICHT dem Referenz-Digest.", "an.webcrypto.na": "Web Crypto hier nicht verfügbar; Digest nicht gegengeprüft.",
  "mi.title": "Miner-Labor · TimsMiner / BM1366-Forschungsknoten", "mi.note": "Nur das Gerät timsminer steht auf der Allowlist. Andere Geräte werden abgelehnt. Die Bridge läuft auf deinem Rechner (127.0.0.1); diese Seite kontaktiert den Miner nie direkt.",
  "mi.id": "Geräteidentität", "mi.state": "Verbindungsstatus", "mi.url": "Adresse der lokalen Bridge", "mi.connect": "Lokalen TimsMiner verbinden",
  "mi.tele": "Telemetrie", "mi.table": "Diagramm als Tabelle", "mi.arm": "Forschung scharf schalten", "mi.start": "Begrenzten Test starten", "mi.restore": "Original-Firmware wiederherstellen",
  "mi.locked": "Scharfschalten, Arbeit und Firmware-Aktionen sind im Demo-Modus und in dieser Read-only-Version nicht verfügbar.",
  "mi.demo.id": "Kein Gerät. Nur Demo-Knoten.", "mi.demo.state": "DEMO – es werden keine LAN-Anfragen gesendet.", "mi.src.demo": "DEMO / SIMULIERT – Fixture mit festem Seed, keine Hardware.",
  "mi.err.url": "Die Bridge muss auf diesem Rechner laufen (127.0.0.1 oder localhost).", "mi.err.net": "Bridge nicht erreichbar. Starte sie auf diesem Rechner, oder der Browser hat die lokale Verbindung blockiert (Seitenberechtigung für das lokale Netzwerk prüfen).",
  "mi.ok": "Bridge erreichbar: Read-only-Modus. Es kann keine Arbeit gesendet und keine Firmware geschrieben werden.", "mi.gap": "Lücken markieren fehlende Messwerte; es wird nichts interpoliert.",
  "be.title": "Engine-Benchmarks", "be.note": "Jede Engine muss einen Selbsttest gegen die Referenz bestehen, bevor sie gewählt wird. Ergebnisse werden nur bei identischer Arbeitslast verglichen.",
  "be.run": "Engines prüfen & kleinen Benchmark laufen lassen", "be.reason": "Grund", "be.workload": "Arbeitslast", "be.unit": "Einheit", "be.value": "Wert",
  "be.units": "SHA-256-Kompressionen pro Sekunde (Software) und GH/s von SHA-256d-Mining (ASIC) sind verschiedene Einheiten. Sie werden nie ohne dokumentierte Umrechnung auf einer Achse gezeigt.",
  "be.running": "Läuft …", "be.selected": "Gewählte Software-Engine", "be.ok": "verfügbar", "be.no": "nicht verfügbar",
  "ev.title": "Nachweis-Protokoll", "ev.note": "Alles, was du hier berechnest, lässt sich mit Eingaben, Engine und Softwareversion exportieren. Nichts wird hochgeladen.", "ev.export": "Sitzung als JSON exportieren",
};

const fr: Dict = {
  skip: "Aller au contenu", lang: "Langue", tagline: "Du vrai silicium. Une science reproductible.", credit: "Fait avec amour par timfromhcs & hcsmedia.",
  "tab.overview": "Aperçu", "tab.analyzer": "Analyseur de tours", "tab.miner": "Labo mineur", "tab.bench": "Benchmarks moteurs", "tab.evidence": "Preuves",
  "ov.title": "SHA-256 pas à pas — et un nœud physique optionnel.",
  "ov.lead": "Suivez les 64 tours de SHA-256 dans votre navigateur, rejouez des en-têtes SHA-256d de type Bitcoin et — seulement si vous lancez le pont local sur votre réseau — consultez un nœud de recherche BM1366. Sans matériel, tout ici est une démo déterministe.",
  "ov.c1.t": "Analyseur de tours", "ov.c1.d": "Bourrage, planning des messages, 64 tours, registres a–h, Ch, Maj, Σ0, Σ1 et condensat, vérifiés avec Web Crypto.",
  "ov.c2.t": "Labo mineur", "ov.c2.d": "La télémétrie de démo est simulée et étiquetée. Le direct exige le pont loopback que vous lancez vous-même ; cette page ne scanne jamais votre réseau.",
  "ov.c3.t": "Benchmarks moteurs", "ov.c3.d": "WebGPU, WebAssembly et CPU sont testés contre la référence. Les échecs basculent visiblement.",
  "ov.bound.t": "Ce qui est mesuré, et ce qui ne l'est pas", "ov.th.source": "Source", "ov.th.what": "Ce qu'elle montre", "ov.th.not": "Ce qu'elle ne montre jamais",
  "ov.row.asic": "ASIC BM1366", "ov.row.asic.w": "Débit de travail de type minage SHA-256d, nonces candidats, télémétrie — chaque candidat est re-haché sur l'hôte.", "ov.row.asic.n": "Entrées SHA-256 arbitraires, états internes ou traces par tour.",
  "ov.row.sw": "Analyseur de tours", "ov.row.sw.w": "FIPS 180-4 en logiciel : bourrage, planning, 64 tours, condensat.", "ov.row.sw.n": "Quoi que ce soit lu depuis l'ASIC.",
  "ov.row.demo": "Démo", "ov.row.demo.w": "Jeux de données déterministes marqués DEMO / SIMULÉ.", "ov.row.demo.n": "Données matérielles en direct.",
  "an.title": "Analyseur de tours SHA", "an.note": "Calculé dans votre navigateur en arithmétique 32 bits exacte. Ce n'est pas une trace lue sur le BM1366.",
  "an.mode": "Entrée", "an.mode.text": "Message texte", "an.mode.hex": "Octets hex", "an.mode.header": "En-tête Bitcoin de 80 octets (SHA-256d)",
  "an.input": "Message", "an.rounds": "Tours (1–64)", "an.run": "Calculer la trace", "an.genesis": "Charger l'en-tête genesis", "an.export": "Exporter la trace JSON",
  "an.src": "SOFTWARE_REPLAY — calculé dans votre navigateur, pas lu depuis un ASIC.", "an.pad": "Bourrage", "an.block": "Bloc", "an.rounds.t": "Tours", "an.pick": "Tour",
  "an.err.hex": "Hex invalide.", "an.err.header": "Un en-tête Bitcoin fait exactement 80 octets (160 caractères hex).", "an.err.rounds": "Les tours doivent être entre 1 et 64.", "an.reduced": "Expérience à tours réduits : ce n'est pas du SHA-256 standard.",
  "an.webcrypto.ok": "Web Crypto confirme le condensat de référence.", "an.webcrypto.bad": "Web Crypto CONTREDIT le condensat de référence.", "an.webcrypto.na": "Web Crypto indisponible ; condensat non recoupé.",
  "mi.title": "Labo mineur · Nœud de recherche TimsMiner / BM1366", "mi.note": "Seule l'unité nommée timsminer est autorisée. Les autres appareils sont refusés. Le pont tourne sur votre ordinateur (127.0.0.1) ; cette page ne contacte jamais le mineur directement.",
  "mi.id": "Identité de l'appareil", "mi.state": "État de connexion", "mi.url": "Adresse du pont local", "mi.connect": "Connecter le TimsMiner local",
  "mi.tele": "Télémétrie", "mi.table": "Graphique en tableau", "mi.arm": "Armer la recherche", "mi.start": "Lancer un test borné", "mi.restore": "Restaurer le firmware d'origine",
  "mi.locked": "Armement, travail et actions firmware sont indisponibles en mode démo et dans cette version en lecture seule.",
  "mi.demo.id": "Aucun appareil. Nœud de démo seulement.", "mi.demo.state": "DEMO — aucune requête LAN n'est envoyée.", "mi.src.demo": "DEMO / SIMULÉ — jeu à graine fixe, pas du matériel.",
  "mi.err.url": "Le pont doit être sur cet ordinateur (127.0.0.1 ou localhost).", "mi.err.net": "Pont injoignable. Lancez-le sur cet ordinateur, ou le navigateur a bloqué la connexion locale (vérifiez l'autorisation réseau local du site).",
  "mi.ok": "Pont joignable : mode lecture seule. Aucun travail ne peut être envoyé ni firmware écrit.", "mi.gap": "Les trous marquent des échantillons manquants ; rien n'est interpolé.",
  "be.title": "Benchmarks moteurs", "be.note": "Chaque moteur doit réussir un auto-test contre la référence avant d'être choisi. Les résultats ne sont comparés que pour une charge identique.",
  "be.run": "Tester les moteurs & lancer un petit benchmark", "be.reason": "Raison", "be.workload": "Charge", "be.unit": "Unité", "be.value": "Valeur",
  "be.units": "Les compressions SHA-256 par seconde (logiciel) et les GH/s de minage SHA-256d (ASIC) sont des unités différentes. Jamais sur un même axe sans conversion documentée.",
  "be.running": "En cours…", "be.selected": "Moteur logiciel choisi", "be.ok": "disponible", "be.no": "indisponible",
  "ev.title": "Registre de preuves", "ev.note": "Tout ce que vous calculez ici peut être exporté avec ses entrées, son moteur et sa version. Rien n'est envoyé.", "ev.export": "Exporter la session JSON",
};

export const DICTS: Record<Lang, Dict> = { en, de, fr };
export const LANGS: Lang[] = ["en", "de", "fr"];

export function pickLang(languages: readonly string[], saved?: string | null): Lang {
  if (saved && (LANGS as string[]).includes(saved)) return saved as Lang;
  for (const l of languages) {
    const code = l.slice(0, 2).toLowerCase();
    if ((LANGS as string[]).includes(code)) return code as Lang;
  }
  return "en";
}

export const t = (lang: Lang, key: string): string => DICTS[lang][key] ?? en[key] ?? key;
