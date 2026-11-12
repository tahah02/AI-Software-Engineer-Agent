import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.enums import ApprovalGateType, ApprovalStatus
from src.domain.workflow_state import WorkflowState
from src.infrastructure.db.models import Base, ProjectORM, WorkflowRunORM, HumanApprovalORM
from src.infrastructure.orchestration.approval_engine import ApprovalEngine
from src.infrastructure.orchestration.graph_builder import WorkflowGraphBuilder


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="Approval Test Project", target_framework="fastapi")
    session.add(project)
    session.flush()

    run = WorkflowRunORM(project_id=project.id, current_phase="SPEC_APPROVAL", status="RUNNING")
    session.add(run)
    session.commit()

    yield session, project, run
    session.close()


def test_create_and_resolve_approval(db_session):
    session, project, run = db_session
    engine = ApprovalEngine(db=session)

    # 1. Create approval request
    req = engine.create_approval_request(
        workflow_run_id=run.id,
        gate_type=ApprovalGateType.SPECIFICATION_APPROVAL,
        prompt_text="Please review docs/TECHNICAL_DESIGN.md and docs/XUNIT_TEST_SPEC.md",
    )
    session.commit()

    assert req.id is not None
    assert req.status == ApprovalStatus.PENDING.value
    assert req.resolved_at is None

    # 2. Resolve approval with comments
    resolved = engine.resolve_approval(
        approval_id=req.id,
        approved=True,
        reviewer_comments="Looks good, approved to build.",
    )
    session.commit()

    assert resolved.status == ApprovalStatus.APPROVED.value
    assert resolved.reviewer_comments == "Looks good, approved to build."
    assert resolved.resolved_at is not None


def test_human_revision_feedback_loops_back_to_agent_1():
    doc_reviewer_invocations = 0

    def doc_reviewer_fn(state):
        nonlocal doc_reviewer_invocations
        doc_reviewer_invocations += 1
        return {**state, "current_phase": "SPECIFICATION"}

    def spec_approval_gate_fn(state):
        # On first pass, human requests revision
        if state.get("iteration", 0) == 0:
            return {
                **state,
                "current_phase": "SPEC_APPROVAL",
                "spec_approved": False,
                "spec_approval_comments": "Please add discount coupon field to payment API",
                "iteration": 1,
            }
        # On second pass, human approves
        return {
            **state,
            "current_phase": "SPEC_APPROVAL",
            "spec_approved": True,
            "spec_approval_comments": "Changes verified and approved.",
        }

    builder = WorkflowGraphBuilder(
        doc_reviewer_fn=doc_reviewer_fn,
        main_coder_fn=lambda s: {**s, "current_phase": "DEVELOPMENT"},
        release_gate_fn=lambda s: {**s, "current_phase": "RELEASE", "is_completed": True},
    )

    # Override gate node to simulate human interaction
    workflow_graph = builder.build_graph()

    initial_state: WorkflowState = {
        "project_id": str(uuid.uuid4()),
        "workflow_run_id": str(uuid.uuid4()),
        "user_requirement": "Build payment API",
        "enabled_agents": {"MOCK_DEVELOPER": False, "QA_ENGINEER": False, "SECURITY_REVIEWER": False},
        "iteration": 0,
        "spec_approved": False,
        "spec_approval_comments": "Please add discount coupon field to payment API",
    }

    # First invoke should loop back to doc reviewer because spec_approved is False
    from src.infrastructure.orchestration.graph_builder import route_after_spec_approval
    next_node = route_after_spec_approval(initial_state)
    assert next_node == "doc_reviewer"
    assert "Human Revision Request" in initial_state["user_requirement"]
    assert "discount coupon field" in initial_state["user_requirement"]

    # When approved, next_node routes forward to main_coder
    initial_state["spec_approved"] = True
    next_node_approved = route_after_spec_approval(initial_state)
    assert next_node_approved == "main_coder"
