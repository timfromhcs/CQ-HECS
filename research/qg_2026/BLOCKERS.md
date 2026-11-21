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
- Next safe action: user provides the **Client Secret**. The value `s_202b92794966480e97c60536145d3596`
  is the **Client ID** (`s_<uuid>`); the **Client Secret** is the second, separate value shown once
  in the portal. Two options:
  1. Paste the Client Secret here (treated as exposed; rotate at
     <https://www.openquantum.com/keys> afterwards), then this agent runs
     `printf '%s\n%s\n' '<id>' '<secret>' | python oq.py setup` (stdin, 0600, never a CLI arg), or
  2. run it yourself and this agent just continues once `doctor` passes.
- Connectivity (measured 2026-11-21): `id.openquantum.com` → HTTP 302 (reachable),
  `scheduler.openquantum.com` / `management.openquantum.com` → HTTP 404 (reachable). The earlier
  `doctor` `ConnectionError` on the id host was transient.
- Status: OPEN (waiting on Client Secret)

## B-2 — Non-local gates not yet run in session 1

- Severity: Low (scheduling, not a defect)
- Category: `RESOURCE`
- Not run: full pytest suite, native CTest, `npm test`, Playwright, mutation gate,
  Vulkan runtime. No supported toolchain gap identified yet; scheduled for M13.
- Status: OPEN (planned)
