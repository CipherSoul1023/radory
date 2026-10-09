"""Add workspace onboarding persistence.

Revision ID: 0002_workspace_onboarding
Revises: 0001_initial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_workspace_onboarding"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clerk_user_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clerk_user_id"),
    )
    op.create_index(op.f("ix_users_clerk_user_id"), "users", ["clerk_user_id"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clerk_organization_id", sa.String(length=64), nullable=True),
        sa.Column("clerk_slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("provisioning_status", sa.String(length=20), nullable=False),
        sa.Column("provisioning_error", sa.String(length=500), nullable=True),
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
            "provisioning_status in ('pending', 'failed', 'complete')",
            name="ck_workspaces_provisioning_status",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clerk_organization_id"),
        sa.UniqueConstraint("clerk_slug"),
        sa.UniqueConstraint("created_by_user_id"),
    )
    op.create_index(
        op.f("ix_workspaces_clerk_organization_id"),
        "workspaces",
        ["clerk_organization_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_workspaces_created_by_user_id"),
        "workspaces",
        ["created_by_user_id"],
        unique=True,
    )

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("clerk_role", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )
    op.create_index(
        op.f("ix_workspace_members_user_id"), "workspace_members", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_workspace_members_workspace_id"),
        "workspace_members",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "brokerage_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("property_sectors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("primary_metro", sa.String(length=120), nullable=False),
        sa.Column("submarkets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("minimum_sqm", sa.Integer(), nullable=False),
        sa.Column("ideal_minimum_sqm", sa.Integer(), nullable=False),
        sa.Column("ideal_maximum_sqm", sa.Integer(), nullable=False),
        sa.Column("maximum_sqm", sa.Integer(), nullable=False),
        sa.Column("industries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prospecting_horizon", sa.String(length=30), nullable=False),
        sa.Column("opportunity_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priorities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.CheckConstraint("minimum_sqm >= 0", name="ck_brokerage_profiles_minimum_sqm"),
        sa.CheckConstraint(
            "minimum_sqm <= ideal_minimum_sqm", name="ck_brokerage_profiles_min_ideal"
        ),
        sa.CheckConstraint(
            "ideal_minimum_sqm <= ideal_maximum_sqm",
            name="ck_brokerage_profiles_ideal_range",
        ),
        sa.CheckConstraint(
            "ideal_maximum_sqm <= maximum_sqm", name="ck_brokerage_profiles_ideal_max"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        op.f("ix_brokerage_profiles_workspace_id"),
        "brokerage_profiles",
        ["workspace_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_brokerage_profiles_workspace_id"), table_name="brokerage_profiles")
    op.drop_table("brokerage_profiles")
    op.drop_index(op.f("ix_workspace_members_workspace_id"), table_name="workspace_members")
    op.drop_index(op.f("ix_workspace_members_user_id"), table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index(op.f("ix_workspaces_created_by_user_id"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_clerk_organization_id"), table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index(op.f("ix_users_clerk_user_id"), table_name="users")
    op.drop_table("users")
