# v3.6.0 release audit

**Status:** LOCAL RELEASE CANDIDATE — cloud publication pending.
**Candidate version:** `3.6.0`
**Candidate source:** the commit recorded in `research/v6/DEPLOYMENTS.md` (filled
after the final local commit; do not use a floating branch name as provenance).
**Previous stable:** `v3.5.0`, tag `725d2c35615b9ccf6f7fdc77cf0992bbc890b66c`.

## 1. Scope

Additive minor release:

- opt-in two-watched-literal SAT propagation with differential and benchmark
  evidence;
- SAT contract 1.2 (`formula_original_sha256`, repeated-literal normalization);
- partial-assignment predicate fix and certificate-deadline cap;
- Windows Vulkan teardown fix;
- web SAT input/canonical digest and normalization parity;
- external DRAT/LRAT/CakeLPR proof evidence;
- research-only separator counter prototype;
- refreshed docs, changelog and release notes.

No public field or command was removed. `P = NP` / `P ≠ NP` remains untouched
and open.

## 2. Local gates

| Gate | Result |
| :--- | :--- |
| L0 repository/provenance | PASS (branch from `origin/main` `33723dd`) |
| L1 version + compileall | PASS, `3.6.0` on all checked surfaces |
| L2 full pytest | see final run in `TEST_MATRIX.md` |
| L3 native build + CTest | PASS 21/21 |
| L4 SAT correctness / external proof | PASS (differential, benchmark, DRAT/LRAT/CakeLPR) |
| L5 counting prototype | PASS (204 oracle cases, research-only) |
| L6 mutation | PASS 54/54 (watched engine not yet in mutant list) |
| L7 shaders / Vulkan primitive | PASS 13/13 shaders; physical-device primitive dispatch |
| L8 web unit/build/E2E/a11y | PASS 17/17, build, 13/13 Playwright+axe |
| L9 Studio/CLI/MCP | PASS targeted tests |
| L10 security/supply chain | PASS secret scan, pip-audit, pinned actions, clean wheel |
| L11 cloud/release | pending PR CI, tag and asset upload |

## 3. Artifact policy for this release

The user requested a **locally built** release with no extra cloud build.
Artifacts are built on the release machine and uploaded to the GitHub release;
the tag-triggered release workflow is disabled for the publication window and
re-enabled afterwards. The exact source SHA is recorded in the release notes,
`DEPLOYMENTS.md` and the SBOM.

## 4. Decision

GO only if the final full local suite, clean-install smoke, exact-SHA CI and
Vercel preview pass. Production/release publication must not silently rebuild
different artifacts.
