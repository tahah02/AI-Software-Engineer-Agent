import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.infrastructure.db.models import (
    Base,
    ProjectORM,
    ProjectAgentConfigORM,
    ProjectFileORM,
    ConversationORM,
    MessageORM,
    WorkflowRunORM,
    HumanApprovalORM,
    TestCaseORM,
    TestRunORM,
    TestResultORM,
    DefectORM,
    SecurityScanORM,
    SecurityFindingORM,
)


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_project_with_agent_config(in_memory_session: Session):
    project_id = uuid.uuid4()
    project = ProjectORM(
        id=project_id,
        name="Beneficiary Management System",
        description="Core banking integration service",
        target_framework="python",
        status="ACTIVE",
    )
    agent_config = ProjectAgentConfigORM(
        project_id=project_id,
        agent_type="Agent 1: Documentation Reviewer",
        is_enabled=True,
        provider="gemini",
        model_name="gemini-3.8-flash",
    )
    in_memory_session.add(project)
    in_memory_session.add(agent_config)
    in_memory_session.commit()

    saved = in_memory_session.scalar(select(ProjectORM).where(ProjectORM.id == project_id))
    assert saved is not None
    assert saved.name == "Beneficiary Management System"
    assert len(saved.agent_configs) == 1
    assert saved.agent_configs[0].agent_type == "Agent 1: Documentation Reviewer"
    assert saved.agent_configs[0].is_enabled is True


def test_project_cascade_delete(in_memory_session: Session):
    project_id = uuid.uuid4()
    project = ProjectORM(
        id=project_id,
        name="Temp Project",
        target_framework="nodejs",
        status="ACTIVE",
    )
    conv = ConversationORM(
        project_id=project_id,
        title="Main Chat",
    )
    in_memory_session.add(project)
    in_memory_session.add(conv)
    in_memory_session.commit()

    msg = MessageORM(
        conversation_id=conv.id,
        sender_type="USER",
        content="Hello AAISE",
    )
    in_memory_session.add(msg)
    in_memory_session.commit()

    in_memory_session.delete(project)
    in_memory_session.commit()

    assert in_memory_session.scalar(select(ProjectORM).where(ProjectORM.id == project_id)) is None
    assert in_memory_session.scalar(select(ConversationORM).where(ConversationORM.id == conv.id)) is None
    assert in_memory_session.scalar(select(MessageORM).where(MessageORM.id == msg.id)) is None


def test_test_run_and_result_relationship(in_memory_session: Session):
    project_id = uuid.uuid4()
    project = ProjectORM(
        id=project_id,
        name="QA Project",
        target_framework="dotnet",
    )
    test_case = TestCaseORM(
        project_id=project_id,
        test_key="TC-001",
        category="POSITIVE",
        endpoint="/api/v1/health",
        http_method="GET",
        expected_status=200,
    )
    test_run = TestRunORM(
        project_id=project_id,
        execution_type="BLACK_BOX_HTTP",
        passed_count=1,
        failed_count=0,
        status="PASSED",
    )
    in_memory_session.add(project)
    in_memory_session.add(test_case)
    in_memory_session.add(test_run)
    in_memory_session.commit()

    result = TestResultORM(
        test_run_id=test_run.id,
        test_case_id=test_case.id,
        status="PASSED",
        actual_status_code=200,
    )
    in_memory_session.add(result)
    in_memory_session.commit()

    saved_run = in_memory_session.scalar(select(TestRunORM).where(TestRunORM.id == test_run.id))
    assert saved_run is not None
    assert len(saved_run.results) == 1
    assert saved_run.results[0].actual_status_code == 200


def test_workflow_checkpoint_unique_constraint(in_memory_session: Session):
    project_id = uuid.uuid4()
    project = ProjectORM(id=project_id, name="P1", target_framework="python")
    run = WorkflowRunORM(project_id=project_id, current_phase="SPECIFICATION")
    in_memory_session.add(project)
    in_memory_session.add(run)
    in_memory_session.commit()

    from src.infrastructure.db.models import WorkflowCheckpointORM, WorkflowEventORM
    cp1 = WorkflowCheckpointORM(
        workflow_run_id=run.id,
        checkpoint_key="agent1_tdd_complete",
        state_data='{"step": 1}',
        version=1,
    )
    in_memory_session.add(cp1)
    in_memory_session.commit()

    # Verify auto-increment on WorkflowEventORM
    ev1 = WorkflowEventORM(workflow_run_id=run.id, event_type="CHECKPOINT", event_payload="{}")
    ev2 = WorkflowEventORM(workflow_run_id=run.id, event_type="CHECKPOINT", event_payload="{}")
    in_memory_session.add_all([ev1, ev2])
    in_memory_session.commit()
    assert ev1.id is not None
    assert ev2.id == ev1.id + 1

    # Verify duplicate checkpoint version fails
    from sqlalchemy.exc import IntegrityError
    cp_dup = WorkflowCheckpointORM(
        workflow_run_id=run.id,
        checkpoint_key="agent1_tdd_complete",
        state_data='{"step": 1}',
        version=1,
    )
    in_memory_session.add(cp_dup)
    with pytest.raises(IntegrityError):
        in_memory_session.commit()
    in_memory_session.rollback()

