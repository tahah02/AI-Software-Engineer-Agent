import uuid
from typing import Any, Callable
from langgraph.graph import END, StateGraph

from src.domain.enums import AgentType
from src.domain.workflow_state import WorkflowState


def route_after_spec_approval(state: WorkflowState) -> str:
    # If human requested revisions or rejected specs, loop back to Agent 1 (Doc Reviewer)
    if not state.get("spec_approved", True):
        # Incorporate human revision feedback into user_requirement
        comments = state.get("spec_approval_comments")
        if comments:
            state["user_requirement"] = (
                f"{state.get('user_requirement', '')}\n\n"
                f"[Human Revision Request]: {comments}"
            )
        return "doc_reviewer"

    enabled = state.get("enabled_agents", {})
    if enabled.get(AgentType.MOCK_DEVELOPER.name, False) or enabled.get("MOCK_DEVELOPER", False):
        return "mock_developer"
    return "main_coder"


def route_after_coding(state: WorkflowState) -> str:
    enabled = state.get("enabled_agents", {})
    if enabled.get(AgentType.QA_ENGINEER.name, False) or enabled.get("QA_ENGINEER", False):
        return "qa_engineer"
    return "check_security"


def route_after_qa(state: WorkflowState) -> str:
    qa_status = state.get("qa_status", "PASSED")
    remediation_count = state.get("defect_remediation_count", 0)

    # Remediation loop: if QA failed and attempts < 3, loop back to Coder
    if qa_status == "FAILED" and remediation_count < 3:
        return "remediate_defect"

    return "check_security"


def route_check_security(state: WorkflowState) -> str:
    enabled = state.get("enabled_agents", {})
    if enabled.get(AgentType.SECURITY_REVIEWER.name, False) or enabled.get("SECURITY_REVIEWER", False):
        return "security_reviewer"
    return "release_approval_gate"


def audit_qa_skip_node(state: WorkflowState) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if not state.get("qa_status"):
        updates["qa_status"] = "SKIPPED"
        updates["qa_passed_count"] = 0
        updates["qa_failed_count"] = 0
    if not state.get("security_status"):
        enabled = state.get("enabled_agents", {})
        if not (enabled.get(AgentType.SECURITY_REVIEWER.name, False) or enabled.get("SECURITY_REVIEWER", False)):
            updates["security_status"] = "NOT_SCANNED"
            updates["security_findings_count"] = 0
    return updates


def remediate_defect_node(state: WorkflowState) -> dict[str, Any]:
    count = state.get("defect_remediation_count", 0) + 1
    return {
        "defect_remediation_count": count,
        "current_phase": "DEFECT_REMEDIATION",
    }


class WorkflowGraphBuilder:
    def __init__(
        self,
        doc_reviewer_fn: Callable[[WorkflowState], WorkflowState] | None = None,
        mock_developer_fn: Callable[[WorkflowState], WorkflowState] | None = None,
        main_coder_fn: Callable[[WorkflowState], WorkflowState] | None = None,
        qa_engineer_fn: Callable[[WorkflowState], WorkflowState] | None = None,
        security_reviewer_fn: Callable[[WorkflowState], WorkflowState] | None = None,
        release_gate_fn: Callable[[WorkflowState], WorkflowState] | None = None,
    ) -> None:
        self.doc_reviewer_fn = doc_reviewer_fn or (lambda s: {**s, "current_phase": "SPECIFICATION"})
        self.mock_developer_fn = mock_developer_fn or (lambda s: {**s, "current_phase": "MOCK_DEVELOPMENT"})
        self.main_coder_fn = main_coder_fn or (lambda s: {**s, "current_phase": "DEVELOPMENT"})
        self.qa_engineer_fn = qa_engineer_fn or (lambda s: {**s, "current_phase": "QA_VERIFICATION"})
        self.security_reviewer_fn = security_reviewer_fn or (lambda s: {**s, "current_phase": "SECURITY_AUDIT"})
        self.release_gate_fn = release_gate_fn or (lambda s: {**s, "current_phase": "RELEASE", "is_completed": True})

    def build_graph(self) -> Any:
        workflow = StateGraph(WorkflowState)

        # 1. Add Nodes
        workflow.add_node("doc_reviewer", self.doc_reviewer_fn)
        workflow.add_node("spec_approval_gate", lambda s: {**s, "current_phase": "SPEC_APPROVAL"})
        workflow.add_node("mock_developer", self.mock_developer_fn)
        workflow.add_node("main_coder", self.main_coder_fn)
        workflow.add_node("qa_engineer", self.qa_engineer_fn)
        workflow.add_node("remediate_defect", remediate_defect_node)
        workflow.add_node("security_reviewer", self.security_reviewer_fn)
        workflow.add_node("release_approval_gate", self.release_gate_fn)

        # Audit node for honest status recording when QA or Security are skipped
        workflow.add_node("check_security", audit_qa_skip_node)

        # 2. Add Edges
        workflow.set_entry_point("doc_reviewer")
        workflow.add_edge("doc_reviewer", "spec_approval_gate")

        # Dynamic routing after spec approval (Revision loop vs Agent 2 Mock Dev vs Agent 3 Coder)
        workflow.add_conditional_edges(
            "spec_approval_gate",
            route_after_spec_approval,
            {
                "doc_reviewer": "doc_reviewer",
                "mock_developer": "mock_developer",
                "main_coder": "main_coder",
            },
        )
        workflow.add_edge("mock_developer", "main_coder")

        # Dynamic routing after coding (Agent 4 QA vs Check Security)
        workflow.add_conditional_edges(
            "main_coder",
            route_after_coding,
            {
                "qa_engineer": "qa_engineer",
                "check_security": "check_security",
            },
        )

        # Dynamic routing after QA (Defect remediation loop vs Check Security)
        workflow.add_conditional_edges(
            "qa_engineer",
            route_after_qa,
            {
                "remediate_defect": "remediate_defect",
                "check_security": "check_security",
            },
        )
        workflow.add_edge("remediate_defect", "main_coder")

        # Dynamic routing to Security or Release Gate
        workflow.add_conditional_edges(
            "check_security",
            route_check_security,
            {
                "security_reviewer": "security_reviewer",
                "release_approval_gate": "release_approval_gate",
            },
        )

        workflow.add_edge("security_reviewer", "release_approval_gate")
        workflow.add_edge("release_approval_gate", END)

        return workflow.compile()
