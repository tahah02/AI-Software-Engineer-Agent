import uuid
import pytest
from pydantic import ValidationError

from src.domain.enums import (
    ProjectStatus,
    TargetLanguage,
    ApprovalGateType,
    ApprovalStatus,
    RepositoryType,
    Severity,
    TestCaseCategory,
)
from src.domain.models import (
    Project,
    GitReleaseManifest,
    TestCase,
    SecurityFinding,
    HumanApproval,
)
from src.domain.exceptions import EntityNotFoundError, ApprovalPendingError


def test_project_instantiation_valid():
    project = Project(
        name="Banking Core Integration",
        target_framework=TargetLanguage.PYTHON,
    )
    assert project.name == "Banking Core Integration"
    assert project.status == ProjectStatus.ACTIVE
    assert project.target_framework == TargetLanguage.PYTHON
    assert isinstance(project.id, uuid.UUID)


def test_project_name_validation_empty_fails():
    with pytest.raises(ValidationError):
        Project(name="", target_framework=TargetLanguage.PYTHON)


def test_git_release_manifest_commit_hash_length():
    channel_hash = "a" * 40
    mock_hash = "b" * 40
    manifest = GitReleaseManifest(
        project_id=uuid.uuid4(),
        release_tag="v1.0.0",
        channel_commit_hash=channel_hash,
        mock_commit_hash=mock_hash,
    )
    assert manifest.channel_commit_hash == channel_hash
    assert manifest.mock_commit_hash == mock_hash

    with pytest.raises(ValidationError):
        GitReleaseManifest(
            project_id=uuid.uuid4(),
            release_tag="v1.0.0",
            channel_commit_hash="short_hash",
            mock_commit_hash=mock_hash,
        )


def test_test_case_validation():
    tc = TestCase(
        project_id=uuid.uuid4(),
        test_key="TC-001",
        category=TestCaseCategory.POSITIVE,
        endpoint="/api/v1/accounts",
        http_method="GET",
        expected_status=200,
    )
    assert tc.expected_status == 200

    with pytest.raises(ValidationError):
        TestCase(
            project_id=uuid.uuid4(),
            test_key="TC-002",
            category=TestCaseCategory.NEGATIVE,
            endpoint="/api/v1/accounts",
            http_method="POST",
            expected_status=999,
        )


def test_security_finding_entity():
    finding = SecurityFinding(
        project_id=uuid.uuid4(),
        severity=Severity.HIGH,
        vulnerability_type="SQL_INJECTION",
        target_repo=RepositoryType.CHANNEL_APP,
        file_path="src/repositories/account.py",
        line_number=45,
        description="Raw string formatting detected in query",
        remediation_advice="Use parameterized queries via SQLAlchemy",
    )
    assert finding.severity == Severity.HIGH
    assert finding.line_number == 45
    assert finding.status == "OPEN"


def test_human_approval_defaults():
    wf_id = uuid.uuid4()
    approval = HumanApproval(
        workflow_run_id=wf_id,
        gate_type=ApprovalGateType.SPECIFICATION_APPROVAL,
        prompt_text="Please review the generated Technical Design Document.",
    )
    assert approval.status == ApprovalStatus.PENDING
    assert approval.resolved_at is None


def test_domain_exceptions():
    err = EntityNotFoundError("Project", "123")
    assert "Project with ID '123' not found" in str(err)

    appr_err = ApprovalPendingError("RELEASE_PROMOTION", "appr-456")
    assert "RELEASE_PROMOTION" in str(appr_err)
