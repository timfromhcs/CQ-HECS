#!/usr/bin/env python3
"""Repository security audit (W15 / C5). Standard library only; reads, never modifies.

Checks
------
secrets   regex scan of every tracked file and, with ``--history``, every line added in the history of
          HEAD. A fallback for gitleaks/trufflehog, which are not assumed to be installed. It is a
          pattern scan, not a proof of absence: entropy-only secrets and unknown formats are not seen.
code      AST scan of ``cqhecs/`` and ``python_bridge/`` for ``pickle``/``marshal``/``shelve``, ``eval``,
          ``exec``, ``os.system``, ``shell=True`` and unsafe ``yaml.load``.
actions   GitHub Actions: every ``uses:`` pinned to a 40-hex commit SHA, explicit top-level
          ``permissions``, no ``pull_request_target``, no untrusted ``github.event`` text in ``run:``.
studio    static contract of the Studio and MCP servers: loopback default bind, bearer token compared in
          constant time, Host/Origin allow-lists, bounded body, no ``print()`` to stdout in the MCP server.

Exit status is 1 when any non-allow-listed finding exists. ``--json-out`` writes the machine-readable
report. An allow-list entry needs a written reason, so a suppression is reviewable.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- secrets
SECRET_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    "aws_access_key_id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----"),
    "anthropic_or_openai_key": re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{32,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    "huggingface_token": re.compile(r"\bhf_[A-Za-z0-9]{34,}\b"),
    "vercel_or_npm_token": re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    "assigned_secret": re.compile(
        r"""(?ix)\b(?:api[_-]?key|api[_-]?token|secret[_-]?key|access[_-]?token|auth[_-]?token|password|passwd)\b
            \s*[:=]\s*["'][A-Za-z0-9/+_\-=]{24,}["']"""
    ),
    "credential_in_url": re.compile(r"https?://[^\s/:@]{1,40}:[^\s/:@]{6,}@[A-Za-z0-9.\-]+"),
}

#: (path glob suffix, pattern name) -> reason. Keep this list short and every entry justified.
SECRET_ALLOW: Dict[Tuple[str, str], str] = {}

#: Placeholders that are documentation, not secrets.
_PLACEHOLDER = re.compile(r"(?i)(?:example|placeholder|your[_-]|xxxx|<[^>]+>|\$\{|changeme|dummy|fake|test[_-]?token)")

_BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".whl", ".wasm", ".spv", ".bin", ".exe",
    ".dll", ".so", ".npy", ".npz", ".woff", ".woff2", ".ttf", ".webp", ".mp4",
}


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _scan_line(line: str) -> Iterator[str]:
    if len(line) > 5000:
        line = line[:5000]
    for name, pattern in SECRET_PATTERNS.items():
        match = pattern.search(line)
        if match and not _PLACEHOLDER.search(match.group(0)):
            yield name


def scan_tree() -> List[dict]:
    out = _git("ls-files", "-z")
    findings: List[dict] = []
    for rel in out.stdout.split("\0"):
        if not rel or Path(rel).suffix.lower() in _BINARY_SUFFIXES:
            continue
        path = ROOT / rel
        try:
            if path.stat().st_size > 5_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for name in _scan_line(line):
                if (rel, name) in SECRET_ALLOW:
                    continue
                findings.append({"where": "tree", "file": rel, "line": number, "pattern": name})
    return findings


def scan_history(max_commits: int = 100000) -> Tuple[List[dict], int]:
    """Every line added by any commit reachable from HEAD."""
    proc = subprocess.Popen(
        ["git", "log", f"--max-count={max_commits}", "-p", "--no-color", "--no-renames", "--pretty=format:@@commit %H"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    findings: List[dict] = []
    commit, current, commits = "", "", 0
    seen = set()
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip("\n")
        if line.startswith("@@commit "):
            commit, commits = line[9:], commits + 1
            continue
        if line.startswith("+++ b/"):
            current = line[6:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if Path(current).suffix.lower() in _BINARY_SUFFIXES:
            continue
        for name in _scan_line(line[1:]):
            if (current, name) in SECRET_ALLOW:
                continue
            key = (commit, current, name)
            if key not in seen:
                seen.add(key)
                findings.append({"where": "history", "commit": commit[:12], "file": current, "pattern": name})
    proc.wait()
    return findings, commits


# --------------------------------------------------------------------------- code
_BANNED_MODULES = {"pickle", "cPickle", "marshal", "shelve", "dill", "cloudpickle"}
_BANNED_CALLS = {"eval", "exec"}


def scan_code(roots: Iterable[str] = ("cqhecs", "python_bridge")) -> List[dict]:
    findings: List[dict] = []
    for root in roots:
        for path in sorted((ROOT / root).rglob("*.py")):
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"))
            except SyntaxError as exc:
                findings.append({"file": rel, "line": exc.lineno or 0, "issue": "syntax_error"})
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in _BANNED_MODULES:
                            findings.append({"file": rel, "line": node.lineno, "issue": f"import {alias.name}"})
                elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in _BANNED_MODULES:
                    findings.append({"file": rel, "line": node.lineno, "issue": f"from {node.module} import"})
                elif isinstance(node, ast.Call):
                    func = node.func
                    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                    if name in _BANNED_CALLS and isinstance(func, ast.Name):
                        findings.append({"file": rel, "line": node.lineno, "issue": f"{name}()"})
                    if isinstance(func, ast.Attribute) and name == "system" and isinstance(func.value, ast.Name) and func.value.id == "os":
                        findings.append({"file": rel, "line": node.lineno, "issue": "os.system"})
                    if isinstance(func, ast.Attribute) and name == "load" and isinstance(func.value, ast.Name) and func.value.id == "yaml":
                        if not any(k.arg == "Loader" for k in node.keywords):
                            findings.append({"file": rel, "line": node.lineno, "issue": "yaml.load without Loader"})
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            findings.append({"file": rel, "line": node.lineno, "issue": "shell=True"})
    return findings


# --------------------------------------------------------------------------- actions
_USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.M)
_SHA = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-/]+@[0-9a-f]{40}$")
_UNTRUSTED = re.compile(
    r"\$\{\{\s*github\.(?:event\.(?:issue|pull_request|comment|review|head_commit|commits|pages|workflow_run)"
    r"[^}]*(?:title|body|name|label|ref|message|email|login)|head_ref)[^}]*\}\}"
)


def scan_actions() -> Dict[str, object]:
    unpinned: List[dict] = []
    other: List[dict] = []
    inventory: List[dict] = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        for match in _USES.finditer(text):
            ref = match.group(1)
            line = text.count("\n", 0, match.start()) + 1
            if ref.startswith("./"):
                continue
            inventory.append({"file": rel, "line": line, "uses": ref})
            if not _SHA.match(ref):
                unpinned.append({"file": rel, "line": line, "uses": ref})
        if not re.search(r"^permissions:", text, re.M):
            other.append({"file": rel, "issue": "no top-level permissions block (token defaults apply)"})
        if "pull_request_target" in text:
            other.append({"file": rel, "issue": "uses pull_request_target"})
        for number, line in enumerate(text.splitlines(), 1):
            if _UNTRUSTED.search(line) and "run:" in text:
                other.append({"file": rel, "line": number, "issue": "untrusted github.event text expanded in a workflow"})
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"curl[^|\n]*\|\s*(?:sudo\s+)?(?:ba)?sh", line):
                other.append({"file": rel, "line": number, "issue": "pipes a download into a shell"})
    return {"unpinned": unpinned, "other": other, "inventory": inventory}


# --------------------------------------------------------------------------- studio / mcp
def scan_studio_contract() -> List[dict]:
    findings: List[dict] = []
    studio = (ROOT / "cqhecs" / "studio" / "app.py").read_text(encoding="utf-8")
    mcp = (ROOT / "cqhecs" / "mcp_server.py").read_text(encoding="utf-8")

    def need(cond: bool, issue: str) -> None:
        if not cond:
            findings.append({"file": "cqhecs/studio/app.py", "issue": issue})

    need('host: str = "127.0.0.1"' in studio, "default bind host is not 127.0.0.1")
    need("secrets.token_urlsafe" in studio, "no per-launch random token")
    need("hmac.compare_digest" in studio, "token is not compared in constant time")
    need("allowed_hosts" in studio and "allowed_origins" in studio, "no Host/Origin allow-list")
    need("MAX_BODY" in studio and "413" in studio, "no request body bound")
    need("application/json" in studio and "415" in studio, "POST is not restricted to application/json")
    need("#token=" in studio, "token is not delivered in the URL fragment")
    need(not re.search(r"Access-Control-Allow-Origin", studio), "a CORS allow header is emitted")
    tree = ast.parse(mcp)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            to_stderr = any(
                k.arg == "file" and isinstance(k.value, ast.Attribute) and k.value.attr == "stderr" for k in node.keywords
            )
            if not to_stderr:
                findings.append({"file": "cqhecs/mcp_server.py", "line": node.lineno, "issue": "print() to stdout in the MCP server"})
    return findings


# --------------------------------------------------------------------------- main
def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--history", action="store_true", help="also scan every line added in HEAD's history")
    parser.add_argument("--only", choices=["secrets", "code", "actions", "studio"], action="append")
    parser.add_argument("--json-out", help="write the machine-readable report here")
    args = parser.parse_args(argv)
    wanted = set(args.only or ["secrets", "code", "actions", "studio"])

    report: Dict[str, object] = {"schema": "cqhecs.security_audit/1"}
    bad = 0
    if "secrets" in wanted:
        tree_findings = scan_tree()
        report["secrets_tree"] = tree_findings
        bad += len(tree_findings)
        if args.history:
            hist, commits = scan_history()
            report["secrets_history"] = hist
            report["history_commits_scanned"] = commits
            bad += len(hist)
        else:
            report["history_scan"] = "NOT_RUN (pass --history)"
    if "code" in wanted:
        report["code"] = scan_code()
        bad += len(report["code"])  # type: ignore[arg-type]
    if "actions" in wanted:
        actions = scan_actions()
        report["actions"] = actions
        bad += len(actions["unpinned"]) + len(actions["other"])  # type: ignore[arg-type]
    if "studio" in wanted:
        report["studio_mcp_contract"] = scan_studio_contract()
        bad += len(report["studio_mcp_contract"])  # type: ignore[arg-type]
    report["findings_total"] = bad
    text = json.dumps(report, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    summary = {k: (len(v) if isinstance(v, list) else v) for k, v in report.items() if k != "actions"}
    if "actions" in report:
        summary["actions_unpinned"] = len(report["actions"]["unpinned"])  # type: ignore[index]
        summary["actions_other"] = len(report["actions"]["other"])  # type: ignore[index]
        summary["actions_inventory"] = len(report["actions"]["inventory"])  # type: ignore[index]
    print(json.dumps(summary, indent=2))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
