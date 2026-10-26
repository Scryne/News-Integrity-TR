"""001 initial schema — the 8 tables of ARCHITECTURE.md §5.

Revision ID: 0001
Revises:
Create Date: 2026-07-22

Schema only. Notable contracts baked in here:
  * ADR-001  — account_id/rest_id and every FK to it are TEXT.
  * ADR-013  — evidence.status enum (complete/pending_completion/archive_only).
  * ADR-015  — edges.target_account_id NULLABLE + target_handle_raw fallback.
  * ADR-017  — evidence.taxonomy_version column (NULL until codes attached).
  * ADR-018  — categories table; evidence.category / evidence_codes.code FKs.
  * ADR-019  — evidence.phase + edges.phase.
  * ADR-020  — handle_history shape (append-only; seeding logic is T4).
  * ADR-025 QUEUE CONTRACT — archive_jobs.status carries the FULL enum
    (pending/in_progress/done/failed/manual_pending/manual_done) so Phase 3
    needs no migration. No state-machine/enforcement here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- accounts (ADR-001: rest_id TEXT PK) -------------------------------
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.String(), primary_key=True),
        sa.Column("current_handle", sa.String(), nullable=False),
        sa.Column("first_seen_at", sa.String(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )

    # --- taxonomy_codes (ADR-016/017/018) ----------------------------------
    op.create_table(
        "taxonomy_codes",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("group_prefix", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("international_equivalent", sa.Text()),
        sa.CheckConstraint(
            "group_prefix IN ('H','E','I')", name="ck_taxonomy_codes_group_prefix"
        ),
    )

    # --- categories (ADR-018) ----------------------------------------------
    op.create_table(
        "categories",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("label", sa.String(), nullable=False),
    )

    # --- evidence (created before handle_history: the latter FKs evidence.id)
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(),
            sa.ForeignKey("accounts.account_id"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),  # ADR-019
        sa.Column("post_url", sa.String(), nullable=False),
        sa.Column("post_id", sa.String()),
        sa.Column("post_text", sa.Text()),
        sa.Column("posted_at", sa.String()),
        sa.Column("captured_at", sa.String()),  # NULL while pending_completion
        sa.Column("handle_at_capture", sa.String()),
        sa.Column("follower_count_at_capture", sa.Integer()),
        sa.Column("category", sa.String(), sa.ForeignKey("categories.key")),
        sa.Column("note", sa.Text()),
        sa.Column("taxonomy_version", sa.String()),  # ADR-017
        sa.Column("capture_source", sa.String(), nullable=False),  # ADR-023
        sa.Column("status", sa.String(), nullable=False),  # ADR-013
        sa.Column("crop_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("screenshot_path", sa.String()),
        sa.Column("screenshot_sha256", sa.String()),
        sa.Column("viewport_path", sa.String()),
        sa.Column("viewport_sha256", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("account_id", "seq", name="uq_evidence_account_seq"),
        sa.CheckConstraint("phase IN ('VK1','VK2')", name="ck_evidence_phase"),
        sa.CheckConstraint(
            "capture_source IN ('extension','cli')", name="ck_evidence_capture_source"
        ),
        sa.CheckConstraint(
            "status IN ('complete','pending_completion','archive_only')",
            name="ck_evidence_status",
        ),
    )
    op.create_index("idx_evidence_post_id", "evidence", ["post_id"])

    # --- handle_history (ADR-020) ------------------------------------------
    op.create_table(
        "handle_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(),
            sa.ForeignKey("accounts.account_id"),
            nullable=False,
        ),
        sa.Column("handle", sa.String(), nullable=False),
        sa.Column("detected_at", sa.String(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence.id")),
    )

    # --- evidence_codes (composite PK) -------------------------------------
    op.create_table(
        "evidence_codes",
        sa.Column(
            "evidence_id", sa.Integer(), sa.ForeignKey("evidence.id"), nullable=False
        ),
        sa.Column(
            "code", sa.String(), sa.ForeignKey("taxonomy_codes.code"), nullable=False
        ),
        sa.PrimaryKeyConstraint("evidence_id", "code"),
    )

    # --- edges (ADR-015 nullable target; ADR-019 phase) --------------------
    op.create_table(
        "edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_account_id",
            sa.String(),
            sa.ForeignKey("accounts.account_id"),
            nullable=False,
        ),
        sa.Column(
            "target_account_id", sa.String(), sa.ForeignKey("accounts.account_id")
        ),
        sa.Column("target_handle_raw", sa.String()),
        sa.Column("edge_type", sa.String(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("post_url", sa.String(), nullable=False),
        sa.Column("observed_at", sa.String(), nullable=False),
        sa.Column("evidence_id", sa.Integer(), sa.ForeignKey("evidence.id")),
        sa.Column("note", sa.Text()),
        sa.CheckConstraint(
            "edge_type IN ('quote','retweet','reply','mention')",
            name="ck_edges_edge_type",
        ),
        sa.CheckConstraint("phase IN ('VK1','VK2')", name="ck_edges_phase"),
    )
    op.create_index("idx_edges_source", "edges", ["source_account_id"])

    # --- archive_jobs (ADR-025 QUEUE CONTRACT: full status enum) -----------
    op.create_table(
        "archive_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "evidence_id", sa.Integer(), sa.ForeignKey("evidence.id"), nullable=False
        ),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("target_url", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.String()),
        sa.Column("archive_url", sa.String()),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "service IN ('wayback','archive_today')", name="ck_archive_jobs_service"
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','done','failed',"
            "'manual_pending','manual_done')",
            name="ck_archive_jobs_status",
        ),
    )
    op.create_index(
        "idx_archive_jobs_due", "archive_jobs", ["status", "next_attempt_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_archive_jobs_due", table_name="archive_jobs")
    op.drop_table("archive_jobs")
    op.drop_index("idx_edges_source", table_name="edges")
    op.drop_table("edges")
    op.drop_table("evidence_codes")
    op.drop_table("handle_history")
    op.drop_index("idx_evidence_post_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_table("categories")
    op.drop_table("taxonomy_codes")
    op.drop_table("accounts")
