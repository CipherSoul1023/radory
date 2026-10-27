from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import authenticated_claims
from app.database.session import get_db_session
from app.services.workspace_context import (
    ActiveOrganizationRequired,
    ResolvedWorkspaceContext,
    WorkspaceUnavailable,
    resolve_current_workspace,
)


def current_workspace_context(
    claims: Annotated[dict, Depends(authenticated_claims)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ResolvedWorkspaceContext:
    try:
        return resolve_current_workspace(db, claims)
    except ActiveOrganizationRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WorkspaceUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def current_workspace_admin(
    context: Annotated[ResolvedWorkspaceContext, Depends(current_workspace_context)],
) -> ResolvedWorkspaceContext:
    if context.clerk_role != "org:admin":
        raise HTTPException(status_code=403, detail="Workspace administrator access required")
    return context
