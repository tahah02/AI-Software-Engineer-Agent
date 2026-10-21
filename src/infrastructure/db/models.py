from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_framework: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    agent_configs: Mapped[list["ProjectAgentConfigORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    files: Mapped[list["ProjectFileORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["ConversationORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    workflow_runs: Mapped[list["WorkflowRunORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    agent_tasks: Mapped[list["AgentTaskORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    git_repositories: Mapped[list["GitRepositoryORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    release_manifests: Mapped[list["GitReleaseManifestORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    test_cases: Mapped[list["TestCaseORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    test_runs: Mapped[list["TestRunORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    defects: Mapped[list["DefectORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    security_scans: Mapped[list["SecurityScanORM"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectAgentConfigORM(Base):
    __tablename__ = "project_agent_configs"
    __table_args__ = (UniqueConstraint("project_id", "agent_type", name="uq_project_agent_type"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="agent_configs")


class ProjectFileORM(Base):
    __tablename__ = "project_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(260), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="files")


class ConversationORM(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="conversations")
    messages: Mapped[list["MessageORM"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageORM(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    sender_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation: Mapped["ConversationORM"] = relationship(back_populates="messages")


class WorkflowRunORM(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    current_phase: Mapped[str] = mapped_column(String(100), nullable=False)
    iteration_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["ProjectORM"] = relationship(back_populates="workflow_runs")
    events: Mapped[list["WorkflowEventORM"]] = relationship(
        back_populates="workflow_run", cascade="all, delete-orphan"
    )
    checkpoints: Mapped[list["WorkflowCheckpointORM"]] = relationship(
        back_populates="workflow_run", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["HumanApprovalORM"]] = relationship(
        back_populates="workflow_run", cascade="all, delete-orphan"
    )


class WorkflowEventORM(Base):
    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    workflow_run: Mapped["WorkflowRunORM"] = relationship(back_populates="events")


class WorkflowCheckpointORM(Base):
    __tablename__ = "workflow_checkpoints"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "checkpoint_key", "version", name="uq_run_checkpoint_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    checkpoint_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state_data: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    workflow_run: Mapped["WorkflowRunORM"] = relationship(back_populates="checkpoints")


class HumanApprovalORM(Base):
    __tablename__ = "human_approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False)
    gate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow_run: Mapped["WorkflowRunORM"] = relationship(back_populates="approvals")


class AgentTaskORM(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="agent_tasks")
    executions: Mapped[list["AgentExecutionORM"]] = relationship(
        back_populates="agent_task", cascade="all, delete-orphan"
    )


class AgentExecutionORM(Base):
    __tablename__ = "agent_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent_task: Mapped["AgentTaskORM"] = relationship(back_populates="executions")
    llm_invocations: Mapped[list["LLMInvocationORM"]] = relationship(
        back_populates="agent_execution", cascade="all, delete-orphan"
    )
    tool_executions: Mapped[list["ToolExecutionORM"]] = relationship(
        back_populates="agent_execution", cascade="all, delete-orphan"
    )


class LLMInvocationORM(Base):
    __tablename__ = "llm_invocations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    agent_execution: Mapped["AgentExecutionORM"] = relationship(back_populates="llm_invocations")
    token_usage: Mapped["TokenUsageORM"] = relationship(
        back_populates="llm_invocation", uselist=False, cascade="all, delete-orphan"
    )


class TokenUsageORM(Base):
    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    llm_invocation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("llm_invocations.id", ondelete="CASCADE"), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    llm_invocation: Mapped["LLMInvocationORM"] = relationship(back_populates="token_usage")


class ToolExecutionORM(Base):
    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_execution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_arguments: Mapped[str] = mapped_column(Text, nullable=False)
    output_result: Mapped[str] = mapped_column(Text, nullable=False)
    exit_code: Mapped[int] = mapped_column(Integer, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    agent_execution: Mapped["AgentExecutionORM"] = relationship(back_populates="tool_executions")


class GitRepositoryORM(Base):
    __tablename__ = "git_repositories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    repo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    local_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="git_repositories")


class GitReleaseManifestORM(Base):
    __tablename__ = "git_release_manifests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    release_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    channel_commit_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    mock_commit_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    test_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_runs.id", ondelete="SET NULL"), nullable=True)
    security_scan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("security_scans.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="release_manifests")


class TestCaseORM(Base):
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    test_key: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    http_method: Mapped[str] = mapped_column(String(10), nullable=False)
    expected_status: Mapped[int] = mapped_column(Integer, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="test_cases")
    results: Mapped[list["TestResultORM"]] = relationship(
        back_populates="test_case", cascade="all, delete-orphan"
    )


class TestRunORM(Base):
    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    execution_type: Mapped[str] = mapped_column(String(50), nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PASSED")
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="test_runs")
    results: Mapped[list["TestResultORM"]] = relationship(
        back_populates="test_run", cascade="all, delete-orphan"
    )


class TestResultORM(Base):
    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    actual_status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    test_run: Mapped["TestRunORM"] = relationship(back_populates="results")
    test_case: Mapped["TestCaseORM"] = relationship(back_populates="results")


class DefectORM(Base):
    __tablename__ = "defects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    assigned_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="defects")


class SecurityScanORM(Base):
    __tablename__ = "security_scans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    scanner_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PASSED")
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["ProjectORM"] = relationship(back_populates="security_scans")
    findings: Mapped[list["SecurityFindingORM"]] = relationship(
        back_populates="security_scan", cascade="all, delete-orphan"
    )


class SecurityFindingORM(Base):
    __tablename__ = "security_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    security_scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("security_scans.id", ondelete="CASCADE"), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    vulnerability_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_repo: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_advice: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    security_scan: Mapped["SecurityScanORM"] = relationship(back_populates="findings")
