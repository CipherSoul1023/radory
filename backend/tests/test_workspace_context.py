import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WorkspaceMember
from app.services.workspace_context import (
    ActiveOrganizationRequired,
    WorkspaceUnavailable,
    resolve_current_workspace,
)


def test_context_uses_exact_active_clerk_organization_and_syncs_role(
    search_db: Session, search_workspace: dict
):
    context = resolve_current_workspace(
        search_db,
        {"sub": "user_search_admin", "o": {"id": "org_search", "rol": "member"}},
    )
    assert context.workspace.id == search_workspace["workspace"].id
    assert context.clerk_role == "org:member"
    member = search_db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == context.workspace.id,
            WorkspaceMember.user_id == context.user.id,
        )
    )
    assert member.clerk_role == "org:member"


def test_context_never_falls_back_without_an_active_organization(
    search_db: Session, search_workspace: dict
):
    with pytest.raises(ActiveOrganizationRequired):
        resolve_current_workspace(search_db, {"sub": "user_search_admin"})


def test_context_rejects_unknown_active_organization(search_db: Session, search_workspace: dict):
    with pytest.raises(WorkspaceUnavailable):
        resolve_current_workspace(
            search_db,
            {"sub": "user_search_admin", "o": {"id": "org_other", "rol": "admin"}},
        )
