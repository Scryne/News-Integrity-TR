"""taxonomy_codes + categories models (ARCHITECTURE §5).

Both are seeded idempotently from repo-root taxonomy.json at startup (T3):
labels upsert, codes are never deleted (evidence references them) — ADR-016/
017/018. This module defines the schema only.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TaxonomyCode(Base):
    __tablename__ = "taxonomy_codes"

    # 'H1'..'H8', 'E1'..'E7', 'I1'..'I5', 'Y1'..'Y2'. Code is the immutable
    # identifier of the methodology; the label/description may be refined across
    # versions.
    code: Mapped[str] = mapped_column(String, primary_key=True)
    group_prefix: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Terminology mapping used by the EN report (ADR-018).
    international_equivalent: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # Y = "Yayın Sonrası Bütünlük" axis added in taxonomy v1.1 (ADR-027).
        CheckConstraint(
            "group_prefix IN ('H','E','I','Y')", name="ck_taxonomy_codes_group_prefix"
        ),
    )


class Category(Base):
    __tablename__ = "categories"

    # ADR-018: fixed seeded list; evidence.category FKs here. No free text.
    # keys: 'news','magazine','agenda','viral','anonymous_news'.
    key: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
