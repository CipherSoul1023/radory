from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.radar as radar_api
from app.api.auth import authenticated_claims
from app.database.session import get_db_session
from app.main import app
from app.search.investigation import InvestigationDecision, InvestigationExecution


class ConfiguredTavily:
    configured = True


def test_build_returns_one_workspace_owned_job_and_26_queries(
    monkeypatch, search_db: Session, search_workspace: dict
):
    def db_override() -> Generator[Session, None, None]:
        yield search_db

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_search_admin",
        "o": {"id": "org_search", "rol": "admin"},
    }
    monkeypatch.setattr(radar_api, "RadarTavilyClient", ConfiguredTavily)
    monkeypatch.setattr(radar_api, "dispatch_search_queries", lambda **kwargs: 26)
    try:
        client = TestClient(app)
        first = client.post("/api/radar/jobs")
        assert first.status_code == 202
        body = first.json()
        assert body["created"] is True
        assert body["workspace_id"] == str(search_workspace["workspace"].id)
        assert body["configured_submarkets"] == ["Sandton", "Rosebank"]
        assert body["resolved_submarket"] == "Sandton"
        assert body["total_queries"] == 26

        second = client.post("/api/radar/jobs")
        assert second.status_code == 200
        assert second.json()["created"] is False
        assert second.json()["id"] == body["id"]

        status = client.get(f"/api/radar/jobs/{body['id']}")
        assert status.status_code == 200
        assert len(status.json()["queries"]) == 26
    finally:
        app.dependency_overrides.clear()


def test_member_cannot_build_a_radar(monkeypatch, search_db: Session, search_workspace: dict):
    def db_override() -> Generator[Session, None, None]:
        yield search_db

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_search_admin",
        "o": {"id": "org_search", "rol": "member"},
    }
    monkeypatch.setattr(radar_api, "RadarTavilyClient", ConfiguredTavily)
    try:
        response = TestClient(app).post("/api/radar/jobs")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_radar_job_lookup_is_scoped_to_active_workspace(search_db: Session, search_workspace: dict):
    def db_override() -> Generator[Session, None, None]:
        yield search_db

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_search_admin",
        "o": {"id": "org_search", "rol": "member"},
    }
    try:
        response = TestClient(app).get("/api/radar/jobs/00000000-0000-0000-0000-000000000001")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_observations_use_active_workspace_scope(
    monkeypatch, search_db: Session, search_workspace: dict
):
    def db_override() -> Generator[Session, None, None]:
        yield search_db

    captured = {}

    def fake_list(db, *, workspace_id, search_job_id, limit):
        captured.update(
            workspace_id=workspace_id,
            search_job_id=search_job_id,
            limit=limit,
        )
        return []

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_search_admin",
        "o": {"id": "org_search", "rol": "member"},
    }
    monkeypatch.setattr(radar_api, "list_signal_observations", fake_list)
    try:
        response = TestClient(app).get("/api/radar/observations?limit=25")
        assert response.status_code == 200
        assert response.json() == []
        assert captured == {
            "workspace_id": search_workspace["workspace"].id,
            "search_job_id": None,
            "limit": 25,
        }
        assert response.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.clear()


def test_admin_can_request_bounded_observation_investigation(
    monkeypatch, search_db: Session, search_workspace: dict
):
    def db_override() -> Generator[Session, None, None]:
        yield search_db

    observation_id = search_workspace["workspace"].id

    async def fake_investigate(db, *, workspace_id, observation_id):
        assert db is search_db
        assert workspace_id == search_workspace["workspace"].id
        return InvestigationExecution(
            observation_id=observation_id,
            decision=InvestigationDecision(
                outcome="stop",
                rationale="The matching requirement is already complete.",
            ),
            queries=(),
        )

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_search_admin",
        "o": {"id": "org_search", "rol": "admin"},
    }
    monkeypatch.setattr(radar_api, "investigate_observation", fake_investigate)
    try:
        response = TestClient(app).post(f"/api/radar/observations/{observation_id}/investigate")
        assert response.status_code == 200
        assert response.json() == {
            "observation_id": str(observation_id),
            "outcome": "stop",
            "rationale": "The matching requirement is already complete.",
            "queries": [],
        }
        assert response.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.clear()


def opportunity_record(workspace_id):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        search_job_id=uuid4(),
        subject_company="Acme",
        status="completed",
        report={
            "company_name": "Acme",
            "headline": {"text": "Acme is evaluating office space"},
        },
        created_at=now,
        updated_at=now,
    )


def test_opportunity_list_uses_active_workspace_scope(
    monkeypatch, search_db: Session, search_workspace: dict
):
    def db_override() -> Generator[Session, None, None]:
        yield search_db

    captured = {}
    item = opportunity_record(search_workspace["workspace"].id)

    def fake_list(db, *, workspace_id, limit):
        captured.update(db=db, workspace_id=workspace_id, limit=limit)
        return [item]

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_search_admin",
        "o": {"id": "org_search", "rol": "member"},
    }
    monkeypatch.setattr(radar_api, "list_radar_opportunities", fake_list)
    try:
        response = TestClient(app).get("/api/radar/opportunities?limit=25")
        assert response.status_code == 200
        assert response.json()[0]["subject_company"] == "Acme"
        assert captured == {
            "db": search_db,
            "workspace_id": search_workspace["workspace"].id,
            "limit": 25,
        }
    finally:
        app.dependency_overrides.clear()


def test_admin_can_create_opportunity_from_validated_observation(
    monkeypatch, search_db: Session, search_workspace: dict
):
    def db_override() -> Generator[Session, None, None]:
        yield search_db

    observation_id = uuid4()
    item = opportunity_record(search_workspace["workspace"].id)

    async def fake_build(db, *, workspace_id, observation_id):
        assert db is search_db
        assert workspace_id == search_workspace["workspace"].id
        return item, True

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[authenticated_claims] = lambda: {
        "sub": "user_search_admin",
        "o": {"id": "org_search", "rol": "admin"},
    }
    monkeypatch.setattr(radar_api, "build_radar_opportunity", fake_build)
    try:
        response = TestClient(app).post(
            f"/api/radar/opportunities/from-observation/{observation_id}"
        )
        assert response.status_code == 201
        assert response.json()["created"] is True
        assert response.json()["report"]["company_name"] == "Acme"
    finally:
        app.dependency_overrides.clear()
