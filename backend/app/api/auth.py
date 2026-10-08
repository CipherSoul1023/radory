from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError
from pydantic import BaseModel

from app.integrations.clerk.verification import ClerkNotConfigured, verify_session_token

router = APIRouter(prefix="/api", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)


def authenticated_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        return verify_session_token(credentials.credentials)
    except (ClerkNotConfigured, PyJWKClientConnectionError) as exc:
        raise HTTPException(503, "Authentication service unavailable") from exc
    except (InvalidTokenError, PyJWKClientError) as exc:
        raise HTTPException(
            401, "Invalid or expired session", headers={"WWW-Authenticate": "Bearer"}
        ) from exc


class IdentityContext(BaseModel):
    user_id: str
    session_id: str
    organization_id: str | None
    organization_role: str | None


@router.get("/me", response_model=IdentityContext)
def me(
    response: Response, claims: Annotated[dict, Depends(authenticated_claims)]
) -> IdentityContext:
    response.headers["Cache-Control"] = "no-store"
    # Clerk v2 puts active organization claims under `o`; retain v1 compatibility.
    organization = claims.get("o")
    if isinstance(organization, dict):
        organization_id = organization.get("id")
        role = organization.get("rol")
        if isinstance(role, str) and not role.startswith("org:"):
            role = f"org:{role}"
    else:
        organization_id = claims.get("org_id")
        role = claims.get("org_role")
    return IdentityContext(
        user_id=claims["sub"],
        session_id=claims["sid"],
        organization_id=organization_id if isinstance(organization_id, str) else None,
        organization_role=role if isinstance(role, str) else None,
    )
