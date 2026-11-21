"""Conversions running in the background (POST /api/v1/jobs), polled by the UI for their progress.

Kept only in this process's memory (task rules: no storage); a job is dropped JOB_TTL_S after its last
change. One worker thread per job; at most MAX_RUNNING at once, so polling never starts more model calls."""

import logging
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from autoformularz import progress
from autoformularz.llm import LLMError
from autoformularz.upload import UploadError

log = logging.getLogger("autoformularz.jobs")

JOB_TTL_S = 15 * 60
MAX_RUNNING = 4


class Cancelled(Exception):
    """Raised in the worker at the next progress report after DELETE: a streamed model answer stops there."""


@dataclass
class Job:
    id: str
    status: str = "running"  # running | done | error | cancelled
    steps: list[dict] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    cancelled: bool = False
    updated: float = field(default_factory=time.monotonic)

    def report(self, kind: str, text: str) -> None:
        if self.cancelled:
            raise Cancelled
        if kind == "tick":
            return
        with _lock:
            self.steps.append({"kind": kind, "text": text})
            self.updated = time.monotonic()

    def view(self) -> dict[str, Any]:
        with _lock:
            out: dict[str, Any] = {"id": self.id, "status": self.status, "steps": list(self.steps)}
            if self.result is not None:
                out["result"] = self.result
            if self.error is not None:
                out["error"] = self.error
            return out


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def _drop_old() -> None:
    now = time.monotonic()
    for key in [k for k, j in _jobs.items() if now - j.updated > JOB_TTL_S]:
        del _jobs[key]


def _finish(job: Job, status: str, result: dict | None = None, error: dict | None = None) -> None:
    with _lock:
        job.status, job.result, job.error = status, result, error
        job.updated = time.monotonic()


def _run(job: Job, work: Callable[[], dict]) -> None:
    try:
        with progress.reporting(job.report):
            result = work()
    except Cancelled:
        _finish(job, "cancelled")
    except (UploadError, LLMError) as e:
        _finish(job, "error", error={"code": e.code, "message": e.message})
    except Exception:
        log.exception("Job %s failed", job.id)
        _finish(job, "error", error={"code": "INTERNAL", "message": "Nie udało się przetworzyć pliku."})
    else:
        _finish(job, "done", result=result)


def start(work: Callable[[], dict]) -> Job | None:
    """Run `work` (returns the response body) in a new thread. None when MAX_RUNNING jobs are running."""
    with _lock:
        _drop_old()
        if sum(j.status == "running" for j in _jobs.values()) >= MAX_RUNNING:
            return None
        job = Job(id=secrets.token_urlsafe(16))
        _jobs[job.id] = job
    threading.Thread(target=_run, args=(job, work), daemon=True, name=f"job-{job.id[:6]}").start()
    return job


def get(job_id: str) -> Job | None:
    with _lock:
        _drop_old()
        return _jobs.get(job_id)


def cancel(job_id: str) -> bool:
    job = get(job_id)
    if job is None:
        return False
    job.cancelled = True
    return True
