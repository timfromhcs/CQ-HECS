# Device research: what the miner computed, and how it was checked

Status: **one campaign, 8 blocks, 512 rounds, all accepted by the independent
replay and by a host build of the same C source** (2026-11-02). Raw files live in
`E:\qCSHA\sha_forge_results\device_campaign_20261102\`; this document is the
committed summary.

## What was run

`scripts/device_research_campaign.py` drives the USB console (no WLAN in the path):
stop mining, wait until the guard agrees no work can leave the device, pair, arm,
then for each block upload it in four 32-hex chunks and request a 64-round trace.
It disarms and restarts mining in a `finally` block whatever happens.

Blocks (deterministic; the pseudo-random ones use seed 20261102): all-zero,
all-0xFF, counting bytes, an ASCII sentence, the first 64 bytes of a Bitcoin-style
header, and three random blocks.

## Result

| Check | Result |
|---|---|
| Traces captured | 8 / 8 |
| Accepted by `cqhecs.sha.round_trace.replay()` | **8 / 8** |
| Rounds re-derived and compared field by field | **512** |
| Also matched by the host build of the same C source | 8 / 8 |
| Digest matched the Python reference for the same block | 8 / 8 |
| Mining resumed afterwards | yes |

Three implementations agree on every block: the device's C (Xtensa), the host C
(same source, MSVC/clang) and the Python reference. The device's own claims
(`compute: software_cpu`, `asic_access: none`) are what the envelope said.

## The transport finding (worth knowing before the next campaign)

The console lost characters **inside** the JSON on 2 of 8 blocks. One of those was
the dangerous kind: the document still parsed as valid JSON, but its `schedule` array
was shorter than 64 entries - a dropped byte inside an array does not break the
syntax. `json.loads` accepted it; `round_trace.replay()` rejected it ("message
schedule differs"), which is exactly why the replay exists.

Two guards are now in place:

- the campaign checks the structure (64 schedule entries, 64 rounds,
  `rounds_executed == 64`, 128 hex characters of block) and retries a short document
  like a corrupt one - the block stays in the device's buffer, so a retry is one
  command;
- the evaluator never trusts a parse: every trace is replayed.

Cost of retries: two blocks needed them, taking ~48-50 s instead of ~4 s.

## What the timing does not mean

Wall clock per trace is 3.8 s in the good case and 50 s when a retry was needed,
including the transfer of about 11 KB of JSON over the console. It is **not** a
compression rate: the research route exposes no timer, and even a measured software
rate would not be comparable to the BM1366's SHA-256d hashrate (different workload,
different measurement, different silicon).

## What this does not show

- Nothing about ASIC-internal SHA state. There is none to read.
- Nothing about 64-round preimage search: these are verification traces of
  caller-supplied blocks, and `SAT_SHA.md` records how far a search gets at reduced
  rounds.

## Reproduce

```bash
cd E:/qCSHA/CQ-HECS
$env:PYTHONPATH="."
python scripts/device_research_campaign.py --port COM3 --out <results dir>
python scripts/evaluate_device_traces.py --campaign <results dir>
```
