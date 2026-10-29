"""Add semantic extraction runs, provenance, and candidate observations.

Revision ID: 0006_extraction_persistence
Revises: 0005_search_execution
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_extraction_persistence"
down_revision: str | None = "0005_search_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("preparation_version", sa.String(length=32), nullable=False),
        sa.Column("extraction_version", sa.String(length=32), nullable=False),
        sa.Column("specification_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("content_basis", sa.String(length=20), nullable=False),
        sa.Column("provider_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("provider_request_id", sa.String(length=128), nullable=True),
        sa.Column("provider_model", sa.String(length=160), nullable=True),
        sa.Column(
            "provider_usage",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.Column("model_calls", sa.Integer(), nullable=False),
        sa.Column(
            "validated_output",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
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
            "content_basis in ('raw_content', 'snippet')",
            name="ck_extraction_runs_content_basis",
        ),
        sa.CheckConstraint("model_calls >= 0", name="ck_extraction_runs_model_calls"),
        sa.CheckConstraint(
            "(status = 'succeeded' and error_code is null and validated_output is not null) "
            "or (status = 'failed' and error_code is not null and validated_output is null)",
            name="ck_extraction_runs_result_shape",
        ),
        sa.CheckConstraint(
            "status in ('succeeded', 'failed')",
            name="ck_extraction_runs_status",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_extraction_runs_id_workspace"),
    )
    op.create_index(
        op.f("ix_extraction_runs_workspace_id"),
        "extraction_runs",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_extraction_runs_workspace_created",
        "extraction_runs",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_extraction_runs_success_cache",
        "extraction_runs",
        ["workspace_id", "cache_key"],
        unique=True,
        postgresql_where=sa.text("status = 'succeeded'"),
    )

    op.create_table(
        "extraction_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("search_result_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["extraction_run_id"], ["extraction_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["search_result_id"], ["search_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "extraction_run_id",
            "search_result_id",
            name="uq_extraction_sources_run_result",
        ),
    )
    op.create_index(
        op.f("ix_extraction_sources_extraction_run_id"),
        "extraction_sources",
        ["extraction_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_sources_search_result_id"),
        "extraction_sources",
        ["search_result_id"],
        unique=False,
    )

    op.create_table(
        "signal_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("signal_key", sa.String(length=64), nullable=False),
        sa.Column("subject_company", sa.String(length=1200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column(
            "subject_company_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("summary_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("signal_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stage_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("locations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timing", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("related_companies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.CheckConstraint("event_index >= 0", name="ck_signal_observations_event_index"),
        sa.CheckConstraint("length(subject_company) > 0", name="ck_signal_observations_company"),
        sa.CheckConstraint("length(summary) > 0", name="ck_signal_observations_summary"),
        sa.CheckConstraint(
            "stage in ('planned', 'underway', 'completed', 'cancelled', 'unclear')",
            name="ck_signal_observations_stage",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_run_id", "workspace_id"],
            ["extraction_runs.id", "extraction_runs.workspace_id"],
            ondelete="CASCADE",
            name="fk_signal_observations_run_workspace",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "extraction_run_id",
            "event_index",
            "signal_key",
            name="uq_signal_observations_run_event_signal",
        ),
    )
    op.create_index(
        op.f("ix_signal_observations_extraction_run_id"),
        "signal_observations",
        ["extraction_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_signal_observations_workspace_id"),
        "signal_observations",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_signal_observations_workspace_created",
        "signal_observations",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_signal_observations_workspace_signal",
        "signal_observations",
        ["workspace_id", "signal_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_signal_observations_workspace_signal", table_name="signal_observations")
    op.drop_index("ix_signal_observations_workspace_created", table_name="signal_observations")
    op.drop_index(op.f("ix_signal_observations_workspace_id"), table_name="signal_observations")
    op.drop_index(
        op.f("ix_signal_observations_extraction_run_id"), table_name="signal_observations"
    )
    op.drop_table("signal_observations")
    op.drop_index(op.f("ix_extraction_sources_search_result_id"), table_name="extraction_sources")
    op.drop_index(op.f("ix_extraction_sources_extraction_run_id"), table_name="extraction_sources")
    op.drop_table("extraction_sources")
    op.drop_index("uq_extraction_runs_success_cache", table_name="extraction_runs")
    op.drop_index("ix_extraction_runs_workspace_created", table_name="extraction_runs")
    op.drop_index(op.f("ix_extraction_runs_workspace_id"), table_name="extraction_runs")
    op.drop_table("extraction_runs")
