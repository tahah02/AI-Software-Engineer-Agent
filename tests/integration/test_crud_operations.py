import os
import uuid

import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from src.infrastructure.db.models import (
    ProjectORM,
    ProjectAgentConfigORM,
    ConversationORM,
    MessageORM,
    WorkflowRunORM,
    WorkflowCheckpointORM,
    HumanApprovalORM,
    GitReleaseManifestORM,
    TestRunORM,
    SecurityScanORM,
    SecurityFindingORM,
)


@pytest.fixture(scope="module")
def temp_db_session():
    db_path = os.path.abspath("./data/test_crud_temp.db")
    db_url = f"sqlite:///{db_path.replace(os.sep, '/')}"

    if os.path.exists(db_path):
        os.remove(db_path)

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(Engine, "connect")
    def _set_fk(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    with session_factory() as session:
        yield session

    engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_crud_temp_db_schema(temp_db_session: Session):
    result = temp_db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    ).fetchall()
    table_names = {r[0] for r in result}
    assert "alembic_version" in table_names
    app_tables = table_names - {"alembic_version"}
    assert len(app_tables) == 22

    rev = temp_db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert rev == "fff15a5af7f9"


def test_crud_project_with_all_five_agent_configs(temp_db_session: Session):
    project_id = uuid.uuid4()
    project = ProjectORM(
        id=project_id,
        name="Beneficiary Management System",
        target_framework="python",
        status="ACTIVE",
    )
    temp_db_session.add(project)

    agent_defaults = [
        ("Agent 1: Documentation Reviewer", "gemini", "gemini-3.8-flash", True),
        ("Agent 2: Mock Vendor API Developer", "groq", "openai/gpt-oss-120b", False),
        ("Agent 3: Main Coding Agent", "ollama", "qwen2.5-coder:7b", True),
        ("Agent 4: Independent QA Engineer", "groq", "qwen/qwen3.8-27b", False),
        ("Agent 5: Security Reviewer", "gemini", "gemini-3.5-flash-lite", True),
    ]
    for agent_type, provider, model_name, is_enabled in agent_defaults:
        temp_db_session.add(ProjectAgentConfigORM(
            project_id=project_id,
            agent_type=agent_type,
            provider=provider,
            model_name=model_name,
            is_enabled=is_enabled,
        ))
    temp_db_session.commit()

    saved = temp_db_session.get(ProjectORM, project_id)
    assert saved is not None
    assert len(saved.agent_configs) == 5

    enabled = [c for c in saved.agent_configs if c.is_enabled]
    disabled = [c for c in saved.agent_configs if not c.is_enabled]
    assert len(enabled) == 3
    assert len(disabled) == 2

    disabled_types = {c.agent_type for c in disabled}
    assert "Agent 2: Mock Vendor API Developer" in disabled_types
    assert "Agent 4: Independent QA Engineer" in disabled_types


def test_crud_agent_config_unique_constraint(temp_db_session: Session):
    project_id = uuid.uuid4()
    temp_db_session.add(ProjectORM(id=project_id, name="Dupe Test Project", target_framework="nodejs"))
    temp_db_session.commit()

    temp_db_session.add(ProjectAgentConfigORM(
        project_id=project_id,
        agent_type="Agent 1: Documentation Reviewer",
        provider="gemini",
        model_name="gemini-3.8-flash",
        is_enabled=True,
    ))
    temp_db_session.commit()

    temp_db_session.add(ProjectAgentConfigORM(
        project_id=project_id,
        agent_type="Agent 1: Documentation Reviewer",
        provider="groq",
        model_name="llama3",
        is_enabled=True,
    ))
    with pytest.raises(IntegrityError):
        temp_db_session.commit()
    temp_db_session.rollback()


def test_crud_conversation_and_messages(temp_db_session: Session):
    project_id = uuid.uuid4()
    temp_db_session.add(ProjectORM(id=project_id, name="Chat Project", target_framework="dotnet"))
    temp_db_session.commit()

    conv = ConversationORM(project_id=project_id, title="Main Engineering Chat")
    temp_db_session.add(conv)
    temp_db_session.commit()

    messages = [
        MessageORM(conversation_id=conv.id, sender_type="USER", content="Generate TDD for payment module."),
        MessageORM(conversation_id=conv.id, sender_type="AGENT", agent_id="Agent 1", content="TDD generated successfully."),
        MessageORM(conversation_id=conv.id, sender_type="ORCHESTRATOR", content="Awaiting user approval."),
    ]
    temp_db_session.add_all(messages)
    temp_db_session.commit()

    reloaded = temp_db_session.get(ConversationORM, conv.id)
    assert reloaded is not None
    assert len(reloaded.messages) == 3
    assert reloaded.messages[1].agent_id == "Agent 1"


def test_crud_workflow_run_checkpoints_and_approvals(temp_db_session: Session):
    project_id = uuid.uuid4()
    temp_db_session.add(ProjectORM(id=project_id, name="Workflow Project", target_framework="python"))
    temp_db_session.commit()

    run = WorkflowRunORM(project_id=project_id, current_phase="SPECIFICATION", iteration_count=0)
    temp_db_session.add(run)
    temp_db_session.commit()

    cp = WorkflowCheckpointORM(
        workflow_run_id=run.id,
        checkpoint_key="agent1_tdd_complete",
        state_data='{"tdd_id": "abc-123", "approved": false}',
        version=1,
    )
    temp_db_session.add(cp)
    temp_db_session.commit()

    approval = HumanApprovalORM(
        workflow_run_id=run.id,
        gate_type="SPECIFICATION_APPROVAL",
        status="PENDING",
        prompt_text="Please review and approve the Technical Design Document before development begins.",
    )
    temp_db_session.add(approval)
    temp_db_session.commit()

    reloaded = temp_db_session.get(WorkflowRunORM, run.id)
    assert len(reloaded.checkpoints) == 1
    assert len(reloaded.approvals) == 1
    assert reloaded.approvals[0].status == "PENDING"
    assert reloaded.approvals[0].resolved_at is None


def test_crud_checkpoint_unique_constraint_enforcement(temp_db_session: Session):
    project_id = uuid.uuid4()
    temp_db_session.add(ProjectORM(id=project_id, name="CP Constraint Project", target_framework="nodejs"))
    temp_db_session.commit()

    run = WorkflowRunORM(project_id=project_id, current_phase="DEVELOPMENT")
    temp_db_session.add(run)
    temp_db_session.commit()

    temp_db_session.add(WorkflowCheckpointORM(
        workflow_run_id=run.id, checkpoint_key="dev_complete", state_data="{}", version=1
    ))
    temp_db_session.commit()

    temp_db_session.add(WorkflowCheckpointORM(
        workflow_run_id=run.id, checkpoint_key="dev_complete", state_data="{}", version=1
    ))
    with pytest.raises(IntegrityError):
        temp_db_session.commit()
    temp_db_session.rollback()


def test_crud_release_manifest_with_optional_qa_security(temp_db_session: Session):
    project_id = uuid.uuid4()
    temp_db_session.add(ProjectORM(id=project_id, name="Release Project", target_framework="python"))
    temp_db_session.commit()

    test_run = TestRunORM(
        project_id=project_id,
        execution_type="BLACK_BOX_HTTP",
        passed_count=12,
        failed_count=0,
        status="PASSED",
    )
    security_scan = SecurityScanORM(
        project_id=project_id,
        scanner_type="SAST",
        status="PASSED",
    )
    temp_db_session.add_all([test_run, security_scan])
    temp_db_session.commit()

    manifest_full = GitReleaseManifestORM(
        project_id=project_id,
        release_tag="v1.0.0",
        channel_commit_hash="a" * 40,
        mock_commit_hash="b" * 40,
        test_run_id=test_run.id,
        security_scan_id=security_scan.id,
    )
    manifest_no_mock = GitReleaseManifestORM(
        project_id=project_id,
        release_tag="v1.1.0",
        channel_commit_hash="c" * 40,
        mock_commit_hash=None,
        test_run_id=None,
        security_scan_id=None,
    )
    temp_db_session.add_all([manifest_full, manifest_no_mock])
    temp_db_session.commit()

    reloaded_full = temp_db_session.get(GitReleaseManifestORM, manifest_full.id)
    assert reloaded_full.mock_commit_hash == "b" * 40
    assert reloaded_full.test_run_id == test_run.id
    assert reloaded_full.security_scan_id == security_scan.id

    reloaded_no_mock = temp_db_session.get(GitReleaseManifestORM, manifest_no_mock.id)
    assert reloaded_no_mock.mock_commit_hash is None
    assert reloaded_no_mock.test_run_id is None
    assert reloaded_no_mock.security_scan_id is None


def test_crud_security_scan_not_scanned_status(temp_db_session: Session):
    project_id = uuid.uuid4()
    temp_db_session.add(ProjectORM(id=project_id, name="Security Skip Project", target_framework="nodejs"))
    temp_db_session.commit()

    scan = SecurityScanORM(project_id=project_id, scanner_type="SAST", status="NOT_SCANNED")
    temp_db_session.add(scan)
    temp_db_session.commit()

    reloaded = temp_db_session.get(SecurityScanORM, scan.id)
    assert reloaded.status == "NOT_SCANNED"


def test_crud_test_run_skipped_status(temp_db_session: Session):
    project_id = uuid.uuid4()
    temp_db_session.add(ProjectORM(id=project_id, name="QA Skip Project", target_framework="dotnet"))
    temp_db_session.commit()

    run = TestRunORM(
        project_id=project_id,
        execution_type="BLACK_BOX_HTTP",
        passed_count=0,
        failed_count=0,
        status="SKIPPED",
    )
    temp_db_session.add(run)
    temp_db_session.commit()

    reloaded = temp_db_session.get(TestRunORM, run.id)
    assert reloaded.status == "SKIPPED"
    assert reloaded.passed_count == 0


def test_crud_cascade_delete_project_removes_all_children(temp_db_session: Session):
    project_id = uuid.uuid4()
    project = ProjectORM(id=project_id, name="Cascade Delete Project", target_framework="python")
    temp_db_session.add(project)
    temp_db_session.commit()

    conv = ConversationORM(project_id=project_id, title="Chat")
    temp_db_session.add(conv)
    temp_db_session.commit()

    msg = MessageORM(conversation_id=conv.id, sender_type="USER", content="Hello")
    scan = SecurityScanORM(project_id=project_id, scanner_type="SAST", status="PASSED")
    temp_db_session.add_all([msg, scan])
    temp_db_session.commit()

    finding = SecurityFindingORM(
        security_scan_id=scan.id,
        severity="HIGH",
        vulnerability_type="SQLi",
        target_repo="CHANNEL_APP",
        file_path="src/api/routes/payments.py",
        description="SQL injection vulnerability detected in raw query.",
        remediation_advice="Use parameterized queries via SQLAlchemy ORM.",
    )
    temp_db_session.add(finding)
    temp_db_session.commit()

    conv_id = conv.id
    msg_id = msg.id
    scan_id = scan.id
    finding_id = finding.id

    temp_db_session.delete(project)
    temp_db_session.commit()

    assert temp_db_session.get(ProjectORM, project_id) is None
    assert temp_db_session.get(ConversationORM, conv_id) is None
    assert temp_db_session.get(MessageORM, msg_id) is None
    assert temp_db_session.get(SecurityScanORM, scan_id) is None
    assert temp_db_session.get(SecurityFindingORM, finding_id) is None


def test_crud_foreign_key_enforcement(temp_db_session: Session):
    fake_project_id = uuid.uuid4()
    temp_db_session.add(ConversationORM(project_id=fake_project_id, title="Orphan Conversation"))
    with pytest.raises(IntegrityError):
        temp_db_session.commit()
    temp_db_session.rollback()
