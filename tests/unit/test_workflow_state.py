import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.workflow_state import WorkflowState
from src.infrastructure.db.models import Base, ProjectORM, WorkflowRunORM, WorkflowCheckpointORM
from src.infrastructure.orchestration.checkpointer import WorkflowCheckpointService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="Workflow State Test Project", target_framework="fastapi")
    session.add(project)
    session.flush()

    run = WorkflowRunORM(project_id=project.id, current_phase="SPECIFICATION", status="RUNNING")
    session.add(run)
    session.commit()

    yield session, project, run
    session.close()


def test_workflow_state_initialization():
    state: WorkflowState = {
        "project_id": str(uuid.uuid4()),
        "workflow_run_id": str(uuid.uuid4()),
        "workspace_path": "/tmp/test",
        "target_framework": "fastapi",
        "user_requirement": "Build a secure payment endpoint",
        "enabled_agents": {
            "DOC_REVIEWER": True,
            "MOCK_DEVELOPER": False,
            "MAIN_CODING": True,
            "QA_ENGINEER": True,
            "SECURITY_REVIEWER": False,
        },
        "qa_status": "SKIPPED",
        "security_status": "NOT_SCANNED",
        "active_defects": [],
        "defect_remediation_count": 0,
        "spec_approved": False,
        "release_approved": False,
        "current_phase": "SPECIFICATION",
        "iteration": 1,
        "is_completed": False,
    }

    assert state["target_framework"] == "fastapi"
    assert state["enabled_agents"]["MOCK_DEVELOPER"] is False
    assert state["qa_status"] == "SKIPPED"
    assert state["security_status"] == "NOT_SCANNED"


def test_checkpoint_service_save_and_load(db_session):
    session, project, run = db_session
    service = WorkflowCheckpointService(db=session)

    test_state: WorkflowState = {
        "project_id": str(project.id),
        "workflow_run_id": str(run.id),
        "workspace_path": "/workspace/proj1",
        "target_framework": "fastapi",
        "user_requirement": "Create user auth",
        "enabled_agents": {"DOC_REVIEWER": True, "MAIN_CODING": True},
        "tdd_path": "docs/TECHNICAL_DESIGN.md",
        "current_phase": "SPEC_APPROVAL",
        "spec_approved": False,
        "iteration": 1,
    }

    checkpoint = service.save_checkpoint(
        workflow_run_id=run.id,
        checkpoint_key="spec_generation_complete",
        state=test_state,
        version=1,
    )
    session.commit()

    assert checkpoint.id is not None
    assert checkpoint.checkpoint_key == "spec_generation_complete"

    loaded_state = service.load_checkpoint(
        workflow_run_id=run.id,
        checkpoint_key="spec_generation_complete",
        version=1,
    )
    assert loaded_state is not None
    assert loaded_state["current_phase"] == "SPEC_APPROVAL"
    assert loaded_state["tdd_path"] == "docs/TECHNICAL_DESIGN.md"
    assert loaded_state["enabled_agents"]["DOC_REVIEWER"] is True
