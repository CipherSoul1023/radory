from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.radar as radar_api
from app.api.auth import authenticated_claims
from app.database.session import get_db_session
from app.main import app


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
