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
  production de `1d38df2` a passé 10/10 — via `vercel curl`, car il est protégé par
  Vercel Deployment Protection ; le script le dit au lieu de prétendre que l'URL est
  publique.

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

## Vérification (commit exact `c854560` et suivants)

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

## Licence

Apache-2.0. Voir [`LICENSE`](LICENSE).
