import sys
import tempfile
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool
from src.api.main import create_app
from src.domain.enums import RepositoryType
from src.infrastructure.db.models import Base, ProjectORM, GitRepositoryORM
from src.infrastructure.db.session import get_db
from src.infrastructure.execution.process_manager import ProjectProcessManager


@pytest.fixture
def runner_test_client():
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
    client = TestClient(app)

    yield client, TestingSessionLocal

    app.dependency_overrides.clear()


def test_run_project_not_found(runner_test_client):
    client, _ = runner_test_client
    fake_id = uuid.uuid4()
    resp = client.post(f"/api/v1/projects/{fake_id}/run")
    assert resp.status_code == 404


def test_run_project_directory_missing(runner_test_client):
    client, SessionLocal = runner_test_client
    project_id = uuid.uuid4()
    db = SessionLocal()
    project = ProjectORM(
        id=project_id,
        name="Empty Project",
        target_framework="PYTHON_FASTAPI",
        status="ACTIVE",
    )
    db.add(project)
    db.commit()
    db.close()

    resp = client.post(f"/api/v1/projects/{project_id}/run")
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]


def test_project_runner_lifecycle_and_endpoints(runner_test_client, tmp_path):
    client, SessionLocal = runner_test_client
    project_id = uuid.uuid4()
    db = SessionLocal()
    project = ProjectORM(
        id=project_id,
        name="Executable Python App",
        target_framework="PYTHON_FASTAPI",
        status="ACTIVE",
    )
    db.add(project)
    db.commit()
    db.close()

    # Create fake synthesized channel-app workspace
    mgr = ProjectProcessManager.get_instance(base_workspace_dir=str(tmp_path))
    mgr.base_workspace_dir = tmp_path
    channel_dir = tmp_path / str(project_id) / "channel-app"
    channel_dir.mkdir(parents=True, exist_ok=True)

    # Simple python script simulating web service
    (channel_dir / "main.py").write_text(
        "import time, sys\n"
        "print('Service started on port', sys.argv)\n"
        "sys.stdout.flush()\n"
        "time.sleep(10)\n",
        encoding="utf-8",
    )

    # 1. Run Project Endpoint
    run_resp = client.post(f"/api/v1/projects/{project_id}/run")
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["status"] == "RUNNING"
    assert "info" in run_data
    assert run_data["info"]["port"] > 0
    assert run_data["info"]["pid"] > 0

    # 2. Check Status Endpoint
    status_resp = client.get(f"/api/v1/projects/{project_id}/status?subsystem=channel-app")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == "RUNNING"
    assert status_data["pid"] == run_data["info"]["pid"]

    # 3. Check Logs Endpoint
    logs_resp = client.get(f"/api/v1/projects/{project_id}/logs?subsystem=channel-app")
    assert logs_resp.status_code == 200
    assert "logs" in logs_resp.json()

    # 4. Stop Project Endpoint
    stop_resp = client.post(f"/api/v1/projects/{project_id}/stop")
    assert stop_resp.status_code == 200
    stop_data = stop_resp.json()
    assert stop_data["status"] == "STOPPED"

    # 5. Verify Stopped Status
    after_status = client.get(f"/api/v1/projects/{project_id}/status?subsystem=channel-app")
    assert after_status.json()["status"] == "STOPPED"


def test_chat_command_run_and_stop_intent(runner_test_client, tmp_path):
    client, SessionLocal = runner_test_client
    project_id = uuid.uuid4()
    db = SessionLocal()
    project = ProjectORM(
        id=project_id,
        name="Chat Trigger Project",
        target_framework="PYTHON_FASTAPI",
        status="ACTIVE",
    )
    db.add(project)
    db.commit()
    db.close()

    mgr = ProjectProcessManager.get_instance(base_workspace_dir=str(tmp_path))
    mgr.base_workspace_dir = tmp_path
    channel_dir = tmp_path / str(project_id) / "channel-app"
    channel_dir.mkdir(parents=True, exist_ok=True)
    (channel_dir / "main.py").write_text("import time\ntime.sleep(10)\n", encoding="utf-8")

    # 1. Send "run project" chat command
    chat_run = client.post(
        "/api/v1/workflow/start",
        json={"project_id": str(project_id), "user_requirement": "run project please"},
    )
    assert chat_run.status_code == 200
    chat_run_data = chat_run.json()
    assert chat_run_data["status"] == "RUNNING"
    assert "Project Started Successfully" in chat_run_data["assistant_reply"]
    assert "http://localhost:" in chat_run_data["assistant_reply"]

    # 2. Send "stop project" chat command
    chat_stop = client.post(
        "/api/v1/workflow/start",
        json={"project_id": str(project_id), "user_requirement": "chalo stop project now"},
    )
    assert chat_stop.status_code == 200
    chat_stop_data = chat_stop.json()
    assert chat_stop_data["status"] == "STOPPED"
    assert "Project Execution Stopped" in chat_stop_data["assistant_reply"]
