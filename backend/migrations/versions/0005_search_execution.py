"""Add durable radar search execution persistence.

Revision ID: 0005_search_execution
Revises: 0004_profile_refinement
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_search_execution"
down_revision: str | None = "0004_profile_refinement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("initiated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("brokerage_profile_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=120), nullable=False),
        sa.Column(
            "configured_submarkets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("resolved_submarket", sa.String(length=120), nullable=True),
        sa.Column("brokerage_profile_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("search_context_version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status in ('pending', 'running', 'completed', 'partial_failed', 'failed')",
            name="ck_search_jobs_status",
        ),
        sa.ForeignKeyConstraint(
            ["brokerage_profile_id"], ["brokerage_profiles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_search_jobs_brokerage_profile_id"),
        "search_jobs",
        ["brokerage_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_jobs_initiated_by_user_id"),
        "search_jobs",
        ["initiated_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_jobs_workspace_id"), "search_jobs", ["workspace_id"], unique=False
    )
    op.create_index(
        "ix_search_jobs_workspace_created",
        "search_jobs",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_search_jobs_active_workspace",
        "search_jobs",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("status in ('pending', 'running')"),
    )

    op.create_table(
        "search_queries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("signal_key", sa.String(length=64), nullable=False),
        sa.Column("query_rank", sa.Integer(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("preferred_domains", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("include_domains_mode", sa.String(length=16), nullable=False),
        sa.Column("search_depth", sa.String(length=16), nullable=False),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("include_raw_content", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("dispatch_attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.String(length=1000), nullable=True),
        sa.Column("provider_request_id", sa.String(length=128), nullable=True),
        sa.Column("provider_response_time_seconds", sa.Float(), nullable=True),
        sa.Column("provider_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
            "include_domains_mode in ('prefer', 'restrict')",
            name="ck_search_queries_domain_mode",
        ),
        sa.CheckConstraint(
            "search_depth in ('basic', 'advanced', 'fast', 'ultra-fast')",
            name="ck_search_queries_depth",
        ),
        sa.CheckConstraint("max_results between 1 and 20", name="ck_search_queries_max_results"),
        sa.CheckConstraint("query_rank in (1, 2)", name="ck_search_queries_rank"),
        sa.CheckConstraint("length(query_text) > 0", name="ck_search_queries_query_text"),
        sa.CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed')",
            name="ck_search_queries_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_search_queries_attempt_count"),
        sa.CheckConstraint(
            "dispatch_attempt_count >= 0", name="ck_search_queries_dispatch_attempt_count"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["search_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id", "signal_key", "query_rank", name="uq_search_queries_job_signal_rank"
        ),
    )
    op.create_index(op.f("ix_search_queries_job_id"), "search_queries", ["job_id"], unique=False)
    op.create_index(
        "ix_search_queries_dispatch",
        "search_queries",
        ["status", "next_attempt_at", "last_dispatched_at"],
        unique=False,
    )
    op.create_index(
        "ix_search_queries_lease",
        "search_queries",
        ["status", "lease_expires_at"],
        unique=False,
    )

    op.create_table(
        "search_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("search_query_id", sa.Uuid(), nullable=False),
        sa.Column("result_rank", sa.Integer(), nullable=False),
        sa.Column("provider_result_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("provider_score", sa.Float(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("result_rank > 0", name="ck_search_results_rank"),
        sa.CheckConstraint("length(url) > 0", name="ck_search_results_url"),
        sa.ForeignKeyConstraint(["search_query_id"], ["search_queries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("search_query_id", "result_rank", name="uq_search_results_query_rank"),
    )
    op.create_index(
        op.f("ix_search_results_search_query_id"),
        "search_results",
        ["search_query_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_search_results_search_query_id"), table_name="search_results")
    op.drop_table("search_results")
    op.drop_index("ix_search_queries_lease", table_name="search_queries")
    op.drop_index("ix_search_queries_dispatch", table_name="search_queries")
    op.drop_index(op.f("ix_search_queries_job_id"), table_name="search_queries")
    op.drop_table("search_queries")
    op.drop_index("uq_search_jobs_active_workspace", table_name="search_jobs")
    op.drop_index("ix_search_jobs_workspace_created", table_name="search_jobs")
    op.drop_index(op.f("ix_search_jobs_workspace_id"), table_name="search_jobs")
    op.drop_index(op.f("ix_search_jobs_initiated_by_user_id"), table_name="search_jobs")
    op.drop_index(op.f("ix_search_jobs_brokerage_profile_id"), table_name="search_jobs")
    op.drop_table("search_jobs")
