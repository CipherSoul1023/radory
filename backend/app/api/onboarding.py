from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.auth import authenticated_claims
from app.database.session import get_db_session
from app.integrations.clerk.organizations import (
    ClerkOrganizationClient,
    ClerkProvisioningError,
    get_clerk_organization_client,
)
from app.schemas import (
    BrokerageProfileResponse,
    BrokerageSetupRequest,
    SetupStatusResponse,
    WorkspaceSetupResponse,
)
from app.services.onboarding import (
    ExistingOrganizationError,
    brokerage_profile,
    provision_workspace,
    setup_status,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace onboarding"])


@router.get("/setup-status", response_model=SetupStatusResponse)
def get_setup_status(
    response: Response,
    claims: Annotated[dict, Depends(authenticated_claims)],
    db: Annotated[Session, Depends(get_db_session)],
) -> SetupStatusResponse:
    response.headers["Cache-Control"] = "no-store"
    return setup_status(db, claims)


@router.post("/setup", response_model=WorkspaceSetupResponse)
def create_workspace(
    payload: BrokerageSetupRequest,
    response: Response,
    claims: Annotated[dict, Depends(authenticated_claims)],
    db: Annotated[Session, Depends(get_db_session)],
    clerk: Annotated[ClerkOrganizationClient, Depends(get_clerk_organization_client)],
) -> WorkspaceSetupResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        return provision_workspace(db, clerk, claims, payload)
    except ExistingOrganizationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ClerkProvisioningError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/brokerage-profile", response_model=BrokerageProfileResponse)
def get_brokerage_profile(
    response: Response,
    claims: Annotated[dict, Depends(authenticated_claims)],
    db: Annotated[Session, Depends(get_db_session)],
) -> BrokerageProfileResponse:
    response.headers["Cache-Control"] = "no-store"
    profile = brokerage_profile(db, claims)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No brokerage profile exists for this workspace.",
        )
    return profile
