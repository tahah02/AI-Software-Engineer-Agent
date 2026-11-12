import uuid
import pytest

from src.domain.workflow_state import WorkflowState
from src.infrastructure.orchestration.graph_builder import WorkflowGraphBuilder


def test_full_5_agent_workflow_execution():
    visited_nodes = []

    def make_fn(name):
        def fn(state):
            visited_nodes.append(name)
            return {**state, "current_phase": name}
        return fn

    builder = WorkflowGraphBuilder(
        doc_reviewer_fn=make_fn("doc_reviewer"),
        mock_developer_fn=make_fn("mock_developer"),
        main_coder_fn=make_fn("main_coder"),
        qa_engineer_fn=lambda s: {**s, "current_phase": "qa_engineer", "qa_status": "PASSED"},
        security_reviewer_fn=lambda s: {**s, "current_phase": "security_reviewer", "security_status": "PASSED"},
        release_gate_fn=lambda s: {**s, "current_phase": "RELEASE", "is_completed": True},
    )

    graph = builder.build_graph()

    initial_state: WorkflowState = {
        "project_id": str(uuid.uuid4()),
        "workflow_run_id": str(uuid.uuid4()),
        "user_requirement": "Build full system",
        "spec_approved": True,
        "enabled_agents": {
            "MOCK_DEVELOPER": True,
            "QA_ENGINEER": True,
            "SECURITY_REVIEWER": True,
        },
        "defect_remediation_count": 0,
    }

    final_state = graph.invoke(initial_state)

    assert final_state["is_completed"] is True
    assert "doc_reviewer" in visited_nodes
    assert "mock_developer" in visited_nodes
    assert "main_coder" in visited_nodes
    assert final_state["qa_status"] == "PASSED"
    assert final_state["security_status"] == "PASSED"


def test_skip_agent_2_mock_developer():
    visited_nodes = []

    def make_fn(name):
        def fn(state):
            visited_nodes.append(name)
            return {**state, "current_phase": name}
        return fn

    builder = WorkflowGraphBuilder(
        doc_reviewer_fn=make_fn("doc_reviewer"),
        mock_developer_fn=make_fn("mock_developer"),
        main_coder_fn=make_fn("main_coder"),
        qa_engineer_fn=lambda s: {**s, "current_phase": "qa_engineer", "qa_status": "PASSED"},
        security_reviewer_fn=lambda s: {**s, "current_phase": "security_reviewer", "security_status": "PASSED"},
        release_gate_fn=lambda s: {**s, "current_phase": "RELEASE", "is_completed": True},
    )

    graph = builder.build_graph()

    initial_state: WorkflowState = {
        "project_id": str(uuid.uuid4()),
        "workflow_run_id": str(uuid.uuid4()),
        "user_requirement": "Standalone CRUD API without mock vendor",
        "spec_approved": True,
        "enabled_agents": {
            "MOCK_DEVELOPER": False,
            "QA_ENGINEER": True,
            "SECURITY_REVIEWER": True,
        },
        "defect_remediation_count": 0,
    }

    final_state = graph.invoke(initial_state)

    assert final_state["is_completed"] is True
    assert "doc_reviewer" in visited_nodes
    assert "mock_developer" not in visited_nodes  # Skipped!
    assert "main_coder" in visited_nodes


def test_skip_agent_2_when_enabled_in_config_but_tdd_requires_mock_is_false():
    visited_nodes = []

    def make_fn(name):
        def fn(state):
            visited_nodes.append(name)
            return {**state, "current_phase": name}
        return fn

    builder = WorkflowGraphBuilder(
        doc_reviewer_fn=make_fn("doc_reviewer"),
        mock_developer_fn=make_fn("mock_developer"),
        main_coder_fn=make_fn("main_coder"),
        qa_engineer_fn=lambda s: {**s, "current_phase": "qa_engineer", "qa_status": "PASSED"},
        security_reviewer_fn=lambda s: {**s, "current_phase": "security_reviewer", "security_status": "PASSED"},
        release_gate_fn=lambda s: {**s, "current_phase": "RELEASE", "is_completed": True},
    )

    graph = builder.build_graph()

    # MOCK_DEVELOPER is True in config, BUT TDD set requires_mock_vendor = False
    initial_state: WorkflowState = {
        "project_id": str(uuid.uuid4()),
        "workflow_run_id": str(uuid.uuid4()),
        "user_requirement": "Student Registration SRS where Agent 2 is out of scope",
        "spec_approved": True,
        "enabled_agents": {
            "MOCK_DEVELOPER": True,
            "QA_ENGINEER": True,
            "SECURITY_REVIEWER": True,
        },
        "requires_mock_vendor": False,
        "defect_remediation_count": 0,
    }

    final_state = graph.invoke(initial_state)

    assert final_state["is_completed"] is True
    assert "doc_reviewer" in visited_nodes
    assert "mock_developer" not in visited_nodes  # Dynamic TDD bypass!
    assert "main_coder" in visited_nodes


def test_skip_qa_and_security_reports_honest_status():
    visited_nodes = []

    builder = WorkflowGraphBuilder(
        doc_reviewer_fn=lambda s: {**s, "current_phase": "doc_reviewer"},
        mock_developer_fn=lambda s: {**s, "current_phase": "mock_developer"},
        main_coder_fn=lambda s: {**s, "current_phase": "main_coder"},
        qa_engineer_fn=lambda s: {**s, "current_phase": "qa_engineer"},
        security_reviewer_fn=lambda s: {**s, "current_phase": "security_reviewer"},
        release_gate_fn=lambda s: {**s, "current_phase": "RELEASE", "is_completed": True},
    )

    graph = builder.build_graph()

    initial_state: WorkflowState = {
        "project_id": str(uuid.uuid4()),
        "workflow_run_id": str(uuid.uuid4()),
        "user_requirement": "Rapid prototype without QA or Security",
        "spec_approved": True,
        "enabled_agents": {
            "MOCK_DEVELOPER": False,
            "QA_ENGINEER": False,
            "SECURITY_REVIEWER": False,
        },
        "defect_remediation_count": 0,
    }

    final_state = graph.invoke(initial_state)

    assert final_state["is_completed"] is True
    # Honest audit reporting verified
    assert final_state["qa_status"] == "SKIPPED"
    assert final_state["security_status"] == "NOT_SCANNED"


def test_qa_defect_remediation_loop():
    coder_calls = 0

    def coder_fn(state):
        nonlocal coder_calls
        coder_calls += 1
        return {**state, "current_phase": "main_coder"}

    def qa_fn(state):
        # Fail first time, pass second time
        if state.get("defect_remediation_count", 0) == 0:
            return {**state, "current_phase": "qa_engineer", "qa_status": "FAILED"}
        return {**state, "current_phase": "qa_engineer", "qa_status": "PASSED"}

    builder = WorkflowGraphBuilder(
        doc_reviewer_fn=lambda s: {**s, "current_phase": "doc_reviewer"},
        main_coder_fn=coder_fn,
        qa_engineer_fn=qa_fn,
        release_gate_fn=lambda s: {**s, "current_phase": "RELEASE", "is_completed": True},
    )

    graph = builder.build_graph()

    initial_state: WorkflowState = {
        "project_id": str(uuid.uuid4()),
        "workflow_run_id": str(uuid.uuid4()),
        "user_requirement": "Buggy feature to test loop",
        "spec_approved": True,
        "enabled_agents": {
            "MOCK_DEVELOPER": False,
            "QA_ENGINEER": True,
            "SECURITY_REVIEWER": False,
        },
        "defect_remediation_count": 0,
    }

    final_state = graph.invoke(initial_state)

    assert final_state["is_completed"] is True
    # Coder should have been called twice: initial execution + 1 remediation loop
    assert coder_calls == 2
    assert final_state["qa_status"] == "PASSED"
    assert final_state["defect_remediation_count"] == 1
