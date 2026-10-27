from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember


class ActiveOrganizationRequired(RuntimeError):
    pass


class WorkspaceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedWorkspaceContext:
    user: User
    workspace: Workspace
    clerk_organization_id: str
    clerk_role: str


def claim_organization(claims: dict) -> tuple[str | None, str]:
    organization = claims.get("o")
    if isinstance(organization, dict):
        organization_id = organization.get("id")
        role = organization.get("rol", "member")
        if isinstance(role, str) and not role.startswith("org:"):
            role = f"org:{role}"
    else:
        organization_id = claims.get("org_id")
        role = claims.get("org_role", "org:member")
    return (
        organization_id if isinstance(organization_id, str) else None,
        role if isinstance(role, str) else "org:member",
    )


def get_or_create_user(db: Session, clerk_user_id: str, claims: dict) -> User:
    user = db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
    if user is not None:
        return user
    email = claims.get("email")
    try:
        with db.begin_nested():
            user = User(
                clerk_user_id=clerk_user_id,
                email=email if isinstance(email, str) else None,
            )
            db.add(user)
            db.flush()
    except IntegrityError:
        user = db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
        if user is None:
            raise
    return user


def resolve_current_workspace(db: Session, claims: dict) -> ResolvedWorkspaceContext:
    organization_id, role = claim_organization(claims)
    if organization_id is None:
        raise ActiveOrganizationRequired("An active Clerk organization is required")
    workspace = db.scalar(
        select(Workspace).where(
            Workspace.clerk_organization_id == organization_id,
            Workspace.provisioning_status == "complete",
        )
    )
    if workspace is None:
        raise WorkspaceUnavailable("The active organization has no ready Radory workspace")

    user = get_or_create_user(db, claims["sub"], claims)
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
        )
    )
    changed = False
    if member is None:
        try:
            with db.begin_nested():
                member = WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    clerk_role=role,
                )
                db.add(member)
                db.flush()
            changed = True
        except IntegrityError:
            member = db.scalar(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace.id,
                    WorkspaceMember.user_id == user.id,
                )
            )
            if member is None:
                raise
    if member.clerk_role != role:
        member.clerk_role = role
        changed = True
    if changed or user in db.new:
        db.commit()

    return ResolvedWorkspaceContext(
        user=user,
        workspace=workspace,
        clerk_organization_id=organization_id,
        clerk_role=role,
    )
