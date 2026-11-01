# SHA Round Analyzer

Open `web/forge.html` (served at `/forge.html`). Everything is computed in your browser; nothing is uploaded.

- **Inputs:** text, hex bytes, or a Bitcoin 80-byte header (SHA-256d with first-block midstate and second pass shown separately).
- **Output:** padding, 64-word message schedule, all rounds with `K`, `W`, registers `a'..h'`, `T1`, `T2`; per-round `Σ1`, `Ch`, `Σ0`, `Maj`; digest.
- **Reduced rounds:** 1–63 rounds are labelled "not standard SHA-256".
- **Cross-check:** the final digest of a full run is compared with Web Crypto (`crypto.subtle.digest`), used only as an independent oracle, never for the trace.
- **Source label:** every trace carries `SOFTWARE_REPLAY`. It was not read from any ASIC.

Trace format `hcs.sha.trace.v1` is identical in Python (`cqhecs/sha/round_trace.py`) and TypeScript (`web/src/forge/sha.ts`); all words are 8-character lowercase hex.
`replay` recomputes a trace from its block and initial state and rejects any altered value.

```bash
python - <<'PY'
from cqhecs.sha import round_trace as rt, sha256_reference as ref
tr = rt.trace_block(ref.IV, ref.pad(b"abc"))
print(rt.replay(tr))
PY
```

Independent checks: NIST vectors, `hashlib`, `node:crypto`, Web Crypto, constants re-derived from prime roots, the Bitcoin genesis header
(`000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f`), and negative controls (wrong IV, missing feed-forward, endian swap, mutated constant, off-by-one round).

Limits: single- and multi-block messages and 80-byte headers only; no UI for the differential view yet (available in Python: `diff_traces`).
