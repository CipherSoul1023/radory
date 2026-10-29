"""Add durable post-discovery radar pipeline state.

Revision ID: 0008_radar_pipeline_state
Revises: 0007_radar_opportunities
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_radar_pipeline_state"
down_revision: str | None = "0007_radar_opportunities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "search_jobs",
        sa.Column(
            "pipeline_status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "search_jobs",
        sa.Column("pipeline_error_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "search_jobs",
        sa.Column("pipeline_error_message", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "search_jobs",
        sa.Column("pipeline_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "search_jobs",
        sa.Column("pipeline_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "update search_jobs set pipeline_status = 'completed', "
        "pipeline_completed_at = completed_at "
        "where status in ('completed', 'partial_failed', 'failed')"
    )
    op.alter_column("search_jobs", "pipeline_status", server_default=None)
    op.create_check_constraint(
        "ck_search_jobs_pipeline_status",
        "search_jobs",
        "pipeline_status in ('pending', 'running', 'completed', 'partial_failed', 'failed')",
    )
    op.drop_index("uq_search_jobs_active_workspace", table_name="search_jobs")
    op.create_index(
        "uq_search_jobs_active_workspace",
        "search_jobs",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text(
            "status in ('pending', 'running') or pipeline_status in ('pending', 'running')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_search_jobs_active_workspace", table_name="search_jobs")
    op.create_index(
        "uq_search_jobs_active_workspace",
        "search_jobs",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("status in ('pending', 'running')"),
    )
    op.drop_constraint(
        "ck_search_jobs_pipeline_status",
        "search_jobs",
        type_="check",
    )
    op.drop_column("search_jobs", "pipeline_completed_at")
    op.drop_column("search_jobs", "pipeline_started_at")
    op.drop_column("search_jobs", "pipeline_error_message")
    op.drop_column("search_jobs", "pipeline_error_code")
    op.drop_column("search_jobs", "pipeline_status")
