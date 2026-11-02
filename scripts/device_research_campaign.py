"""Run a research campaign against the miner over the USB console.

The console path exists so a campaign does not depend on the network, and so every
byte the device produces can be captured verbatim. This script:

1. stops mining over the console and waits until the guard agrees no mining work
   can leave the device,
2. pairs (the token is printed to the console), arms,
3. uploads each block in four 32-hex chunks (a console line longer than ~64 bytes
   loses characters - measured) and requests a 64-round trace,
4. stores every trace verbatim, one file per block, with timings,
5. disarms and starts mining again **whatever happened**, and says so in the log.

Nothing is written to flash. The device is only asked for read-only research work.

    python scripts/device_research_campaign.py --port COM3 \
        --out E:/qCSHA/sha_forge_results/device_campaign_20261102

The evaluation is a separate step (`evaluate_device_traces.py`): this script only
captures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover - the operator machine has it
    sys.exit("pyserial is required for the console campaign (pip install pyserial)")

TOKEN_RE = re.compile(r"token[:\s]+(\d{1,10})")
BLOCK_ACCEPTED_RE = re.compile(r"research block (\d) accepted \((\d+)/64 bytes\)")
TRACE_START = '{"schema":"hcs.sha.device_sha256.v1"'
MINING_ACTIVE_RE = re.compile(r"mining_active=(yes|no)")
THERMAL_RE = re.compile(r"thermal=([0-9.]+)C ceiling=([0-9.]+)C age_ms=(\d+)")


def blocks(seed: int) -> list[tuple[str, bytes]]:
    """Deterministic, named test blocks. Names go into the report, not into Git."""
    rng = random.Random(seed)
    choices = [
        ("zeros", bytes(64)),
        ("ones", b"\xff" * 64),
        ("counting", bytes(range(64))),
        ("ascii", (b"the quick brown fox jumps over the lazy dog, 64 bytes exactly!!" + bytes(64))[:64]),
        # A Bitcoin-style 80-byte header's first block: version, prev-hash, merkle
        # root, time. Not a real header (the nonce is in the second block).
        (
            "header-first-block",
            bytes.fromhex(
                "01000000"
                "0000000000000000000000000000000000000000000000000000000000000000"
                "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
                "29ab5f49"
            ),
        ),
    ]
    out = list(choices)
    for i in range(1, 4):
        out.append((f"random-{i}", bytes(rng.getrandbits(8) for _ in range(64))))
    # The console command carries exactly one 64-byte block; anything longer would be
    # silently truncated by the device, so it is truncated here where it is visible.
    return [(name, block[:64]) for name, block in out]


@dataclass
class Console:
    port: str
    baud: int = 115200
    timeout: float = 0.2
    _serial: "serial.Serial | None" = None
    _pending: str = field(default="")

    def open(self) -> None:
        self._serial = serial.Serial(self.port, self.baud, timeout=self.timeout)
        # Do not touch DTR/RTS: asserting them resets the ESP32-S3.
        self._serial.dtr = False
        self._serial.rts = False
        self._serial.reset_input_buffer()

    def close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()

    def send(self, line: str) -> None:
        assert self._serial is not None
        self._serial.write((line + "\n").encode("utf-8"))
        self._serial.flush()
        time.sleep(0.25)

    def read_for(self, seconds: float) -> list[str]:
        """Collect complete lines for `seconds`; never blocks longer than that."""
        assert self._serial is not None
        lines: list[str] = []
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            chunk = self._serial.read(4096)
            if not chunk:
                continue
            text = chunk.decode("utf-8", "replace").replace("\x1b", "")
            text = re.sub(r"\[[0-9;]*m", "", text)
            self._pending += text
            while "\n" in self._pending:
                line, self._pending = self._pending.split("\n", 1)
                line = line.rstrip("\r")
                if line:
                    lines.append(line)
        return lines

    def wait_for(self, pattern: re.Pattern[str], seconds: float) -> tuple[bool, list[str]]:
        lines: list[str] = []
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            lines.extend(self.read_for(min(0.3, max(0.05, deadline - time.monotonic()))))
            for line in lines:
                if pattern.search(line):
                    return True, lines
        return False, lines


def run(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log: list[dict] = []
    started = time.time()
    campaign = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)), "port": args.port, "blocks": []}

    console = Console(args.port, args.baud)
    console.open()
    mining_stopped = False
    armed = False
    try:
        # -- make sure a fresh thermal reading exists before pausing --------
        # The guard refuses an arm when the last chip temperature is older than its
        # window (5 min) or unknown. While mining, the power task samples it every
        # few seconds; after a pause it stops sampling entirely (the ASIC is off), so
        # the campaign must start from a fresh reading instead of inheriting an old
        # one from a previous session.
        fresh = False
        for _ in range(20):
            console.send("research status")
            ok, lines = console.wait_for(re.compile(r"thermal="), 6)
            for line in lines:
                match = THERMAL_RE.search(line)
                if match and float(match.group(3)) < 60_000:
                    fresh = True
            if fresh:
                break
            time.sleep(3.0)
        log.append({"step": "fresh thermal reading", "ok": fresh})
        if not fresh:
            raise RuntimeError("no fresh thermal reading; is mining running?")

        # -- stop mining ---------------------------------------------------
        console.read_for(0.2)
        console.send("research mining off")
        ok, lines = console.wait_for(re.compile(r"mining off"), 10)
        log.append({"step": "mining off", "ok": ok, "reply": lines[-3:]})
        mining_stopped = ok
        if not ok:
            raise RuntimeError("the console did not confirm 'mining off'")

        # -- wait until no mining work can leave the device ----------------
        drained = False
        for _ in range(12):
            console.send("research status")
            ok, lines = console.wait_for(re.compile(r"mining_active="), 6)
            for line in lines:
                if MINING_ACTIVE_RE.search(line) and "mining_active=no" in line:
                    drained = True
            if drained:
                break
            time.sleep(2.0)
        log.append({"step": "drain", "ok": drained})
        if not drained:
            raise RuntimeError("mining work is still flowing; refusing to arm")

        # -- pair ----------------------------------------------------------
        console.send("research challenge")
        ok, lines = console.wait_for(TOKEN_RE, 10)
        token = None
        for line in lines:
            match = TOKEN_RE.search(line)
            if match:
                token = match.group(1)
        log.append({"step": "challenge", "ok": bool(token), "token_prefix": (token or "")[:2] + "****"})
        if not token:
            raise RuntimeError("no pairing token appeared")

        console.send(f"research arm {token}")
        ok, lines = console.wait_for(re.compile(r"research arm "), 10)
        armed = any("state=armed" in line for line in lines)
        log.append({"step": "arm", "ok": armed, "reply": [line for line in lines if "research arm" in line][-1:]})
        if not armed:
            raise RuntimeError("arm refused: " + " | ".join(line for line in lines if "research arm" in line))

        # -- the blocks ----------------------------------------------------
        for name, block in blocks(args.seed):
            entry = {"name": name, "block_hex": block.hex(), "chunks": [], "trace": None, "seconds": None}
            t0 = time.monotonic()
            for index in range(4):
                chunk = block[index * 16 : (index + 1) * 16].hex()
                console.send(f"research block {index} {chunk}")
                ok, lines = console.wait_for(BLOCK_ACCEPTED_RE, 6)
                entry["chunks"].append(ok)
                if not ok:
                    break
            if not all(entry["chunks"]):
                entry["error"] = "a block chunk was not accepted"
                campaign["blocks"].append(entry)
                continue

            # The block stays in the device's buffer, so a retry is one command.
            # Measured on this unit: roughly one trace in eight loses a character
            # somewhere in the ~11 KB stream, which the retry absorbs.
            document = None
            raw = ""
            attempts = 0
            for attempts in range(1, args.retries + 1):
                console.send("research trace")
                buffer = ""
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    buffer += "\n".join(console.read_for(0.4)) + "\n"
                    start = buffer.find(TRACE_START)
                    if start >= 0 and buffer.rstrip().endswith("}"):
                        break
                start = buffer.find(TRACE_START)
                if start < 0:
                    continue
                raw = buffer[start:]
                raw = raw[: raw.rfind("}") + 1]
                try:
                    candidate = json.loads(raw)
                except json.JSONDecodeError:
                    candidate = None
                # A dropped byte inside an array does not break the syntax: the
                # document parses as valid JSON with a *shorter* schedule or round
                # list. Measured on this unit (one block in eight). The structure is
                # therefore checked explicitly, and a short document is retried like
                # a corrupt one - the independent replay would catch it later, but it
                # is cheaper to refuse it here.
                if candidate is not None:
                    inner = candidate.get("trace") or {}
                    complete = (
                        len(inner.get("schedule") or []) == 64
                        and len(inner.get("rounds") or []) == 64
                        and inner.get("rounds_executed") == 64
                        and len(inner.get("block") or "") == 128
                    )
                    if complete:
                        document = candidate
                        break
                    entry.setdefault("incomplete_attempts", 0)
                    entry["incomplete_attempts"] += 1
                document = None
                time.sleep(0.8)
            entry["attempts"] = attempts
            entry["seconds"] = round(time.monotonic() - t0, 2)
            if document is None:
                entry["error"] = f"no parseable trace after {attempts} attempts"
                campaign["blocks"].append(entry)
                continue
            entry["trace"] = document
            (out / f"trace_{name}.json").write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
            entry["trace_file"] = f"trace_{name}.json"
            entry["trace_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            entry["output_state"] = (document.get("trace") or {}).get("output_state")
            campaign["blocks"].append(entry)
            print(f"  {name:<20} {entry['seconds']:>5.1f}s  {(entry.get('output_state') or '')[:16]}")
    except Exception as exc:  # noqa: BLE001 - the campaign must record any failure
        campaign["aborted"] = str(exc)
        print(f"campaign aborted: {exc}")
    finally:
        # -- always disarms and resumes mining ----------------------------
        try:
            if armed:
                console.send("research disarm")
                console.wait_for(re.compile(r"research disarm "), 8)
        except Exception:  # noqa: BLE001
            log.append({"step": "disarm", "ok": False})
        try:
            if mining_stopped:
                console.send("research mining on")
                ok, _ = console.wait_for(re.compile(r"mining on"), 10)
                log.append({"step": "mining on", "ok": ok})
                campaign["mining_resumed"] = ok
        except Exception as exc:  # noqa: BLE001
            log.append({"step": "mining on", "ok": False, "error": str(exc)})
            campaign["mining_resumed"] = False
        console.close()

    campaign["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    campaign["duration_s"] = round(time.time() - started, 1)
    campaign["log"] = log
    (out / "campaign.json").write_text(json.dumps(campaign, indent=2, sort_keys=True), encoding="utf-8")

    captured = sum(1 for b in campaign["blocks"] if b.get("trace"))
    print(f"\ncaptured {captured}/{len(campaign['blocks'])} traces in {campaign['duration_s']}s -> {out}")
    if not campaign.get("mining_resumed", False):
        print("WARNING: mining was not confirmed as resumed")
        return 2
    return 0 if captured == len(campaign["blocks"]) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=20261102, help="seed for the pseudo-random blocks")
    parser.add_argument("--retries", type=int, default=3, help="attempts per block when a trace arrives corrupted")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
