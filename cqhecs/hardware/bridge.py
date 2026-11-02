"""Host-local companion bridge (read-only phase).

* Binds to loopback only; no subnet scanning, no proxying, no raw device access.
* Exact-origin CORS allowlist; pairing needs an allowed Origin and issues a
  short-lived bearer token. Mutating routes are POST-only, rate limited and
  validated against strict schemas.
* In this phase every work/flash route answers 403 READ_ONLY. The only device
  call is a GET of the stock `/api/system/info` for one explicitly configured host.
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import miner_capabilities as caps
from . import miner_protocol as proto

LOOPBACK = {"127.0.0.1", "::1", "localhost"}
MAX_BODY = 4096
RATE_LIMIT = 30          # POSTs per window
RATE_WINDOW_S = 60.0
READ_RATE_LIMIT = 120    # GETs per window
CRLF = bytes([13, 10])
POST_ROUTES = {"/pair", "/pair/revoke", "/research/jobs", "/research/pause", "/research/cancel",
               "/backup/export", "/restore/preview"}
GET_ROUTES = {"/health", "/capabilities", "/telemetry", "/research/status", "/backup/status"}
BLOCKED_WHEN_READ_ONLY = {"/research/jobs", "/research/pause", "/research/cancel", "/backup/export"}
_HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.\-]*[A-Za-z0-9])?$")


class HttpDeviceClient:
    """Reads the stock info endpoint of exactly one configured host. Nothing else."""

    def __init__(self, host: str, timeout: float = 3.0):
        if not host or not _HOST_RE.match(host):
            raise ValueError("host must be one exact hostname or IPv4 address (no paths, ranges or ports)")
        self.host = host
        self.timeout = timeout
        self.url = f"http://{host}/api/system/info"

    def get_info(self) -> dict:
        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(urllib.request.Request(self.url, method="GET"), timeout=self.timeout) as r:
            return json.loads(r.read(65536))


@dataclass(frozen=True)
class BridgeConfig:
    allowed_origins: tuple
    profile: caps.DeviceProfile
    host: str = "127.0.0.1"
    port: int = 0
    token_ttl_s: float = 600.0
    request_timeout_s: float = 5.0    # per-socket timeout: a stalled client can never pin a thread
    max_connections: int = 32         # concurrent connections; extra ones get 503
    read_cache_s: float = 1.0         # device reads inside this window are served from cache


class _Server(ThreadingHTTPServer):
    """Threaded server with a hard connection cap and no traceback spam from hostile clients."""

    daemon_threads = True
    request_queue_size = 16

    def __init__(self, addr, handler, max_connections: int):
        super().__init__(addr, handler)
        self._slots = threading.BoundedSemaphore(max_connections)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable" + CRLF + b"Content-Length: 0" + CRLF + b"Connection: close" + CRLF + CRLF)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):  # malformed or aborted clients are expected
        pass


class Bridge:
    def __init__(self, config: BridgeConfig, device, clock=time.monotonic):
        if config.host not in LOOPBACK:
            raise ValueError("the bridge binds to loopback only")
        if "*" in config.allowed_origins:
            raise ValueError("wildcard origins are not allowed")
        self.config = config
        self.device = device
        self.clock = clock
        self._tokens: dict = {}
        self._hits: list = []
        self._reads: list = []
        self._cache = None            # (expiry, (status, body))
        self._lock = threading.Lock()
        self._server = None
        self._thread = None

    # -- lifecycle
    def start(self):
        bridge = self

        class Handler(_Handler):
            owner = bridge
            timeout = bridge.config.request_timeout_s

        self._server = _Server((self.config.host, self.config.port), Handler, self.config.max_connections)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    # -- tokens and limits
    def issue_token(self) -> str:
        tok = secrets.token_urlsafe(24)
        with self._lock:
            self._tokens[tok] = self.clock() + self.config.token_ttl_s
        return tok

    def token_valid(self, tok: str | None) -> bool:
        if not tok:
            return False
        with self._lock:
            exp = self._tokens.get(tok)
            if exp is None:
                return False
            if self.clock() > exp:
                del self._tokens[tok]
                return False
            return True

    def revoke(self, tok: str):
        with self._lock:
            self._tokens.pop(tok, None)

    def rate_ok(self) -> bool:
        now = self.clock()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < RATE_WINDOW_S]
            if len(self._hits) >= RATE_LIMIT:
                return False
            self._hits.append(now)
            return True

    def read_rate_ok(self) -> bool:
        now = self.clock()
        with self._lock:
            self._reads = [t for t in self._reads if now - t < RATE_WINDOW_S]
            if len(self._reads) >= READ_RATE_LIMIT:
                return False
            self._reads.append(now)
            return True

    # -- device
    def read_device(self):
        """Returns (status, body). Identity is verified before anything is exposed.

        Results (including failures) are cached briefly so request bursts never reach the miner.
        """
        now = self.clock()
        with self._lock:
            if self._cache and now < self._cache[0]:
                return self._cache[1]
        result = self._read_device_uncached()
        with self._lock:
            self._cache = (self.clock() + self.config.read_cache_s, result)
        return result

    def _read_device_uncached(self):
        try:
            info = self.device.get_info()
        except Exception:
            return 502, {"error": "DEVICE_UNREACHABLE"}
        res = caps.check_identity(info, self.config.profile)
        if not res.ok:
            return 403, {"error": "IDENTITY_REJECTED", "reason": res.reason}
        return 200, proto.normalize_info(info, self.config.profile.device_id)


class _Handler(BaseHTTPRequestHandler):
    owner: Bridge
    server_version = "HCSBridge"

    def log_message(self, *args):  # never log headers, tokens or bodies
        pass

    # -- helpers
    def _origin(self):
        o = self.headers.get("Origin")
        return o if o in self.owner.config.allowed_origins else None

    def _send(self, status: int, body: dict):
        raw = json.dumps(body).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            origin = self._origin()
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(raw)
        except OSError:  # client went away mid-response
            self.close_connection = True

    def send_error(self, code, message=None, explain=None):  # JSON instead of the stock HTML page
        self._send(code, {"error": "BAD_REQUEST" if code < 500 else "SERVER_ERROR"})
        self.close_connection = True

    def _token(self):
        auth = self.headers.get("Authorization", "")
        return auth[7:] if auth.startswith("Bearer ") else None

    def _body(self):
        cl = self.headers.get("Content-Length")
        if cl is not None and not cl.isascii() or cl is not None and not cl.isdigit():
            self._send(400, {"error": "INVALID_CONTENT_LENGTH"})
            return None
        n = int(cl) if cl else 0
        if n > MAX_BODY:
            self._send(413, {"error": "PAYLOAD_TOO_LARGE"})
            return None
        try:
            raw = self.rfile.read(n) if n else b"{}"
        except OSError:  # includes socket timeouts: a stalled client is dropped, not waited for
            self._send(408, {"error": "REQUEST_TIMEOUT"})
            return None
        if len(raw) != n and n:
            self._send(400, {"error": "INCOMPLETE_BODY"})
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            self._send(400, {"error": "INVALID_JSON"})
            return None
        if not isinstance(data, dict):
            self._send(400, {"error": "INVALID_JSON"})
            return None
        return data

    def _strict(self, data: dict, allowed: dict) -> bool:
        """allowed maps key -> validator; unknown keys are rejected."""
        if set(data) - set(allowed) or any(not allowed[k](v) for k, v in data.items()):
            self._send(400, {"error": "INVALID_FIELDS"})
            return False
        return True

    # -- verbs
    def do_OPTIONS(self):
        origin = self._origin()
        self.send_response(204 if origin else 403)
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in POST_ROUTES:
            return self._send(405, {"error": "METHOD_NOT_ALLOWED"})
        if path == "/health":
            return self._send(200, {"ok": True, "service": "hcs-sha-forge-bridge"})
        if path == "/capabilities":
            return self._send(200, {"mode": "READ_ONLY", "can_flash": False, "can_send_work": False,
                                    "device_scan": False, "schema": proto.SCHEMA})
        m = re.fullmatch(r"/devices/([^/]+)/info", path)
        if not (path in GET_ROUTES or m):
            return self._send(404, {"error": "NOT_FOUND"})
        if not self.owner.token_valid(self._token()):
            return self._send(401, {"error": "UNAUTHORIZED"})
        if m:
            if m.group(1) != self.owner.config.profile.device_id:
                return self._send(404, {"error": "UNKNOWN_DEVICE"})
            if not self.owner.read_rate_ok():
                return self._send(429, {"error": "RATE_LIMITED"})
            return self._send(*self.owner.read_device())
        if path == "/telemetry":
            if not self.owner.read_rate_ok():
                return self._send(429, {"error": "RATE_LIMITED"})
            return self._send(*self.owner.read_device())
        if path == "/research/status":
            return self._send(200, {"state": "CONNECTED_READ_ONLY", "research_armed": False, "active_jobs": 0})
        if path == "/backup/status":
            return self._send(200, {"state": "BACKUP_REQUIRED", "verified": False, "manifests": 0})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path in GET_ROUTES:
            return self._send(405, {"error": "METHOD_NOT_ALLOWED"})
        if path not in POST_ROUTES:
            return self._send(404, {"error": "NOT_FOUND"})
        if self._origin() is None:
            return self._send(403, {"error": "ORIGIN_NOT_ALLOWED"})
        if not self.owner.rate_ok():
            return self._send(429, {"error": "RATE_LIMITED"})
        data = self._body()
        if data is None:
            return
        if path == "/pair":
            if not self._strict(data, {"purpose": lambda v: v == "read_only"}):
                return
            return self._send(200, {"token": self.owner.issue_token(), "ttl_s": self.owner.config.token_ttl_s,
                                    "scope": "read_only"})
        if not self.owner.token_valid(self._token()):
            return self._send(401, {"error": "UNAUTHORIZED"})
        if path == "/pair/revoke":
            self.owner.revoke(self._token())
            return self._send(200, {"revoked": True})
        if path == "/restore/preview":
            if not self._strict(data, {"target_slot": lambda v: v in ("ota_0", "ota_1")}):
                return
            return self._send(200, {"allowed": False, "problems": ["no verified backup manifest"],
                                    "requires_operator_confirmation": True,
                                    "target_slot": data.get("target_slot")})
        if path in BLOCKED_WHEN_READ_ONLY:
            return self._send(403, {"error": "READ_ONLY"})


class SimulatedDevice:
    """Deterministic stand-in for the allowlisted unit. Makes no network request."""

    INFO = {
        "hostname": "timsminer", "boardVersion": "201", "ASICModel": "BM1366", "version": "SIMULATED",
        "macAddr": "00:00:00:00:00:01", "runningPartition": "ota_0", "hashRate": 400.0, "temp": 52.0,
    }

    def get_info(self) -> dict:
        return dict(self.INFO)


SIMULATED_PROFILE = caps.DeviceProfile(
    device_id="simulated-timsminer", hostname="timsminer", board_version="201",
    asic_model="BM1366", mac="00:00:00:00:00:01",
)


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m cqhecs.hardware.bridge", description="HCS SHA Forge local bridge (read-only)")
    p.add_argument("--origin", action="append", required=True, help="exact allowed web origin (repeatable)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--simulate", action="store_true", help="use a simulated device; no LAN access")
    p.add_argument("--profile", help="local JSON device profile (device_id, hostname, board_version, asic_model, mac)")
    p.add_argument("--device-host", help="the one exact host of the allowlisted unit")
    args = p.parse_args(argv)
    if args.simulate:
        profile, device = SIMULATED_PROFILE, SimulatedDevice()
    else:
        if not (args.profile and args.device_host):
            p.error("--profile and --device-host are required unless --simulate is given")
        profile, device = caps.DeviceProfile.load(args.profile), HttpDeviceClient(args.device_host)
    bridge = Bridge(BridgeConfig(allowed_origins=tuple(args.origin), profile=profile, port=args.port), device)
    bridge.start()
    print(f"bridge listening on 127.0.0.1:{bridge.port} (READ_ONLY, {'SIMULATED' if args.simulate else 'device ' + args.device_host})", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
