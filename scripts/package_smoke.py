"""Smoke-test an installed CQ-HECS command (wheel venv console script or onedir exe).

    python scripts/package_smoke.py --cmd <path to cq-hecs[.exe]> --label wheel-venv \
        [--python <venv python>] [--expect-version 5.0.0] [--out report.json]

The command runs from a fresh temporary working directory that is checked to be outside
the repository, with PYTHONPATH/PYTHONHOME/VIRTUAL_ENV removed from the environment, so
the repository source cannot satisfy an import by accident.  Checks:

  version, doctor (typed vulkan_loader state), Bell circuit, SAT + DRAT proof (OMNIWAVE),
  qg catalog, qg run-local (offline model), Studio start / health / stop, Studio port
  conflict (must exit non-zero, not hang), Studio process-tree shutdown, MCP stdio
  initialize + tools/list.

Nothing here calls a QPU provider or reads a credential.  A check that cannot run is
reported SKIPPED with a reason, never PASS.  Exit code is 0 only if no check FAILED.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRUB_ENV = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTHONSTARTUP", "PYTHONUSERBASE")
PIGEON_CNF = (
    "c pigeonhole 3 pigeons / 2 holes (UNSAT)\n"
    "p cnf 6 9\n"
    "1 2 0\n3 4 0\n5 6 0\n"
    "-1 -3 0\n-1 -5 0\n-3 -5 0\n"
    "-2 -4 0\n-2 -6 0\n-4 -6 0\n"
)


def clean_env() -> Dict[str, str]:
    env = dict(os.environ)
    for key in SCRUB_ENV:
        env.pop(key, None)
    # No credential of any kind may leak into a packaged-binary smoke test.
    for key in list(env):
        if key.upper().startswith(("CQ_HECS_STUDIO_TOKEN", "OPENQUANTUM", "IBM_", "QISKIT_IBM")):
            env.pop(key, None)
    return env


def is_admin() -> Optional[bool]:
    if os.name != "nt":
        return os.geteuid() == 0 if hasattr(os, "geteuid") else None
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001 - report unknown instead of guessing
        return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def process_tree(pid: int) -> List[int]:
    """PIDs of ``pid`` and all of its descendants (best effort, stdlib + PowerShell)."""
    try:
        import psutil  # type: ignore

        p = psutil.Process(pid)
        return [pid] + [c.pid for c in p.children(recursive=True)]
    except ImportError:
        pass
    except Exception:  # noqa: BLE001
        return [pid]
    if os.name != "nt":
        return [pid]
    ps = (
        "$q=@(%d);$all=@(%d);while($q.Count){$n=@();foreach($p in $q){"
        "$n+=Get-CimInstance Win32_Process -Filter \"ParentProcessId=$p\" | "
        "ForEach-Object {$_.ProcessId}};$all+=$n;$q=$n};$all -join ','"
    ) % (pid, pid)
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60
    ).stdout.strip()
    return [int(x) for x in out.split(",") if x.strip().isdigit()] or [pid]


STUDIO_TOKEN = "package-smoke-test-token-not-a-secret"


def studio_env(env: Dict[str, str]) -> Dict[str, str]:
    out = dict(env)
    out["CQ_HECS_STUDIO_TOKEN"] = STUDIO_TOKEN  # throwaway local value, loopback only
    return out


def http_get(port: int, path: str, token: Optional[str] = STUDIO_TOKEN, timeout: int = 5):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return urllib.request.urlopen(req, timeout=timeout)


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Smoke:
    def __init__(self, cmd: List[str], cwd: Path, env: Dict[str, str], python: Optional[str]):
        self.cmd, self.cwd, self.env, self.python = cmd, cwd, env, python
        self.results: List[Dict[str, Any]] = []

    def run(self, args: List[str], timeout: int = 180, stdin: Optional[str] = None):
        return subprocess.run(
            self.cmd + args, cwd=self.cwd, env=self.env, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, input=stdin,
        )

    def check(self, name: str, fn: Callable[[], Any]) -> None:
        t0 = time.time()
        try:
            detail = fn()
            status = "PASS"
            if isinstance(detail, tuple):
                status, detail = detail
        except Skip as exc:
            status, detail = "SKIPPED", str(exc)
        except Exception as exc:  # noqa: BLE001
            status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
        self.results.append(
            {"check": name, "status": status, "seconds": round(time.time() - t0, 2), "detail": detail}
        )
        print(f"[{status}] {name}: {str(detail)[:200]}", flush=True)


class Skip(Exception):
    pass


def _json(proc: subprocess.CompletedProcess) -> Any:
    if proc.returncode != 0:
        raise AssertionError(f"exit {proc.returncode}: {proc.stderr[-400:]}")
    return json.loads(proc.stdout)


def run_checks(s: Smoke, expect_version: Optional[str]) -> None:
    def version():
        p = s.run(["version"])
        assert p.returncode == 0, p.stderr[-300:]
        if expect_version:
            assert expect_version in p.stdout, f"{expect_version!r} not in {p.stdout!r}"
        return p.stdout.strip()

    def where():
        if not s.python:
            raise Skip("no --python given (frozen app: import location is the bundle)")
        p = subprocess.run(
            [s.python, "-I", "-c", "import cqhecs,sys;print(cqhecs.__file__)"],
            cwd=s.cwd, env=s.env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        loc = p.stdout.strip()
        assert p.returncode == 0, p.stderr[-300:]
        assert "site-packages" in loc and str(REPO_ROOT).lower() not in loc.lower(), loc
        return loc

    def doctor():
        d = _json(s.run(["--format", "json", "doctor"]))
        vk = d["components"]["vulkan_loader"]
        assert vk["status"] in ("available", "not_available"), vk
        return {"vulkan_loader": vk, "native_binding": d["components"]["native_binding"]["status"]}

    def bell():
        d = _json(s.run(["--format", "json", "run", "name:bell", "--shots", "64"]))["result"]
        assert set(d["counts"]) <= {"00", "11"} and sum(d["counts"].values()) == 64
        assert d["execution_mode"] == "IDEAL_CLASSICAL" and d["is_real_hardware"] is False
        return "counts " + json.dumps(d["counts"], sort_keys=True)

    def sat_proof():
        cnf = s.cwd / "pigeon.cnf"
        cnf.write_text(PIGEON_CNF)
        proof = s.cwd / "pigeon.drat"
        d = _json(s.run(["--format", "json", "sat", "solve", str(cnf), "--engine", "omniwave",
                         "--proof-out", str(proof)]))["result"]
        assert d["satisfiable"] is False and d["status"] == "UNSAT", d
        assert d["certified"] is True and d["certification"] == "DRAT_CHECKED", d
        assert proof.exists() and proof.stat().st_size > 0
        return f"{d['certification']} ({d['proof_system']})"

    def sat_dpll_sat():
        d = _json(s.run(["--format", "json", "sat", "solve", "--cnf", "p cnf 2 2\n1 2 0\n-1 0\n",
                         "--engine", "dpll", "--show-model"]))["result"]
        assert d["satisfiable"] is True and d["model_verified"] is True, d
        return "SAT model verified"

    def qg_catalog():
        d = _json(s.run(["--format", "json", "qg", "catalog"]))
        assert d.get("campaign_default") and "CLASSICAL_REFERENCE" in d.get("execution_surfaces", [])
        return f"campaign {d['campaign_default']}"

    def qg_local():
        d = _json(s.run(["--format", "json", "qg", "run-local", "--theta", "0.5"]))
        assert d["status"] == "COMPLETED" and d["execution_surface"] == "CLASSICAL_REFERENCE", d
        return d["execution_surface"]

    def studio_health():
        port = free_port()
        proc = subprocess.Popen(
            s.cmd + ["studio", "--no-browser", "--port", str(port)], cwd=s.cwd, env=studio_env(s.env),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        try:
            health = None
            last_err = None
            for _ in range(90):
                if proc.poll() is not None:
                    raise AssertionError(f"studio exited early {proc.returncode}: {proc.stderr.read()[-300:]}")
                try:
                    with http_get(port, "/api/health", timeout=3) as r:
                        health = json.load(r)
                        break
                except Exception as exc:  # noqa: BLE001
                    last_err = repr(exc)
                    time.sleep(1)
            assert health and health.get("ok"), f"no health after 90s: {last_err}"
            with http_get(port, "/static/qg.js") as r:
                assert r.status == 200 and len(r.read()) > 100
            with http_get(port, "/") as r:
                assert r.status == 200
            try:
                http_get(port, "/api/health", token=None)
                raise AssertionError("health answered without a token")
            except urllib.error.HTTPError as exc:
                assert exc.code == 401, exc.code
            tree = process_tree(proc.pid)
            return {"health_ok": True, "tree_pids": len(tree), "_proc": (proc, tree, port)}
        except BaseException:
            _kill_tree(proc)
            raise

    # Studio start -> health -> forceful tree stop -> every PID gone -> port released.
    def studio_lifecycle():
        out = studio_health()
        proc, tree, port = out.pop("_proc")
        _kill_tree(proc)
        time.sleep(2)
        alive = [p for p in tree if pid_alive(p)]
        assert not alive, f"processes survived tree kill: {alive}"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))  # port is free again
        return {**out, "after_stop_alive": 0}

    def studio_graceful():
        if os.name != "nt":
            raise Skip("CTRL_BREAK graceful stop is exercised on Windows only here")
        import signal

        port = free_port()
        proc = subprocess.Popen(
            s.cmd + ["studio", "--no-browser", "--port", str(port)], cwd=s.cwd, env=studio_env(s.env),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            for _ in range(90):
                try:
                    http_get(port, "/api/health", timeout=3).read()
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(1)
            tree = process_tree(proc.pid)
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                proc.wait(timeout=20)
                graceful = True
            except subprocess.TimeoutExpired:
                graceful = False
            time.sleep(2)
            alive = [p for p in tree if pid_alive(p)]
            _kill_tree(proc)
            if alive:
                return "FAIL", f"CTRL_BREAK left processes alive: {alive}"
            return f"graceful_exit={graceful}, tree of {len(tree)} gone"
        finally:
            _kill_tree(proc)

    def studio_port_conflict():
        port = free_port()
        blocker = socket.socket()
        blocker.bind(("127.0.0.1", port))
        blocker.listen(1)
        try:
            p = subprocess.run(
                s.cmd + ["studio", "--no-browser", "--port", str(port)], cwd=s.cwd, env=studio_env(s.env),
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise AssertionError("studio hung on a busy port instead of exiting")
        finally:
            blocker.close()
        assert p.returncode != 0, "studio reported success on a busy port"
        tail = (p.stderr or p.stdout).strip().splitlines()[-1:] or [""]
        typed = "Traceback" not in (p.stderr or "")
        return ("PASS" if typed else "PARTIAL",
                f"exit {p.returncode}; typed_message={typed}; last line: {tail[0][:160]}")

    def mcp_stdio():
        proc = subprocess.Popen(
            s.cmd + ["mcp"], cwd=s.cwd, env=s.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        )
        try:
            def rpc(obj):
                proc.stdin.write(json.dumps(obj) + "\n")
                proc.stdin.flush()
                line = proc.stdout.readline()
                if not line:
                    raise AssertionError("MCP closed stdout: " + proc.stderr.read()[-300:])
                return json.loads(line)

            init = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {},
                "clientInfo": {"name": "package-smoke", "version": "0"}}})
            assert init["result"]["protocolVersion"] and init["result"]["serverInfo"], init
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            tools = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
            names = {t["name"] for t in tools}
            assert "cqhecs_qg_catalog" in names and "cqhecs_run" in names, names
            proc.stdin.close()
            proc.wait(timeout=30)
            return f"protocol {init['result']['protocolVersion']}, {len(names)} tools, clean EOF exit {proc.returncode}"
        finally:
            _kill_tree(proc)

    s.check("not_elevated", lambda: ("PASS" if is_admin() is False else "PARTIAL",
                                      f"is_admin={is_admin()}"))
    def cwd_outside():
        assert str(REPO_ROOT).lower() not in str(s.cwd).lower(), str(s.cwd)
        return str(s.cwd)

    def env_scrubbed():
        left = [k for k in SCRUB_ENV if k in s.env]
        assert not left, left
        return "removed from parent env: " + (",".join(k for k in SCRUB_ENV if k in os.environ) or "none present")

    s.check("cwd_outside_repo", cwd_outside)
    s.check("env_scrubbed", env_scrubbed)
    s.check("import_location", where)
    s.check("version", version)
    s.check("doctor", doctor)
    s.check("circuit_bell", bell)
    s.check("sat_dpll_model", sat_dpll_sat)
    s.check("sat_omniwave_drat", sat_proof)
    s.check("qg_catalog", qg_catalog)
    s.check("qg_offline_model", qg_local)
    s.check("studio_health_and_stop", studio_lifecycle)
    s.check("studio_graceful_stop", studio_graceful)
    s.check("studio_port_conflict", studio_port_conflict)
    s.check("mcp_initialize", mcp_stdio)


def _kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            proc.kill()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cmd", required=True, help="path to cq-hecs / cq-hecs.exe")
    ap.add_argument("--label", default="package")
    ap.add_argument("--python", default=None, help="venv python, to verify the import location")
    ap.add_argument("--expect-version", default=None)
    ap.add_argument("--out", default=None, help="write the JSON report here")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    cmd = [str(Path(args.cmd).resolve())]
    with tempfile.TemporaryDirectory(prefix="cqhecs-smoke-") as tmp:
        cwd = Path(tmp).resolve()
        smoke = Smoke(cmd, cwd, clean_env(), args.python)
        run_checks(smoke, args.expect_version)
    report = {
        "label": args.label,
        "command": cmd[0],
        "platform": sys.platform,
        "is_admin": is_admin(),
        "results": smoke.results,
        "summary": {st: sum(r["status"] == st for r in smoke.results)
                    for st in ("PASS", "PARTIAL", "FAIL", "SKIPPED")},
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(report["summary"]))
    return 1 if report["summary"]["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
