# HCS SHA Forge - Literature map

Snapshot date: 2026-11-01, updated 2026-11-02 with the sources that were actually fetched in the second pass. Each row states what was actually read.

| Source | Reported claim | Read by us | Status |
|---|---|---|---|
| IACR ePrint 2026/232, Zhang, Li, Gao, Wang - *Collision Attacks on SHA-256 up to 37 Steps with Improved Trail Search* | First 37-step collision attack on SHA-256 (previous best: 31 steps, EUROCRYPT 2013); automated local-collision search plus two Boolean-function models for signed differential trails. | Abstract page fetched 2026-11-01. Page says "a minor revision of an IACR publication in EUROCRYPT 2026". Full PDF **not read**. | `SOURCE_CLAIM`. Concrete colliding pair, IV convention and cost model **not checked**. |
| IACR ePrint 2026/1120, Li, Zhang, Li, Liu, Qian, Zhu - *Pushing Collision Attacks on SHA-2 to 39 Steps* (last revised 2026-09-09, preprint) | 38-step SHA-256 and SHA-512 collisions at 2^104.3 and 2^125.4; 36-step SHA-256 at 2^57 **with a verified colliding message pair**; effective 39-step **SHA-512** at 2^178; **no** effective 39-step SHA-256. | Full abstract re-read 2026-11-02. Full PDF **not read**; the 36-step witness **not re-verified here**. | `SOURCE_CLAIM`, preprint. The 36-step pair is the one artifact a future session could actually check. |
| EternaX Labs blog, D. Porechna - *Pushing Collision Attacks on 39-Step SHA-256 Below Generic Search* (2026-10-21) | 39-step SHA-256 differential attack at ~2^118.35 board cost against 2^124.83 for the best accepted generic search; ~2^127.6 under the harshest accounting; built on the 2026/1120 trail by freeing two state words and rebuilding the step-16 condition as a claw search. | **Read in full** 2026-11-02. The source states its own limits: not a break, no colliding pair from the standard IV, not peer-reviewed, 25 rounds of margin remain. | `SOURCE_CLAIM` from the author, with those non-claims repeated here rather than dropped. |
| HashSmash / Yukon board (`yukon.org/hashsmash`) | Live frontier table for reduced-round SHA-256 collisions; cost is log2 of charged work in a fixed word-RAM model, memory penalised above 1 MiB. | Board table fetched 2026-11-02. At that moment the 39-round frontier was ~2^116.58 (AI-reviewed) and 40-round entries sat at ~2^123.9. **A live board: these numbers move.** | `OBSERVED_AT_DATE`. Board acceptance is not peer review. |
| `timfromhcs/sha256-research-framework` (main `050cff7b254078f5c4e35aadb995a2be5a4bfe87`, README "v5.0.0 + unreleased throughput work") | No cryptanalysis claim of its own: a local-first platform (native CPU, Vulkan, SAT/SMT, independent verifier, tamper-evident evidence packages) with an L0-L5 epistemic trust model. Its README states plainly that **no full SHA-256 collision is demonstrated** and that agent output is never treated as proof. | README fetched and read 2026-11-02 at that commit; **not built or run** here. | `SOURCE_CLAIM` for the architecture; nothing `REPRODUCED_HERE`. Any result of that framework must be replayed at the pin before reuse. |
| NIST FIPS 180-4 | Canonical SHA-256. | Constants and structure checked by test: `K` and `IV` are re-derived from prime roots (`tests/test_sha_reference.py::test_constants_derive_from_primes`); NIST/CAVS vectors pass. | `REPRODUCED_HERE` for the reference implementation. |

## Discrepancy to resolve

ePrint 2026/1120's abstract credits the 37-step result to "Li et al. at CRYPTO 2026". ePrint 2026/232 (Zhang et al.) is marked EUROCRYPT 2026. The second reading confirms the CRYPTO 2026 attribution appears in 2026/1120 itself, so the mismatch is between the two papers' descriptions, not a transcription error here. Do not cite a venue for the 37-step result without reading both PDFs.

## What the second reading changed

- The HashSmash frontier is **further than the AGENTBUILD snapshot**: 39-step collisions are now below generic search on the board, and 40-step entries exist. Both are author/board claims inside a declared cost model, not peer-reviewed results.
- The framework is a platform, not a claim, and says so itself.

## Result classes are not comparable

A reduced-step collision, a semi-free-start collision, a reduced-round preimage, a SHA-512 result and a Bitcoin hash-rate are different tasks. Nothing in the Forge ranks them on one scale. No full SHA-256 break is claimed or implied.

## Not yet done (research sprint items)

Read both PDFs for exact step/round indexing and IV model; re-verify the 36-step colliding pair from 2026/1120 independently; pin and **build** the framework instead of reading its README; check `secworks/sha256` licence before any reuse; verify Chrome Local Network Access behaviour on the tested Chrome/Edge builds (B-07).
