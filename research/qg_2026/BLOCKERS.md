# BLOCKERS.md

## B-1 — Open Quantum credential pair incomplete (no Client Secret)

- Severity: High (blocks M6/M7, all live simulator/QPU evidence)
- Category: `INTEROP` / credentials
- Minimal reproduction and evidence (2026-11-21):
  - Correct endpoint verified via `.well-known/openid-configuration`:
    issuer `https://id.openquantum.com/realms/platform`.
  - `POST /realms/platform/protocol/openid-connect/token`, `grant_type=client_credentials`:
    - non-existent client id → `{"error":"invalid_client"}`
    - both provided `s_...` values (in either role) → `{"error":"unauthorized_client"}`
      **identical to using a deliberately wrong secret**, so the secret is not accepted.
  - HTTP-Basic, `scope=openid`, prefix-stripped variants, and realms
    `openquantum`/`quantumrings` (404) all fail. Bearer-token auth with the value → 401.
- Root cause: an Open Quantum SDK key is **Client ID (`s_<uuid>`)** + **Client Secret (private,
  shown once)**. Both supplied values are Client **IDs** (both are recognized clients). The secret
  is a different value that was not provided.
- Next safe action (user): open <https://www.openquantum.com/keys>, confirm the key is
  **Enabled**, and copy the **Client Secret**. If it is no longer shown, create a new key and
  provide **both** the Client ID and the Client Secret. Alternatively provide a bearer token
  (`OPENQUANTUM_TOKEN`, format `oq_tok_...`) if one exists.
- Status: OPEN (waiting on Client Secret)

## B-2 — Non-local gates not yet run in session 1

- Severity: Low (scheduling, not a defect)
- Category: `RESOURCE`
- Not run: full pytest suite, native CTest, `npm test`, Playwright, mutation gate,
  Vulkan runtime. No supported toolchain gap identified yet; scheduled for M13.
- Status: OPEN (planned)
