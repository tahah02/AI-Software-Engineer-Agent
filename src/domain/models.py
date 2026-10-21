from datetime import datetime, timezone
from typing import Any
import uuid

from pydantic import BaseModel, Field, ConfigDict

from src.domain.enums import (
    ProjectStatus,
    TargetLanguage,
    AgentType,
    TaskStatus,
    ApprovalGateType,
    ApprovalStatus,
    MessageSenderType,
    Severity,
    TestCaseCategory,
    RepositoryType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DomainEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ProjectAgentConfig(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    agent_type: AgentType
    is_enabled: bool = True
    provider: str = Field(min_length=1, max_length=50)
    model_name: str = Field(min_length=1, max_length=100)
    custom_system_prompt: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Project(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    target_framework: TargetLanguage
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    agent_configs: list[ProjectAgentConfig] = Field(default_factory=list)


class ProjectFile(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    file_name: str = Field(min_length=1, max_length=260)
    file_path: str = Field(max_length=1000)
    file_type: str = Field(max_length=50)
    file_size_bytes: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class Conversation(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    created_at: datetime = Field(default_factory=utc_now)


class Message(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    conversation_id: uuid.UUID
    sender_type: MessageSenderType
    agent_id: str | None = None
    content: str = Field(min_length=1)
    metadata_json: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=utc_now)


class AgentTask(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    agent_name: AgentType
    task_type: str = Field(min_length=1, max_length=100)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)


class TokenMetric(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    llm_invocation_id: uuid.UUID
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)


class LLMInvocation(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    agent_execution_id: uuid.UUID
    provider: str = Field(max_length=50)
    model_name: str = Field(max_length=100)
    latency_ms: int = Field(ge=0)
    success: bool
    error_message: str | None = None
    invoked_at: datetime = Field(default_factory=utc_now)
    token_metric: TokenMetric | None = None


class GitRepositoryRef(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    repo_type: RepositoryType
    local_path: str = Field(max_length=1000)
    created_at: datetime = Field(default_factory=utc_now)


class GitReleaseManifest(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    release_tag: str = Field(min_length=1, max_length=100)
    channel_commit_hash: str = Field(min_length=40, max_length=40)
    mock_commit_hash: str | None = Field(default=None, min_length=40, max_length=40)
    test_run_id: uuid.UUID | None = None
    security_scan_id: uuid.UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)


class TestCase(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    test_key: str = Field(min_length=1, max_length=100)
    category: TestCaseCategory
    endpoint: str = Field(min_length=1, max_length=500)
    http_method: str = Field(min_length=3, max_length=10)
    expected_status: int = Field(ge=100, le=599)


class TestRun(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    execution_type: str = Field(max_length=50)
    passed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    executed_at: datetime = Field(default_factory=utc_now)


class Defect(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    assigned_agent: AgentType
    severity: Severity
    description: str = Field(min_length=5)
    status: str = Field(default="OPEN", max_length=50)
    created_at: datetime = Field(default_factory=utc_now)


class SecurityFinding(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    severity: Severity
    vulnerability_type: str = Field(min_length=1, max_length=100)
    target_repo: RepositoryType
    file_path: str = Field(min_length=1, max_length=1000)
    line_number: int | None = Field(default=None, ge=1)
    description: str = Field(min_length=5)
    remediation_advice: str = Field(min_length=5)
    status: str = Field(default="OPEN", max_length=50)
    discovered_at: datetime = Field(default_factory=utc_now)


class HumanApproval(DomainEntity):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    workflow_run_id: uuid.UUID
    gate_type: ApprovalGateType
    status: ApprovalStatus = ApprovalStatus.PENDING
    prompt_text: str = Field(min_length=1)
    reviewer_comments: str | None = None
    requested_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None
