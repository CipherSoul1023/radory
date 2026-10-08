import time
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.clerk import verification
from app.main import app


@pytest.fixture
def auth_context(monkeypatch):
    # All credentials and signing keys here are ephemeral, local test fixtures.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(
        _env_file=None,
        clerk_issuer="https://identity.example.test",
        frontend_url="http://localhost:5173",
        clerk_audience="",
    )
    monkeypatch.setattr(verification, "get_settings", lambda: settings)
    jwks = Mock()
    jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key=private_key.public_key())
    monkeypatch.setattr(verification, "get_jwks_client", lambda _: jwks)
    now = int(time.time())
    claims = {
        "iss": settings.clerk_issuer,
        "azp": settings.frontend_url,
        "sub": "user_test",
        "sid": "sess_test",
        "iat": now,
        "nbf": now - 5,
        "exp": now + 60,
    }
    return private_key, claims, settings, jwks


def request_with_token(key, claims, **kwargs):
    token = jwt.encode(claims, key, algorithm="RS256")
    return TestClient(app).get(
        "/api/me?user_id=user_forged&organization_id=org_forged",
        headers={"Authorization": f"Bearer {token}"},
        **kwargs,
    )


def test_missing_token_rejected():
    response = TestClient(app).get("/api/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("authorization", ["Basic abc", "Bearer malformed", "Bearer "])
def test_invalid_authorization(auth_context, authorization):
    response = TestClient(app).get("/api/me", headers={"Authorization": authorization})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": 1},
        {"nbf": 9999999999},
        {"iat": 9999999999},
        {"iss": "https://untrusted.example.test"},
        {"azp": "https://untrusted.example.test"},
        {"sub": ""},
        {"sid": ""},
        {"sid": 10},
        {"sts": "pending"},
    ],
)
def test_invalid_claims_rejected(auth_context, changes):
    key, claims, _, _ = auth_context
    assert request_with_token(key, claims | changes).status_code == 401


@pytest.mark.parametrize("missing", ["exp", "iat", "nbf", "iss", "sub", "sid", "azp"])
def test_required_claims(auth_context, missing):
    key, claims, _, _ = auth_context
    claims.pop(missing)
    assert request_with_token(key, claims).status_code == 401


def test_wrong_signature_rejected(auth_context):
    _, claims, _, _ = auth_context
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert request_with_token(wrong_key, claims).status_code == 401


def test_algorithm_confusion_rejected(auth_context):
    _, claims, _, _ = auth_context
    token = jwt.encode(claims, "local-test-signing-material-only-123456", algorithm="HS256")
    response = TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "organization_claims,expected_id,expected_role",
    [
        ({}, None, None),
        ({"o": {"id": "org_test", "rol": "admin"}}, "org_test", "org:admin"),
        ({"org_id": "org_old", "org_role": "org:member"}, "org_old", "org:member"),
    ],
)
def test_verified_identity_only(auth_context, organization_claims, expected_id, expected_role):
    key, claims, _, _ = auth_context
    response = request_with_token(key, claims | organization_claims | {"unsafe_metadata": "hidden"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "user_id": "user_test",
        "session_id": "sess_test",
        "organization_id": expected_id,
        "organization_role": expected_role,
    }


def test_configured_audience_checked(auth_context):
    key, claims, settings, _ = auth_context
    settings.clerk_audience = "radory-api"
    assert request_with_token(key, claims).status_code == 401
    assert request_with_token(key, claims | {"aud": "other-api"}).status_code == 401
    assert request_with_token(key, claims | {"aud": "radory-api"}).status_code == 200


def test_jwks_unavailable_is_safe_503(auth_context):
    key, claims, _, jwks = auth_context
    jwks.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientConnectionError("private details")
    response = request_with_token(key, claims)
    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}


def test_missing_configuration_is_safe_503(auth_context):
    key, claims, settings, _ = auth_context
    settings.clerk_issuer = ""
    assert request_with_token(key, claims).status_code == 503
