# Blockers and open risks (v5)

| ID | Blocker | Effect | Next safe step |
| :--- | :--- | :--- | :--- |
| B-01 | No elan/Lean toolchain locally; the Anthropic build needs ≈7 GB RAM and ≈8 min on 24 vCPU (per its README) | Lean proofs and comparator/nanoda are `NOT RUN` by this project | Add an opt-in CI job that runs `lake build` + `PrintAxioms` on the pinned revisions |
| B-02 | No formally verified proof checker (cake_lpr) available | DRAT checks use the in-repo checker (D-02), which is not formally verified | Package cake_lpr in CI and cross-check the in-repo checker against it |
| B-03 | SAT Competition 2026 instances: licence and size need review before vendoring | No competition benchmark numbers are claimed | Pick a licence-cleared subset and pin it by SHA-256 |
| B-04 | Open Quantum and IBM keys from earlier runs still valid | Credential risk, not a code risk | The owner rotates them at the providers |
