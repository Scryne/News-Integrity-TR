"""accounts + handle_history models (ARCHITECTURE §5)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Account(Base):
    __tablename__ = "accounts"

    # ADR-001: account_id is the X rest_id (immutable, digits only) stored as
    # TEXT and used as the FK everywhere. Handles are display data, never keys.
    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    # ADR-020: current_handle is denormalized convenience only, updated on
    # change detection; the authoritative dated list lives in handle_history.
    current_handle: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class HandleHistory(Base):
    __tablename__ = "handle_history"

    # ADR-020: append-only and COMPLETE FROM BIRTH. Account creation seeds the
    # initial handle here (detected_at = first_seen_at, evidence_id when created
    # via a capture); a change appends the NEWLY observed handle. Never
    # UPDATE/DELETE. (Seeding/append logic is the accounts service, T4.)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String, ForeignKey("accounts.account_id"), nullable=False
    )
    handle: Mapped[str] = mapped_column(String, nullable=False)
    detected_at: Mapped[str] = mapped_column(String, nullable=False)
    # The capture that detected this handle, if any (NULL when seeded outside a
    # capture, e.g. a CLI-created account).
    evidence_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("evidence.id"))
