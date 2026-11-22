"""Smoke a packaged native zip from a temporary directory (Windows or POSIX shared library).

    python scripts/package_native_smoke.py cq-hecs-cpu-7.0.0-windows-x64.zip --kind cpu
    python scripts/package_native_smoke.py cq-hecs-vulkan-7.0.0-windows-x64.zip --kind vulkan

Extracts the zip into a fresh temp directory outside the repository, loads
``cq_hecs_core`` with ctypes and reads ``cq_core_build_capabilities()``:

  cpu    -> {"cpu_core": true, "vulkan_linked": false}  and no ``vulkan-1`` import marker in any binary
  vulkan -> {"cpu_core": true, "vulkan_linked": true}   and ``cq_hecs.exe ghz`` runs

Report is JSON on stdout.  Exit 1 on any FAIL.  Not a clean-machine test.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKERS = (b"vulkan-1", b"libvulkan")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip", type=Path)
    ap.add_argument("--kind", choices=("cpu", "vulkan"), required=True)
    ap.add_argument("--allow-typed-refusal", action="store_true",
                    help="on a host without a Vulkan device, accept the CLI's typed vulkan_unavailable refusal "
                         "(exit 3, CPU reference available) as REFUSED_OK instead of a failure; it is never a PASS")
    a = ap.parse_args(argv)
    checks: List[Dict[str, Any]] = []

    def rec(name: str, status: str, detail: Any) -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    with tempfile.TemporaryDirectory(prefix="cqhecs-native-") as tmp:
        tmp_path = Path(tmp).resolve()
        with zipfile.ZipFile(a.zip) as z:
            names = z.namelist()
            z.extractall(tmp_path)
        rec("outside_repo", "PASS" if str(REPO_ROOT).lower() not in str(tmp_path).lower() else "FAIL", str(tmp_path))
        bins = sorted((tmp_path).rglob("bin/*"))
        rec("contents", "PASS", sorted(n for n in names if "/bin/" in n))
        core = next((b for b in bins if b.name.lower() in ("cq_hecs_core.dll", "libcq_hecs_core.so", "libcq_hecs_core.dylib")), None)
        if core is None:
            rec("load_core", "FAIL", "cq_hecs_core library not in package")
        else:
            # A child process loads the library, so the DLL is unlocked when the temp dir is removed.
            probe = (
                "import ctypes,json,os,sys;"
                "p=sys.argv[1];"
                "os.name=='nt' and os.add_dll_directory(os.path.dirname(p));"
                "l=ctypes.CDLL(p);l.cq_core_build_capabilities.restype=ctypes.c_char_p;"
                "print(l.cq_core_build_capabilities().decode())"
            )
            try:
                p = subprocess.run([sys.executable, "-I", "-c", probe, str(core)], cwd=tmp_path,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
                caps = json.loads(p.stdout.strip().splitlines()[-1])
                want = {"cpu_core": True, "vulkan_linked": a.kind == "vulkan"}
                rec("build_capabilities", "PASS" if caps == want else "FAIL", {"got": caps, "want": want})
            except Exception as exc:  # noqa: BLE001
                rec("load_core", "FAIL", f"{type(exc).__name__}: {exc}")
        if a.kind == "cpu":
            offenders = [b.name for b in bins if b.suffix.lower() in (".dll", ".exe", ".so")
                         and any(m in b.read_bytes().lower() for m in MARKERS)]
            rec("no_vulkan_loader_marker", "PASS" if not offenders else "FAIL", offenders or "none")
            rec("no_cli_in_cpu_package", "PASS" if not any(b.name.lower().startswith("cq_hecs.") for b in bins) else "FAIL",
                "cq_hecs.exe absent" )
        else:
            exe = next((b for b in bins if b.name.lower() == "cq_hecs.exe"), None)
            if exe is None:
                rec("cli_ghz", "FAIL", "cq_hecs.exe missing")
            else:
                env = {k: v for k, v in os.environ.items() if k.upper() not in ("PYTHONPATH", "PYTHONHOME")}
                p = subprocess.run([str(exe), "ghz", "--shots", "16", "--json"], cwd=tmp_path, env=env,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
                try:
                    out = json.loads(p.stdout.strip().splitlines()[-1])
                    ok = p.returncode == 0 and out.get("success") is True and out.get("non_parity") == 0
                except Exception as exc:  # noqa: BLE001
                    out, ok = f"{type(exc).__name__}: {p.stdout[-200:]}", False
                refused = (not ok and a.allow_typed_refusal and p.returncode == 3 and isinstance(out, dict)
                           and out.get("status") == "refused" and out.get("code") == "vulkan_unavailable"
                           and out.get("cpu_reference_available") is True)
                rec("cli_ghz", "PASS" if ok else ("REFUSED_OK" if refused else "FAIL"), out)
    summary = {s: sum(c["status"] == s for c in checks) for s in ("PASS", "REFUSED_OK", "FAIL")}
    print(json.dumps({"zip": a.zip.name, "kind": a.kind, "checks": checks, "summary": summary}, indent=2))
    return 1 if summary["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
