"""0003 evidence.sidecar_path + evidence.sidecar_sha256 (ADR-029).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31

The manifest (ARCHITECTURE §6) lists "all evidence files + sidecars with
SHA-256" and ``verify=true`` must flag a tampered sidecar exactly like a
tampered PNG. A verifier needs the hash recorded at write time; migration 0001
stored it for the two images only. Additive: two nullable columns, NULL while a
row is ``pending_completion`` (no files yet) or ``archive_only`` (never gets
files). No existing row is rewritten.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidence") as batch:
        batch.add_column(sa.Column("sidecar_path", sa.String()))
        batch.add_column(sa.Column("sidecar_sha256", sa.String()))


def downgrade() -> None:
    with op.batch_alter_table("evidence") as batch:
        batch.drop_column("sidecar_sha256")
        batch.drop_column("sidecar_path")
