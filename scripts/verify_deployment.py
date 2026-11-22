#!/usr/bin/env python3
"""Check that a deployed CQ-HECS web build is the expected version and source commit.

The Vite build embeds ``__APP_VERSION__`` and ``__SOURCE_SHA__`` as string literals in the
entry bundle (src/main.ts provenance line). This fetches the app shell, finds the module
scripts, fetches them and looks for those literals. Standard library only.

    python scripts/verify_deployment.py <base-url> --sha <commit> [--version 7.0.0]
                                        [--bypass-token TOKEN | env VERCEL_PROTECTION_BYPASS]

Exit codes: 0 verified, 1 mismatch, 2 unreachable / no bundle found,
            3 Vercel protection page (nothing verified; never reported as a pass).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request

PROTECTION_MARKERS = (b"Log in to Vercel", b"Protected Deployment", b"vercel.com/login")
SCRIPT_RE = re.compile(rb'<script[^>]+src="([^"]+\.js)"')
PRELOAD_RE = re.compile(rb'<link[^>]+rel="modulepreload"[^>]+href="([^"]+\.js)"')


def _default_version() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        text = open(os.path.join(here, "version.py"), encoding="utf-8").read()
        m = re.search(r'^VERSION = "([^"]+)"', text, re.M)
        return m.group(1) if m else "7.0.0"
    except OSError:
        return "7.0.0"


def fetch(url: str, bypass: str = "", timeout: float = 20.0) -> tuple[int, bytes]:
    headers = {"User-Agent": "cqhecs-verify-deployment"}
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0, b""


def verify(base: str, sha: str, version: str, bypass: str = "") -> tuple[int, list[str]]:
    """Return (exit_code, report lines)."""
    base = base.rstrip("/")
    log: list[str] = []
    status, shell = fetch(base + "/", bypass)
    if status == 0:
        return 2, [f"unreachable: {base}"]
    if any(m in shell for m in PROTECTION_MARKERS):
        return 3, ["Vercel Deployment Protection page served; nothing verified (not an app failure)."]
    if status != 200:
        return 2, [f"app shell answered HTTP {status}"]
    paths = [m.decode() for m in SCRIPT_RE.findall(shell)]
    if not paths:
        return 2, ["no module script in the app shell"]
    # Follow modulepreload too: the provenance literals may live in a shared chunk.
    paths += [m.decode() for m in PRELOAD_RE.findall(shell) if m.decode() not in paths]
    ver_lit = f'"{version}"'.encode()
    sha_lit = f'"{sha}"'.encode()
    found_ver = found_sha = False
    for path in paths:
        url = path if path.startswith("http") else base + (path if path.startswith("/") else "/" + path)
        st, body = fetch(url, bypass)
        if st != 200:
            log.append(f"FAIL  {path}: HTTP {st}")
            continue
        has_v, has_s = ver_lit in body, sha_lit in body
        found_ver |= has_v
        found_sha |= has_s
        log.append(f"      {path}: version={'yes' if has_v else 'no'} sha={'yes' if has_s else 'no'}")
    log.append(f"{'PASS' if found_ver else 'FAIL'}  version literal {version}")
    log.append(f"{'PASS' if found_sha else 'FAIL'}  source SHA literal {sha}")
    return (0 if found_ver and found_sha else 1), log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--sha", required=True, help="expected full 40-hex source commit")
    ap.add_argument("--version", default=_default_version())
    ap.add_argument("--bypass-token", default=os.environ.get("VERCEL_PROTECTION_BYPASS", ""))
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        print("--sha must be a full 40-character lowercase hex commit", file=sys.stderr)
        return 2
    code, lines = verify(args.url, args.sha, args.version, args.bypass_token)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
