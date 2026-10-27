import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import BrokerageProfile, User, Workspace, WorkspaceMember


@pytest.fixture
def search_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def search_workspace(search_db: Session) -> dict:
    user = User(clerk_user_id="user_search_admin", email="admin@example.com")
    search_db.add(user)
    search_db.flush()
    workspace = Workspace(
        clerk_organization_id="org_search",
        clerk_slug="radory-search",
        name="Northstar Tenant Advisory",
        created_by_user_id=user.id,
        provisioning_status="complete",
    )
    search_db.add(workspace)
    search_db.flush()
    search_db.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, clerk_role="org:admin")
    )
    profile = BrokerageProfile(
        workspace_id=workspace.id,
        property_sectors=["office"],
        custom_property_sectors=[],
        country="South Africa",
        primary_market="Johannesburg",
        submarkets=["Sandton", "Rosebank"],
        custom_submarkets=[],
        min_transaction_size_sqm=500,
        ideal_transaction_size_min_sqm=1000,
        ideal_transaction_size_max_sqm=3000,
        max_transaction_size_sqm=6000,
        industries=["technology"],
        custom_industries=[],
        prospecting_horizon="up_to_12_months",
        opportunity_types=["expansion"],
        priority_factors=["location_fit"],
    )
    search_db.add(profile)
    search_db.commit()
    search_db.refresh(user)
    search_db.refresh(workspace)
    search_db.refresh(profile)
    return {"user": user, "workspace": workspace, "profile": profile}
