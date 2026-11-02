"""Evaluate a device research campaign on the PC, from the captured files.

Nothing is trusted because the device said it: every trace is re-derived by
`cqhecs.sha.round_trace.replay()` (which recomputes the message schedule and all 64
rounds and rejects the first deviation), and the digest is recomputed from the block.
When a host C emitter is available, the same block is hashed by the firmware's own C
implementation compiled for the host, so three implementations have to agree.

    python scripts/evaluate_device_traces.py \
        --campaign E:/qCSHA/sha_forge_results/device_campaign_20261102

Writes `REPORT.md` and `report.json` next to `campaign.json` and returns 0 only when
every captured trace was accepted and every digest matched.

What the throughput number is and is not
----------------------------------------
The device has no exposed timer for the research route, and the trace is streamed
over a serial console, so the only honest figure is **wall-clock per trace including
the transfer**. It is reported as such. It is not a compression rate, and it is not
comparable to the BM1366's SHA-256d hashrate (a different workload, measured
differently, on a different piece of silicon).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import subprocess
import sys
import tempfile
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from cqhecs.sha import round_trace, sha256_reference as ref  # noqa: E402

# Reuse the compiler discovery from the trace cross-check so both scripts agree on
# what "the host C implementation" means.
from verify_firmware_trace import find_compiler  # noqa: E402

DEFAULT_FIRMWARE = REPO.parent / "ESP-Miner"


def build_host_emitter(firmware_root: pathlib.Path, out: pathlib.Path) -> pathlib.Path | None:
    """Compile the firmware's own SHA source plus its `--emit` entry point."""
    fw_main = firmware_root / "main" / "research" / "research_sha.c"
    fw_test = firmware_root / "simulation" / "test_research_sha.c"
    if not fw_main.is_file() or not fw_test.is_file():
        return None
    compiler = find_compiler()
    if compiler is None:
        return None
    command = compiler + [
        "-Wall",
        "-Wextra",
        "-O2",
        "-std=c11",
        "-D_CRT_SECURE_NO_WARNINGS",
        f"-I{fw_main.parent}",
        "-o",
        str(out),
        str(fw_main),
        str(fw_test),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError):
        return None
    return out if out.exists() else None


def host_state(binary: pathlib.Path, block: bytes) -> str | None:
    """Return the host C implementation's output state for one block."""
    try:
        proc = subprocess.run([str(binary), "--emit", block.hex()], capture_output=True, text=True, check=True, timeout=60)
        document = json.loads(proc.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
        return None
    return (document.get("output_state") or "").lower() or None


def evaluate(campaign_path: pathlib.Path, c_binary: pathlib.Path | None) -> dict[str, Any]:
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    results = []
    for entry in campaign.get("blocks", []):
        block_hex = entry.get("block_hex", "")
        record: dict[str, Any] = {
            "name": entry.get("name"),
            "seconds": entry.get("seconds"),
            "attempts": entry.get("attempts"),
            "captured": bool(entry.get("trace")),
        }
        if not entry.get("trace"):
            record.update(ok=False, reason=entry.get("error") or "not captured")
            results.append(record)
            continue
        trace = entry["trace"].get("trace") or {}
        block = bytes.fromhex(block_hex) if block_hex else b""
        if len(block) != 64:
            record.update(ok=False, reason=f"the campaign recorded a {len(block)}-byte block; the console command carries exactly 64")
            results.append(record)
            continue
        try:
            replay_state = round_trace.replay(dict(trace))
            record["replay"] = "accepted"
        except (round_trace.TraceMismatch, KeyError, ValueError, TypeError) as exc:
            record.update(ok=False, replay="rejected", reason=str(exc))
            results.append(record)
            continue

        # Digest of the block, computed here, not read from the device.
        expected = ref.compress(ref.IV, ref.block_words(block))
        expected_hex = ref.state_bytes(expected).hex()
        device_state = (trace.get("output_state") or "").lower()
        record["device_output_state"] = device_state
        record["reference_output_state"] = expected_hex
        record["matches_reference"] = device_state == expected_hex
        record["matches_replay"] = device_state == replay_state
        record["block_matches"] = (trace.get("block") or "").lower() == block.hex()
        record["rounds"] = int(trace.get("rounds_executed") or 0)
        record["rounds_returned"] = len(trace.get("rounds") or [])

        if c_binary is not None:
            c_state = host_state(c_binary, block)
            record["host_c_output_state"] = c_state
            record["matches_host_c"] = c_state == device_state
        else:
            record["host_c_output_state"] = None
            record["matches_host_c"] = None

        record["ok"] = all(
            [
                record["matches_reference"],
                record["matches_replay"],
                record["block_matches"],
                record["rounds"] == 64,
                record["rounds_returned"] == 64,
                record.get("matches_host_c") in (True, None),
            ]
        )
        results.append(record)

    captured = [r for r in results if r.get("captured")]
    ok = [r for r in results if r.get("ok")]
    durations = [r["seconds"] for r in captured if isinstance(r.get("seconds"), (int, float))]
    summary = {
        "campaign": campaign_path.name,
        "blocks_total": len(results),
        "blocks_captured": len(captured),
        "blocks_ok": len(ok),
        "rounds_verified": sum(int(r.get("rounds_returned") or 0) for r in ok),
        "host_c_checked": c_binary is not None,
        "wall_clock_per_trace_s": {
            "median": round(statistics.median(durations), 2) if durations else None,
            "min": round(min(durations), 2) if durations else None,
            "max": round(max(durations), 2) if durations else None,
        },
        "retried": sum(1 for r in captured if (r.get("attempts") or 1) > 1),
        "mining_resumed": bool(campaign.get("mining_resumed")),
        "device_version": (campaign.get("log") and None) or None,
        "ok": len(ok) == len(results) and bool(campaign.get("mining_resumed")),
    }
    return {"summary": summary, "blocks": results}


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Device research campaign - evaluation",
        "",
        f"Campaign: `{s['campaign']}`",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Blocks captured | {s['blocks_captured']} / {s['blocks_total']} |",
        f"| Blocks accepted by the independent replay | {s['blocks_ok']} / {s['blocks_total']} |",
        f"| Rounds re-derived and compared | {s['rounds_verified']} |",
        f"| Host C cross-check | {'run' if s['host_c_checked'] else 'NOT RUN (no compiler)'} |",
        f"| Traces that needed a retry | {s['retried']} |",
        f"| Mining resumed afterwards | {'yes' if s['mining_resumed'] else 'NO'} |",
        f"| Wall clock per trace (s) | median {s['wall_clock_per_trace_s']['median']}, "
        f"min {s['wall_clock_per_trace_s']['min']}, max {s['wall_clock_per_trace_s']['max']} |",
        "",
        "| Block | Rounds | Device state (first 16) | Reference match | Host C match | Seconds |",
        "|---|---:|---|---|---|---:|",
    ]
    for block in report["blocks"]:
        state = (block.get("device_output_state") or "-")[:16]
        lines.append(
            f"| {block['name']} | {block.get('rounds_returned', '-')} | `{state}` | "
            f"{'yes' if block.get('matches_reference') else 'NO'} | "
            f"{'yes' if block.get('matches_host_c') else ('NOT RUN' if block.get('matches_host_c') is None else 'NO')} | "
            f"{block.get('seconds', '-')} |"
        )
    lines += [
        "",
        "## What the timing means",
        "",
        "The figure above is wall clock for one trace **including the serial transfer** of",
        "about 11 KB of JSON. It is not a compression rate: the device exposes no timer for",
        "this route, and the number would still not be comparable to the BM1366's SHA-256d",
        "hashrate, which is a different workload measured differently on different silicon.",
        "",
        "## What this does not show",
        "",
        "- Nothing about ASIC-internal SHA state: the device computes in software and says so",
        "  (`compute: software_cpu`, `asic_access: none`).",
        "- Nothing about full 64-round preimage search: these are *verification* traces of",
        "  caller-supplied blocks.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--campaign", required=True, help="directory holding campaign.json")
    parser.add_argument("--firmware-root", type=pathlib.Path, default=DEFAULT_FIRMWARE)
    parser.add_argument("--no-host-c", action="store_true", help="skip the host C cross-check")
    args = parser.parse_args(argv)

    campaign_dir = pathlib.Path(args.campaign)
    campaign_json = campaign_dir / "campaign.json"
    if not campaign_json.is_file():
        print(f"no campaign.json in {campaign_dir}", file=sys.stderr)
        return 2

    c_binary = None
    if not args.no_host_c:
        tmpdir = tempfile.mkdtemp(prefix="sha_forge_eval_")
        c_binary = build_host_emitter(args.firmware_root, pathlib.Path(tmpdir) / "emit.exe")
        if c_binary is None:
            print("host C emitter not built (no compiler or firmware source); continuing without it")

    report = evaluate(campaign_json, c_binary)
    (campaign_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (campaign_dir / "REPORT.md").write_text(render_markdown(report), encoding="utf-8")

    s = report["summary"]
    print(f"blocks ok: {s['blocks_ok']}/{s['blocks_total']}, rounds verified: {s['rounds_verified']}")
    print(f"host C cross-check: {'run' if s['host_c_checked'] else 'NOT RUN'}")
    print(f"wall clock per trace: median {s['wall_clock_per_trace_s']['median']}s")
    print(f"report: {campaign_dir / 'REPORT.md'}")
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
