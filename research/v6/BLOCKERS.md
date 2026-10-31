# v6 blockers and open risks

| ID | Blocker / risk | Effect | Next safe step | Status |
| :--- | :--- | :--- | :--- | :--- |
| B-01 | Lean 4.33.1 build, Comparator and `nanoda` all passed on the pinned Anthropic artifact | ETH Lean artifact is reproduced here, including statement equality and the second kernel | Add the same pinned check to an opt-in CI job | RESOLVED locally; CI TODO |
| B-02 | CakeML `cake_lpr` and `lrat-check` were built and accepted the committed LRAT vector | The Python checker itself remains unverified | Add the pinned checker to an optional CI job; record the trust boundary | RESOLVED for the vector; CI TODO |
| B-03 | SAT Competition 2026 instance licences and size are not cleared for vendoring | No competition benchmark numbers may be claimed | Select a licence-cleared subset and pin SHA-256 | OPEN |
| B-04 | Open Quantum / IBM credentials from earlier runs are still reported valid | Credential risk, not a code defect | Owner rotates them at the providers; never stage ignored key files | OPEN (owner action) |
| B-05 | Local `main` is stale and must not be used as a base | Could cause a wrong baseline | Always branch from fetched `origin/main`; never reset user work | MITIGATED in this branch |
| B-06 | Vercel project state is not re-verified in this session | Preview/Production claims would be unproven | Read project settings and deployment SHA before any preview claim | OPEN |
| B-07 | Full Windows artifact re-download/hash not repeated here | Release asset claim relies on the v5 audit + GitHub digests | Re-download and hash at M12/M14 | OPEN |

## Escalation rule

After three focused repair cycles for the same defect without a root cause, mark
the task `BLOCKED`, preserve the reproducer, and continue unrelated safe work.
Never delete or skip a test to obtain green CI.
