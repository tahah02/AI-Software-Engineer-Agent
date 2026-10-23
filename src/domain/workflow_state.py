from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    # Core Identifiers
    project_id: str
    workflow_run_id: str
    workspace_path: str
    target_framework: str
    user_requirement: str

    # Dynamic Agent Topology (Enabled/Disabled flags)
    enabled_agents: dict[str, bool]

    # Artifacts & Repositories
    tdd_path: str | None
    xunit_spec_path: str | None
    channel_repo_path: str | None
    mock_repo_path: str | None

    # Git Hashes
    channel_commit_hash: str | None
    mock_commit_hash: str | None
    release_tag: str | None

    # QA & Defect Tracking
    qa_status: str  # PASSED, FAILED, SKIPPED
    qa_passed_count: int
    qa_failed_count: int
    active_defects: list[dict[str, Any]]
    defect_remediation_count: int

    # Security Tracking
    security_status: str  # PASSED, FAILED, NOT_SCANNED
    security_findings_count: int

    # Human-in-the-Loop Approval Gates
    spec_approved: bool
    spec_approval_comments: str | None
    release_approved: bool
    release_approval_comments: str | None

    # Workflow Execution State
    current_phase: str
    iteration: int
    is_completed: bool
    error: str | None
