# v6 deployments and cloud state

No cloud action has been taken for v3.6. This file records only verified state.

| Surface | Version / SHA | Status | Evidence |
| :--- | :--- | :--- | :--- |
| GitHub `origin/main` | `33723dda200428d50f0923fa7bccb7726ff88e47` | CI success `41178394449`; release run `41178394448` success (no-op) | `gh run list`, `gh release view` |
| GitHub Release `v3.5.0` | tag `725d2c35615b9ccf6f7fdc77cf0992bbc890b66c` | published, not draft | `gh release view v3.5.0` |
| Vercel project `cq-hecs-web` | unknown for v3.6 | not re-verified in this session | must be checked before a preview claim |
| Vercel Production | recorded in v5 audit as bundle SHA `725d2c3`, deployment `dpl_3UnqEcDSXToopPPE6DJyYPKLW5Qq` | historical, not re-tested | `research/v5/RELEASE_AUDIT.md` |

Feature branch: `agent/v3.6.0-sat-core`, local only at the time of writing.
No push, PR, preview, merge, tag, release or production deploy has been performed.
