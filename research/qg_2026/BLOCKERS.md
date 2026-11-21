# BLOCKERS.md

## B-1 — Open Quantum Client Secret missing

- Severity: High (blocks M6/M7 and all live simulator/QPU evidence)
- Category: `INTEROP` / credentials
- Affected version: main `fa1cc87` (campaign start)
- Minimal reproduction:
  - `OPENQUANTUM_TOKEN=<s_… value>` then `OpenQuantumClient.from_env()` →
    `ManagementClient.list_user_organizations()` → `APIError 401 UNAUTHORIZED`.
- Expected: authenticated `list_user_organizations()` + `get_credit_balance()`.
- Observed: 401. Official docs (`docs.openquantum.com/core-sdk/authentication`) state an
  SDK key is a **Client ID** (`s_<uuid>`) **plus a Client Secret** used in the OAuth2
  client-credentials grant. Only the `s_…` (Client ID shape) was supplied.
- Evidence: `research/qg_2026/EXECUTION_LOG.md` 2026-11-21; probe output in session log.
- Fix attempted: token-based auth (rejected: it is not a JWT).
- Remaining risk: none to the repo; no spend occurred.
- Next safe action: user provides the **Client Secret** (and confirms the `s_…` value is
  the Client ID). Set only as a local env var / non-repo file:
  `OPENQUANTUM_CLIENT_ID`, `OPENQUANTUM_CLIENT_SECRET`. Then rerun
  `python scripts/run_qg_openquantum_campaign.py doctor`.
- Status: OPEN

## B-2 — Non-local gates not yet run in session 1

- Severity: Low (scheduling, not a defect)
- Category: `RESOURCE`
- Not run: full pytest suite, native CTest, `npm test`, Playwright, mutation gate,
  Vulkan runtime. No supported toolchain gap identified yet; scheduled for M13.
- Status: OPEN (planned)
