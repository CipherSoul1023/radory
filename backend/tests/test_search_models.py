import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SearchJob


def test_database_enforces_one_active_job_per_workspace(search_db: Session, search_workspace: dict):
    profile = search_workspace["profile"]
    values = {
        "workspace_id": search_workspace["workspace"].id,
        "initiated_by_user_id": search_workspace["user"].id,
        "brokerage_profile_id": profile.id,
        "status": "pending",
        "country": profile.country,
        "market": profile.primary_market,
        "configured_submarkets": profile.submarkets,
        "resolved_submarket": profile.submarkets[0],
        "brokerage_profile_updated_at": profile.updated_at,
        "search_context_version": 1,
    }
    search_db.add(SearchJob(id=uuid.uuid4(), **values))
    search_db.commit()
    search_db.add(SearchJob(id=uuid.uuid4(), **values))
    with pytest.raises(IntegrityError):
        search_db.commit()


def test_terminal_job_allows_a_later_active_job(search_db: Session, search_workspace: dict):
    profile = search_workspace["profile"]
    first = SearchJob(
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
        brokerage_profile_id=profile.id,
        status="completed",
        country=profile.country,
        market=profile.primary_market,
        configured_submarkets=profile.submarkets,
        resolved_submarket=profile.submarkets[0],
        brokerage_profile_updated_at=profile.updated_at,
        search_context_version=1,
    )
    second = SearchJob(
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
        brokerage_profile_id=profile.id,
        status="pending",
        country=profile.country,
        market=profile.primary_market,
        configured_submarkets=profile.submarkets,
        resolved_submarket=profile.submarkets[0],
        brokerage_profile_updated_at=profile.updated_at,
        search_context_version=1,
    )
    search_db.add_all([first, second])
    search_db.commit()
    assert first.id != second.id
