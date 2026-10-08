from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings


class ClerkNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=4)
def get_jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, timeout=5)


def verify_session_token(token: str) -> dict:
    settings = get_settings()
    if not settings.clerk_issuer:
        raise ClerkNotConfigured("CLERK_ISSUER is required for token verification")
    jwks_url = (
        settings.clerk_jwks_url or f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json"
    )
    signing_key = get_jwks_client(jwks_url).get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.clerk_issuer,
        audience=settings.clerk_audience or None,
        options={
            "verify_aud": bool(settings.clerk_audience),
            "require": ["exp", "iat", "nbf", "iss", "sub", "sid"],
        },
    )
    if claims.get("azp") != settings.frontend_url:
        raise jwt.InvalidTokenError("Untrusted authorized party")
    if not isinstance(claims["sub"], str) or not claims["sub"]:
        raise jwt.InvalidTokenError("Missing user identity")
    if not isinstance(claims["sid"], str) or not claims["sid"]:
        raise jwt.InvalidTokenError("Missing session identity")
    if claims.get("sts") == "pending":
        raise jwt.InvalidTokenError("Session has unfinished tasks")
    return claims
