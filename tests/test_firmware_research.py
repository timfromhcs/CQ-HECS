"""Firmware profile pinning and the device research client.

Two halves, both about not believing a device:

* `firmware_profile` refuses a profile that makes an ASIC-internal claim, and
  refuses an image whose digest does not match the record.
* `research_client` replays every trace the device returns through the
  independent Python reference before it accepts a single value.

The fake firmware below speaks the real route shapes (`/api/research/*`) and can
be told to tamper, so the client's checks are exercised against behaviour a
broken or dishonest build would actually produce.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cqhecs.hardware import firmware_profile as fw
from cqhecs.hardware.research_client import ResearchClient, ResearchError
from cqhecs.sha import round_trace, sha256_reference as ref


# ------------------------------------------------------------------ profile


def valid_profile_dict(**overrides):
    data = {
        "schema": fw.SCHEMA,
        "version": "v4.0.2-test",
        "project": "esp-miner",
        "chip": "ESP32-S3",
        "source_commit": "deadbee",
        "image_sha256": "ab" * 32,
        "image_bytes": 1234,
        "board_version": "201",
        "asic_model": "BM1366",
        "features": ["sha256", "sha256d", "round_trace", "reduced_rounds"],
        "build_flags": {"CONFIG_TIMSMINER_SHA_RESEARCH": "y"},
        "research_limits": {"max_jobs": 64, "max_runtime_s": 900, "max_temperature_c": 65},
        "compute": "software_cpu",
        "asic_access": "none",
    }
    data.update(overrides)
    return data


def test_profile_roundtrip():
    profile = fw.FirmwareProfile.from_dict(valid_profile_dict())
    assert profile.features == ("sha256", "sha256d", "round_trace", "reduced_rounds")
    assert fw.FirmwareProfile.from_dict(profile.to_dict()) == profile


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"schema": "hcs.sha.firmware_profile.v2"}, "schema"),
        ({"project": "some-other-app"}, "ESP-Miner"),
        ({"chip": "ESP32-C3"}, "target"),
        ({"image_sha256": "zz" * 32}, "hexadecimal"),
        ({"image_sha256": "ab"}, "sha256"),
        ({"features": ["sha256", "asic_rounds"]}, "ASIC-internal"),
        ({"features": ["sha256", "teleport"]}, "unknown features"),
        ({"features": []}, "non-empty"),
        ({"compute": "asic_native"}, "not supported"),
        ({"asic_access": "rounds"}, "asic_access"),
        ({"research_limits": {"max_jobs": 8}}, "max_runtime_s"),
    ],
)
def test_profile_rejects_bad_input(overrides, message):
    with pytest.raises(fw.ProfileError) as exc:
        fw.FirmwareProfile.from_dict(valid_profile_dict(**overrides))
    assert message.lower() in str(exc.value).lower()


def test_profile_requires_fields():
    data = valid_profile_dict()
    del data["build_flags"]
    with pytest.raises(fw.ProfileError, match="missing"):
        fw.FirmwareProfile.from_dict(data)


def test_profile_verify_image(tmp_path):
    image = tmp_path / "esp-miner.bin"
    image.write_bytes(b"firmware-image-bytes")
    import hashlib

    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    profile = fw.FirmwareProfile.from_dict(
        valid_profile_dict(image_sha256=digest, image_bytes=image.stat().st_size)
    )
    assert profile.verify_image(image).ok

    other = tmp_path / "other.bin"
    other.write_bytes(b"tampered")
    assert not profile.verify_image(other).ok
    assert not profile.verify_image(tmp_path / "missing.bin").ok

    size_mismatch = fw.FirmwareProfile.from_dict(valid_profile_dict(image_sha256=digest, image_bytes=1))
    assert not size_mismatch.verify_image(image).ok


def status_doc(**overrides):
    data = {
        "schema": "hcs.sha.miner.v1",
        "kind": "research_status",
        "firmware_version": "v4.0.2-test",
        "mcu": "ESP32-S3",
        "asic_model": "BM1366",
        "board_version": "201",
        "firmware_build_id": "ab" * 8,
        "research_enabled": True,
        "research_state": "disarmed",
    }
    data.update(overrides)
    return data


def test_profile_matches_device():
    profile = fw.FirmwareProfile.from_dict(valid_profile_dict())
    assert profile.matches_device(status_doc()).ok

    cases = [
        (status_doc(firmware_version="v9"), "version"),
        (status_doc(mcu="ESP32-C3"), "MCU"),
        (status_doc(asic_model="BM1370"), "ASIC"),
        (status_doc(board_version="204"), "board"),
        (status_doc(research_enabled=False), "research mode"),
        (status_doc(schema="hcs.sha.miner.v2"), "schema"),
        (status_doc(firmware_build_id="cd" * 8), "build id"),
        ({}, "no device status"),
    ]
    for document, reason in cases:
        result = profile.matches_device(document)
        assert not result.ok and reason.lower() in result.reason.lower(), (result, reason)


def test_capabilities_claim_guard():
    fw.reject_asic_round_claim({"compute": "software_cpu", "limitations": {"asic_access": "none"},
                                "features": ["sha256", "round_trace"]})
    with pytest.raises(fw.ProfileError, match="asic_access"):
        fw.reject_asic_round_claim({"limitations": {"asic_access": "round-registers"}})
    with pytest.raises(fw.ProfileError, match="compute"):
        fw.reject_asic_round_claim({"compute": "asic_dma"})
    with pytest.raises(fw.ProfileError, match="cannot provide"):
        fw.reject_asic_round_claim({"features": ["asic_rounds"]})
    with pytest.raises(fw.ProfileError, match="unknown feature"):
        fw.reject_asic_round_claim({"features": ["quantum"]})


# ------------------------------------------------------------- fake firmware


class FakeFirmware:
    """Speaks the `/api/research/*` shapes; can be told to lie."""

    def __init__(self):
        self.compute = "software_cpu"
        self.asic_access = "none"
        self.tamper_round = False
        self.tamper_digest = False
        self.refuse_trace = None
        self.requests = []
        self.version = "v4.0.2-test"
        self.server = None
        self.thread = None
        self.port = None

    # -- documents
    def status(self):
        return status_doc(firmware_version=self.version)

    def capabilities(self):
        return {
            "schema": "hcs.sha.miner.v1",
            "kind": "research_capabilities",
            "compute": self.compute,
            "limitations": {"asic_access": self.asic_access},
            "features": ["sha256", "sha256d", "round_trace", "reduced_rounds"],
        }

    def trace_response(self, block_hex, rounds, feed_forward):
        block = bytes.fromhex(block_hex)
        trace = round_trace.trace_block(ref.IV, block, rounds=rounds, feed_forward=feed_forward)
        if self.tamper_round and trace["rounds"]:
            trace["rounds"][3]["out"]["a"] = "deadbeef"
        return {
            "schema": "hcs.sha.device_sha256.v1",
            "kind": "block_trace",
            "compute": self.compute,
            "asic_access": self.asic_access,
            "firmware_version": self.version,
            "trace": trace,
        }

    def digest_response(self, message_hex, sha256d):
        message = bytes.fromhex(message_hex)
        digest = (ref.sha256d(message) if sha256d else ref.sha256(message)).hex()
        if self.tamper_digest:
            digest = ("00" if digest[:2] != "00" else "11") + digest[2:]
        return {
            "schema": "hcs.sha.device_sha256.v1",
            "kind": "message_digest",
            "compute": "software_cpu",
            "asic_access": "none",
            "algorithm": "sha256d" if sha256d else "sha256",
            "message_bytes": len(message),
            "digest": digest,
        }

    # -- server
    def start(self):
        firmware = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # keep pytest output clean
                pass

            def _send(self, status, body):
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _read(self):
                length = int(self.headers.get("Content-Length", 0))
                return json.loads(self.rfile.read(length) or b"{}")

            def do_GET(self):
                firmware.requests.append(("GET", self.path))
                if self.path == "/api/research/status":
                    return self._send(200, firmware.status())
                if self.path == "/api/research/capabilities":
                    return self._send(200, firmware.capabilities())
                if self.path == "/redirect-me":
                    self.send_response(302)
                    self.send_header("Location", "/api/research/status")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return None
                return self._send(404, {"status": "not found"})

            def do_POST(self):
                firmware.requests.append(("POST", self.path))
                body = self._read()
                if self.path == "/api/research/sha256":
                    if firmware.refuse_trace:
                        return self._send(409, {"status": "conflict", "message": firmware.refuse_trace})
                    if "block_hex" in body:
                        return self._send(
                            200,
                            firmware.trace_response(
                                body["block_hex"], body.get("rounds", 64), body.get("feed_forward", True)
                            ),
                        )
                    return self._send(
                        200, firmware.digest_response(body.get("message_hex", ""), bool(body.get("sha256d")))
                    )
                if self.path == "/api/research/challenge":
                    return self._send(200, {"schema": "hcs.sha.miner.v1", "result": "challenge_issued", "digits": 6})
                if self.path == "/api/research/arm":
                    token = str(body.get("token", ""))
                    if token == "482913":
                        return self._send(200, {"accepted": True, "result": "ok", "state": "armed"})
                    return self._send(409, {"accepted": False, "result": "no_valid_token", "state": "disarmed"})
                if self.path in ("/api/research/pause", "/api/research/resume",
                                 "/api/research/cancel", "/api/research/disarm"):
                    return self._send(200, {"accepted": True, "result": "ok", "state": "disarmed"})
                return self._send(404, {"status": "not found"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()


@pytest.fixture
def firmware():
    fake = FakeFirmware().start()
    yield fake
    fake.stop()


@pytest.fixture
def client(firmware):
    return ResearchClient("127.0.0.1", port=firmware.port, timeout=5.0)


BLOCK = bytes(range(64))


# ------------------------------------------------------------------ client


def test_client_status_and_capabilities(client):
    status = client.status()
    assert status["schema"] == "hcs.sha.miner.v1"
    caps = client.capabilities()
    assert caps["limitations"]["asic_access"] == "none"


def test_client_rejects_asic_round_claim(firmware, client):
    firmware.asic_access = "round-registers"
    with pytest.raises(fw.ProfileError, match="asic_access"):
        client.capabilities()


def test_trace_is_verified_against_the_reference(client):
    result = client.trace_block(BLOCK)
    assert result.ok, result.reason
    assert result.trace["rounds_executed"] == 64
    # The state the device reported must equal the Python reference compression
    # of the same block with the same input state.
    expected = ref.compress(ref.IV, ref.block_words(BLOCK))
    assert result.output_state == ref.state_bytes(expected).hex()


def test_reduced_rounds_are_verified(client):
    result = client.trace_block(BLOCK, rounds=7, feed_forward=False)
    assert result.ok, result.reason
    assert result.trace["rounds_executed"] == 7
    assert len(result.trace["rounds"]) == 7
    assert result.trace["feed_forward"] is False


def test_tampered_trace_is_refused(firmware, client):
    firmware.tamper_round = True
    result = client.trace_block(BLOCK)
    assert not result.ok
    assert "replay" in result.reason.lower()


def test_device_claiming_asic_access_is_refused(firmware, client):
    firmware.asic_access = "round-registers"
    result = client.trace_block(BLOCK)
    assert not result.ok and "ASIC" in result.reason


def test_device_claiming_native_compute_is_refused(firmware, client):
    firmware.compute = "asic_native"
    result = client.trace_block(BLOCK)
    assert not result.ok and "software" in result.reason


def test_refusal_is_a_result_not_an_exception(firmware, client):
    firmware.refuse_trace = "thermal_unsafe"
    result = client.trace_block(BLOCK)
    assert not result.ok
    assert result.reason == "thermal_unsafe"


def test_client_validates_inputs_before_sending(firmware, client):
    with pytest.raises(ValueError, match="64 bytes"):
        client.trace_block(b"too short")
    with pytest.raises(ValueError, match="rounds"):
        client.trace_block(BLOCK, rounds=65)
    with pytest.raises(ValueError, match="token"):
        client.arm("not-a-number")
    with pytest.raises(ValueError, match="512"):
        client.digest(b"x" * 513)
    assert not any(path == "/api/research/sha256" for _, path in firmware.requests)


def test_digest_matches_reference(client):
    digest, body = client.digest(b"abc", sha256d=False)
    assert digest == ref.sha256(b"abc").hex()
    assert body["kind"] == "message_digest"


def test_digest_mismatch_raises(firmware, client):
    firmware.tamper_digest = True
    with pytest.raises(ResearchError, match="does not match"):
        client.digest(b"abc")


def test_commands(client):
    assert client.challenge().ok
    assert client.arm(482913).ok
    assert client.arm(1).reason == "no_valid_token"
    assert client.pause().ok and client.resume().ok and client.cancel().ok and client.disarm().ok


def test_redirects_are_not_followed(firmware):
    client = ResearchClient("127.0.0.1", port=firmware.port, timeout=5.0)
    before = len(firmware.requests)
    status, body = client._request("GET", "/redirect-me")
    # The 302 is surfaced as a status, not followed to the JSON route behind it.
    assert status == 302
    assert firmware.requests[before:] == [("GET", "/redirect-me")]


def test_unreachable_device_raises():
    client = ResearchClient("127.0.0.1", port=1, timeout=1.0)
    with pytest.raises(ResearchError):
        client.status()


def test_host_validation():
    for bad in ("", "http://x", "127.0.0.1/api", "*", "10.0.0.0/8"):
        with pytest.raises(ValueError):
            ResearchClient(bad)
    with pytest.raises(ValueError):
        ResearchClient("127.0.0.1", port=0)
    with pytest.raises(ValueError):
        ResearchClient("127.0.0.1", port=70000)


# ----------------------------------------------------------------------- CLI


def test_cli_profile_and_verify(tmp_path, capsys):
    import importlib.util
    import pathlib

    script = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sha_forge_firmware.py"
    spec = importlib.util.spec_from_file_location("sha_forge_firmware", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    image = tmp_path / "esp-miner.bin"
    image.write_bytes(b"firmware-image")
    profile_path = tmp_path / "profile.json"

    assert module.main([
        "profile", "--image", str(image), "--out", str(profile_path),
        "--version", "v4.0.2-test", "--commit", "abc1234",
    ]) == 0
    capsys.readouterr()

    profile = fw.FirmwareProfile.load(profile_path)
    assert profile.image_bytes == len(b"firmware-image")
    assert profile.research_limits["max_jobs"] == 64
    assert profile.asic_access == "none"

    assert module.main(["verify-profile", "--profile", str(profile_path), "--image", str(image)]) == 0
    assert "OK" in capsys.readouterr().out

    image.write_bytes(b"tampered")
    assert module.main(["verify-profile", "--profile", str(profile_path), "--image", str(image)]) == 1
    assert "FAIL" in capsys.readouterr().out
