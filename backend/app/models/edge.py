"""edges model (ARCHITECTURE §5)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.account_id"), nullable=False
    )
    # ADR-015: target rest_id kept NULL when unresolvable — never guessed;
    # target_handle_raw is the fallback identity, never a key.
    target_account_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("accounts.account_id")
    )
    target_handle_raw: Mapped[str | None] = mapped_column(String)
    edge_type: Mapped[str] = mapped_column(String, nullable=False)
    # ADR-019: stamped from NIT_PHASE at creation.
    phase: Mapped[str] = mapped_column(String, nullable=False)
    post_url: Mapped[str] = mapped_column(String, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, nullable=False)
    # Set when the edge was logged inline with a capture.
    evidence_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("evidence.id"))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "edge_type IN ('quote','retweet','reply','mention')",
            name="ck_edges_edge_type",
        ),
        CheckConstraint("phase IN ('VK1','VK2')", name="ck_edges_phase"),
        Index("idx_edges_source", "source_account_id"),
    )
