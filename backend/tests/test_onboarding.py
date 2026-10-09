import json
from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import authenticated_claims
from app.database.base import Base
from app.database.session import get_db_session
from app.integrations.clerk.organizations import (
    ClerkOrganization,
    ClerkOrganizationClient,
    ClerkProvisioningError,
    get_clerk_organization_client,
)
from app.main import app
from app.models import BrokerageProfile, User, Workspace, WorkspaceMember

SETUP = {
    "brokerage_name": "Northstar Tenant Advisory",
    "property_sectors": ["Office", "Industrial / Logistics"],
    "country": "South Africa",
    "primary_metro": "Johannesburg",
    "submarkets": ["Sandton", "Rosebank"],
    "minimum_sqm": 500,
    "ideal_minimum_sqm": 1500,
    "ideal_maximum_sqm": 4000,
    "maximum_sqm": 8000,
    "industries": ["Technology", "Financial services"],
    "prospecting_horizon": "6–12 months",
    "opportunity_types": ["Expansion", "Relocation"],
    "priorities": ["opportunity:Expansion", "submarket:Sandton"],
}


def test_clerk_client_uses_backend_api_creator_and_recovery_metadata():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404, json={})
        payload = json.loads(request.content)
        assert payload == {
            "name": "Northstar Tenant Advisory",
            "slug": "radory-workspace",
            "created_by": "user_onboarding",
            "max_allowed_memberships": 5,
            "private_metadata": {"radory_workspace_id": "workspace-id"},
        }
        assert request.headers["authorization"] == "Bearer test_secret"
        return httpx.Response(
            200,
            json={
                "id": "org_radory",
                "name": payload["name"],
                "slug": payload["slug"],
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.clerk.com/v1"
    ) as http_client:
        client = ClerkOrganizationClient(secret_key="test_secret", http_client=http_client)
        organization = client.create_or_find(
            name="Northstar Tenant Advisory",
            slug="radory-workspace",
            user_id="user_onboarding",
            workspace_id="workspace-id",
        )
    assert organization.id == "org_radory"
    assert [request.method for request in requests] == ["GET", "POST"]


def test_clerk_client_recovers_an_org_created_by_an_interrupted_request():
    get_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal get_calls
        if request.method == "GET":
            get_calls += 1
            if get_calls == 1:
                return httpx.Response(404, json={})
            return httpx.Response(
                200,
                json={
                    "id": "org_recovered",
                    "name": "Recovered Brokerage",
                    "slug": "radory-recovery",
                    "private_metadata": {"radory_workspace_id": "workspace-id"},
                },
            )
        return httpx.Response(422, json={"errors": [{"code": "form_identifier_exists"}]})

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.clerk.com/v1"
    ) as http_client:
        client = ClerkOrganizationClient(secret_key="test_secret", http_client=http_client)
        organization = client.create_or_find(
            name="Recovered Brokerage",
            slug="radory-recovery",
            user_id="user_onboarding",
            workspace_id="workspace-id",
        )
    assert organization.id == "org_recovered"
    assert get_calls == 2


class FakeClerk:
    def __init__(self, memberships: list[str] | None = None):
        self.memberships = memberships or []
        self.created: list[dict[str, str]] = []

    def list_user_organization_ids(self, user_id: str) -> list[str]:
        assert user_id == "user_onboarding"
        return self.memberships

    def create_or_find(self, **kwargs: str) -> ClerkOrganization:
        self.created.append(kwargs)
        assert kwargs["user_id"] == "user_onboarding"
        assert kwargs["slug"].startswith("radory-")
        assert kwargs["workspace_id"]
        return ClerkOrganization(id="org_radory", name=kwargs["name"], slug=kwargs["slug"])


@pytest.fixture
def onboarding_client() -> Generator[
    tuple[TestClient, sessionmaker[Session], FakeClerk], None, None
]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    clerk = FakeClerk()

    def db_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_onboarding",
        "sid": "session_onboarding",
    }
    app.dependency_overrides[get_clerk_organization_client] = lambda: clerk
    try:
        yield TestClient(app), factory, clerk
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_setup_creates_clerk_org_and_persists_profile_idempotently(onboarding_client):
    client, factory, clerk = onboarding_client

    initial = client.get("/api/workspace/setup-status")
    assert initial.status_code == 200
    assert initial.json()["status"] == "needs_setup"

    first = client.post("/api/workspace/setup", json=SETUP)
    assert first.status_code == 200
    assert first.json()["organization_id"] == "org_radory"
    assert len(clerk.created) == 1

    second = client.post("/api/workspace/setup", json=SETUP)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(clerk.created) == 1

    with factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Workspace)) == 1
        assert db.scalar(select(func.count()).select_from(WorkspaceMember)) == 1
        assert db.scalar(select(func.count()).select_from(BrokerageProfile)) == 1

    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_onboarding",
        "sid": "session_onboarding",
        "o": {"id": "org_radory", "rol": "admin"},
    }
    profile = client.get("/api/workspace/brokerage-profile")
    assert profile.status_code == 200
    assert profile.json()["brokerage_name"] == SETUP["brokerage_name"]
    assert profile.json()["submarkets"] == SETUP["submarkets"]


def test_existing_clerk_membership_cannot_create_another_workspace(onboarding_client):
    client, factory, clerk = onboarding_client
    clerk.memberships = ["org_existing"]
    response = client.post("/api/workspace/setup", json=SETUP)
    assert response.status_code == 409
    assert clerk.created == []
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Workspace)) == 0


def test_failed_clerk_call_reuses_pending_workspace_on_retry(onboarding_client):
    client, factory, clerk = onboarding_client
    original_create = clerk.create_or_find
    calls = 0

    def fail_once(**kwargs: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ClerkProvisioningError("Clerk temporarily unavailable")
        return original_create(**kwargs)

    clerk.create_or_find = fail_once  # type: ignore[method-assign]
    failed = client.post("/api/workspace/setup", json=SETUP)
    assert failed.status_code == 502
    with factory() as db:
        assert db.scalar(select(Workspace.provisioning_status)) == "failed"
    retried = client.post("/api/workspace/setup", json=SETUP)
    assert retried.status_code == 200
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Workspace)) == 1


def test_active_invited_member_is_mirrored_without_onboarding(onboarding_client):
    client, factory, _ = onboarding_client
    with factory() as db:
        creator = User(clerk_user_id="creator")
        db.add(creator)
        db.flush()
        workspace = Workspace(
            clerk_organization_id="org_invited",
            clerk_slug="invited-workspace",
            name="Existing Brokerage",
            created_by_user_id=creator.id,
            provisioning_status="complete",
        )
        db.add(workspace)
        db.commit()

    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_onboarding",
        "sid": "session_onboarding",
        "o": {"id": "org_invited", "rol": "member"},
    }
    response = client.get("/api/workspace/setup-status")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    with factory() as db:
        member = db.scalar(
            select(WorkspaceMember).where(WorkspaceMember.clerk_role == "org:member")
        )
        assert member is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"industries": ["Any industry", "Technology"]},
        {"priorities": ["one", "two", "three", "four"]},
        {"minimum_sqm": 9000},
        {"property_sectors": ["Residential"]},
        {"priorities": ["industry:Unselected industry"]},
    ],
)
def test_setup_validation_rejects_invalid_profiles(onboarding_client, changes):
    client, _, clerk = onboarding_client
    response = client.post("/api/workspace/setup", json=SETUP | changes)
    assert response.status_code == 422
    assert clerk.created == []
