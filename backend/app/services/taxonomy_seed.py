"""Idempotent taxonomy + category seeding (T3).

Reads the repo-root ``taxonomy.json`` — the single source of truth for the
coding vocabulary (version + groups + categories + codes, ADR-016/017/018) —
and converges the ``categories`` and ``taxonomy_codes`` tables to it.

Seed contract (ADR-016, enforced here):
  * labels / descriptions / international_equivalent **upsert** on every run;
  * codes are **never deleted** — a code present in the DB but absent from the
    file is left untouched (evidence rows reference codes via FK);
  * categories are likewise never deleted (``evidence.category`` FKs them).

Because the operation only inserts-or-updates and never deletes, it is safe to
run on every startup: repeated runs converge to the file's labels and leave row
counts stable once seeded (the T3 idempotency guarantee).

``group_prefix`` is pre-validated against the ``taxonomy_codes`` CHECK domain
(``'H','E','I','Y'`` after migration 0002 / ADR-027) so a malformed file fails
loudly here with an actionable message instead of as an opaque ``IntegrityError``
mid-transaction.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.taxonomy import Category, TaxonomyCode

logger = logging.getLogger("news_integrity")

# repo root: this file is backend/app/services/taxonomy_seed.py -> parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TAXONOMY_PATH = REPO_ROOT / "taxonomy.json"

# Mirror of the taxonomy_codes CHECK (widened by migration 0002 for the Y axis,
# ADR-027). Kept as a literal so a file carrying an out-of-domain prefix is
# rejected here, before it reaches the DB constraint, with a message that names
# the offending code.
GROUP_PREFIX_DOMAIN = frozenset({"H", "E", "I", "Y"})


class TaxonomySeedError(RuntimeError):
    """``taxonomy.json`` is missing, malformed, or violates the seed contract."""


@dataclass
class SeedSummary:
    """Outcome of one seeding pass — used for the startup log and T3 proofs."""

    version: str
    categories_inserted: int = 0
    categories_updated: int = 0
    codes_inserted: int = 0
    codes_updated: int = 0
    categories_total: int = 0
    codes_total: int = 0

    def as_log(self) -> str:
        return (
            f"taxonomy v{self.version} seeded: "
            f"categories +{self.categories_inserted}/~{self.categories_updated} "
            f"(total {self.categories_total}); "
            f"codes +{self.codes_inserted}/~{self.codes_updated} "
            f"(total {self.codes_total})"
        )


def load_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> dict:
    """Parse and structurally validate ``taxonomy.json``.

    Raises :class:`TaxonomySeedError` (never a bare ``KeyError``/``JSONDecode``)
    so the caller can fail startup with an actionable message.
    """
    if not path.exists():
        raise TaxonomySeedError(f"taxonomy.json not found at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise TaxonomySeedError(f"taxonomy.json is not valid UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TaxonomySeedError(f"taxonomy.json is not valid JSON: {exc}") from exc

    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise TaxonomySeedError(
            'taxonomy.json is missing a non-empty top-level "version" (ADR-017)'
        )

    codes = data.get("codes")
    cats = data.get("categories")
    if not isinstance(codes, list) or not codes:
        raise TaxonomySeedError('taxonomy.json "codes" must be a non-empty list')
    if not isinstance(cats, list) or not cats:
        raise TaxonomySeedError('taxonomy.json "categories" must be a non-empty list')

    for cat in cats:
        if not str(cat.get("key", "")).strip() or not str(cat.get("label", "")).strip():
            raise TaxonomySeedError(
                f"category {cat.get('key')!r} is missing a non-empty key/label "
                "(ADR-016: no placeholders)"
            )

    for code in codes:
        gp = code.get("group_prefix")
        if gp not in GROUP_PREFIX_DOMAIN:
            raise TaxonomySeedError(
                f"code {code.get('code')!r} has group_prefix {gp!r} outside the "
                f"migration-001 CHECK domain {sorted(GROUP_PREFIX_DOMAIN)}"
            )
        for required in ("code", "label"):
            if not str(code.get(required, "")).strip():
                raise TaxonomySeedError(
                    f"code {code.get('code')!r} has empty required field "
                    f"{required!r} (ADR-016: no placeholders)"
                )
    return data


def seed_taxonomy(session: Session, path: Path = DEFAULT_TAXONOMY_PATH) -> SeedSummary:
    """Idempotently upsert categories + taxonomy_codes. The caller commits.

    Never issues a DELETE: codes/categories absent from the file are preserved.
    """
    data = load_taxonomy(path)
    summary = SeedSummary(version=str(data["version"]))

    # --- categories: upsert label; never delete (evidence.category FK) --------
    for cat in data["categories"]:
        key, label = cat["key"], cat["label"]
        row = session.get(Category, key)
        if row is None:
            session.add(Category(key=key, label=label))
            summary.categories_inserted += 1
        elif row.label != label:
            row.label = label
            summary.categories_updated += 1

    # --- taxonomy_codes: upsert label/desc/intl; never delete the code --------
    for code in data["codes"]:
        code_id = code["code"]
        fields = {
            "group_prefix": code["group_prefix"],
            "label": code["label"],
            "description": code.get("description"),
            "international_equivalent": code.get("international_equivalent"),
        }
        row = session.get(TaxonomyCode, code_id)
        if row is None:
            session.add(TaxonomyCode(code=code_id, **fields))
            summary.codes_inserted += 1
        elif any(getattr(row, name) != value for name, value in fields.items()):
            for name, value in fields.items():
                setattr(row, name, value)
            summary.codes_updated += 1

    session.flush()  # surface any CHECK/constraint failure before the caller commits
    summary.categories_total = session.scalar(select(func.count()).select_from(Category))
    summary.codes_total = session.scalar(select(func.count()).select_from(TaxonomyCode))
    logger.info(summary.as_log())
    return summary
