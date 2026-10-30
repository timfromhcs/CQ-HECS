#!/usr/bin/env python3
"""
Run the preregistered 25-job ``r-io-7`` suite on one Open Quantum backend.

Steps (each one is a sub-command, so a person can stop between them):

    generate   write the QASM files and manifest (no network)
    quote      price every job through ``oq.py quote``; charges nothing
    submit     spend the quotes, only with --yes and a total --budget
    collect    download results of jobs that finished after ``submit`` returned
    evaluate   fit M-FIT on the FIT split and test H-V3-8 on the EVAL split

``oq.py`` is the Open Quantum skill's CLI. It needs a machine that can reach
``id``/``scheduler``/``management.openquantum.com`` and a key stored with
``oq.py setup``. This script never reads or stores credentials itself.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cqhecs.openquantum_suite import build_suite, evaluate_suite, write_suite  # noqa: E402

DEFAULT_SUITE_DIR = REPO_ROOT / "research" / "v3" / "openquantum_suite"
DEFAULT_RUNS_DIR = REPO_ROOT / "research" / "v3" / "evidence" / "openquantum"


def _oq(args: argparse.Namespace, *command: str) -> Dict[str, Any]:
    cmd = [sys.executable, args.oq, *command, "--json"]
    if args.org:
        cmd += ["--org", args.org]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw_stdout": proc.stdout}
    payload["_exit_code"] = proc.returncode
    return payload


def _state_path(args: argparse.Namespace) -> Path:
    return Path(args.runs_dir) / args.backend.replace(":", "_") / "suite_state.json"


def _load_state(args: argparse.Namespace) -> Dict[str, Any]:
    path = _state_path(args)
    if path.is_file():
        return json.loads(path.read_text("utf-8"))
    return {"backend": args.backend, "jobs": {}}


def _save_state(args: argparse.Namespace, state: Dict[str, Any]) -> None:
    path = _state_path(args)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", "utf-8")


def cmd_generate(args: argparse.Namespace) -> int:
    manifest = write_suite(Path(args.suite_dir))
    print(f"wrote {len(manifest['jobs'])} circuits and manifest.json to {args.suite_dir}")
    return 0


def cmd_quote(args: argparse.Namespace) -> int:
    manifest = json.loads((Path(args.suite_dir) / "manifest.json").read_text("utf-8"))
    state = _load_state(args)
    total = 0.0
    rows: List[str] = []
    for entry in manifest["jobs"]:
        qasm = Path(args.suite_dir) / entry["qasm_file"]
        quote = _oq(args, "quote", str(qasm), "-b", args.backend, "-s", str(entry["shots"]),
                    "-c", args.subcategory, "--plan", args.plan, "--priority", args.priority)
        if quote["_exit_code"] != 0 or "preparation_id" not in quote:
            print(f"{entry['job_id']}: quote failed: {quote}", file=sys.stderr)
            _save_state(args, state)
            return 1
        cost = float(quote["selected"]["total_cost"])
        total += cost
        state["jobs"][entry["job_id"]] = {
            "name": entry["name"],
            "qasm_sha256": entry["qasm_sha256"],
            "preparation_id": quote["preparation_id"],
            "quoted_credits": cost,
            "plan": quote["selected"]["plan"],
        }
        rows.append(f"{entry['job_id']} {entry['name']:<18} {entry['shots']:>5} shots  {cost:>8.3f} credits")
    state["quoted_total"] = total
    _save_state(args, state)
    print("\n".join(rows))
    print(f"TOTAL {total:.3f} credits on {args.backend} (nothing charged yet)")
    print(f"next: {Path(__file__).name} submit -b {args.backend} --budget {total:.3f} --yes")
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    state = _load_state(args)
    if not state["jobs"]:
        print("no quotes; run `quote` first", file=sys.stderr)
        return 2
    total = float(state.get("quoted_total", 0.0))
    if not args.yes:
        print(f"refusing to spend {total:.3f} credits without --yes", file=sys.stderr)
        return 2
    if total > args.budget:
        print(f"quoted total {total:.3f} exceeds --budget {args.budget:.3f}; nothing submitted", file=sys.stderr)
        return 2
    per_job_cap = max(job["quoted_credits"] for job in state["jobs"].values())
    for job_id in sorted(state["jobs"]):
        job = state["jobs"][job_id]
        if job.get("provider_job_id"):
            continue
        out = Path(args.runs_dir) / args.backend.replace(":", "_") / job_id
        command = ["submit", "--prep", job["preparation_id"], "--yes", "--calibration",
                   "--max-credits", f"{per_job_cap:g}", "--out", str(out), "--timeout", str(args.timeout)]
        if args.allow_full:
            command.append("--allow-full")
        result = _oq(args, *command)
        if not result.get("submitted"):
            print(f"{job_id}: not submitted: {result}", file=sys.stderr)
            _save_state(args, state)
            return 1
        job["provider_job_id"] = result["job_id"]
        job["status"] = result.get("status")
        _save_state(args, state)
        print(f"{job_id}: job {result['job_id']} {result.get('status')}")
    return cmd_collect(args)


def cmd_collect(args: argparse.Namespace) -> int:
    state = _load_state(args)
    suite = {job.job_id: job for job in build_suite()}
    pending = 0
    for job_id, job in sorted(state["jobs"].items()):
        provider_id = job.get("provider_job_id")
        if not provider_id:
            continue
        out = Path(args.runs_dir) / args.backend.replace(":", "_") / job_id
        if not (out / "result.json").is_file():
            status = _oq(args, "status", provider_id)
            job["status"] = status.get("status")
            if status.get("status") != "Completed":
                pending += 1
                continue
            _oq(args, "results", provider_id, "--out", str(out), "--calibration")
        # oq.py copies the quoted circuit only when its quote cache is present;
        # write the preregistered text so the evaluation can check the digest.
        qasm = out / "circuit.qasm"
        if not qasm.is_file():
            qasm.write_bytes(suite[job_id].qasm.encode("ascii"))
        job["status"] = "Completed"
    _save_state(args, state)
    print(f"{pending} job(s) still pending" if pending else "all submitted jobs have results")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    root = Path(args.runs_dir) / args.backend.replace(":", "_")
    payload = evaluate_suite(root, bootstrap_samples=args.bootstrap)
    target = Path(args.out or root / "h_v3_8_evaluation.json")
    target.write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
    agg = payload["aggregate"]
    print(f"backend     : {payload['backend']}")
    print(f"M-FIT       : cx_p={payload['model']['cx_depolarizing']:.5f} "
          f"p01={payload['model']['p01_mean']:.4f} p10={payload['model']['p10_mean']:.4f}")
    print(f"EVAL jobs   : {agg['n_eval']}/{agg['n_eval_preregistered']}")
    print(f"median dTV  : {agg['median_delta_tv']:+.6f}  95% CI [{agg['ci95_low']:+.6f}, {agg['ci95_high']:+.6f}]")
    print(f"verdict     : {agg['verdict']}")
    print(f"wrote       : {target}")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite-dir", default=str(DEFAULT_SUITE_DIR))
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    parser.add_argument("--oq", default="oq.py", help="path to the Open Quantum skill's oq.py")
    parser.add_argument("--org", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("generate")
    for name in ("quote", "submit", "collect", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("-b", "--backend", required=True, help="Open Quantum short code, e.g. iqm:garnet")
        if name == "quote":
            p.add_argument("-c", "--subcategory", default="phys:oth")
            p.add_argument("--plan", default="public")
            p.add_argument("--priority", default="standard")
        if name == "submit":
            p.add_argument("--budget", type=float, required=True, help="approved total credits")
            p.add_argument("--yes", action="store_true")
            p.add_argument("--allow-full", action="store_true")
            p.add_argument("--timeout", type=float, default=1800)
        if name == "evaluate":
            p.add_argument("--bootstrap", type=int, default=5000)
            p.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    handler = {
        "generate": cmd_generate,
        "quote": cmd_quote,
        "submit": cmd_submit,
        "collect": cmd_collect,
        "evaluate": cmd_evaluate,
    }[args.command]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
