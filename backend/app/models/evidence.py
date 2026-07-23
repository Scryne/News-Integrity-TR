"""evidence + evidence_codes models (ARCHITECTURE §5)."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.account_id"), nullable=False
    )
    # Per-account, assigned at row creation and reserving the filename slot (T5).
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    # ADR-019: stamped from NIT_PHASE at creation; also the evidence folder prefix.
    phase: Mapped[str] = mapped_column(String, nullable=False)
    post_url: Mapped[str] = mapped_column(String, nullable=False)
    post_id: Mapped[str | None] = mapped_column(String)
    post_text: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[str | None] = mapped_column(String)
    captured_at: Mapped[str | None] = mapped_column(String)  # NULL while pending_completion
    handle_at_capture: Mapped[str | None] = mapped_column(String)
    follower_count_at_capture: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String, ForeignKey("categories.key"))
    note: Mapped[str | None] = mapped_column(Text)
    # ADR-017: stamped from the seeded taxonomy version when codes are attached;
    # NULL while pending_completion (no codes yet).
    taxonomy_version: Mapped[str | None] = mapped_column(String)
    # ADR-023: capture_source records how the ROW came into existence. Merged
    # rows keep 'cli' -> ('cli' + status 'complete') unambiguously reads as
    # CLI-queued, extension-completed.
    capture_source: Mapped[str] = mapped_column(String, nullable=False)
    # ADR-013: explicit tier. Legal transitions (enforced in services, Phase 3+):
    # pending_completion -> complete (merge) | pending_completion -> archive_only.
    status: Mapped[str] = mapped_column(String, nullable=False)
    # ADR-005: crop is best-effort; 1 means the canonical name holds the viewport.
    crop_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    screenshot_path: Mapped[str | None] = mapped_column(String)  # primary (canonical name)
    screenshot_sha256: Mapped[str | None] = mapped_column(String)
    viewport_path: Mapped[str | None] = mapped_column(String)  # NULL when crop_failed
    viewport_sha256: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "seq", name="uq_evidence_account_seq"),
        CheckConstraint("phase IN ('VK1','VK2')", name="ck_evidence_phase"),
        CheckConstraint(
            "capture_source IN ('extension','cli')", name="ck_evidence_capture_source"
        ),
        CheckConstraint(
            "status IN ('complete','pending_completion','archive_only')",
            name="ck_evidence_status",
        ),
        Index("idx_evidence_post_id", "post_id"),
    )


class EvidenceCode(Base):
    __tablename__ = "evidence_codes"

    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidence.id"), primary_key=True
    )
    code: Mapped[str] = mapped_column(
        String, ForeignKey("taxonomy_codes.code"), primary_key=True
    )
