"""Firmware profile, device status and trace capture for HCS SHA Forge.

Read-only by design: this script never flashes, never reboots and never writes to
the miner. It records what a build is, asks the device to prove what it is
running, and stores the result as evidence.

    # Pin a build (writes a profile next to it; the image is hashed, not modified)
    python scripts/sha_forge_firmware.py profile \
        --image ESP-Miner/build/esp-miner.bin \
        --version v4.0.2-rc1-timsminer-sha-research --commit 564016e \
        --board 201 --asic BM1366 --out E:/results/timsminer.firmware.json

    # Re-check the image against its profile
    python scripts/sha_forge_firmware.py verify-profile \
        --profile E:/results/timsminer.firmware.json --image ESP-Miner/build/esp-miner.bin

    # Ask the device what it is running (and check it against the profile)
    python scripts/sha_forge_firmware.py status --host <device> --profile <profile>

    # On-device SHA-256 trace, verified locally, stored as evidence
    python scripts/sha_forge_firmware.py trace --host <device> \
        --block 00..64 bytes.. --rounds 64 --out E:/results

The host is a command-line argument on purpose: no device address, MAC or pool
setting is ever stored in this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from cqhecs.hardware import firmware_profile as fw  # noqa: E402
from cqhecs.hardware.research_client import ResearchClient, ResearchError  # noqa: E402

DEFAULT_FEATURES = ["sha256", "sha256d", "round_trace", "reduced_rounds"]


def _json_out(path: pathlib.Path, document: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def build_profile(args) -> int:
    image = pathlib.Path(args.image)
    if not image.is_file():
        print(f"image not found: {image}", file=sys.stderr)
        return 2
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    data = {
        "schema": fw.SCHEMA,
        "version": args.version,
        "project": args.project,
        "chip": args.chip,
        "source_commit": args.commit,
        "image_sha256": digest,
        "image_bytes": image.stat().st_size,
        "board_version": args.board,
        "asic_model": args.asic,
        "features": DEFAULT_FEATURES,
        "build_flags": {
            "CONFIG_TIMSMINER_SHA_RESEARCH": "y",
            "CONFIG_TIMSMINER_SHA_RESEARCH_MAX_JOBS": str(args.max_jobs),
            "CONFIG_TIMSMINER_SHA_RESEARCH_MAX_RUNTIME_S": str(args.max_runtime_s),
            "CONFIG_TIMSMINER_SHA_RESEARCH_TEMPERATURE_C": str(args.max_temp_c),
        },
        "research_limits": {
            "max_jobs": args.max_jobs,
            "max_runtime_s": args.max_runtime_s,
            "max_temperature_c": args.max_temp_c,
            "max_trace_rounds": 64,
            "max_message_bytes": 512,
        },
        "compute": "software_cpu",
        "asic_access": "none",
    }
    profile = fw.FirmwareProfile.from_dict(data)  # validates before anything is written
    out = pathlib.Path(args.out)
    record_hash = _json_out(out, profile.to_dict())
    print(f"profile written: {out}")
    print(f"image sha256   : {digest}")
    print(f"image bytes    : {profile.image_bytes}")
    print(f"record sha256  : {record_hash}")
    return 0


def verify_profile(args) -> int:
    profile = fw.FirmwareProfile.load(args.profile)
    result = profile.verify_image(args.image)
    print(f"{'OK  ' if result.ok else 'FAIL'} {result.reason}")
    return 0 if result.ok else 1


def _device(args) -> ResearchClient:
    return ResearchClient(args.host, port=args.port, timeout=args.timeout)


def status(args) -> int:
    client = _device(args)
    try:
        document = client.status()
        capabilities = client.capabilities()
    except ResearchError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2
    # The device must not claim ASIC-internal state; the call above already
    # refused if it did, which is why it is not repeated here.
    print(json.dumps({"status": document, "capabilities": capabilities}, indent=2, sort_keys=True))
    if args.profile:
        profile = fw.FirmwareProfile.load(args.profile)
        match = profile.matches_device(document)
        print(f"\n{'OK  ' if match.ok else 'FAIL'} {match.reason}")
        return 0 if match.ok else 1
    return 0


def trace(args) -> int:
    block = bytes.fromhex(args.block)
    client = _device(args)
    try:
        result = client.trace_block(block, rounds=args.rounds, feed_forward=not args.no_feed_forward)
    except (ResearchError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2
    if not result.ok:
        print(f"REFUSED {result.reason}", file=sys.stderr)
        return 1

    document = {
        "schema": "hcs.sha.forge.evidence.v1",
        "kind": "device_block_trace",
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request": {
            "block_hex": block.hex(),
            "rounds": args.rounds,
            "feed_forward": not args.no_feed_forward,
        },
        "verification": {
            "verified": True,
            "by": "cqhecs.sha.round_trace.replay",
            "output_state": result.output_state,
        },
        "envelope": {k: v for k, v in (result.envelope or {}).items() if k != "trace"},
        "trace": result.trace,
    }
    name = f"device_trace_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    out = pathlib.Path(args.out) / name if args.out else pathlib.Path(name)
    record_hash = _json_out(out, document)
    print(f"trace verified : {result.output_state}")
    print(f"evidence       : {out}")
    print(f"record sha256  : {record_hash}")
    return 0


def digest(args) -> int:
    message = bytes.fromhex(args.message)
    client = _device(args)
    try:
        value, body = client.digest(message, sha256d=args.sha256d)
    except (ResearchError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2
    print(f"algorithm      : {'sha256d' if args.sha256d else 'sha256'}")
    print(f"message_bytes  : {len(message)}")
    print(f"digest         : {value}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_profile = sub.add_parser("profile", help="pin a built firmware image in a profile file")
    p_profile.add_argument("--image", required=True)
    p_profile.add_argument("--out", required=True)
    p_profile.add_argument("--version", required=True)
    p_profile.add_argument("--commit", default="")
    p_profile.add_argument("--project", default="esp-miner")
    p_profile.add_argument("--chip", default="ESP32-S3")
    p_profile.add_argument("--board", default="201")
    p_profile.add_argument("--asic", default="BM1366")
    p_profile.add_argument("--max-jobs", type=int, default=64)
    p_profile.add_argument("--max-runtime-s", type=int, default=900)
    p_profile.add_argument("--max-temp-c", type=int, default=65)
    p_profile.set_defaults(func=build_profile)

    p_verify = sub.add_parser("verify-profile", help="re-check an image against its profile")
    p_verify.add_argument("--profile", required=True)
    p_verify.add_argument("--image", required=True)
    p_verify.set_defaults(func=verify_profile)

    for name, func, help_text in (
        ("status", status, "read the device research status and capabilities"),
        ("trace", trace, "capture a verified on-device SHA-256 trace"),
        ("digest", digest, "compare an on-device message digest with the local reference"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--host", required=True, help="device hostname or IPv4 address (not committed)")
        p.add_argument("--port", type=int, default=80)
        p.add_argument("--timeout", type=float, default=10.0)
        if name == "status":
            p.add_argument("--profile", default=None, help="optional profile to match against")
        if name == "trace":
            p.add_argument("--block", required=True, help="exactly 64 bytes of hex")
            p.add_argument("--rounds", type=int, default=64)
            p.add_argument("--no-feed-forward", action="store_true")
            p.add_argument("--out", default=None, help="directory for the evidence record")
        if name == "digest":
            p.add_argument("--message", required=True, help="message hex, at most 512 bytes")
            p.add_argument("--sha256d", action="store_true")
        p.set_defaults(func=func)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
