# CQ-HECS v2.5.1 Release Audit

## 1. Provenance

- Tag `v2.5.1` → `1be682a20ca3ccc9079893e0b150217a568a23e6` (merge of PR #16,
  which contains the PR #15 fixes merged as `9c1a877`).
- Release: https://github.com/timfromhcs/CQ-HECS/releases/tag/v2.5.1
  (published 2026-10-30T01:21:05Z, not draft, not prerelease).
- Release pipeline run: https://github.com/timfromhcs/CQ-HECS/actions/runs/40984668504
  (`success`). It was triggered by the push to `main`, found no `v2.5.1` tag,
  waited for green CI on `1be682a`, then created tag and release.
- Required CI named in the release notes: https://github.com/timfromhcs/CQ-HECS/actions/runs/40984668303
- The tag was created by the pipeline because the agent session could not
  push tags (HTTP 403 from its git proxy); see EXECUTION_LOG.md §7.

## 2. Assets (downloaded and re-hashed independently)

`sha256sum -c sha256sums.txt` on the downloaded files: all OK. Values also
match GitHub's per-asset digests.

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `cqhecs-2.5.1-py3-none-any.whl` | 150956 | `9eb318a5db005215a6cfbf2bfa59d25ccfc117e9d7d63b4176508e191e673500` |
| `cqhecs-2.5.1.tar.gz` | 219465 | `df63489cff508f24cefb6ef207da2376651747cc11ef6e9494ff6a52d99aaaee` |
| `cqhecs-sbom.spdx.json` | 1717 | `d85889a4bbda5031a5bc31d58096373f0044d0a4fff784b6b163f7bcc7b835c5` |
| `RELEASE_NOTES_v2.5.1.md` | 5281 | `b6229e4e0be3660f2a8befd4d43c699538963c57dfe720fb5de6d9f6442019f3` |
| `sha256sums.txt` | 360 | `7f70e3a278b6dc4625f10e16f415be927d2496197a77d0f8adcc12c92fcc3731` |

- SBOM: SPDX-2.3, package version `2.5.1`.
- Release notes asset starts with `Source commit: 1be682a…` and describes
  v2.5.1 (the v2.5.0 mismatch, CQ-V251-06, does not recur).
- The local candidate wheel (built from `777a66f`) had the same size as the
  published wheel; the sdist differs (219846 vs 219465 B) because it was built
  from a different working tree. Only the published files are authoritative.

## 3. Published wheel smoke test (clean venv)

- `cq-hecs version` → `2.5.1`.
- `x q[0]; measure q -> c;`: router `{"01": 16}`, `--profile fake_manila
  --no-noisy` `{"01": 16}` (v2.5.0 wheel gave `{"10": 16}` on the profile path).
- `profile show fake_manila`: provider `CQ-HECS-Synthetic`, synthetic `True`.

## 4. Gate summary

| Gate | Status |
|---|---|
| A Baseline / reproducibility | PASS (BASELINE.md) |
| B Scientific correctness | PASS — P0/P1 findings fixed with independent-oracle tests |
| C Software quality | PASS — CI 7/7 on `777a66f`, `f91bbe4`; 470 local tests; 20/20 mutants |
| D Performance evidence | NOT RUN — no performance claim made |
| E GPU/QPU honesty | PASS — no real QPU used; synthetic profiles labelled |
| F Security / supply chain | PASS — pinned actions unchanged; checksums + SBOM verified; offered PAT not used |
| G Docs and release | PASS — tag = version, assets re-hashed, notes match release |

## 5. Known limitations

- Circuits are not transpiled to profile basis gates; uncalibrated gates are
  noiseless.
- No mid-circuit measurement, reset or classical control.
- Physical GPU evidence unchanged (one AMD iGPU, primitives only); this audit
  ran on Mesa llvmpipe.
- The published v2.5.0 release-notes asset still describes v2.4.0 (erratum in
  `research/v2_5/RELEASE_AUDIT.md`).
