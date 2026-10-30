# v3.0.0 release audit

**Audited:** 2026-10-30, after publication, from a separate environment.
**Result:** PASS. Every published asset was downloaded and its SHA-256
recomputed independently; all agree with `sha256sums.txt`, the release body
and GitHub's own asset digests.

## 1. Source and CI

| Item | Value |
| :--- | :--- |
| Tag | `v3.0.0` → `86784b4419965ff1aadabcbd12f1bcc92fbfe12f` (merge of PR #27) |
| Release | https://github.com/timfromhcs/CQ-HECS/releases/tag/v3.0.0 (published 2026-10-30T15:12:41Z, not a draft or pre-release) |
| Required CI on the tag SHA | https://github.com/timfromhcs/CQ-HECS/actions/runs/41077263731 — success, 7/7 jobs |
| Release pipeline | https://github.com/timfromhcs/CQ-HECS/actions/runs/41077263764 — success |
| CI on the release-candidate head `00a5980` | push 41075891817, pull_request 41075928684 — both success |
| Linux lane, native required (head `74f7b77`, same code as the tag except release surfaces) | 594 passed, 0 skipped, 1 opt-in slow gate deselected; branch coverage 86 %; CTest 21/21; mutation 40/40; selftest 12/12 |

## 2. Assets (independently recomputed SHA-256)

| Asset | Bytes | SHA-256 | `sha256sums.txt` | Release body | GitHub digest |
| :--- | ---: | :--- | :---: | :---: | :---: |
| `cqhecs-3.0.0-py3-none-any.whl` | 202 789 | `f16608a0df354a335631265e2f2ed7f4cefad0e87d5d7f3611eaf32b26e25059` | ✓ | ✓ | ✓ |
| `cqhecs-3.0.0.tar.gz` | 307 377 | `3ae1df6a539797c609141b9fc71fdb65136047a49d1e3fafeab55f3745bc339a` | ✓ | ✓ | ✓ |
| `cqhecs-sbom.spdx.json` | 1 717 | `ebff2b1adda621711b6830dddd898d24106541bae6c216cdc0c9e3d5826a727e` | ✓ | ✓ | ✓ |
| `RELEASE_NOTES_v3.0.0.md` | 6 111 | `5e7ad2f1a35af6be66a5c06a9b4621f763e96b5ad9ac267a8c98ec50fb91f285` | ✓ | ✓ | ✓ |
| `sha256sums.txt` | 360 | `ac2eb0e8cd3e7ae09112abc1b20558c472083dfd0064df78ffc7de246fc03537` | — | — | ✓ |

## 3. Content checks

- SBOM: SPDX-2.3, document `CQ-HECS-v3.0.0-SBOM`, package `cqhecs 3.0.0`
  with its declared dependencies (`numpy`, `qiskit`).
- Wheel contents: `cqhecs/` (27 files), `python_bridge/` (7),
  `cqhecs-3.0.0.dist-info/` (6). No native binaries, as documented.
- Credential scan of wheel and sdist (every file's bytes) for the Open
  Quantum key prefixes used during the `r-io-7` run: no match. No
  `QUANTUM_RUN.md`, key file or `.openquantum` path in either archive.
- Clean-venv smoke test of the downloaded wheel: `cq-hecs version` →
  `3.0.0`; `cq-hecs selftest` → PASS; `cq-hecs --format json run name:bell
  --profile fake_manila --shots 500` → counts `{00: 221, 01: 15, 10: 16, 11:
  248}`, `execution_mode = NOISY_CLASSICAL`.

## 4. Final gate table

| Gate | Status |
| :--- | :--- |
| V3-A calibration import | PASS |
| V3-B Aer parity | PASS (amended criterion E-V3-02; original 1e-9 recorded as not met on manila) |
| V3-C Sycamore gates | PASS |
| V3-D real-data reference | PASS — R-IO-7, H-V3-8 `SUPPORTED` (one backend, one day) |
| V3-E schema 2.0 / migration | PASS |
| V3-F CI on release SHA, assets re-hashed, audit | PASS (this document) |
| GEMINI A repository truth | PASS |
| GEMINI B scientific correctness | PASS (CQ-V3-01…04 fixed) |
| GEMINI C quantum correctness | PASS within declared scope |
| GEMINI D SAT correctness | PASS (CQ-V3-01…03 fixed, brute-force differential) |
| GEMINI E hardware/GPU truth | PASS (no package-run QPU job, no physical-GPU claim) |
| GEMINI F UX/observability | PASS (CQ-V3-06/08) |
| GEMINI G software quality | PASS (7/7 CI, 40/40 mutants, sanitizers) |
| GEMINI H performance | PASS by abstention (no performance claim) |
| GEMINI I supply chain | PASS (pinned actions, SBOM, independently verified checksums, no credentials in assets) |
| GEMINI J docs/release | PASS (all version surfaces 3.0.0, notes match the tag, wheel smoke test) |

## 5. Known limitations carried into 3.0.0

- Real-hardware evidence is one backend, one day, no calibration snapshot,
  no published layout (H-V3-9).
- No physical-GPU verification; CI uses a software Vulkan ICD.
- The package itself submits no QPU jobs (Open Quantum adapter, W6, open).
- The CLI prints a traceback instead of exiting quietly when its stdout pipe
  is closed early (e.g. `| head`); cosmetic, recorded for 3.0.1.
