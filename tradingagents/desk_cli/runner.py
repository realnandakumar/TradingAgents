"""Run dashboard desk CLI jobs (python -m cli.main ...)."""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_tradingagents_home() -> Path:
    return Path(os.environ.get("TRADINGAGENTS_HOME", os.path.expanduser("~/.tradingagents")))


def jobs_dir() -> Path:
    return get_tradingagents_home() / "desk_cli" / "jobs"


def progress_path_for_job(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.progress.json"


def job_path_for_id(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.json"


class DeskCliProgressWriter:
    """Write CLI stdout/stderr tail to a JSON file for dashboard polling."""

    MAX_LINES = 200

    def __init__(self, path: Path, job: dict):
        self.path = path
        self.job_id = job["job_id"]
        self.desk_id = job.get("desk_id", "")
        self.action_id = job.get("action_id", "")
        self.command = job.get("command", "")
        self.status = "running"
        self.percent = 5
        self.lines: List[str] = []
        self.error: Optional[str] = None
        self.exit_code: Optional[int] = None
        self.started_at = datetime.datetime.now().isoformat()
        self.updated_at = self.started_at
        self.completed_at: Optional[str] = None
        self._line_count = 0

    def append_line(self, line: str, stream: str = "out") -> None:
        prefix = "[err] " if stream == "err" else ""
        self.lines.append(f"{prefix}{line.rstrip()}")
        if len(self.lines) > self.MAX_LINES:
            self.lines = self.lines[-self.MAX_LINES :]
        self._line_count += 1
        # Indeterminate progress while running
        self.percent = min(90, 5 + self._line_count // 2)
        self._flush()

    def finish(self, exit_code: int, error: Optional[str] = None) -> None:
        self.exit_code = exit_code
        self.completed_at = datetime.datetime.now().isoformat()
        if exit_code == 0:
            self.status = "completed"
            self.percent = 100
        else:
            self.status = "failed"
            self.percent = 100
            self.error = error or f"Command exited with code {exit_code}"
        self._flush()

    def _flush(self) -> None:
        self.updated_at = datetime.datetime.now().isoformat()
        payload: Dict[str, Any] = {
            "jobId": self.job_id,
            "deskId": self.desk_id,
            "actionId": self.action_id,
            "command": self.command,
            "status": self.status,
            "percent": self.percent,
            "lines": self.lines,
            "error": self.error,
            "startedAt": self.started_at,
            "updatedAt": self.updated_at,
            "completedAt": self.completed_at,
            "exitCode": self.exit_code,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _update_job_file(job_path: Path, **fields: Any) -> None:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job.update(fields)
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")


def _stream_reader(pipe, writer: DeskCliProgressWriter, stream: str) -> None:
    try:
        for raw in iter(pipe.readline, ""):
            if not raw:
                break
            writer.append_line(raw, stream=stream)
    finally:
        pipe.close()


def run_desk_cli_job(job: dict, progress_path: Path, repo_root: Optional[Path] = None) -> dict:
    """Execute cli.main or a repo script and stream output to progress_path."""
    job_id = job["job_id"]
    script_rel = job.get("script")
    cli_args: List[str] = job.get("cli_args") or []
    root = repo_root or _repo_root()
    job_path = jobs_dir() / f"{job_id}.json"

    writer = DeskCliProgressWriter(progress_path, job)
    writer._flush()

    _update_job_file(job_path, status="running", started_at=writer.started_at)

    if script_rel:
        script_path = root / script_rel
        cmd = [sys.executable, str(script_path)]
    else:
        cmd = [sys.executable, "-m", "cli.main", *cli_args]
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:  # noqa: BLE001
        writer.finish(1, str(exc))
        _update_job_file(
            job_path,
            status="failed",
            completed_at=writer.completed_at,
            exit_code=1,
            error=str(exc),
        )
        return {"job_id": job_id, "status": "failed", "error": str(exc)}

    threads = []
    if proc.stdout:
        threads.append(
            threading.Thread(
                target=_stream_reader,
                args=(proc.stdout, writer, "out"),
                daemon=True,
            )
        )
    if proc.stderr:
        threads.append(
            threading.Thread(
                target=_stream_reader,
                args=(proc.stderr, writer, "err"),
                daemon=True,
            )
        )
    for t in threads:
        t.start()

    exit_code = proc.wait()
    for t in threads:
        t.join(timeout=5)

    writer.finish(exit_code)
    _update_job_file(
        job_path,
        status=writer.status,
        completed_at=writer.completed_at,
        exit_code=exit_code,
        error=writer.error,
    )
    return {
        "job_id": job_id,
        "status": writer.status,
        "exit_code": exit_code,
        "error": writer.error,
    }
