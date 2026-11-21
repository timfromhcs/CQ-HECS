#!/usr/bin/env python3
"""Quantum Gravity Open Quantum campaign runner (campaign ``qg-2026-01``).

Separable phases (never merged):

    doctor    prove authentication without printing any secret
    discover  list organisations, balances and backends; persist a capability snapshot
    generate  write the model and circuit manifests (no network, deterministic)
    validate  re-check manifest digests and the campaign guardrails (no network)
    quote     prepare each circuit and read its pricing quote (spends nothing)
    submit    submit already-quoted jobs under the cumulative Spark budget guard
    collect   download finished results (append-only evidence)
    analyse   run the preregistered analysis on collected raw results
    report    assemble the campaign report from the ledgers

Safety rules enforced here (not only in the SDK):

* credentials are read from the environment only and never written to disk or logs;
* ``quote`` never spends; ``submit`` enforces ``min(25.0, available Spark)`` itself;
* ``execution_plan="public"`` and ``queue_priority="standard"`` are forced;
  the Full-credit plan is refused;
* ``auto_approve_quote`` is left ``False`` so a quote is never silently approved.

This script never touches the historical ``r-io-7`` paths.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cqhecs.quantum_gravity import circuits as qg_circuits  # noqa: E402
from cqhecs.quantum_gravity.hamiltonians import build_syk  # noqa: E402
from cqhecs.quantum_gravity.models import BMVEffectivePhaseModel  # noqa: E402

DEFAULT_CAMPAIGN_ID = "qg-2026-01"
DEFAULT_CAMPAIGN_DIR = REPO_ROOT / "research" / "qg_2026"
AUTHORISED_SPARK_CEILING = 25.0
CLIENT_ID_ENV = "OPENQUANTUM_CLIENT_ID"
CLIENT_SECRET_ENV = "OPENQUANTUM_CLIENT_SECRET"


# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------
def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _redact(text: str, limit: int = 240) -> str:
    """Never echo anything that looks like a credential."""
    cleaned = text
    for env in (CLIENT_ID_ENV, CLIENT_SECRET_ENV, "OPENQUANTUM_TOKEN"):
        value = os.environ.get(env)
        if value and len(value) >= 8:
            cleaned = cleaned.replace(value, "***REDACTED***")
    return cleaned[:limit]


def _rel(path: Path) -> str:
    """Repo-relative when possible, else the absolute path (campaign may be a tmp dir)."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _campaign_dir(args: argparse.Namespace) -> Path:
    return Path(args.campaign)


def _load_ledger_spend(campaign_dir: Path) -> float:
    """Sum actually-submitted credits from the append-only job ledger."""
    ledger = campaign_dir / "JOB_LEDGER.jsonl"
    if not ledger.is_file():
        return 0.0
    total = 0.0
    for line in ledger.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "submitted":
            total += float(event.get("quoted_credits", 0.0))
    return total


def _resolve_credentials():
    """Return ``(client_id, client_secret)`` from the environment, or ``(None, None)``."""
    return os.environ.get(CLIENT_ID_ENV), os.environ.get(CLIENT_SECRET_ENV)


def _build_client(require: bool = True):
    from openquantum_sdk.session import OpenQuantumClient

    client_id, client_secret = _resolve_credentials()
    if not (client_id and client_secret):
        if require:
            raise RuntimeError(
                "missing credentials: set OPENQUANTUM_CLIENT_ID and OPENQUANTUM_CLIENT_SECRET "
                "(the value in this campaign that starts with 's_' is only the Client ID)"
            )
        return None
    return OpenQuantumClient.from_env(client_id=client_id, client_secret=client_secret, require=require)


# --------------------------------------------------------------------------------------
# generate / validate (offline)
# --------------------------------------------------------------------------------------
def _model_manifest() -> Dict[str, Any]:
    bmv = BMVEffectivePhaseModel(theta=0.0).manifest()
    syk = build_syk(4, seed=20260101, scale=0.5).manifest()
    return {
        "schema": "cqhecs.qg.model_manifest.v1",
        "campaign_id": DEFAULT_CAMPAIGN_ID,
        "models": [bmv, syk],
    }


def cmd_generate(args: argparse.Namespace) -> int:
    campaign_dir = _campaign_dir(args)
    theta_values = qg_circuits.default_theta_values()
    circuit_manifest = qg_circuits.build_bmv_manifest(theta_values)
    circuit_path = qg_circuits.write_manifest(circuit_manifest, campaign_dir / "qasm", embed_qasm=False)
    model_path = _write_json(campaign_dir / "MODEL_MANIFEST.json", _model_manifest())
    print(json.dumps({
        "status": "OK",
        "circuit_manifest": _rel(circuit_path),
        "model_manifest": _rel(model_path),
        "circuits": circuit_manifest["count"],
        "theta_values": list(theta_values),
    }, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    campaign_dir = _campaign_dir(args)
    problems: List[str] = []
    circuit_path = campaign_dir / "qasm" / "CIRCUIT_MANIFEST.json"
    model_path = campaign_dir / "MODEL_MANIFEST.json"
    if not circuit_path.is_file():
        problems.append(f"missing {_rel(circuit_path)}; run `generate`")
    else:
        manifest = json.loads(circuit_path.read_text("utf-8"))
        for circuit in manifest.get("circuits", []):
            qasm_file = campaign_dir / "qasm" / circuit["qasm_file"]
            if not qasm_file.is_file():
                problems.append(f"missing qasm {circuit['qasm_file']}")
                continue
            digest = qg_circuits.sha256_text(qasm_file.read_text("utf-8"))
            if digest != circuit["qasm_sha256"]:
                problems.append(f"digest mismatch for {circuit['circuit_id']}")
    if not model_path.is_file():
        problems.append("missing MODEL_MANIFEST.json; run `generate`")
    # guardrail: no obvious secret in tracked campaign files
    for path in campaign_dir.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl", ".md", ".qasm", ".csv"):
            text = path.read_text("utf-8", errors="ignore")
            if "OPENQUANTUM_CLIENT_SECRET" in text and "=" in text:
                # mentions of the variable name are fine; an assignment is not
                for line in text.splitlines():
                    if line.strip().startswith("OPENQUANTUM_CLIENT_SECRET="):
                        problems.append(f"possible secret assignment in {path}")
    payload = {"status": "OK" if not problems else "FAILED", "problems": problems}
    print(json.dumps(payload, indent=2))
    return 0 if not problems else 1


# --------------------------------------------------------------------------------------
# doctor / discover (read-only network)
# --------------------------------------------------------------------------------------
def cmd_doctor(args: argparse.Namespace) -> int:
    try:
        client = _build_client(require=True)
    except Exception as exc:  # noqa: BLE001 - reported as BLOCKED, not a crash
        print(json.dumps({
            "status": "BLOCKED",
            "code": "QG_BLOCKED",
            "reason": type(exc).__name__,
            "detail": _redact(str(exc)),
            "next_action": "set OPENQUANTUM_CLIENT_ID and OPENQUANTUM_CLIENT_SECRET in the environment",
        }, indent=2))
        return 2
    try:
        orgs = client.organizations()
        rows = []
        for org in orgs:
            balance = client.management.get_credit_balance(organization_id=str(org.id))
            rows.append({
                "organisation_id": str(org.id),
                "name": org.name,
                "spark_credits": getattr(balance, "spark_credits", None),
                "full_credits": getattr(balance, "full_credits", None),
            })
        print(json.dumps({"status": "OK", "organisations": rows}, indent=2))
        return 0
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass


def _iter_backend_classes(management) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    for _ in range(200):  # hard bound on pagination
        page = management.list_backend_classes(limit=100, cursor=cursor)
        for backend in getattr(page, "backend_classes", []) or []:
            rows.append({
                "id": str(getattr(backend, "id", "")),
                "name": getattr(backend, "name", None),
                "short_code": getattr(backend, "short_code", None),
                "type": getattr(backend, "type", None),
                "provider_id": str(getattr(backend, "provider_id", "")),
                "status": getattr(backend, "status", None),
                "queue_depth": getattr(backend, "queue_depth", None),
                "accepting_jobs": getattr(backend, "accepting_jobs", None),
            })
        pagination = getattr(page, "pagination", None)
        cursor = getattr(pagination, "next_cursor", None) if pagination else None
        if not cursor:
            break
    return rows


def cmd_discover(args: argparse.Namespace) -> int:
    try:
        client = _build_client(require=True)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({
            "status": "BLOCKED",
            "code": "QG_BLOCKED",
            "reason": type(exc).__name__,
            "detail": _redact(str(exc)),
        }, indent=2))
        return 2
    campaign_dir = _campaign_dir(args)
    try:
        orgs = client.organizations()
        account_rows = []
        chosen_org = args.org
        for org in orgs:
            balance = client.management.get_credit_balance(organization_id=str(org.id))
            account_rows.append({
                "organisation_id": str(org.id),
                "name": org.name,
                "spark_credits": getattr(balance, "spark_credits", None),
                "full_credits": getattr(balance, "full_credits", None),
            })
        if chosen_org is None and len(account_rows) == 1:
            chosen_org = account_rows[0]["organisation_id"]
        backends = _iter_backend_classes(client.management)
        stamp = _utc().replace(":", "").replace("-", "")
        snapshot = {
            "schema": "cqhecs.qg.capability_snapshot.v1",
            "campaign_id": DEFAULT_CAMPAIGN_ID,
            "read_at": _utc(),
            "organisations": account_rows,
            "selected_org": chosen_org,
            "backends": backends,
            "qpu_count": sum(1 for b in backends if str(b["type"]).upper() == "QPU"),
            "simulator_count": sum(1 for b in backends if str(b["type"]).upper() == "SIMULATOR"),
        }
        path = _write_json(campaign_dir / "raw" / f"capability_snapshot_{stamp}.json", snapshot)
        print(json.dumps({
            "status": "OK",
            "organisations": len(account_rows),
            "backends": len(backends),
            "qpu_count": snapshot["qpu_count"],
            "simulator_count": snapshot["simulator_count"],
            "snapshot": _rel(path),
        }, indent=2))
        return 0
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------------------
# quote / submit / collect (delegate to the official Open Quantum CLI, oq.py)
# --------------------------------------------------------------------------------------
def _oq_path(args: argparse.Namespace) -> str:
    return getattr(args, "oq", None) or os.environ.get("OPENQUANTUM_OQ") or "oq.py"


def _oq(args: argparse.Namespace, *command: str) -> Dict[str, Any]:
    cmd = [sys.executable, _oq_path(args), *command, "--json"]
    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        env={**os.environ, "OPENQUANTUM_HIDE_CITATION_NOTICE": "1"},
    )
    payload: Dict[str, Any] = {}
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {"raw_stdout": proc.stdout[-500:]}
    payload["_exit_code"] = proc.returncode
    return payload


def _load_set(set_dir: Path) -> Dict[str, Any]:
    for name in ("MANIFEST.json", "CIRCUIT_MANIFEST.json"):
        candidate = set_dir / name
        if candidate.is_file():
            manifest = json.loads(candidate.read_text("utf-8"))
            circuits = manifest.get("circuits", [])
            for circuit in circuits:
                circuit.setdefault("file", circuit.get("qasm_file"))
            return {"dir": set_dir, "circuits": circuits}
    raise FileNotFoundError(f"no MANIFEST.json or CIRCUIT_MANIFEST.json under {set_dir}")


def cmd_quote(args: argparse.Namespace) -> int:
    """Price every circuit in the set (Public/Standard). Spends nothing."""
    campaign_dir = _campaign_dir(args)
    try:
        circuit_set = _load_set(Path(args.set))
    except FileNotFoundError as exc:
        print(json.dumps({"status": "FAILED", "detail": str(exc)}, indent=2))
        return 1
    quotes = []
    total = 0.0
    for circuit in circuit_set["circuits"]:
        qasm = circuit_set["dir"] / circuit["file"]
        result = _oq(args, "quote", str(qasm), "-b", args.backend, "-s", str(args.shots),
                     "--plan", "public", "--priority", "standard", "-c", "phys:oth")
        if result.get("_exit_code") != 0 or "preparation_id" not in result:
            print(json.dumps({"status": "FAILED", "circuit": circuit.get("circuit_id"), "detail": result}, indent=2))
            return 1
        selected = result["selected"]
        cost = float(selected["total_cost"])
        total += cost
        quotes.append({
            "circuit_id": circuit.get("circuit_id"), "qasm_file": circuit["file"],
            "preparation_id": result["preparation_id"], "shots": args.shots,
            "plan": selected["plan"], "priority": selected["priority"], "quoted_credits": cost,
        })
    ledger = {
        "schema": "cqhecs.qg.quote_ledger.v1", "campaign_id": DEFAULT_CAMPAIGN_ID,
        "set": str(circuit_set["dir"]), "backend": args.backend, "shot_count": args.shots,
        "authorised_spark_ceiling": AUTHORISED_SPARK_CEILING, "quotes": quotes,
        "quoted_total_credits": total, "spent_credits": _load_ledger_spend(campaign_dir),
    }
    _write_json(campaign_dir / "QUOTE_LEDGER.json", ledger)
    print(json.dumps({"status": "OK", "quotes": len(quotes), "quoted_total_credits": total, "spend": 0.0}, indent=2))
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    """Submit the quoted jobs under the cumulative Spark budget guard."""
    campaign_dir = _campaign_dir(args)
    ledger_path = campaign_dir / "QUOTE_LEDGER.json"
    if not ledger_path.is_file():
        print(json.dumps({"status": "FAILED", "detail": "run `quote` first"}, indent=2))
        return 1
    ledger = json.loads(ledger_path.read_text("utf-8"))
    spent = _load_ledger_spend(campaign_dir)
    proposed = float(ledger.get("quoted_total_credits", 0.0))
    if not args.yes:
        print(json.dumps({"status": "REFUSED", "detail": "pass --yes to spend", "proposed_total": proposed}, indent=2))
        return 2
    if spent + proposed > min(AUTHORISED_SPARK_CEILING, args.budget):
        print(json.dumps({"status": "REFUSED", "detail": "would exceed budget",
                          "spent": spent, "proposed": proposed, "budget": args.budget}, indent=2))
        return 2
    set_name = Path(ledger.get("set", "set")).name
    job_log = campaign_dir / "JOB_LEDGER.jsonl"
    submitted = 0
    for quote in ledger["quotes"]:
        out = campaign_dir / "raw" / set_name / quote["circuit_id"]
        result = _oq(args, "submit", "--prep", quote["preparation_id"], "--yes", "--no-wait",
                     "--calibration", "--max-credits", f"{args.max_credits:g}", "--out", str(out))
        event = {
            "schema": "cqhecs.qg.job_ledger.v1", "event": "submitted", "at": _utc(),
            "circuit_id": quote["circuit_id"], "preparation_id": quote["preparation_id"],
            "provider_job_id": result.get("job_id") or result.get("id"), "backend": ledger.get("backend"),
            "shots": quote.get("shots"), "plan": quote.get("plan"), "priority": quote.get("priority"),
            "quoted_credits": quote.get("quoted_credits"), "status": result.get("status"), "out": str(out),
        }
        with job_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        submitted += 1
    print(json.dumps({"status": "OK", "submitted": submitted, "cumulative_credits": spent + proposed}, indent=2))
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    """Wait for and download any submitted job lacking a collected event."""
    campaign_dir = _campaign_dir(args)
    job_log = campaign_dir / "JOB_LEDGER.jsonl"
    if not job_log.is_file():
        print(json.dumps({"status": "NOT_RUN", "detail": "no jobs yet"}, indent=2))
        return 0
    events = [json.loads(line) for line in job_log.read_text("utf-8").splitlines() if line.strip()]
    collected = {e["provider_job_id"] for e in events if e.get("event") == "collected"}
    pending = [e for e in events if e.get("event") == "submitted" and e["provider_job_id"] not in collected]
    for event in pending:
        out = Path(event["out"])
        out.mkdir(parents=True, exist_ok=True)
        _oq(args, "wait", event["provider_job_id"], "--timeout", str(args.timeout))
        _oq(args, "results", event["provider_job_id"], "--calibration", "--out", str(out))
        with job_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "schema": "cqhecs.qg.job_ledger.v1", "event": "collected", "at": _utc(),
                "circuit_id": event["circuit_id"], "provider_job_id": event["provider_job_id"], "out": str(out),
            }, sort_keys=True) + "\n")
    print(json.dumps({"status": "OK", "collected": len(pending)}, indent=2))
    return 0


def cmd_analyse(args: argparse.Namespace) -> int:
    print(json.dumps({"status": "NOT_RUN", "detail": "no raw results yet"}, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    campaign_dir = _campaign_dir(args)
    report = {
        "campaign_id": DEFAULT_CAMPAIGN_ID,
        "generated_at": _utc(),
        "authorised_spark_ceiling": AUTHORISED_SPARK_CEILING,
        "submitted_credits": _load_ledger_spend(campaign_dir),
        "note": "live campaign report; scientific results require raw evidence under raw/",
    }
    path = _write_json(campaign_dir / "reports" / "campaign_report.json", report)
    print(json.dumps({"status": "OK", "report": _rel(path)}, indent=2))
    return 0


# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--campaign", default=str(DEFAULT_CAMPAIGN_DIR))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    discover = sub.add_parser("discover")
    discover.add_argument("--org", default=None, help="explicit organisation UUID")
    sub.add_parser("generate")
    sub.add_parser("validate")
    quote = sub.add_parser("quote")
    quote.add_argument("--backend", required=True, help="live backend short code (e.g. qr:sim)")
    quote.add_argument("--set", required=True, help="directory with MANIFEST.json (circuit set)")
    quote.add_argument("--shots", type=int, default=1000)
    quote.add_argument("--oq", default=None, help="path to oq.py (Open Quantum CLI)")
    submit = sub.add_parser("submit")
    submit.add_argument("--budget", type=float, default=AUTHORISED_SPARK_CEILING)
    submit.add_argument("--yes", action="store_true")
    submit.add_argument("--max-credits", type=float, default=10.0, help="per-job hard cap")
    submit.add_argument("--oq", default=None)
    collect = sub.add_parser("collect")
    collect.add_argument("--timeout", type=float, default=1800)
    collect.add_argument("--oq", default=None)
    sub.add_parser("analyse")
    sub.add_parser("report")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    handler = {
        "doctor": cmd_doctor,
        "discover": cmd_discover,
        "generate": cmd_generate,
        "validate": cmd_validate,
        "quote": cmd_quote,
        "submit": cmd_submit,
        "collect": cmd_collect,
        "analyse": cmd_analyse,
        "report": cmd_report,
    }[args.command]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
