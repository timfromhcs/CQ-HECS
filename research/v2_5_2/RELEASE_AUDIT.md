# CQ-HECS v2.5.2 Release Audit

## 1. Provenance

- PR: https://github.com/timfromhcs/CQ-HECS/pull/17, head
  `3f5972909343fe4d8c1c5ac1d727f201d345c730`, merged as
  `a65c35baebfe88f9497130de1c1ad060695448b9` (merge commit).
- Tag `v2.5.2` → `a65c35baebfe88f9497130de1c1ad060695448b9` (`git ls-remote`).
- Release: https://github.com/timfromhcs/CQ-HECS/releases/tag/v2.5.2
  (published 2026-10-30T02:27:15Z, not draft, not prerelease).
- CI on the merged SHA: https://github.com/timfromhcs/CQ-HECS/actions/runs/40991232761 — success.
- Release pipeline: https://github.com/timfromhcs/CQ-HECS/actions/runs/40991232929 — success
  (created the tag after green CI on `main`).

## 2. Exact-SHA CI on the PR head (`3f59729`)

- push run https://github.com/timfromhcs/CQ-HECS/actions/runs/40990556773 — success
- pull_request run https://github.com/timfromhcs/CQ-HECS/actions/runs/40990588972 — success, 7/7:
  static checks & package smoke; Linux C++20/Vulkan/full Python suite with
  coverage and mutation gate; Windows C++20/Vulkan/full suite; Linux
  ASan+UBSan; Python 3.12/3.13/3.14 compatibility.

## 3. Assets (downloaded and re-hashed independently)

`sha256sum -c sha256sums.txt` on the downloaded files: all OK.

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `cqhecs-2.5.2-py3-none-any.whl` | 153016 | `39f9d67220b691b21f681938b96405f2e2c71be48bd5c6bdab1393c1a38ece03` |
| `cqhecs-2.5.2.tar.gz` | 225150 | `cfa48e9046014deacb8d743e908131d908ed6bb1b4b438500c8d821b5e648274` |
| `cqhecs-sbom.spdx.json` | 1717 | `9deab0be54bc015b2469dbc20cb99c75aaefdc44419cc404207e2f8509c5b4ff` |
| `RELEASE_NOTES_v2.5.2.md` | 5669 | `919a2c8cf65abffe54885bfac708e75871017965116fcfe411fc6739b1446b0c` |
| `sha256sums.txt` | 360 | `9346ef6ad028423628a1506bac1d75874129f3caf5d3749d6f695101343427b2` |

- SBOM: SPDX-2.3, package version `2.5.2`.
- Release-notes asset starts with `Source commit: a65c35b…` and the required
  CI run above.
- The published wheel (153016 B) differs from the local candidate build
  (153024 B); only the published files are authoritative.

## 4. Published wheel smoke test (clean CPython 3.11 venv)

- `cq-hecs version` → `2.5.2`.
- Path B `h t s h`: `P(0) = 0.1471` (v2.5.1 wheel: 0.8505; closed form 0.146).
- `fake_manila` `sx` channel infidelity `0.00025` = reported gate error
  (v2.5.1: 0.000125).
- `--profile fake_manila name:bell`: `NOISY_CLASSICAL`, `{00: 469, 01: 30, 10: 27, 11: 474}`.

## 5. Gate summary

| Gate | Status |
|---|---|
| A Baseline / reproducibility | PASS (BASELINE.md) |
| B Scientific correctness | PASS — P0/P1 findings fixed with independent-oracle tests |
| C Software quality | PASS — CI 7/7 on `3f59729` and on `a65c35b`; 483 local tests; 24/24 mutants |
| D Performance evidence | NOT RUN — no performance claim |
| E GPU/QPU honesty | PASS — no real QPU; Vulkan evidence software ICD only in this audit |
| F Security / supply chain | PASS — pinned actions unchanged; checksums + SBOM verified |
| G Docs and release | PASS — tag = version = merged SHA; assets re-hashed |

## 6. Known limitations

As in RELEASE_NOTES.md §4; CQ-V252-06 (QASM `gate` definitions) deferred.
