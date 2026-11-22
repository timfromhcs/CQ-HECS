<!-- Language selector: keep the three files in sync (tests/test_readme_languages.py) -->
<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a> · <b>Français</b></p>

<div align="center">

# CQ-HECS

**Simulation quantique classique avec résultats attestés — et un laboratoire de recherche SHA-256 pour du matériel réel.**

</div>

> **Note sur la langue :** `README.md` (anglais) fait foi. Cette traduction couvre
> entièrement les parties utiles du produit ; les dossiers de recherche sous `research/`
> et `docs/` restent en anglais pour la traçabilité. Les chiffres ci-dessous sont
> identiques à la version anglaise et sont vérifiés par un test.

---

## Ce qu'est CQ-HECS

CQ-HECS est un simulateur classique de circuits quantiques basé sur un routeur. Il ne
cherche pas à être un algorithme unique : il analyse le circuit, choisit le chemin adapté
et renvoie un résultat typé qui dit ce qui a été calculé — et ce qui ne l'a pas été.

S'y ajoute **HCS SHA Forge** : une surface de recherche bornée et fondée sur des preuves
autour de SHA-256, qui relie trois implémentations et un mineur physique.

## Ce qu'il n'est pas

- Pas une preuve sur P vs NP, pas d'affirmation sur la sécurité de SHA-256.
- Pas un « analyseur de tours ASIC » : le BM1366 calcule en interne et renvoie des nonces,
  pas un état de tour.
- Pas un remplaçant de CaDiCaL ou Kissat ; les solveurs intégrés sont des références.
- Pas d'accès matériel automatique : le navigateur ne peut pas joindre le mineur
  directement (mesuré, voir plus bas).

## Solveur unifié

Un point d'entrée sur quatre moteurs — DPLL intégré (scan et watched), OMNIWAVE et
CaDiCaL si `python-sat` est installé — avec un schéma de résultat et un dossier de
preuves : quel moteur a décidé, chaque tentative avec son budget, et le statut de preuve
de chaque moteur.

- `unified.solve_unified(formula)` renvoie `hcs.sat.unified.v1` : statut, moteur, ordre,
  fractions de budget, tentatives, affectation vérifiée, taille du certificat, empreinte
  de la formule.
- Le portefeuille re-vérifie chaque modèle SAT contre la CNF d'origine et ne promeut
  jamais un statut de preuve UNSAT ; un backend optionnel absent est signalé comme
  `unavailable`, jamais ignoré.
- CLI : `cq-hecs sat solve --cnf ... --engine unified`.
- Mesuré sur cinq familles, deux fois : **zéro désaccord**, une fois sans le backend
  optionnel (Python 3.14 ici, sans `python-sat`) et une fois avec **CaDiCaL 1.9.5** dans un
  environnement Python 3.12. Avec CaDiCaL, `watched` était le plus rapide sur trois familles
  et `cadical` sur deux ; l'ordre déclaré y coûte 0,12 s et 0,16 s — c'est écrit, pas caché.
  Tableaux et données brutes : [`docs/UNIFIED_SOLVER.md`](docs/UNIFIED_SOLVER.md).

## Provenance (`hcs.run.v2`)

Une fiche de provenance par exécution, commune à la CLI, au Studio et au navigateur : le
texte d'entrée exact et son SHA-256, le type/précision/mode du moteur, la graine, la version
logicielle et la révision source, les trois types d'erreur séparés (approximation, virgule
flottante, échantillonnage) et les limites déclarées. L'empreinte porte toujours sur la
charge utile stockée dans la fiche : elle se vérifie sans autre fichier.

- CLI : `cq-hecs sat solve --cnf … --provenance card.json`
- Navigateur : l'export du laboratoire écrit le même schéma
- Les anciennes fiches v1 (`cqhecs.web.run/1.1`) sont **refusées** avec un renvoi vers la
  régénération, jamais réinterprétées.

Détails : [`docs/PROVENANCE.md`](docs/PROVENANCE.md), migration :
[`MIGRATION_V5.md`](MIGRATION_V5.md).

## Moteurs navigateur (Vercel, WebAssembly, WebGPU)

Les mêmes circuits tournent dans le navigateur via trois moteurs : un cœur
Rust/WebAssembly en f64 (chemin exact), un chemin WGSL/WebGPU en f32 (chemin rapide,
seulement avec un adaptateur) et un repli CPU en TypeScript. Ce sont des implémentations
indépendantes, pas le moteur Python ; la seule affirmation est leur accord sur un corpus
déclaré.

- **Corpus de conformité :** six circuits avec une référence NumPy dense, rejoués dans le
  cœur WASM ; les amplitudes (pas seulement les probabilités) sont comparées à `1e-12`.
  Un test casse volontairement une entrée de matrice et doit échouer.
- **Budget de bundle :** `npm run build` échoue au-delà de 270 Ko gzip de JavaScript,
  18 Ko de WASM et 8 Ko de CSS ; mesuré le 2026-11-02 : 233,5 / 15,0 / 6,6 Ko.
- **Contrôle de livraison :** `npm run verify:deploy -- <url>` vérifie la coquille, les
  en-têtes de sécurité, le type MIME et la politique de cache du WASM. Le déploiement de
  production public (`https://cq-hecs-web.vercel.app`, ancien commit `e7e5c1e`, non relancé pour le candidat 7.0.0) a passé 10/10 en anonyme, sans
  `--via-cli` (la Deployment Protection est désactivée depuis le 2026-11-02, voir
  `docs/WEB_ENGINES.md`) ; si une page de protection revenait, le script la détecte et
  quitte avec le code 3.

- **Corpus avec un oracle indépendant :** six cas OpenQASM lus par l'analyseur du
  navigateur et comparés à **Qiskit 2.5.1 Statevector** à `1e-12` ; un test inverse un CNOT
  et doit échouer. Mesure sur 12/16/20 qubits : 0,20 / 4,08 / 111,5 ms en médiane. WebGPU
  n'a **aucun** chiffre ici — le Chromium fourni n'expose pas d'adaptateur, donc la colonne
  indique `NOT RUN` au lieu d'un nombre inventé.
  [`docs/CONFORMANCE.md`](docs/CONFORMANCE.md).

Détails : [`docs/WEB_ENGINES.md`](docs/WEB_ENGINES.md).

## OMNIWAVE

Recherche exhaustive par cubes avec preuves UNSAT vérifiées, plus une heuristique de
branchement apprise, optionnelle. Pris en charge avec un périmètre explicite :

- `SAT` seulement avec un modèle vérifié contre la CNF d'origine, `UNSAT` seulement avec
  une preuve acceptée par `cqhecs.drat`, sinon `UNKNOWN`.
- Réécriture de la propagation le 2026-11-02 : instance SHA-256 W=16 r=8 de 0,26 s à
  0,11 s (2,4×), pigeons quasi inchangé (le coût y est le nombre de fronts).
- L'heuristique apprise est intégrée, **désactivée par défaut** et non promue : sur
  l'instance pigeons retenue, elle demande 157 973 fronts au lieu de 10 079.
- Référence : [`docs/OMNIWAVE.md`](docs/OMNIWAVE.md).

## Nouveautés depuis la dernière publication (brouillon `7.0.0`)

Cette branche est en avance sur la dernière publication. Le détail, réparti en implémenté /
expérimental / mesuré / vérifié formellement / non pris en charge, est dans
[`RELEASE_NOTES_DRAFT.md`](RELEASE_NOTES_DRAFT.md) ; chaque changement visible pour
l'appelant, avec des exemples exécutés, dans [`MIGRATION_V7.md`](MIGRATION_V7.md). En bref :

- **Un plan, quatre surfaces :** `cq-hecs plan`, Python, MCP et Studio renvoient le même
  document `ExecutionPlan` (un test vérifie l'égalité). Studio a OpenAPI 3.1 et `/api/v1` ;
  chaque appel exige un jeton par lancement (**changement pour les scripts**).
- **MaxSAT typé :** `OPTIMAL` seulement après énumération exhaustive (20 variables au
  plus), sinon `UNKNOWN` ; pas de certificat d'optimalité.
- **Erreurs déclarées honnêtement :** le chemin A tire chaque tir demandé ou refuse avec un
  type d'erreur ; pour les chemins B et C, `numerical_error_bound` reste `None` (non
  dérivé, pas zéro). Les portes sans canal calibré figurent dans `uncovered_gates` ; le
  schéma de calibration v3 porte l'origine et la fraîcheur.
- **Natif et web :** ABI 1.1, arguments validés, injection de fautes Vulkan ; WebGPU
  bascule visiblement sur WASM en cas de perte de périphérique.
- **Laboratoire Quantum Gravity :** modèles finis sur référence classique, sans envoi de
  job, sans identifiants et sans coût ; aucune mesure de la gravité.
- **Formel :** lemmes de spécification Lean (`FORMALIZED_LEMMA`), pas de preuve de
  raffinement du code. Les chemins de recherche E, F, G sont restés `RESEARCH_ONLY` et ne
  sont pas routables.

## Vérification

Deux tableaux séparés, pour qu'aucun chiffre ne soit attribué au mauvais commit.

### État actuel du développement (`release/v7-stable`)

| Contrôle | Résultat | Preuve |
|---|---|---|
| Suite Python, Windows, relancée sur `f880d0a` + arbre de travail wave F | 4314 réussis, 133 ignorés, 0 échec | `research/v7/evidence/waveE_E2.md` (relevé de l'intégrateur) |
| Tests ignorés | dépendent de l'environnement, pas des échecs, mais pas une preuve non plus. Le contrôle du budget (`skip_budget.py --check`) a échoué au gel (134 contre un budget de 105 ; B-V7-11) ; le budget est désormais par environnement, les 133 ignorés de l'exécution récente sont dans le budget `default` | `research/v7/SKIP_BUDGET.json` |
| Tests de mutation, sur place au gel | 95/95 tués | `research/v7/evidence/waveE_E2.md` |
| CTest natif (Vulkan actif / CPU seul) | 26/26 / 15/15 | `research/v7/evidence/waveE_E2.md`, `waveA_A2.md` |
| Tests unitaires web | 167/167 | `research/v7/evidence/waveE_E2.md` |
| Playwright | 128 réussis / 1 ignoré (WebGPU, NOT_RUN : aucun adaptateur) ; interface de plan Studio : 6 | `research/v7/evidence/waveE_E2.md` |
| CI hébergée | rouge à `38e799b` (B-V7-15) ; à `f880d0a`, selon l'intégrateur, toutes les lanes sont vertes sauf la lane Windows complète encore en attente, non revérifié ici auprès de GitHub | `research/v7/RELEASE_CANDIDATE_AUDIT.md` |
| Artefacts de release | construits depuis `38e799b`, non publiés | `research/v7/evidence/waveE_E2.md` |
| Exécuté en plus (hébergé, `38e799b`) | Linux GCC-12 ASan+UBSan 9/9, Linux CPU seul, Linux lavapipe (ICD logiciel) CTest 26/26 (conformité seulement, pas une preuve de GPU physique) | `research/v7/evidence/waveE_E3.md` |
| Non exécuté | sanitizers Clang, WebGPU sur matériel (exécution partielle seulement), `drat-trim`, `lrat-check`, `cake_lpr`, installation sur machine propre, publication (aucun tag n'existe encore) | `RELEASE_NOTES_DRAFT.md` |

### Mesure historique (commit exact `c854560`)


| Contrôle | Résultat |
|---|---|
| Suite Python, Linux / Python 3.11 | 2786 réussis, 7 ignorés |
| Suite Python, Windows / Python 3.11 | 2690 réussis, 53 ignorés |
| CTest (natif, Release) | 21/21 |
| Tests de mutation | 60/60 tués |
| Tests unitaires web | 39/39 |
| Playwright + axe | 41/41 |
| Solveur unifié | 0 désaccord entre quatre moteurs sur cinq familles |
| Campagne sur l'appareil | 8 blocs, 512 tours, tous confirmés par le replay Python et le C hôte |
| OTA par WLAN | HTTP 200 en 23,2 s, appareil revenu sur `ota_0`, minage repris automatiquement |

## Démarrage rapide

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
python -m pip install -e ".[dev]"

cq-hecs selftest --cases 4
cq-hecs sat solve --random 40 --engine unified
python -m pytest tests/ -q
```

## Limites

- Les quatre chemins A–D sont de l'émulation classique, pas de l'exécution sur QPU.
- Les modèles de bruit sont des modèles mathématiques ; une calibration mesurée est
  étiquetée comme telle.
- Le navigateur n'exécute pas le moteur Python ; le site documente les résultats mesurés,
  il ne revendique pas d'OMNIWAVE côté client.
- Le mineur est un appareil unique et explicitement autorisé ; aucun autre appareil du
  réseau n'est contacté.

## Documentation

| Sujet | Fichier |
|---|---|
| Solveur unifié | [`docs/UNIFIED_SOLVER.md`](docs/UNIFIED_SOLVER.md) |
| OMNIWAVE | [`docs/OMNIWAVE.md`](docs/OMNIWAVE.md) |
| Pont local | [`docs/LOCAL_BRIDGE.md`](docs/LOCAL_BRIDGE.md) |
| Analyse des tours SHA | [`docs/SHA_ROUND_ANALYZER.md`](docs/SHA_ROUND_ANALYZER.md) |
| Dossier de recherche | [`research/sha_forge/`](research/sha_forge/) (anglais) |
| Architecture (faisant foi) | [`ARCHITECTURE.md`](ARCHITECTURE.md) (`docs/ARCHITECTURE.md` est un état historique) |
| Migration | [`MIGRATION_V7.md`](MIGRATION_V7.md) |
| Brouillon des notes de version | [`RELEASE_NOTES_DRAFT.md`](RELEASE_NOTES_DRAFT.md) |

## Licence

Apache-2.0. Voir [`LICENSE`](LICENSE).
