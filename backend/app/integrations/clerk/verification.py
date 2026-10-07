import jwt
from jwt import PyJWKClient

from app.core.config import get_settings


class ClerkNotConfigured(RuntimeError):
    pass


def verify_session_token(token: str) -> dict:
    settings = get_settings()
    if not settings.clerk_issuer:
        raise ClerkNotConfigured("CLERK_ISSUER is required for token verification")
    jwks_url = (
        settings.clerk_jwks_url or f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json"
    )
    signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.clerk_issuer,
        audience=settings.clerk_audience or None,
        options={"verify_aud": bool(settings.clerk_audience)},
    )
    if claims.get("azp") != settings.frontend_url:
        raise jwt.InvalidTokenError("Untrusted authorized party")
    return claims
