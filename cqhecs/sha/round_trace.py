"""Per-round SHA-256 traces computed in software.

Every value is a fixed-width lowercase hex string (8 chars per 32-bit word).
Traces are SOFTWARE_REPLAY data: they are never read from ASIC silicon.
"""
from __future__ import annotations

from typing import Sequence

from . import sha256_reference as ref

REGS = ("a", "b", "c", "d", "e", "f", "g", "h")
SOURCE = "SOFTWARE_REPLAY"


class TraceMismatch(ValueError):
    """Replaying a trace did not reproduce its recorded values."""


def _hx(x: int) -> str:
    return f"{x & ref.MASK:08x}"


def _regs(state: Sequence[int]) -> dict:
    return {n: _hx(v) for n, v in zip(REGS, state)}


def _state_hex(state: Sequence[int]) -> str:
    return "".join(_hx(v) for v in state)


def _parse_state(s: str) -> tuple:
    if len(s) != 64:
        raise ValueError("state hex must be 64 characters")
    return tuple(int(s[i : i + 8], 16) for i in range(0, 64, 8))


def trace_block(state: Sequence[int], block: bytes, rounds: int = 64, feed_forward: bool = True) -> dict:
    """Trace one compression of a 64-byte block."""
    if not 0 <= rounds <= 64:
        raise ValueError("rounds must be between 0 and 64")
    words = ref.block_words(block)
    w = ref.schedule(words)
    work = tuple(state)
    out_rounds = []
    for t in range(rounds):
        new, t1, t2 = ref.round_step(work, ref.K[t], w[t])
        out_rounds.append(
            {"t": t, "K": _hx(ref.K[t]), "W": _hx(w[t]), "in": _regs(work), "T1": _hx(t1), "T2": _hx(t2), "out": _regs(new)}
        )
        work = new
    final = tuple((s + x) & ref.MASK for s, x in zip(state, work)) if feed_forward else work
    return {
        "schema": "hcs.sha.trace.v1",
        "source": SOURCE,
        "block": block.hex(),
        "input_state": _state_hex(state),
        "schedule": [_hx(x) for x in w],
        "rounds_executed": rounds,
        "feed_forward": feed_forward,
        "rounds": out_rounds,
        "output_state": _state_hex(final),
    }


def replay(trace: dict) -> str:
    """Re-derive a block trace from its inputs and compare every recorded value.

    Returns the output state hex; raises TraceMismatch on any deviation.
    """
    fresh = trace_block(
        _parse_state(trace["input_state"]),
        bytes.fromhex(trace["block"]),
        rounds=trace["rounds_executed"],
        feed_forward=trace["feed_forward"],
    )
    if len(trace["rounds"]) != len(fresh["rounds"]):
        raise TraceMismatch("round count differs")
    for rec, exp in zip(trace["rounds"], fresh["rounds"]):
        if rec != exp:
            raise TraceMismatch(f"round {exp['t']} differs from the reference")
    if trace.get("schedule") != fresh["schedule"]:
        raise TraceMismatch("message schedule differs from the reference")
    if trace["output_state"] != fresh["output_state"]:
        raise TraceMismatch("output state differs from the reference")
    return fresh["output_state"]


def trace_message(message: bytes, iv: Sequence[int] = ref.IV) -> dict:
    """Trace a whole byte message through padding and every block."""
    padded = ref.pad(message)
    state = tuple(iv)
    blocks = []
    for i in range(0, len(padded), 64):
        tb = trace_block(state, padded[i : i + 64])
        blocks.append(tb)
        state = _parse_state(tb["output_state"])
    return {
        "schema": "hcs.sha.message_trace.v1",
        "source": SOURCE,
        "message_length": len(message),
        "padding": {
            "padded_length": len(padded),
            "bit_length": len(message) * 8,
            "zero_bytes": len(padded) - len(message) - 1 - 8,
            "padded_hex": padded.hex(),
        },
        "blocks": blocks,
        "digest": _state_hex(state),
    }


def trace_sha256d(header: bytes) -> dict:
    """Trace SHA256(SHA256(header)) for an 80-byte Bitcoin block header."""
    if len(header) != 80:
        raise ValueError("a Bitcoin block header is exactly 80 bytes")
    first = trace_message(header)
    first["midstate"] = first["blocks"][0]["output_state"]
    inner = bytes.fromhex(first["digest"])
    second = trace_message(inner)
    double = second["digest"]
    return {
        "schema": "hcs.sha.sha256d_trace.v1",
        "source": SOURCE,
        "header": header.hex(),
        "first_pass": first,
        "second_pass": second,
        "double_hash": double,
        "display_hash": bytes.fromhex(double)[::-1].hex(),
    }


def _leading_zero_bits(digest_display: bytes) -> int:
    value = int.from_bytes(digest_display, "big")
    return 256 - value.bit_length()


def replay_candidate(header_prefix: bytes, nonce: int, leading_zero_bits: int) -> dict:
    """Independently recompute a returned nonce candidate (never trusts the device)."""
    if len(header_prefix) != 76:
        raise ValueError("header prefix must be 76 bytes (header without nonce)")
    if not 0 <= nonce <= 0xFFFFFFFF:
        raise ValueError("nonce must be a 32-bit unsigned integer")
    if not 0 <= leading_zero_bits <= 256:
        raise ValueError("leading_zero_bits must be in 0..256")
    header = header_prefix + nonce.to_bytes(4, "little")
    digest = ref.sha256d(header)
    display = digest[::-1]
    lz = _leading_zero_bits(display)
    return {
        "source": SOURCE,
        "nonce": nonce,
        "hash": display.hex(),
        "leading_zero_bits": lz,
        "required_leading_zero_bits": leading_zero_bits,
        "verified": lz >= leading_zero_bits,
    }


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def diff_traces(a: dict, b: dict) -> dict:
    """Bit-level differences between two block traces round by round."""
    n = min(len(a["rounds"]), len(b["rounds"]))
    rounds = []
    for ra, rb in zip(a["rounds"][:n], b["rounds"][:n]):
        rounds.append({"t": ra["t"], "hamming": {r: _hamming(ra["out"][r], rb["out"][r]) for r in REGS}})
    return {
        "schema": "hcs.sha.trace_diff.v1",
        "source": SOURCE,
        "rounds": rounds,
        "final_hamming": _hamming(a["output_state"], b["output_state"]),
    }
