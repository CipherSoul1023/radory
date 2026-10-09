"""Remove unique constraints duplicated by unique indexes.

Revision ID: 0003_unique_cleanup
Revises: 0002_workspace_onboarding
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_unique_cleanup"
down_revision: str | None = "0002_workspace_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "brokerage_profiles_workspace_id_key",
        "brokerage_profiles",
        type_="unique",
    )
    op.drop_constraint("users_clerk_user_id_key", "users", type_="unique")
    op.drop_constraint(
        "workspaces_clerk_organization_id_key",
        "workspaces",
        type_="unique",
    )
    op.drop_constraint(
        "workspaces_created_by_user_id_key",
        "workspaces",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "workspaces_created_by_user_id_key",
        "workspaces",
        ["created_by_user_id"],
    )
    op.create_unique_constraint(
        "workspaces_clerk_organization_id_key",
        "workspaces",
        ["clerk_organization_id"],
    )
    op.create_unique_constraint("users_clerk_user_id_key", "users", ["clerk_user_id"])
    op.create_unique_constraint(
        "brokerage_profiles_workspace_id_key",
        "brokerage_profiles",
        ["workspace_id"],
    )
