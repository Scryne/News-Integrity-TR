"""0002 widen taxonomy_codes.group_prefix CHECK for the Y axis (ADR-027).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-24

Schema-only, content-free change: the ``ck_taxonomy_codes_group_prefix`` CHECK
domain is widened from ``('H','E','I')`` to ``('H','E','I','Y')`` so the taxonomy
v1.1 "Yayın Sonrası Bütünlük" axis (codes Y1, Y2) can be seeded. This migration
adds NO rows — the new codes arrive via ``taxonomy.json`` and idempotent startup
seeding. It is deliberately applied BEFORE the ``taxonomy.json`` bump: the CHECK
domain must never lag behind the file's prefix set, or seeding a Y row would hit
the old constraint (ADR-027 Consequences; ADR-016 additive-growth rule).

SQLite has no ALTER ... DROP CONSTRAINT, so the widening goes through Alembic
batch mode (``render_as_batch=True`` in env.py), which recreates the table and
copies the existing 19 rows across. The widened domain is a superset, so every
existing row passes the new CHECK by construction.

``downgrade()`` intentionally raises (see below): narrowing the domain while the
seeder still re-inserts Y rows from taxonomy.json on every startup would make the
app un-startable. Reversal is a guided manual procedure, not an automatic step.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode recreates taxonomy_codes with the widened CHECK and copies the
    # existing rows. The named constraint from migration 0001 is dropped by name
    # and re-created with the wider domain; if a future SQLite/SQLAlchemy version
    # cannot reflect the name to drop it, switch this block to an explicit
    # ``copy_from`` Table definition (see ADR-027 apply notes).
    with op.batch_alter_table("taxonomy_codes", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_taxonomy_codes_group_prefix", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_taxonomy_codes_group_prefix",
            "group_prefix IN ('H','E','I','Y')",
        )


def downgrade() -> None:
    # Deliberately NOT auto-reversible. The startup seeder re-inserts the Y-axis
    # rows from taxonomy.json on every boot; narrowing the CHECK back to
    # ('H','E','I') while those rows (or the v1.1 file) still exist would make the
    # next startup fail on the constraint. Reverse by hand, in order:
    #   1. restore taxonomy.json to the v1.0 codebook (drop the Y group + Y1/Y2,
    #      and H8, and set version back to "1.0");
    #   2. DELETE FROM taxonomy_codes WHERE group_prefix = 'Y' (and 'H8'), after
    #      confirming no evidence_codes rows reference them (ADR-016: codes with
    #      evidence are never removed);
    #   3. only then hand-write the narrowing batch migration.
    raise NotImplementedError(
        "0002 is not auto-reversible: the seeder re-inserts Y-axis rows from "
        "taxonomy.json every startup, so narrowing the CHECK first would break "
        "boot. Reverse manually: (1) restore taxonomy.json to v1.0, (2) delete "
        "the Y1/Y2/H8 rows only if no evidence references them (ADR-016), then "
        "(3) apply a hand-written narrowing migration. See this migration's "
        "docstring."
    )
