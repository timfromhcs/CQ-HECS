"""Build the public, secret-free baseline bundle from a raw capture and place it where the UI and repo consume it.

    python scripts/sha_forge_publish_results.py --raw <baseline_*.jsonl> --results-dir <dir outside both repos> \
        [--web-out web/public/forge/baseline_results.json] [--interval 30]

The raw capture stays in --results-dir. Only the safety-checked bundle is written to the repo path.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from cqhecs.hardware import results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", required=True)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--web-out", default="web/public/forge/baseline_results.json")
    ap.add_argument("--interval", type=float, default=30.0)
    args = ap.parse_args()

    raw = Path(args.raw)
    out_dir = Path(args.results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if raw.parent.resolve() != out_dir.resolve():
        shutil.copy2(raw, out_dir / raw.name)
    bundle = results.build_public_baseline(raw, interval_s=args.interval)
    text = json.dumps(bundle, indent=1, sort_keys=True)
    (out_dir / "baseline_public.json").write_text(text, encoding="utf-8")
    web_out = Path(args.web_out)
    web_out.parent.mkdir(parents=True, exist_ok=True)
    web_out.write_text(text, encoding="utf-8")
    s = bundle["summary"]
    print(f"verdict={bundle['verdict']} samples={s['samples']} gaps={s['gaps']} -> {web_out}")
    return 0 if bundle["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
