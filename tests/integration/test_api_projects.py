import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import create_app
from src.infrastructure.db.models import Base, ProjectORM
from src.infrastructure.db.session import get_db


@pytest.fixture
def in_memory_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    # Seed test project
    db = TestingSessionLocal()
    proj_id = uuid.uuid4()
    proj = ProjectORM(id=proj_id, name="Test Bank App", target_framework="PYTHON_FASTAPI", status="ACTIVE")
    db.add(proj)
    db.commit()
    db.close()

    client = TestClient(app)
    return client, proj_id


def test_get_and_update_project_agents(in_memory_client):
    client, proj_id = in_memory_client

    # 1. GET defaults
    resp = client.get(f"/api/v1/projects/{proj_id}/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["agents"]) == 5
    assert data["agents"][0]["agent_type"] == "AGENT_1"
    assert data["agents"][0]["is_mandatory"] is True

    # 2. UPDATE toggles (disable agent 2 and agent 5)
    update_payload = {
        "agent2_enabled": False,
        "agent4_enabled": True,
        "agent5_enabled": False,
    }
    update_resp = client.put(f"/api/v1/projects/{proj_id}/agents", json=update_payload)
    assert update_resp.status_code == 200
    updated_data = update_resp.json()

    agent_map = {a["agent_type"]: a["is_enabled"] for a in updated_data["agents"]}
    assert agent_map["AGENT_2"] is False
    assert agent_map["AGENT_4"] is True
    assert agent_map["AGENT_5"] is False
    assert agent_map["AGENT_1"] is True
    assert agent_map["AGENT_3"] is True


def test_get_nonexistent_project_returns_404(in_memory_client):
    client, _ = in_memory_client
    fake_id = uuid.uuid4()
    resp = client.get(f"/api/v1/projects/{fake_id}/agents")
    assert resp.status_code == 404

