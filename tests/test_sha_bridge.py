"""Host-local bridge: loopback only, exact-origin CORS, pairing tokens, typed read-only routes."""
import json
import urllib.error
import urllib.request

import pytest

from cqhecs.hardware import miner_capabilities as caps
from cqhecs.hardware.bridge import Bridge, BridgeConfig, HttpDeviceClient

ORIGIN = "https://sha-forge.example.test"
INFO = {
    "hostname": "timsminer", "boardVersion": "201", "ASICModel": "BM1366", "version": "v4.0.2-rc1",
    "macAddr": "AA:BB:CC:DD:EE:01", "runningPartition": "ota_0", "hashRate": 400.0, "temp": 50.0,
    "wifiPass": "SECRETPSK", "stratumPassword": "SECRETPOOL",
}
PROFILE = caps.DeviceProfile(device_id="timsminer-local", hostname="timsminer", board_version="201",
                             asic_model="BM1366", mac="AA:BB:CC:DD:EE:01")


class FakeDevice:
    def __init__(self, info):
        self.info = info
        self.calls = []

    def get_info(self):
        self.calls.append("info")
        return dict(self.info)


@pytest.fixture
def served():
    made = []

    def make(info=INFO, clock=None):
        dev = FakeDevice(info)
        cfg = BridgeConfig(allowed_origins=(ORIGIN,), profile=PROFILE, token_ttl_s=60)
        b = Bridge(cfg, dev, clock=clock) if clock else Bridge(cfg, dev)
        b.start()
        made.append(b)
        return b, dev

    yield make
    for b in made:
        b.stop()


def call(bridge, method, path, body=None, origin=ORIGIN, token=None, raw=None):
    url = f"http://127.0.0.1:{bridge.port}{path}"
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    if origin:
        req.add_header("Origin", origin)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read() or b"{}")


def pair(bridge):
    status, _, body = call(bridge, "POST", "/pair", {"purpose": "read_only"})
    assert status == 200
    return body["token"]


def test_refuses_non_loopback_bind():
    with pytest.raises(ValueError):
        Bridge(BridgeConfig(allowed_origins=(ORIGIN,), profile=PROFILE, host="0.0.0.0"), FakeDevice(INFO))


def test_health_and_capabilities(served):
    b, _ = served()
    s, _, body = call(b, "GET", "/health")
    assert s == 200 and body["ok"] is True
    s, _, body = call(b, "GET", "/capabilities")
    assert body["mode"] == "READ_ONLY" and body["can_flash"] is False and body["can_send_work"] is False


def test_cors_exact_origin_only(served):
    b, _ = served()
    _, h, _ = call(b, "GET", "/health", origin=ORIGIN)
    assert h.get("Access-Control-Allow-Origin") == ORIGIN
    _, h, _ = call(b, "GET", "/health", origin="https://evil.example")
    assert "Access-Control-Allow-Origin" not in h
    assert h.get("Access-Control-Allow-Origin") != "*"


def test_foreign_origin_cannot_mutate(served):
    b, _ = served()
    s, _, _ = call(b, "POST", "/pair", {"purpose": "read_only"}, origin="https://evil.example")
    assert s == 403
    s, _, _ = call(b, "POST", "/pair", {"purpose": "read_only"}, origin=None)
    assert s == 403  # no Origin header: not a browser we approved


def test_info_requires_token_and_checks_identity(served):
    b, dev = served()
    s, _, _ = call(b, "GET", "/devices/timsminer-local/info")
    assert s == 401 and dev.calls == []
    tok = pair(b)
    s, _, body = call(b, "GET", "/devices/timsminer-local/info", token=tok)
    assert s == 200 and body["schema"] == "hcs.sha.miner.v1" and body["hashrate_ghs"] == 400.0
    assert "SECRETPSK" not in json.dumps(body) and "SECRETPOOL" not in json.dumps(body)
    s, _, _ = call(b, "GET", "/devices/someone-else/info", token=tok)
    assert s == 404


@pytest.mark.parametrize("hostname", ["blackharkminer", "timminer2", "other"])
def test_wrong_or_excluded_device_fails_closed(served, hostname):
    b, _ = served({**INFO, "hostname": hostname})
    tok = pair(b)
    s, _, body = call(b, "GET", "/devices/timsminer-local/info", token=tok)
    assert s == 403 and "hashrate_ghs" not in body


def test_token_expires_and_can_be_revoked(served):
    now = [1000.0]
    b, _ = served(clock=lambda: now[0])
    tok = pair(b)
    assert call(b, "GET", "/telemetry", token=tok)[0] == 200
    now[0] += 61
    assert call(b, "GET", "/telemetry", token=tok)[0] == 401
    now[0] = 2000.0
    tok2 = pair(b)
    assert call(b, "POST", "/pair/revoke", {}, token=tok2)[0] == 200
    assert call(b, "GET", "/telemetry", token=tok2)[0] == 401


def test_mutating_routes_are_post_only_and_read_only_mode_refuses_work(served):
    b, dev = served()
    tok = pair(b)
    for path in ("/research/jobs", "/research/pause", "/research/cancel", "/backup/export"):
        assert call(b, "GET", path, token=tok)[0] == 405
    for path in ("/research/jobs", "/backup/export"):
        s, _, body = call(b, "POST", path, {}, token=tok)
        assert s == 403 and body["error"] == "READ_ONLY"
    assert dev.calls == []  # nothing reached the device


def test_unknown_paths_and_no_proxy(served):
    b, dev = served()
    tok = pair(b)
    for path in ("/proxy?url=http://10.0.0.1", "/api/system/restart", "/flash", "/ota", "/uart"):
        assert call(b, "GET", path, token=tok)[0] == 404
        assert call(b, "POST", path, {}, token=tok)[0] in (404, 405)
    assert dev.calls == []


def test_strict_json_validation(served):
    b, _ = served()
    assert call(b, "POST", "/pair", {"purpose": "read_only", "extra": 1})[0] == 400
    assert call(b, "POST", "/pair", {"purpose": "write_flash"})[0] == 400
    assert call(b, "POST", "/pair", raw=b"{not json")[0] == 400
    assert call(b, "POST", "/pair", raw=b"x" * 5000)[0] == 413


def test_restore_preview_is_preview_only(served):
    b, _ = served()
    tok = pair(b)
    s, _, body = call(b, "POST", "/restore/preview", {"target_slot": "ota_1"}, token=tok)
    assert s == 200 and body["allowed"] is False and body["requires_operator_confirmation"] is True


def test_backup_status_reports_no_backup(served):
    b, _ = served()
    tok = pair(b)
    s, _, body = call(b, "GET", "/backup/status", token=tok)
    assert s == 200 and body["verified"] is False and body["state"] == "BACKUP_REQUIRED"


def test_rate_limit(served):
    b, _ = served()
    codes = [call(b, "POST", "/pair", {"purpose": "read_only"})[0] for _ in range(40)]
    assert 429 in codes


def test_http_device_client_only_reads_info_endpoint():
    c = HttpDeviceClient("192.0.2.1")
    assert c.url == "http://192.0.2.1/api/system/info"
    with pytest.raises(ValueError):
        HttpDeviceClient("192.0.2.1/../../x")
    with pytest.raises(ValueError):
        HttpDeviceClient("")
    with pytest.raises(ValueError):
        HttpDeviceClient("192.168.1.0/24")  # no ranges: an exact device only
