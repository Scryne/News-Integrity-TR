"""SQLAlchemy 2.0 ORM models — the 8 tables from ARCHITECTURE.md §5 (ADR-003).

Importing this package registers every table on ``Base.metadata`` (used as
Alembic's ``target_metadata``). Schema only; no query/write logic (T4-T6).
"""

from app.models.account import Account, HandleHistory
from app.models.archive import ArchiveJob
from app.models.edge import Edge
from app.models.evidence import Evidence, EvidenceCode
from app.models.taxonomy import Category, TaxonomyCode

__all__ = [
    "Account",
    "ArchiveJob",
    "Category",
    "Edge",
    "Evidence",
    "EvidenceCode",
    "HandleHistory",
    "TaxonomyCode",
]
