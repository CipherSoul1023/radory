from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.integrations.clerk.organizations import ClerkOrganizationClient, ClerkProvisioningError
from app.models import BrokerageProfile, User, Workspace, WorkspaceMember
from app.schemas import (
    BrokerageProfileResponse,
    BrokerageSetupRequest,
    SetupStatusResponse,
    WorkspaceSetupResponse,
)


class ExistingOrganizationError(RuntimeError):
    pass


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


def _user(db: Session, clerk_user_id: str, claims: dict) -> User:
    user = db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
    if user is None:
        email = claims.get("email")
        user = User(
            clerk_user_id=clerk_user_id,
            email=email if isinstance(email, str) else None,
        )
        db.add(user)
        db.flush()
    return user


def _membership_workspace(db: Session, user_id: uuid.UUID) -> Workspace | None:
    return db.scalar(
        select(Workspace)
        .join(WorkspaceMember)
        .where(
            WorkspaceMember.user_id == user_id,
            Workspace.provisioning_status == "complete",
        )
        .order_by(Workspace.created_at)
    )


def _response(workspace: Workspace) -> WorkspaceSetupResponse:
    if workspace.clerk_organization_id is None:
        raise RuntimeError("Completed workspace has no Clerk organization")
    return WorkspaceSetupResponse(
        workspace_id=str(workspace.id),
        organization_id=workspace.clerk_organization_id,
        organization_name=workspace.name,
    )


def setup_status(db: Session, claims: dict) -> SetupStatusResponse:
    clerk_user_id = claims["sub"]
    user = db.scalar(select(User).where(User.clerk_user_id == clerk_user_id))
    active_org_id, role = claim_organization(claims)

    if active_org_id:
        active_workspace = db.scalar(
            select(Workspace).where(
                Workspace.clerk_organization_id == active_org_id,
                Workspace.provisioning_status == "complete",
            )
        )
        if active_workspace is not None:
            user = user or _user(db, clerk_user_id, claims)
            member = db.scalar(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == active_workspace.id,
                    WorkspaceMember.user_id == user.id,
                )
            )
            if member is None:
                db.add(
                    WorkspaceMember(
                        workspace_id=active_workspace.id, user_id=user.id, clerk_role=role
                    )
                )
                db.commit()
            return SetupStatusResponse(
                status="ready",
                organization_id=active_workspace.clerk_organization_id,
                workspace_id=str(active_workspace.id),
            )

    if user is None:
        return SetupStatusResponse(status="needs_setup")
    existing = _membership_workspace(db, user.id)
    if existing is not None:
        return SetupStatusResponse(
            status="ready",
            organization_id=existing.clerk_organization_id,
            workspace_id=str(existing.id),
        )
    pending = db.scalar(select(Workspace).where(Workspace.created_by_user_id == user.id))
    if pending is not None:
        return SetupStatusResponse(
            status="provisioning",
            organization_id=pending.clerk_organization_id,
            workspace_id=str(pending.id),
        )
    return SetupStatusResponse(status="needs_setup")


def provision_workspace(
    db: Session,
    clerk: ClerkOrganizationClient,
    claims: dict,
    setup: BrokerageSetupRequest,
) -> WorkspaceSetupResponse:
    user = _user(db, claims["sub"], claims)
    existing = _membership_workspace(db, user.id)
    if existing is not None:
        return _response(existing)

    workspace = db.scalar(select(Workspace).where(Workspace.created_by_user_id == user.id))
    if workspace is None:
        active_org_id, _ = claim_organization(claims)
        if active_org_id or clerk.list_user_organization_ids(claims["sub"]):
            raise ExistingOrganizationError(
                "This account already belongs to a Clerk organization and cannot create "
                "another workspace."
            )
        workspace_id = uuid.uuid4()
        workspace = Workspace(
            id=workspace_id,
            clerk_slug=f"radory-{workspace_id.hex}",
            name=setup.brokerage_name,
            created_by_user_id=user.id,
            provisioning_status="pending",
        )
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

    try:
        organization = clerk.create_or_find(
            name=workspace.name,
            slug=workspace.clerk_slug,
            user_id=claims["sub"],
            workspace_id=str(workspace.id),
        )
    except ClerkProvisioningError as exc:
        workspace.provisioning_status = "failed"
        workspace.provisioning_error = str(exc)[:500]
        db.commit()
        raise

    workspace.clerk_organization_id = organization.id
    workspace.provisioning_status = "complete"
    workspace.provisioning_error = None
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if member is None:
        db.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                clerk_role="org:admin",
            )
        )
    profile = db.scalar(
        select(BrokerageProfile).where(BrokerageProfile.workspace_id == workspace.id)
    )
    profile_values = setup.model_dump(exclude={"brokerage_name"})
    if profile is None:
        profile = BrokerageProfile(workspace_id=workspace.id, **profile_values)
        db.add(profile)
    else:
        for key, value in profile_values.items():
            setattr(profile, key, value)
    db.commit()
    db.refresh(workspace)
    return _response(workspace)


def brokerage_profile(db: Session, claims: dict) -> BrokerageProfileResponse | None:
    organization_id, role = claim_organization(claims)
    if not organization_id:
        return None
    workspace = db.scalar(
        select(Workspace)
        .options(joinedload(Workspace.brokerage_profile))
        .where(
            Workspace.clerk_organization_id == organization_id,
            Workspace.provisioning_status == "complete",
        )
    )
    if workspace is None or workspace.brokerage_profile is None:
        return None
    user = _user(db, claims["sub"], claims)
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if member is None:
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, clerk_role=role))
        db.commit()
    profile = workspace.brokerage_profile
    return BrokerageProfileResponse(
        workspace_id=str(workspace.id),
        organization_id=organization_id,
        brokerage_name=workspace.name,
        property_sectors=profile.property_sectors,
        custom_property_sectors=profile.custom_property_sectors,
        country=profile.country,
        primary_market=profile.primary_market,
        submarkets=profile.submarkets,
        custom_submarkets=profile.custom_submarkets,
        min_transaction_size_sqm=profile.min_transaction_size_sqm,
        ideal_transaction_size_min_sqm=profile.ideal_transaction_size_min_sqm,
        ideal_transaction_size_max_sqm=profile.ideal_transaction_size_max_sqm,
        max_transaction_size_sqm=profile.max_transaction_size_sqm,
        industries=profile.industries,
        custom_industries=profile.custom_industries,
        prospecting_horizon=profile.prospecting_horizon,
        opportunity_types=profile.opportunity_types,
        priority_factors=profile.priority_factors,
    )
