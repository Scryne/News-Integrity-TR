"""UTC timestamps in the one format the schema uses (ARCHITECTURE §5).

Every stored timestamp is an ISO-8601 UTC string with a ``Z`` suffix and
second precision, so lexical order equals chronological order — the archive
worker's due-job query (``next_attempt_at <= now``) relies on that.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def to_iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utcnow() -> datetime:
    return datetime.now(UTC)


def now_iso() -> str:
    return to_iso(utcnow())


def iso_after(seconds: float, start: datetime | None = None) -> str:
    return to_iso((start or utcnow()) + timedelta(seconds=seconds))
