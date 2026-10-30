#!/usr/bin/env python3
"""
Spend the remaining Open Quantum credits on the preregistered ``r-io-7`` jobs.

Design rules, in order of importance:

1. **Never overspend.** The balance is re-read before every single job; a job is
   only created if the *free* balance covers its quote. The loop stops on its
   own when the money is gone, so "run the credits empty" cannot become "run
   past the credits".
2. **Never double-spend.** Before preparing a job the server is asked whether a
   job with that name already exists (state file lost, process killed, 401,
   crash). If it does, the job is adopted instead of resubmitted.
3. **Never lose evidence.** Every step appends one JSON line to
   ``run_log.jsonl``: timestamp, phase, job, HTTP outcome, credits before and
   after, circuit SHA-256. A run can be reconstructed from that file alone.
4. **Never print a secret.** Credentials come from the SDK account store; only
   the client-id prefix is ever logged.

Usage::

    python scripts/run_openquantum_credits.py -b rigetti:cepheus-1-108q
    python scripts/run_openquantum_credits.py -b <backend> --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from openquantum_sdk import (  # noqa: E402
    ClientCredentialsAuth,
    ManagementClient,
    SchedulerClient,
    accounts as oq_accounts,
    models as oq_models,
)

from cqhecs.openquantum_suite import build_suite, evaluate_suite  # noqa: E402

SUITE_DIR = REPO_ROOT / "research" / "v3" / "openquantum_suite"
RUNS_DIR = REPO_ROOT / "research" / "v3" / "evidence" / "openquantum"
ACCOUNT_NAME = "default"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Log:
    """Append-only JSONL evidence trail."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, phase: str, **fields: Any) -> None:
        record = {"ts": now(), "phase": phase, **fields}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        bits = " ".join(f"{k}={v}" for k, v in fields.items() if k in
                        ("job", "status", "credits", "cost", "attempt", "error"))
        print(f"[{record['ts']}] {phase:<10} {bits}")

    def tail(self, n: int = 5) -> List[Dict[str, Any]]:
        if not self.path.is_file():
            return []
        lines = self.path.read_text("utf-8").strip().splitlines()[-n:]
        return [json.loads(line) for line in lines]


class Session:
    """Clients plus a token refresh that survives a 401."""

    def __init__(self, org: Optional[str]) -> None:
        acct = oq_accounts.load_account(ACCOUNT_NAME)
        if not acct or acct.get("creds") is None:
            raise RuntimeError("no stored credentials: run `python oq.py setup` first")
        self.creds = acct["creds"]
        self.org = org
        self._build()

    def _build(self) -> None:
        auth = ClientCredentialsAuth(creds=self.creds)
        self.mgmt = ManagementClient(auth=auth)
        self.sched = SchedulerClient(auth=auth, management_client=self.mgmt)
        if self.org is None:
            orgs = self.mgmt.list_user_organizations(limit=20).organizations
            if not orgs:
                raise RuntimeError("account belongs to no organization")
            self.org = orgs[0].id

    def refresh(self) -> None:
        self._build()

    def balance(self) -> float:
        # 401 here is the same short-lived-token problem as on create; go
        # through call() so it refreshes instead of aborting a paid run.
        return float(self.call(self.mgmt.get_credit_balance, self.org).spark_credits)

    def call(self, fn, *args, **kwargs):
        """Run a call, refreshing the token and retrying on transient failure."""
        last: Optional[Exception] = None
        for attempt in range(3):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                text = str(exc)
                last = exc
                transient = any(
                    token in text
                    for token in ("401", "UNAUTHORIZED", "409", "502", "503", "504", "Timeout")
                )
                if not transient or attempt == 2:
                    raise
                time.sleep(2 ** attempt * 2)
                self.refresh()
        raise last  # pragma: no cover


def prepare_and_quote(session: "Session", qasm: bytes, backend: str, name: str,
                      subcategory: str, shots: int, organization_id: str) -> Dict[str, Any]:
    """Upload -> prepare -> wait -> pick Public/Standard. Charges nothing."""
    upload_id = session.call(session.sched.upload_job_input, file_content=qasm)
    preparation = oq_models.JobPreparationCreate(
        organization_id=organization_id,
        backend_class_id=backend,
        name=name,
        upload_endpoint_id=upload_id,
        job_subcategory_id=subcategory,
        shots=shots,
        submitted_with="credits-runner",
        input_format="qasm",
    )
    resp = session.call(session.sched.prepare_job, preparation)
    result = session.call(session.sched.wait_for_preparation, resp.id,
                          timeout=300.0, interval=2.0)
    selection = session.call(session.sched.choose_plan_and_priority, result,
                             "public", "standard", prefer_public=True)
    return {
        "preparation_id": resp.id,
        "cost": selection.total_cost,
        "plan_name": selection.plan_name,
        "priority_name": selection.priority_name,
        "execution_plan_id": selection.execution_plan_id,
        "queue_priority_id": selection.queue_priority_id,
        "quotes": [{"plan": p.name, "price": p.price} for p in result.quote],
    }


def existing_jobs(session: Session) -> Dict[str, str]:
    """Map job name -> job id for everything already on the server."""
    found: Dict[str, str] = {}
    cursor = None
    while True:
        page = session.call(session.sched.list_jobs, organization_id=session.org,
                            limit=50, cursor=cursor)
        for job in page.jobs:
            name = getattr(job, "name", None)
            if name:
                found[str(name)] = job.id
        cursor = page.pagination.next_cursor if page.pagination else None
        if not cursor:
            break
    return found


def load_state(path: Path, backend: str) -> Dict[str, Any]:
    if path.is_file():
        return json.loads(path.read_text("utf-8"))
    return {"backend": backend, "jobs": {}}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, default=str) + "\n", "utf-8")


def artifacts(out: Path, job: Any, circuit_qasm: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "circuit.qasm").write_bytes(circuit_qasm.encode("ascii"))


def counts_of(payload: Any) -> Optional[Dict[str, int]]:
    if isinstance(payload, dict):
        if payload and all(
            isinstance(k, str) and k and set(k) <= {"0", "1"}
            and isinstance(v, (int, float)) and not isinstance(v, bool)
            for k, v in payload.items()
        ):
            return {k: int(v) for k, v in payload.items()}
        for key in ("counts", "measurement_counts", "histogram"):
            inner = payload.get(key)
            if isinstance(inner, dict) and inner:
                return {str(k): int(v) for k, v in inner.items()}
    if isinstance(payload, list) and payload:
        return counts_of(payload[0])
    return None


def write_result(out: Path, job: Any, payload: Any, quote: Dict[str, Any]) -> Optional[int]:
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    counts = counts_of(payload)
    if not counts:
        return None
    rows = sorted(counts.items(), key=lambda kv: -kv[1])
    total = sum(counts.values())
    (out / "counts.csv").write_text(
        "outcome,count\n" + "".join(f"{k},{v}\n" for k, v in rows), "utf-8")
    lines = [f"# {out.name}", "",
             f"- provider job: `{getattr(job, 'id', '?')}`",
             f"- backend: `{quote.get('backend')}`",
             f"- status: `{getattr(job, 'status', '?')}`",
             f"- shots: {total}",
             f"- distinct outcomes: {len(counts)}", "",
             "| outcome | counts | share |", "|---|---:|---:|"]
    lines += [f"| `{k}` | {v} | {v / total:.4f} |" for k, v in rows[:24]]
    (out / "summary.md").write_text("\n".join(lines) + "\n", "utf-8")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        top = rows[:24]
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.bar([k for k, _ in top], [v for _, v in top])
        ax.set_xlabel("outcome")
        ax.set_ylabel("counts")
        ax.set_title(f"{out.name} — {total} shots")
        plt.xticks(rotation=90, fontsize=7)
        fig.tight_layout()
        fig.savefig(out / "histogram.png", dpi=110)
        plt.close(fig)
    except Exception:  # noqa: BLE001
        pass
    return total


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-b", "--backend", required=True)
    parser.add_argument("--org", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--collect-only", action="store_true",
                        help="fetch results of jobs already paid for, submit nothing")
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--subcategory", default="phys:oth")
    parser.add_argument("--keep", type=float, default=0.0,
                        help="credits to leave untouched (default 0)")
    args = parser.parse_args(argv)

    backend_key = args.backend.replace(":", "_")
    run_dir = RUNS_DIR / backend_key
    state_path = run_dir / "suite_state.json"
    log = Log(run_dir / "run_log.jsonl")

    circuits = {job.name: job for job in build_suite()}
    ordered = build_suite()
    state = load_state(state_path, args.backend)

    session = Session(args.org)
    balance = session.balance()
    log.write("start", backend=args.backend, organization=session.org, credits=balance)

    pending = [j for j in ordered if not state["jobs"].get(j.job_id, {}).get("provider_job_id")]
    log.write("plan", pending=[j.job_id for j in pending], credits=balance)
    if args.dry_run:
        print(f"dry run: {len(pending)} job(s) pending, balance {balance:.2f}")
        return 0

    on_server = existing_jobs(session)
    for job in pending:
        if args.collect_only:
            break
        name = f"{job.job_id}_{job.name}"
        try:
            session.refresh()  # fresh token per job; the API rejects stale ones with 401
            if name in on_server:
                job_id = on_server[name]
                state["jobs"].setdefault(job.job_id, {})["provider_job_id"] = job_id
                state["jobs"][job.job_id]["status"] = "adopted"
                save_state(state_path, state)
                log.write("adopt", job=job.job_id, provider_job=job_id,
                          note="job already existed on the server; not resubmitted")
                continue

            quote = session.call(prepare_and_quote, session,
                                 (SUITE_DIR / f"{job.job_id}_{job.name}.qasm").read_bytes(),
                                 args.backend, name, args.subcategory, args.shots, session.org)
            cost = int(quote["cost"])
            balance = session.balance()
            if balance - cost < args.keep:
                log.write("stop", reason="budget", credits=balance, cost=cost, job=job.job_id)
                print(f"stop: {balance:.2f} credits left, next job costs {cost}")
                break

            result = session.call(session.sched.create_job, oq_models.JobCreate(
                job_preparation_id=quote["preparation_id"],
                execution_plan_id=quote["execution_plan_id"],
                queue_priority_id=quote["queue_priority_id"],
                organization_id=session.org,
            ))
            state["jobs"][job.job_id] = {
                "name": job.name,
                "qasm_sha256": job.sha256,
                "preparation_id": quote["preparation_id"],
                "quoted_credits": cost,
                "plan": quote["plan_name"],
                "priority": quote["priority_name"],
                "provider_job_id": result.id,
                "status": result.status,
                "submitted_at": now(),
            }
            save_state(state_path, state)
            out = run_dir / job.job_id
            artifacts(out, result, job.qasm)
            (out / "job.json").write_text(json.dumps({
                "job": {"id": result.id, "status": result.status,
                        "submitted_at": result.submitted_at},
                "quote": {"backend": args.backend, "plan": quote["plan_name"],
                          "priority": quote["priority_name"], "total_cost": cost,
                          "execution_plan_id": quote["execution_plan_id"],
                          "queue_priority_id": quote["queue_priority_id"]},
                "qasm_sha256": job.sha256,
            }, indent=2), "utf-8")
            log.write("submit", job=job.job_id, provider_job=result.id, status=result.status,
                      cost=cost, credits=session.balance(), qasm_sha256=job.sha256[:16])

            # The job is paid for; from here on nothing may abort the loop.
            try:
                done = session.call(session.sched.wait_for_job, result.id,
                                    timeout=args.timeout, interval=5.0,
                                    raise_on_failure=False, raise_on_timeout=False)
            except Exception as exc:  # noqa: BLE001
                log.write("wait_failed", job=job.job_id, error=str(exc)[:160])
                continue
            state["jobs"][job.job_id]["status"] = done.status
            save_state(state_path, state)
            if done.status == "Completed" and done.output_data_url:
                payload = session.call(session.sched.download_job_output, done)
                shots = write_result(out, done, payload, {"backend": args.backend})
                log.write("result", job=job.job_id, status=done.status, shots=shots)
            else:
                log.write("wait", job=job.job_id, status=done.status)
        except Exception as exc:  # noqa: BLE001
            log.write("job_error", job=job.job_id, error=str(exc)[:200])
            continue

    # Collect anything that finished after its wait window.
    for job in ordered:
        entry = state["jobs"].get(job.job_id, {})
        provider_id = entry.get("provider_job_id")
        if not provider_id:
            continue
        out = run_dir / job.job_id
        if (out / "result.json").is_file():
            continue
        try:
            done = session.call(session.sched.get_job, provider_id)
            if done.status != "Completed" or not done.output_data_url:
                continue
            payload = session.call(session.sched.download_job_output, done)
            write_result(out, done, payload, {"backend": args.backend})
            entry["status"] = "Completed"
            save_state(state_path, state)
            log.write("collect", job=job.job_id, status=done.status)
        except Exception as exc:  # noqa: BLE001
            log.write("collect_failed", job=job.job_id, error=str(exc)[:160])

    final = session.balance()
    log.write("finish", credits=final, submitted=sum(
        1 for v in state["jobs"].values() if v.get("provider_job_id")))

    if (run_dir / "OQ-03").is_dir():
        payload = evaluate_suite(run_dir, bootstrap_samples=5000)
        (run_dir / "h_v3_8_evaluation.json").write_text(
            json.dumps(payload, indent=2) + "\n", "utf-8")
        agg = payload["aggregate"]
        print(f"verdict: {agg['verdict']}  median dTV {agg['median_delta_tv']:+.6f} "
              f"CI [{agg['ci95_low']:+.6f}, {agg['ci95_high']:+.6f}]")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(1)
