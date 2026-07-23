"""archive_jobs model (ARCHITECTURE §5).

QUEUE CONTRACT (locked here so Phase 3 needs no migration): the status enum
carries the FULL state space defined in ARCHITECTURE §3.4/§5 and shaped by
ADR-007/008 (escalate to manual_pending, never silently dropped) — including
manual_pending and manual_done — because ADR-025 makes the manual-assist queue
the PRIMARY archive path for x.com URLs (Wayback + archive.today both
manual-first). Rows are NEVER deleted; only status-transitioned. This module
defines the schema ONLY — the worker, the state-machine/enforcement, and the
ADR-022 URL short-circuit are Phase 3, not here.

NB: this is the ARCHIVE-JOB status. The separate evidence.status model
(complete/pending_completion/archive_only) is ADR-013 — do not conflate the two.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ArchiveJob(Base):
    __tablename__ = "archive_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence.id"), nullable=False
    )
    service: Mapped[str] = mapped_column(String, nullable=False)
    target_url: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[str | None] = mapped_column(String)
    archive_url: Mapped[str | None] = mapped_column(String)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "service IN ('wayback','archive_today')", name="ck_archive_jobs_service"
        ),
        # Full status enum — the queue contract. Do NOT trim in Phase 3.
        CheckConstraint(
            "status IN ('pending','in_progress','done','failed',"
            "'manual_pending','manual_done')",
            name="ck_archive_jobs_status",
        ),
        Index("idx_archive_jobs_due", "status", "next_attempt_at"),
    )
