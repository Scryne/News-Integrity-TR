"""Read side of the coding vocabulary (ADR-016/017/018).

``taxonomy_seed`` converges the DB to ``taxonomy.json`` at startup; this module
serves that vocabulary to the overlay and validates what a capture attaches.
The seeded file version is the ONLY source of ``evidence.taxonomy_version``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import unprocessable
from app.models import Category, TaxonomyCode


@dataclass(frozen=True)
class Vocabulary:
    version: str
    groups: dict[str, str]


def vocabulary_from(data: dict) -> Vocabulary:
    return Vocabulary(version=str(data["version"]), groups=dict(data.get("groups") or {}))


def payload(session: Session, vocab: Vocabulary) -> dict:
    categories = session.scalars(select(Category).order_by(Category.key))
    codes = session.scalars(select(TaxonomyCode))
    group_order = list(vocab.groups) or ["H", "E", "I", "Y"]

    def sort_key(row: TaxonomyCode) -> tuple[int, int, str]:
        rank = group_order.index(row.group_prefix) if row.group_prefix in group_order else 99
        digits = "".join(ch for ch in row.code if ch.isdigit())
        return rank, int(digits or 0), row.code

    return {
        "version": vocab.version,
        "groups": vocab.groups,
        "categories": [{"key": c.key, "label": c.label} for c in categories],
        "codes": [
            {
                "code": c.code,
                "group_prefix": c.group_prefix,
                "label": c.label,
                "description": c.description,
                "international_equivalent": c.international_equivalent,
            }
            for c in sorted(codes, key=sort_key)
        ],
    }


def validate(session: Session, category: str, codes: list[str]) -> None:
    if session.get(Category, category) is None:
        raise unprocessable(f"unknown category {category!r} (ADR-018: fixed seeded list)")
    known = set(session.scalars(select(TaxonomyCode.code).where(TaxonomyCode.code.in_(codes))))
    unknown = [code for code in codes if code not in known]
    if unknown:
        raise unprocessable(f"unknown taxonomy code(s): {', '.join(unknown)}")
