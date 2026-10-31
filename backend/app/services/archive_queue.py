"""Archive job queue: enqueue, guarded status transitions, user actions.

The state machine is ARCHITECTURE §3.4. Every status change goes through
:func:`transition`, which rejects anything not in :data:`LEGAL` — no bare
assignments (``evidence-integrity`` rule 5). Rows are never deleted.

One transition is added beyond the diagram: ``in_progress → pending`` on
startup recovery. A job left ``in_progress`` by a killed process has no result;
putting it back in the queue is what "killing/restarting the backend loses no
jobs" (PLAN Phase 3) requires.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError, conflict, not_found, unprocessable
from app.models import ArchiveJob, Evidence

SERVICES = ("wayback", "archive_today")
STATUSES = ("pending", "in_progress", "done", "failed", "manual_pending", "manual_done")

LEGAL: frozenset[tuple[str, str]] = frozenset(
    {
        ("pending", "in_progress"),
        ("in_progress", "done"),
        ("in_progress", "pending"),  # transient failure → backoff; startup recovery
        ("in_progress", "manual_pending"),
        ("in_progress", "failed"),
        ("manual_pending", "manual_done"),
        ("failed", "manual_done"),
        ("failed", "pending"),  # retry endpoint
        ("manual_pending", "pending"),  # retry endpoint (ARCHITECTURE §6)
    }
)

# What a pasted-back archive link must look like, per service (manual-assist).
_ARCHIVE_URL = {
    "wayback": re.compile(r"^https://web\.archive\.org/web/\d{8,14}[a-z_]*/\S+$"),
    "archive_today": re.compile(
        r"^https://archive\.(?:ph|md|is|today|li|vn|fo)/[A-Za-z0-9]{4,}(?:/\S*)?$"
    ),
}

# Where the manual-assist loop sends the user (ARCHITECTURE §3.4). archive.ph is
# TR-blocked at the network level; archive.md is the reachable front (S2).
SUBMIT_PAGE = {
    "wayback": "https://web.archive.org/save/{url}",
    "archive_today": "https://archive.md/?url={url}",
}


class IllegalTransition(ApiError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(409, f"archive job cannot go from {current!r} to {target!r}")


def transition(job: ArchiveJob, target: str, now: str) -> None:
    if (job.status, target) not in LEGAL:
        raise IllegalTransition(job.status, target)
    job.status = target
    job.updated_at = now


def enqueue_for(session: Session, evidence: Evidence, now: str) -> list[ArchiveJob]:
    """Both services, in the caller's transaction (ARCHITECTURE §6 step 5)."""
    jobs = [
        ArchiveJob(
            evidence_id=evidence.id,
            service=service,
            target_url=evidence.post_url,
            status="pending",
            attempts=0,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        for service in SERVICES
    ]
    session.add_all(jobs)
    return jobs


def list_jobs(session: Session, status: str | None) -> list[ArchiveJob]:
    query = select(ArchiveJob).order_by(ArchiveJob.id)
    if status is not None:
        if status not in STATUSES:
            raise unprocessable(f"unknown status {status!r}; one of {', '.join(STATUSES)}")
        query = query.where(ArchiveJob.status == status)
    return list(session.scalars(query))


def get_job(session: Session, job_id: int) -> ArchiveJob:
    job = session.get(ArchiveJob, job_id)
    if job is None:
        raise not_found(f"archive job {job_id}")
    return job


def retry(session: Session, job_id: int, now: str) -> ArchiveJob:
    job = get_job(session, job_id)
    if job.status not in ("failed", "manual_pending"):
        raise conflict(f"only failed or manual_pending jobs can be retried (job is {job.status!r})")
    transition(job, "pending", now)
    job.attempts = 0
    job.next_attempt_at = now
    session.commit()
    return job


def complete_manually(session: Session, job_id: int, archive_url: str, now: str) -> ArchiveJob:
    job = get_job(session, job_id)
    if job.status not in ("manual_pending", "failed"):
        raise conflict(
            f"paste-back is for manual_pending or failed jobs (job is {job.status!r})"
        )
    url = archive_url.strip()
    if not _ARCHIVE_URL[job.service].match(url):
        example = (
            "https://web.archive.org/web/20260719190822/https://x.com/..."
            if job.service == "wayback"
            else "https://archive.md/AbCd1"
        )
        raise unprocessable(f"not a {job.service} archive link (expected e.g. {example})")
    transition(job, "manual_done", now)
    job.archive_url = url
    session.commit()
    return job


def submit_page(job: ArchiveJob) -> str:
    return SUBMIT_PAGE[job.service].format(url=job.target_url)


def job_dict(job: ArchiveJob) -> dict:
    return {
        "id": job.id,
        "evidence_id": job.evidence_id,
        "service": job.service,
        "target_url": job.target_url,
        "status": job.status,
        "attempts": job.attempts,
        "next_attempt_at": job.next_attempt_at,
        "archive_url": job.archive_url,
        "last_error": job.last_error,
        "submit_page": submit_page(job),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
