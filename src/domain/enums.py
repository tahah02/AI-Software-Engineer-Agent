from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    ERROR = "ERROR"


class TargetLanguage(str, Enum):
    PYTHON = "python"
    DOTNET = "dotnet"
    NODEJS = "nodejs"


class AgentType(str, Enum):
    DOC_REVIEWER = "Agent 1: Documentation Reviewer"
    MOCK_DEVELOPER = "Agent 2: Mock Vendor API Developer"
    MAIN_CODING = "Agent 3: Main Coding Agent"
    QA_ENGINEER = "Agent 4: Independent QA Engineer"
    SECURITY_REVIEWER = "Agent 5: Security Reviewer"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowPhase(str, Enum):
    INGESTION = "INGESTION"
    SPECIFICATION = "SPECIFICATION"
    SPEC_APPROVAL = "SPEC_APPROVAL"
    DEVELOPMENT = "DEVELOPMENT"
    QA_SECURITY = "QA_SECURITY"
    DEFECT_FIX = "DEFECT_FIX"
    RELEASE_PROMOTION = "RELEASE_PROMOTION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ApprovalGateType(str, Enum):
    SPECIFICATION_APPROVAL = "SPECIFICATION_APPROVAL"
    RELEASE_PROMOTION = "RELEASE_PROMOTION"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MessageSenderType(str, Enum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
    ORCHESTRATOR = "ORCHESTRATOR"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TestCaseCategory(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BOUNDARY = "BOUNDARY"
    SECURITY = "SECURITY"


class TestStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RepositoryType(str, Enum):
    MOCK_VENDOR_API = "MOCK_VENDOR_API"
    CHANNEL_APP = "CHANNEL_APP"
