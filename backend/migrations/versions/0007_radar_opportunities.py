"""Add unified radar opportunity snapshots.

Revision ID: 0007_radar_opportunities
Revises: 0006_extraction_persistence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_radar_opportunities"
down_revision: str | None = "0006_extraction_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "radar_opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("search_job_id", sa.Uuid(), nullable=False),
        sa.Column("seed_extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("seed_event_index", sa.Integer(), nullable=False),
        sa.Column("subject_company", sa.String(length=1200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("discovery_observation_ids", postgresql.JSONB(), nullable=False),
        sa.Column(
            "investigation_decision",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("investigation_queries", postgresql.JSONB(), nullable=False),
        sa.Column("investigation_observations", postgresql.JSONB(), nullable=False),
        sa.Column("synthesis_model", sa.String(length=160), nullable=True),
        sa.Column("synthesis_provider_request_id", sa.String(length=128), nullable=True),
        sa.Column(
            "synthesis_usage",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column(
            "report",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "seed_event_index >= 0",
            name="ck_radar_opportunities_event_index",
        ),
        sa.CheckConstraint(
            "status in ('running', 'completed', 'failed')",
            name="ck_radar_opportunities_status",
        ),
        sa.CheckConstraint(
            "(status = 'completed' and report is not null and error_code is null) or "
            "(status = 'failed' and report is null and error_code is not null) or "
            "(status = 'running' and report is null and error_code is null)",
            name="ck_radar_opportunities_result_shape",
        ),
        sa.ForeignKeyConstraint(
            ["seed_extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["search_job_id"], ["search_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "seed_extraction_run_id",
            "seed_event_index",
            name="uq_radar_opportunities_workspace_event",
        ),
    )
    op.create_index(
        op.f("ix_radar_opportunities_workspace_id"),
        "radar_opportunities",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_radar_opportunities_search_job_id"),
        "radar_opportunities",
        ["search_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_radar_opportunities_seed_extraction_run_id"),
        "radar_opportunities",
        ["seed_extraction_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_radar_opportunities_workspace_created",
        "radar_opportunities",
        ["workspace_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_radar_opportunities_workspace_created",
        table_name="radar_opportunities",
    )
    op.drop_index(
        op.f("ix_radar_opportunities_seed_extraction_run_id"),
        table_name="radar_opportunities",
    )
    op.drop_index(
        op.f("ix_radar_opportunities_search_job_id"),
        table_name="radar_opportunities",
    )
    op.drop_index(
        op.f("ix_radar_opportunities_workspace_id"),
        table_name="radar_opportunities",
    )
    op.drop_table("radar_opportunities")
