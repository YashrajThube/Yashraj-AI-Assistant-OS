"""initial

Revision ID: 20260413_0001
Revises: None
Create Date: 2026-04-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260413_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("google_event_id", sa.String(length=255), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("sync_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_events_user_id", "events", ["user_id"])
    op.create_index("ix_events_start_time", "events", ["start_time"])
    op.create_index("ix_events_created_at", "events", ["created_at"])

    op.create_table(
        "notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notes_user_id", "notes", ["user_id"])
    op.create_index("ix_notes_created_at", "notes", ["created_at"])

    op.create_table(
        "failed_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
    )
    op.create_index("ix_failed_jobs_type", "failed_jobs", ["type"])
    op.create_index("ix_failed_jobs_status", "failed_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_failed_jobs_status", table_name="failed_jobs")
    op.drop_index("ix_failed_jobs_type", table_name="failed_jobs")
    op.drop_table("failed_jobs")

    op.drop_index("ix_notes_created_at", table_name="notes")
    op.drop_index("ix_notes_user_id", table_name="notes")
    op.drop_table("notes")

    op.drop_index("ix_events_created_at", table_name="events")
    op.drop_index("ix_events_start_time", table_name="events")
    op.drop_index("ix_events_user_id", table_name="events")
    op.drop_table("events")
