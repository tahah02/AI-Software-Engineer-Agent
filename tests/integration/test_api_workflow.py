import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.domain.enums import ApprovalGateType, ApprovalStatus
from src.infrastructure.db.models import Base, ProjectORM, WorkflowRunORM, HumanApprovalORM
from src.infrastructure.db.session import get_db


@pytest.fixture
def client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Create dummy project and run
    db = TestingSessionLocal()
    project = ProjectORM(name="API Test Project", target_framework="fastapi")
    db.add(project)
    db.flush()

    run = WorkflowRunORM(project_id=project.id, current_phase="SPECIFICATION", status="RUNNING")
    db.add(run)
    db.flush()

    approval = HumanApprovalORM(
        workflow_run_id=run.id,
        gate_type=ApprovalGateType.SPECIFICATION_APPROVAL.value,
        status=ApprovalStatus.PENDING.value,
        prompt_text="Please approve specs",
    )
    db.add(approval)
    db.commit()

    with TestClient(app) as test_client:
        yield test_client, project.id, run.id, approval.id

    app.dependency_overrides.clear()


def test_start_workflow_api_success(client_with_db):
    client, project_id, _, _ = client_with_db

    resp = client.post(
        "/api/v1/workflow/start",
        json={
            "project_id": str(project_id),
            "user_requirement": "Build user authentication endpoint",
        },
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert "workflow_run_id" in data
    assert data["status"] == "RUNNING"


def test_start_workflow_api_not_found(client_with_db):
    client, _, _, _ = client_with_db

    fake_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/workflow/start",
        json={
            "project_id": fake_id,
            "user_requirement": "Build something",
        },
    )
    assert resp.status_code == 404


def test_resolve_approval_api_success(client_with_db):
    client, _, _, approval_id = client_with_db

    resp = client.post(
        "/api/v1/workflow/approval/resolve",
        json={
            "approval_id": str(approval_id),
            "approved": True,
            "comments": "Approved from UI button",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == ApprovalStatus.APPROVED.value
    assert data["reviewer_comments"] == "Approved from UI button"


def test_workflow_sse_streaming_endpoint(client_with_db):
    client, _, run_id, _ = client_with_db

    resp = client.get(f"/api/v1/workflow/{run_id}/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "data:" in resp.text
