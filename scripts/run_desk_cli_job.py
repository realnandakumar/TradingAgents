#!/usr/bin/env python3
"""Run a dashboard desk CLI job from ~/.tradingagents/desk_cli/jobs/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tradingagents.desk_cli.runner import (  # noqa: E402
    job_path_for_id,
    progress_path_for_job,
    run_desk_cli_job,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a TradingAgents desk CLI job")
    parser.add_argument("--job-id", help="Job id under ~/.tradingagents/desk_cli/jobs/")
    parser.add_argument("--job-file", help="Explicit path to job JSON file")
    args = parser.parse_args()

    if args.job_file:
        job_path = Path(args.job_file)
    elif args.job_id:
        job_path = job_path_for_id(args.job_id)
    else:
        parser.error("Provide --job-id or --job-file")

    if not job_path.exists():
        print(f"Job file not found: {job_path}", file=sys.stderr)
        return 1

    job = json.loads(job_path.read_text(encoding="utf-8"))
    job_id = job.get("job_id") or args.job_id or job_path.stem
    job["job_id"] = job_id
    progress_path = progress_path_for_job(job_id)

    try:
        result = run_desk_cli_job(job, progress_path, repo_root=_REPO_ROOT)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "completed" else 1
    except Exception as exc:  # noqa: BLE001
        print(f"Job failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
