# HCS SHA Forge — Literature map

Snapshot date: 2026-11-01. Each row states what was actually read.

| Source | Reported claim | Read by us | Status |
|---|---|---|---|
| IACR ePrint 2026/232, Zhang, Li, Gao, Wang — *Collision Attacks on SHA-256 up to 37 Steps with Improved Trail Search* | First 37-step collision attack on SHA-256 (previous best: 31 steps, EUROCRYPT 2013); automated local-collision search plus two Boolean-function models for signed differential trails. | Abstract page fetched 2026-11-01. Page says "a minor revision of an IACR publication in EUROCRYPT 2026". Full PDF **not read**. | `SOURCE_CLAIM`. Concrete colliding pair, IV convention and cost model **not checked**. |
| IACR ePrint 2026/1120, Li, Zhang, Li, Liu, Qian, Zhu — *Pushing Collision Attacks on SHA-2 to 39 Steps* (last revised 2026-09-09, preprint) | 38-step SHA-256 and SHA-512 collisions at 2^104.3 and 2^125.4; 36-step SHA-256 at 2^57 with a concrete colliding pair; **no** effective 39-step SHA-256 attack; effective 39-step **SHA-512** at 2^178. | Abstract page fetched 2026-11-01; matches the AGENTBUILD snapshot. Full PDF **not read**; witness **not re-verified**. | `SOURCE_CLAIM`, preprint. |
| EternaX / HashSmash article (2026-10-21) | Competition-board 39-step SHA-256 submission with author-reported cost 2^118.35. | **Not fetched** this session. | `NOT VERIFIED`. Competition/author-reported; treat as such. |
| `timfromhcs/sha256-research-framework` README (19-round preimage claim) | See AGENTBUILD §11.1. | **Not fetched or built.** | `NOT VERIFIED`. Must be replayed at a pinned commit before any reuse. |
| NIST FIPS 180-4 | Canonical SHA-256. | Constants and structure checked by test: `K` and `IV` are re-derived from prime roots (`tests/test_sha_reference.py::test_constants_derive_from_primes`); NIST/CAVS vectors pass. | `REPRODUCED_HERE` for the reference implementation. |

## Discrepancy to resolve

ePrint 2026/1120's abstract credits the 37-step result to "Li et al. at CRYPTO 2026". ePrint 2026/232 (Zhang et al.) is marked EUROCRYPT 2026.
These may be different papers or a venue mismatch in the abstract. Not resolved; do not cite the venue for the 37-step result without reading the PDFs.

## Result classes are not comparable

A reduced-step collision, a semi-free-start collision, a reduced-round preimage, a SHA-512 result and a Bitcoin hash-rate
are different tasks. Nothing in the Forge ranks them on one scale. No full SHA-256 break is claimed or implied.

## Not yet done (research sprint items)

Read both PDFs for exact step/round indexing and IV model; fetch the HashSmash entry; pin and replay the user's framework; check `secworks/sha256` licence before any reuse; verify Chrome Local Network Access behaviour on the tested Chrome/Edge builds.
