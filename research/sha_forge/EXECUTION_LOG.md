# HCS SHA Forge — Execution log

Date: 2026-11-01. Operator: timfromhcs. Agent session: Claude Code (Sonnet 5.5). All times local; only events that happened are listed.

1. Read `E:\qCSHA\AGENTBUILD.md`. Inspected CQ-HECS (`423e389`, v4.0.0, clean) and ESP-Miner (`21f543c`, clean). Created branch `feat/sha-forge-hardware-lab`.
2. Operator instruction mid-run: use only `timsminer`; "blackhark data" (ambiguous, B-02); then `timminer2` also excluded. Encoded as hard denies in code and tests.
3. M1 (TDD): wrote failing-first tests, then `cqhecs/sha/*`. 45 tests passed.
4. M2: state machine, allowlist, protocol normaliser, backup manifest/restore preview (28 tests), loopback bridge (16 tests).
5. **Process fault:** my first bridge test file reused the name `tests/test_hardware_bridge.py`, which already existed (quantum bridge). Noticed from `git status` showing ` M`; copied mine to `tests/test_sha_bridge.py` and restored the original with `git checkout --`. The restored file's 20 tests pass.
6. Web: TS reference + traces, WGSL kernel, backend probe, demo fixtures, EN/DE/FR page `web/forge.html`. Python-generated trace fixtures compared round by round in TS.
7. Verified in the in-app Chromium: analyzer, genesis check, WebGPU self-test and batch, bridge-unreachable state, then a real `--simulate` bridge on loopback (state `CONNECTED_READ_ONLY`, badge `LOCAL`).
8. Playwright: first run found a real accessibility defect (`aria-required-parent`: tabs outside a `tablist`) and a validation-UX defect (native `max` blocked the localised error). Both fixed (diagnosis changed, not rerun blindly).
9. Fetched the two IACR abstract pages; recorded in `LITERATURE_MAP.md`. Did not read PDFs.
10. Added a "SHA Forge" link to the CQ-HECS nav and a second Vite entry (`forge.html`).
11. **Not done, by design:** no contact with any physical miner, no firmware work in ESP-Miner, no push, no PR, no Vercel deployment.

Commit: see FINAL_REPORT (a local checkpoint commit is created only if the operator asks; nothing was committed at the time of writing).
