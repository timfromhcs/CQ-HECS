"""Adversarial tests: the bridge must survive malformed, slow and abusive clients without crashing or leaking."""
import json
import socket
import time

import pytest

from cqhecs.hardware.bridge import SIMULATED_PROFILE, Bridge, BridgeConfig, SimulatedDevice

ORIGIN = "https://sha-forge.example.test"
HDR = f"Host: x\r\nOrigin: {ORIGIN}\r\n".encode()


class CountingDevice(SimulatedDevice):
    def __init__(self):
        self.calls = 0

    def get_info(self):
        self.calls += 1
        return super().get_info()


@pytest.fixture
def bridge():
    made = []

    def make(**kw):
        cfg = BridgeConfig(allowed_origins=(ORIGIN,), profile=SIMULATED_PROFILE, token_ttl_s=60, **kw)
        dev = CountingDevice()
        b = Bridge(cfg, dev)
        b.start()
        made.append(b)
        return b, dev

    yield make
    for b in made:
        b.stop()


def raw(bridge, data: bytes, wait=3.0) -> bytes:
    s = socket.create_connection(("127.0.0.1", bridge.port), timeout=wait)
    try:
        s.sendall(data)
        out = b""
        try:
            while True:
                c = s.recv(4096)
                if not c:
                    break
                out += c
        except (socket.timeout, ConnectionError):
            pass
        return out
    finally:
        s.close()


def status(resp: bytes) -> int:
    return int(resp.split(b" ", 2)[1]) if resp.startswith(b"HTTP/") else 0


def alive(bridge) -> bool:
    return status(raw(bridge, b"GET /health HTTP/1.1\r\n" + HDR + b"\r\n")) == 200


@pytest.mark.parametrize("cl", [b"-5", b"abc", b"1e3", b" ", b"99999999999999999999", b"+5", b"0x10"])
def test_bad_content_length_is_a_clean_400_or_413(bridge, cl, capfd):
    b, _ = bridge()
    resp = raw(b, b"POST /pair HTTP/1.1\r\n" + HDR + b"Content-Length: " + cl + b"\r\n\r\n{}")
    assert status(resp) in (400, 413)
    assert alive(b)
    assert "Traceback" not in capfd.readouterr().err


def test_truncated_body_times_out_instead_of_hanging(bridge, capfd):
    b, _ = bridge(request_timeout_s=1.0)
    t0 = time.monotonic()
    resp = raw(b, b"POST /pair HTTP/1.1\r\n" + HDR + b"Content-Length: 4000\r\n\r\n{", wait=6)
    assert time.monotonic() - t0 < 4
    assert status(resp) in (408, 0)
    assert alive(b)
    assert "Traceback" not in capfd.readouterr().err


def test_idle_connections_do_not_exhaust_the_server(bridge):
    b, _ = bridge(request_timeout_s=1.0, max_connections=8)
    idle = [socket.create_connection(("127.0.0.1", b.port)) for _ in range(8)]
    try:
        time.sleep(1.6)  # idle sockets hit the request timeout and are released
        assert alive(b)
    finally:
        for s in idle:
            s.close()


@pytest.mark.parametrize("junk", [b"\x00\xff\xfeGARBAGE\r\n\r\n", b"GET\r\n\r\n", b"POST /pair\r\n\r\n", b"\r\n" * 50])
def test_garbage_requests_do_not_crash_or_trace(bridge, junk, capfd):
    b, _ = bridge()
    raw(b, junk)
    assert alive(b)
    assert "Traceback" not in capfd.readouterr().err


def test_client_that_disconnects_mid_response_is_silent(bridge, capfd):
    b, _ = bridge()
    for _ in range(20):
        s = socket.create_connection(("127.0.0.1", b.port))
        s.sendall(b"POST /pair HTTP/1.1\r\n" + HDR + b"Content-Length: 5\r\n\r\n{bad}")
        s.close()
    time.sleep(0.3)
    assert alive(b)
    assert "Traceback" not in capfd.readouterr().err


def _token(b):
    body = json.dumps({"purpose": "read_only"}).encode()
    resp = raw(b, b"POST /pair HTTP/1.1\r\n" + HDR + b"Content-Length: %d\r\n\r\n" % len(body) + body)
    return json.loads(resp.split(b"\r\n\r\n", 1)[1])["token"]


def test_device_reads_are_throttled_to_protect_the_miner(bridge):
    b, dev = bridge()
    tok = _token(b)
    codes = []
    for _ in range(40):
        r = raw(b, b"GET /telemetry HTTP/1.1\r\n" + HDR + f"Authorization: Bearer {tok}\r\n\r\n".encode())
        codes.append(status(r))
    assert dev.calls <= 3, "a burst of reads must be served from a short cache"
    assert set(codes) <= {200, 429}
    assert 200 in codes


def test_token_comparison_does_not_accept_prefixes_or_case_changes(bridge):
    b, _ = bridge()
    tok = _token(b)
    for bad in (tok[:-1], tok + "x", tok.upper() if tok.upper() != tok else tok[::-1], ""):
        r = raw(b, b"GET /telemetry HTTP/1.1\r\n" + HDR + f"Authorization: Bearer {bad}\r\n\r\n".encode())
        assert status(r) == 401


def test_response_headers_forbid_caching_and_sniffing(bridge):
    b, _ = bridge()
    r = raw(b, b"GET /health HTTP/1.1\r\n" + HDR + b"\r\n").lower()
    assert b"cache-control: no-store" in r
    assert b"x-content-type-options: nosniff" in r
