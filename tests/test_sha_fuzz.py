"""Property/fuzz tests: random inputs must never crash the policy code or make a wrong result look verified."""
import hashlib
import random
import struct

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from cqhecs.hardware import evidence, miner_capabilities as caps, miner_protocol as proto
from cqhecs.hardware.state_machine import ALLOWED, NEEDS_OPERATOR, IllegalTransition, MinerState, MinerStateMachine
from cqhecs.sha import round_trace as rt
from cqhecs.sha import sha256_reference as ref
from cqhecs.sha.model import ShaResult, ShaState, ShaTask

FAST = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
words32 = st.integers(min_value=0, max_value=0xFFFFFFFF)


@FAST
@given(st.binary(max_size=700))
def test_sha256_equals_hashlib_for_any_bytes(data):
    assert ref.sha256(data) == hashlib.sha256(data).digest()


@FAST
@given(st.binary(min_size=0, max_size=200))
def test_sha256d_equals_hashlib(data):
    assert ref.sha256d(data) == hashlib.sha256(hashlib.sha256(data).digest()).digest()


@FAST
@given(st.lists(words32, min_size=8, max_size=8), st.lists(words32, min_size=16, max_size=16), st.integers(0, 64))
def test_trace_replay_matches_compress_for_any_state_block_rounds(state, words, rounds):
    block = b"".join(w.to_bytes(4, "big") for w in words)
    tr = rt.trace_block(tuple(state), block, rounds=rounds)
    expect = "".join(f"{w:08x}" for w in ref.compress(tuple(state), tuple(words), rounds=rounds))
    assert tr["output_state"] == expect
    assert rt.replay(tr) == expect


@FAST
@given(st.integers(0, 63), st.sampled_from(["K", "W", "T1", "T2"]), st.integers(1, 0xFFFFFFFF))
def test_any_single_tampered_round_value_is_rejected(idx, field, xor):
    tr = rt.trace_block(ref.IV, ref.pad(b"fuzz"))
    tr["rounds"][idx][field] = f"{int(tr['rounds'][idx][field], 16) ^ xor:08x}"
    with pytest.raises(rt.TraceMismatch):
        rt.replay(tr)


@FAST
@given(st.integers(0, 63), st.sampled_from(list("abcdefgh")), st.integers(1, 0xFFFFFFFF))
def test_any_tampered_register_is_rejected(idx, reg, xor):
    tr = rt.trace_block(ref.IV, ref.pad(b"fuzz"))
    side = "in" if idx % 2 else "out"
    tr["rounds"][idx][side][reg] = f"{int(tr['rounds'][idx][side][reg], 16) ^ xor:08x}"
    with pytest.raises(rt.TraceMismatch):
        rt.replay(tr)


@FAST
@given(st.binary(min_size=76, max_size=76), st.integers(0, 0xFFFFFFFF), st.integers(0, 256))
def test_candidate_replay_is_consistent_with_its_own_hash(prefix, nonce, bits):
    r = rt.replay_candidate(prefix, nonce, bits)
    value = int(r["hash"], 16)
    assert r["leading_zero_bits"] == 256 - value.bit_length()
    assert r["verified"] == (r["leading_zero_bits"] >= bits)
    assert r["hash"] == ref.sha256d(prefix + nonce.to_bytes(4, "little"))[::-1].hex()


@FAST
@given(st.integers(min_value=-(2**40), max_value=2**40))
def test_candidate_replay_rejects_out_of_range_nonce(nonce):
    if 0 <= nonce <= 0xFFFFFFFF:
        rt.replay_candidate(b"\x00" * 76, nonce, 0)
    else:
        with pytest.raises(ValueError):
            rt.replay_candidate(b"\x00" * 76, nonce, 0)


json_leaf = st.none() | st.booleans() | st.integers(-(2**70), 2**70) | st.floats(allow_nan=True, allow_infinity=True) | st.text(max_size=40)
junk_info = st.dictionaries(st.text(max_size=20), st.recursive(json_leaf, lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=5), c, max_size=3), max_leaves=6), max_size=12)
PROFILE = caps.DeviceProfile(device_id="d", hostname="timsminer", board_version="201", asic_model="BM1366", mac="AA:BB")


@FAST
@given(junk_info)
def test_identity_check_never_raises_and_rejects_junk(info):
    res = caps.check_identity(info, PROFILE)
    assert res.ok is False  # random junk can never match all four identity fields


@FAST
@given(st.one_of(st.none(), st.integers(), st.text(), st.lists(st.integers())))
def test_identity_check_rejects_non_dict_input(info):
    assert caps.check_identity(info, PROFILE).ok is False


@FAST
@given(junk_info)
def test_normalize_info_never_raises_and_never_copies_secrets(info):
    info = {**info, "wifiPass": "SECRETPSK", "stratumPassword": "SECRETPOOL", "stratumUser": "WALLET.worker"}
    out = proto.normalize_info(info, device_id="d")
    blob = str(out)
    assert "SECRETPSK" not in blob and "SECRETPOOL" not in blob and "WALLET" not in blob
    for k in ("temperature_c", "power_w", "frequency_mhz", "hashrate_ghs"):
        assert out[k] is None or isinstance(out[k], float)


@FAST
@given(st.text(max_size=30))
def test_excluded_names_stay_excluded_in_any_case_and_padding(pad):
    for name in ("blackharkminer", "timminer2"):
        assert caps.is_excluded(name.upper().center(len(name) + 4))


def _valid_image():
    header = bytearray(24)
    header[0], header[1] = 0xE9, 1
    struct.pack_into("<H", header, 12, 9)
    desc = bytearray(256)
    struct.pack_into("<I", desc, 0, 0xABCD5432)
    desc[16:26], desc[48:57] = b"v4.0.2-rc1", b"esp-miner"
    img = bytes(header) + struct.pack("<II", 0x3C010020, 256) + bytes(desc)
    return img + b"\x00" * (4096 - len(img))


@FAST
@given(st.binary(max_size=600))
def test_image_inspection_never_raises_on_random_bytes(data):
    assert evidence.inspect_app_image(data).valid in (True, False)


@FAST
@given(pos=st.integers(0, 4095), xor=st.integers(1, 255))
def test_any_flipped_header_byte_never_yields_a_verified_manifest_for_wrong_identity(pos, xor, tmp_path_factory):
    img = bytearray(_valid_image())
    img[pos] ^= xor
    d = tmp_path_factory.mktemp("img")
    p = d / "x.bin"
    p.write_bytes(bytes(img))
    m = evidence.build_backup_manifest(
        image_path=p, device_id="d", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="factory", slot_size=0x400000, expected_project="esp-miner",
    )
    if evidence.manifest_is_verified(m):
        # only bytes that do not influence identity may change while staying verified
        info = evidence.inspect_app_image(bytes(img))
        assert (info.chip, info.project, info.version) == ("ESP32-S3", "esp-miner", "v4.0.2-rc1")
    assert evidence.recheck_manifest(m, p) == evidence.manifest_is_verified(m) or not evidence.manifest_is_verified(m)


@FAST
@given(cut=st.integers(1, 4095))
def test_every_truncation_of_a_valid_image_is_rejected_when_size_is_known(cut, tmp_path_factory):
    img = _valid_image()
    p = tmp_path_factory.mktemp("trunc") / "x.bin"
    p.write_bytes(img[:cut])
    m = evidence.build_backup_manifest(
        image_path=p, device_id="d", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="factory", slot_size=0x400000, expected_project="esp-miner",
        expected_size=len(img), expected_sha256=hashlib.sha256(img).hexdigest(),
    )
    assert not evidence.manifest_is_verified(m)


def test_restore_preview_never_targets_factory_or_running_slot(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(_valid_image())
    m = evidence.build_backup_manifest(
        image_path=p, device_id="d", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="factory", slot_size=0x400000, expected_project="esp-miner",
    )
    prof = caps.DeviceProfile(device_id="d", hostname="timsminer", board_version="201", asic_model="BM1366", mac="AA")
    for slot in ("factory", "otadata", "nvs", "../x", "", "OTA_0", "ota_2"):
        assert not evidence.restore_preview(m, p, prof, slot)["allowed"]
    assert evidence.restore_preview(m, p, prof, "ota_0")["allowed"]


@pytest.mark.parametrize("seed", range(25))
def test_state_machine_random_walk_never_skips_confirmation(seed):
    rng = random.Random(seed)
    sm = MinerStateMachine()
    for _ in range(300):
        target = rng.choice(list(MinerState))
        confirmed = rng.random() < 0.3
        before = sm.state
        try:
            sm.transition(target, operator_confirmed=confirmed)
        except IllegalTransition:
            assert sm.state is before
            continue
        assert target in ALLOWED[before]
        if (before, target) in NEEDS_OPERATOR:
            assert confirmed
        if before is MinerState.DEMO:
            assert target is MinerState.DISCONNECTED
    assert not (sm.state is MinerState.DEMO and sm.may_flash())


@FAST
@given(st.text(max_size=40), st.integers(-5, 80), st.text(max_size=30))
def test_result_contract_rejects_bad_tasks_and_never_forges_integrity(task_id, rounds, backend):
    try:
        task = ShaTask(task_id=task_id, algorithm="SHA-256", rounds=rounds, iv="standard", input_model="bytes",
                       target="digest", endian="big", seed=0, budget={}, backend=backend)
    except ValueError:
        assert not (0 <= rounds <= 64 and backend in ("WEBGPU", "WASM_SIMD", "WASM_SCALAR", "BROWSER_CPU", "LOCAL_NATIVE", "ASIC_BM1366", "DEMO_SIMULATED"))
        return
    state = ShaState.SIMULATED if backend == "DEMO_SIMULATED" else ShaState.COMPUTED
    try:
        res = ShaResult.create(task, state, payload={"x": 1}, software={}, firmware_version="v" if backend == "ASIC_BM1366" else None)
    except ValueError:
        return
    assert res.verify_integrity()
    d = res.to_dict()
    d["payload"]["x"] = 2
    assert not ShaResult.from_dict(d).verify_integrity()
