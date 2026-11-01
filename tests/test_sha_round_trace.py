"""Round trace: every round reproducible, replay equals reference digest."""
import hashlib
import json

import pytest

from cqhecs.sha import round_trace as rt
from cqhecs.sha import sha256_reference as ref
from cqhecs.sha import vectors


def test_single_block_trace_shape_and_replay():
    tr = rt.trace_block(ref.IV, ref.pad(b"abc"))
    assert len(tr["rounds"]) == 64
    r0 = tr["rounds"][0]
    assert r0["t"] == 0 and r0["K"] == "428a2f98" and r0["W"] == "61626380"
    assert all(len(v) == 8 for v in r0["in"].values())
    expected = "".join(f"{w:08x}" for w in ref.compress(ref.IV, ref.block_words(ref.pad(b"abc"))))
    assert tr["output_state"] == expected
    assert rt.replay(tr) == tr["output_state"]
    assert tr["output_state"] == vectors.SHA256_KAT[1][1]


def test_round_equations_hold_for_every_round():
    tr = rt.trace_block(ref.IV, ref.pad(b"abc"))
    for r in tr["rounds"]:
        i = {k: int(v, 16) for k, v in r["in"].items()}
        o = {k: int(v, 16) for k, v in r["out"].items()}
        t1 = (i["h"] + ref.big_sigma1(i["e"]) + ref.ch(i["e"], i["f"], i["g"]) + int(r["K"], 16) + int(r["W"], 16)) & 0xFFFFFFFF
        t2 = (ref.big_sigma0(i["a"]) + ref.maj(i["a"], i["b"], i["c"])) & 0xFFFFFFFF
        assert int(r["T1"], 16) == t1 and int(r["T2"], 16) == t2
        assert o["a"] == (t1 + t2) & 0xFFFFFFFF
        assert o["e"] == (i["d"] + t1) & 0xFFFFFFFF
        assert (o["b"], o["c"], o["d"]) == (i["a"], i["b"], i["c"])
        assert (o["f"], o["g"], o["h"]) == (i["e"], i["f"], i["g"])


def test_trace_is_json_roundtrippable():
    tr = rt.trace_block(ref.IV, ref.pad(b"abc"))
    assert rt.replay(json.loads(json.dumps(tr))) == tr["output_state"]


def test_tampered_trace_fails_replay():
    tr = rt.trace_block(ref.IV, ref.pad(b"abc"))
    tr["rounds"][17]["W"] = "00000000"
    with pytest.raises(rt.TraceMismatch):
        rt.replay(tr)


def test_reduced_round_trace():
    tr = rt.trace_block(ref.IV, ref.pad(b"abc"), rounds=20)
    assert len(tr["rounds"]) == 20 and tr["rounds_executed"] == 20
    assert rt.replay(tr) == tr["output_state"]
    assert tr["output_state"] != rt.trace_block(ref.IV, ref.pad(b"abc"))["output_state"]


def test_message_trace_multiblock_chain():
    msg = b"a" * 100
    tr = rt.trace_message(msg)
    assert len(tr["blocks"]) == 2
    assert tr["digest"] == hashlib.sha256(msg).hexdigest()
    assert tr["blocks"][1]["input_state"] == tr["blocks"][0]["output_state"]
    assert tr["padding"]["padded_length"] == 128


def test_sha256d_header_trace_structure():
    header = bytes.fromhex(vectors.GENESIS_HEADER_HEX)
    tr = rt.trace_sha256d(header)
    first = tr["first_pass"]
    assert len(first["blocks"]) == 2
    assert first["midstate"] == first["blocks"][0]["output_state"]
    assert len(tr["second_pass"]["blocks"]) == 1
    assert tr["double_hash"] == hashlib.sha256(hashlib.sha256(header).digest()).hexdigest()
    assert tr["display_hash"] == vectors.GENESIS_BLOCK_HASH
    assert tr["source"] == "SOFTWARE_REPLAY"


def test_sha256d_rejects_non_80_byte_header():
    with pytest.raises(ValueError):
        rt.trace_sha256d(b"\x00" * 79)


def test_replay_candidate():
    header = bytes.fromhex(vectors.GENESIS_HEADER_HEX)
    nonce = int.from_bytes(header[76:80], "little")
    ok = rt.replay_candidate(header[:76], nonce, leading_zero_bits=32)
    assert ok["verified"] is True and ok["source"] == "SOFTWARE_REPLAY"
    bad = rt.replay_candidate(header[:76], nonce ^ 1, leading_zero_bits=32)
    assert bad["verified"] is False
    with pytest.raises(ValueError):
        rt.replay_candidate(b"\x00" * 75, 0, leading_zero_bits=1)
    with pytest.raises(ValueError):
        rt.replay_candidate(header[:76], 2**32, leading_zero_bits=1)


def test_differential_view():
    a = rt.trace_block(ref.IV, ref.pad(b"abc"))
    b = rt.trace_block(ref.IV, ref.pad(b"abd"))
    d = rt.diff_traces(a, b)
    assert len(d["rounds"]) == 64
    assert d["final_hamming"] > 64
