# HCS SHA Forge — Final report (this run)

**Verdict: PARTIAL.** The software side (M1, M2 read-only, M6 partly, M7 demo) is built and tested. The hardware side (M0 device part, M3, M4, M5, M8) is **not started by design** and gated on operator action.

## 1. Commits and branches

| Repo | Branch | Commit |
|---|---|---|
| CQ-HECS | `feat/sha-forge-hardware-lab` (from `423e389`, tag v4.0.0) | `7c4b62f` plus a follow-up commit for this report; **not pushed**, no PR |
| ESP-Miner | none | unchanged (`21f543c`) |
| sha256-research-framework | none | not touched |

## 2. Files (CQ-HECS)

Python: `cqhecs/sha/{__init__,model,round_trace,sha256_reference,vectors}.py`, `cqhecs/hardware/{__init__,bridge,evidence,miner_capabilities,miner_protocol,state_machine}.py`.
Tests: `tests/test_sha_{reference,round_trace,model,bridge}.py`, `tests/test_hardware_policy.py`.
Web: `web/forge.html`, `web/src/forge/*`, `web/tests/forge.test.ts` (+ fixture), `web/e2e/forge.spec.ts`; edited `web/vite.config.ts` (second entry), `web/tests/run.mjs`, `web/index.html` (one nav link).
Docs/research: `docs/{LOCAL_BRIDGE,MINER_BACKUP_RESTORE,SHA_ROUND_ANALYZER,TIMSMINER_RESEARCH_MODE,WEBGPU_WASM_BACKENDS}.md`, `research/sha_forge/*`, `CHANGELOG.md` (Unreleased).

## 3. How to run

```bash
# Python tests
python -m pytest tests/test_sha_reference.py tests/test_sha_round_trace.py tests/test_sha_model.py tests/test_sha_bridge.py tests/test_hardware_policy.py -q
# Web demo
cd web && npm ci && npm run dev      # open /forge.html
# Local bridge without any hardware
python -m cqhecs.hardware.bridge --origin http://127.0.0.1:5173 --simulate
```

The Vercel preview was **not** deployed.

## 4. Capability results on the test machine

Backend probe in the in-app Chromium: `WEBGPU` available (self-test matched CPU), `WASM_SIMD`/`WASM_SCALAR` not available (no module bundled), `BROWSER_CPU` available, bridge-dependent backends unavailable without a bridge. Selected: `WEBGPU`. Browser and adapter versions were not recorded.

## 5–8. Hardware

Device identity, firmware state, backup, flash and restore: **none performed, none verified** (`NOT TESTED`). No backup file exists. The miner was never contacted and is in whatever state it was in before; this run neither changed nor observed it.

## 9. Test matrix

See `TEST_MATRIX.md`. Summary: Python 2499 passed / 109 skipped; web unit 33 passed; Playwright 30 passed; hardware, firmware, WASM, remote CI: not tested.

## 10. Known limitations and next smallest useful task

- Device scope: only `timsminer`; `blackharkminer` and `timminer2` excluded. The instruction about "blackhark data" is unresolved (B-02).
- Smallest next step needing no approval: a Rust `wasm32` SHA-256 module so the WASM tiers can be tested (B-05).
- Smallest next step needing operator input: approve a read-only `/api/system/info` read of `timsminer` via the bridge (`--device-host`), then capture the 60-minute baseline (B-01).
- Then M3: implement and bench-test the read-only WLAN backup route in ESP-Miner.

## Definition-of-done check (AGENTBUILD §16)

Done: SHA reference vs independent oracles; reproducible 64-round trace; no false round-access claim; bridge loopback-only, paired, allowlisted, schema-validated; demo deterministic and labelled; no secrets or device identifiers committed.
Not done: three-repo audit, ASIC candidate verification on real data, research mode, WLAN backup/restore, WASM/WebGPU parity beyond one browser, Vercel preview, CI/licence/SBOM gates.
