"""Hardware policy: state machine, device allowlist (timsminer only), protocol, backup manifest."""
import hashlib
import json
import struct

import pytest

from cqhecs.hardware import evidence, miner_capabilities as caps, miner_protocol as proto
from cqhecs.hardware.state_machine import IllegalTransition, MinerState, MinerStateMachine

# ---------------------------------------------------------------- state machine


def test_demo_can_never_reach_flash_or_hardware_states():
    sm = MinerStateMachine()
    assert sm.state is MinerState.DEMO
    for target in (MinerState.RESEARCH_ARMED, MinerState.RUNNING, MinerState.RESTORING, MinerState.READY):
        with pytest.raises(IllegalTransition):
            sm.transition(target)
    assert not sm.may_flash()


def test_read_only_never_auto_arms():
    sm = MinerStateMachine(MinerState.CONNECTED_READ_ONLY)
    with pytest.raises(IllegalTransition):
        sm.transition(MinerState.RESEARCH_ARMED)
    sm.transition(MinerState.BACKUP_REQUIRED)
    sm.transition(MinerState.READY)
    sm.transition(MinerState.RESEARCH_ARMED, operator_confirmed=True)
    assert sm.state is MinerState.RESEARCH_ARMED


def test_arming_needs_operator_confirmation():
    sm = MinerStateMachine(MinerState.READY)
    with pytest.raises(IllegalTransition):
        sm.transition(MinerState.RESEARCH_ARMED)
    sm.transition(MinerState.RESEARCH_ARMED, operator_confirmed=True)
    sm.transition(MinerState.RUNNING)
    sm.transition(MinerState.PAUSED)


def test_restore_requires_confirmation_and_failure_goes_to_recovery():
    sm = MinerStateMachine(MinerState.RESTORE_READY)
    with pytest.raises(IllegalTransition):
        sm.transition(MinerState.RESTORING)
    sm.transition(MinerState.RESTORING, operator_confirmed=True)
    sm.transition(MinerState.RECOVERY_REQUIRED)
    # no automatic retry from recovery/fault
    with pytest.raises(IllegalTransition):
        sm.transition(MinerState.RESTORING, operator_confirmed=True)


def test_fault_has_no_auto_retry():
    sm = MinerStateMachine(MinerState.RUNNING)
    sm.transition(MinerState.FAULT)
    for t in (MinerState.RUNNING, MinerState.RESTORING, MinerState.RESEARCH_ARMED):
        with pytest.raises(IllegalTransition):
            sm.transition(t, operator_confirmed=True)


# ---------------------------------------------------------------- allowlist

INFO = {
    "hostname": "timsminer", "boardVersion": "201", "ASICModel": "BM1366", "deviceModel": "Ultra",
    "version": "v4.0.2-rc1", "idfVersion": "v5.4", "macAddr": "AA:BB:CC:DD:EE:01",
    "runningPartition": "ota_0", "wifiStatus": "Connected!", "isUsingFallbackStratum": 0,
}
PROFILE = caps.DeviceProfile(device_id="timsminer-local", hostname="timsminer", board_version="201",
                             asic_model="BM1366", mac="AA:BB:CC:DD:EE:01")


def test_exact_device_passes():
    assert caps.check_identity(INFO, PROFILE).ok


@pytest.mark.parametrize("name", ["blackharkminer", "timminer2", "BlackHarkMiner", "TIMMINER2", " timminer2 "])
def test_excluded_devices_always_rejected(name):
    res = caps.check_identity({**INFO, "hostname": name}, PROFILE)
    assert not res.ok and "excluded" in res.reason


def test_profile_cannot_be_built_for_excluded_device():
    with pytest.raises(ValueError):
        caps.DeviceProfile(device_id="x", hostname="blackharkminer", board_version="201", asic_model="BM1366", mac="AA")
    with pytest.raises(ValueError):
        caps.DeviceProfile(device_id="x", hostname="timminer2", board_version="201", asic_model="BM1366", mac="AA")


@pytest.mark.parametrize(
    "patch", [{"hostname": "other"}, {"boardVersion": "400"}, {"ASICModel": "BM1370"}, {"macAddr": "AA:BB:CC:DD:EE:02"}]
)
def test_any_identity_mismatch_fails_closed(patch):
    assert not caps.check_identity({**INFO, **patch}, PROFILE).ok


def test_missing_fields_fail_closed():
    info = dict(INFO)
    del info["macAddr"]
    assert not caps.check_identity(info, PROFILE).ok
    assert not caps.check_identity({}, PROFILE).ok


# ---------------------------------------------------------------- protocol


def test_normalize_info_uses_null_and_strips_secrets():
    raw = {**INFO, "wifiPass": "secret", "stratumPassword": "pw", "stratumUser": "wallet.worker", "hashRate": 430.5,
           "temp": 55.0}
    out = proto.normalize_info(raw, device_id="timsminer-local")
    assert out["schema"] == "hcs.sha.miner.v1"
    assert out["asic_model"] == "BM1366" and out["board_version"] == 201
    assert out["hashrate_ghs"] == 430.5 and out["temperature_c"] == 55.0
    assert out["power_w"] is None and out["frequency_mhz"] is None
    blob = json.dumps(out)
    for secret in ("secret", "wallet", "pw\""):
        assert secret not in blob
    assert out["research_armed"] is False and out["research_enabled"] is False
    assert out["pool_connected"] is None  # not reported by the stock API: never guessed


def test_normalize_rejects_non_numeric_telemetry():
    out = proto.normalize_info({**INFO, "hashRate": "fast", "temp": float("nan")}, device_id="d")
    assert out["hashrate_ghs"] is None and out["temperature_c"] is None


# ---------------------------------------------------------------- backup manifest


def _fake_app_image(project="esp-miner", version="v4.0.2-rc1", chip_id=9, size=4096):
    header = bytearray(24)
    header[0] = 0xE9
    header[1] = 1  # one segment
    struct.pack_into("<H", header, 12, chip_id)
    seg = struct.pack("<II", 0x3C010020, 256)
    desc = bytearray(256)
    struct.pack_into("<I", desc, 0, 0xABCD5432)
    desc[16:16 + len(version)] = version.encode()
    desc[48:48 + len(project)] = project.encode()
    img = bytes(header) + seg + bytes(desc)
    return img + b"\x00" * (size - len(img))


def test_inspect_valid_image():
    info = evidence.inspect_app_image(_fake_app_image())
    assert info.valid and info.chip == "ESP32-S3" and info.project == "esp-miner" and info.version == "v4.0.2-rc1"


@pytest.mark.parametrize("img", [b"", b"\x00" * 100, _fake_app_image(chip_id=5)])
def test_inspect_rejects_bad_images(img):
    info = evidence.inspect_app_image(img)
    assert not (info.valid and info.chip == "ESP32-S3")


def test_manifest_only_records_checks_that_ran(tmp_path):
    img = _fake_app_image()
    p = tmp_path / "orig.bin"
    p.write_bytes(img)
    m = evidence.build_backup_manifest(
        image_path=p, device_id="timsminer-local", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="ota_0", slot_size=0x400000, expected_project="esp-miner",
    )
    assert m["schema"] == "hcs.miner.backup.v1"
    assert m["sha256"] == hashlib.sha256(img).hexdigest() and m["image_size"] == len(img)
    v = m["verification"]
    assert v["sha256_recomputed"] and v["esp_image_info_valid"] and v["chip_match"] and v["project_match"]
    assert v["descriptor_match"] and v["fits_slot"]
    assert evidence.manifest_is_verified(m)


def test_wrong_project_or_oversize_not_verified(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(_fake_app_image(project="other"))
    m = evidence.build_backup_manifest(
        image_path=p, device_id="d", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="ota_0", slot_size=0x400000, expected_project="esp-miner",
    )
    assert not m["verification"]["project_match"] and not evidence.manifest_is_verified(m)
    p.write_bytes(_fake_app_image())
    m = evidence.build_backup_manifest(
        image_path=p, device_id="d", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="ota_0", slot_size=1024, expected_project="esp-miner",
    )
    assert not m["verification"]["fits_slot"] and not evidence.manifest_is_verified(m)


def test_incomplete_download_never_verified(tmp_path):
    p = tmp_path / "x.bin"
    img = _fake_app_image()
    p.write_bytes(img[:2000])
    m = evidence.build_backup_manifest(
        image_path=p, device_id="d", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="ota_0", slot_size=0x400000, expected_project="esp-miner",
        expected_size=len(img), expected_sha256=hashlib.sha256(img).hexdigest(),
    )
    assert not evidence.manifest_is_verified(m)


def test_tampered_manifest_not_verified(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(_fake_app_image())
    m = evidence.build_backup_manifest(
        image_path=p, device_id="d", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="ota_0", slot_size=0x400000, expected_project="esp-miner",
    )
    m["verification"]["chip_match"] = False
    assert not evidence.manifest_is_verified(m)
    assert evidence.recheck_manifest(m, p)  # recheck recomputes from the file, ignoring claimed flags
    m["verification"]["chip_match"] = True
    assert evidence.recheck_manifest(m, p)
    p.write_bytes(_fake_app_image() + b"x")
    assert not evidence.recheck_manifest(m, p)


def test_restore_preview_requires_matching_device_and_verified_manifest(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(_fake_app_image())
    m = evidence.build_backup_manifest(
        image_path=p, device_id="timsminer-local", board_version=201, asic_model="BM1366", mcu="ESP32-S3",
        firmware_version="v4.0.2-rc1", running_partition="ota_0", slot_size=0x400000, expected_project="esp-miner",
    )
    prev = evidence.restore_preview(m, p, PROFILE, target_slot="ota_1")
    assert prev["allowed"] and prev["target_slot"] == "ota_1" and prev["sha256"] == m["sha256"]
    other = caps.DeviceProfile(device_id="someone-else", hostname="timsminer", board_version="201",
                               asic_model="BM1366", mac="AA:BB:CC:DD:EE:01")
    assert not evidence.restore_preview(m, p, other, target_slot="ota_1")["allowed"]
    assert not evidence.restore_preview(m, p, PROFILE, target_slot="factory")["allowed"]
