import shutil
import tempfile
import uuid
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.enums import RepositoryType
from src.infrastructure.db.models import Base, ProjectORM, GitRepositoryORM
from src.infrastructure.git.git_service import GitService
from src.ports.git_service import IGitService


@pytest.fixture
def temp_workspace():
    tmp_dir = tempfile.mkdtemp(prefix="aaise_git_test_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    project = ProjectORM(name="Repo Test Project", target_framework="fastapi")
    session.add(project)
    session.commit()

    yield session
    session.close()


def test_git_service_implements_protocol(db_session, temp_workspace):
    service = GitService(db=db_session, base_workspace_dir=temp_workspace)
    assert isinstance(service, IGitService)


def test_initialize_channel_repository(db_session, temp_workspace):
    project = db_session.query(ProjectORM).first()
    service = GitService(db=db_session, base_workspace_dir=temp_workspace)

    repo_path_str = service.initialize_repository(
        project_id=project.id,
        repo_type=RepositoryType.CHANNEL_APP,
        target_framework="python",
    )
    db_session.commit()

    repo_path = Path(repo_path_str)
    assert repo_path.exists()
    assert (repo_path / ".git").exists()
    assert (repo_path / ".gitignore").exists()
    assert (repo_path / "README.md").exists()

    gitignore_content = (repo_path / ".gitignore").read_text(encoding="utf-8")
    assert "__pycache__/" in gitignore_content

    # Verify database persistence
    record = (
        db_session.query(GitRepositoryORM)
        .filter_by(project_id=project.id, repo_type="CHANNEL_APP")
        .first()
    )
    assert record is not None
    assert record.local_path == repo_path_str


def test_initialize_mock_vendor_repository(db_session, temp_workspace):
    project = db_session.query(ProjectORM).first()
    service = GitService(db=db_session, base_workspace_dir=temp_workspace)

    repo_path_str = service.initialize_repository(
        project_id=project.id,
        repo_type=RepositoryType.MOCK_VENDOR_API,
        target_framework="typescript",
    )
    db_session.commit()

    repo_path = Path(repo_path_str)
    assert repo_path.exists()
    assert (repo_path / ".git").exists()
    assert "node_modules/" in (repo_path / ".gitignore").read_text(encoding="utf-8")

    record = (
        db_session.query(GitRepositoryORM)
        .filter_by(project_id=project.id, repo_type="MOCK_VENDOR_API")
        .first()
    )
    assert record is not None


def test_initialize_repository_idempotent(db_session, temp_workspace):
    project = db_session.query(ProjectORM).first()
    service = GitService(db=db_session, base_workspace_dir=temp_workspace)

    path1 = service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)
    path2 = service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)
    assert path1 == path2

    count = (
        db_session.query(GitRepositoryORM)
        .filter_by(project_id=project.id, repo_type="CHANNEL_APP")
        .count()
    )
    assert count == 1


def test_create_branch_and_commit(db_session, temp_workspace):
    project = db_session.query(ProjectORM).first()
    service = GitService(db=db_session, base_workspace_dir=temp_workspace)

    repo_path_str = service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)
    repo_path = Path(repo_path_str)

    # Create feature branch
    branch_name = service.create_branch(
        project_id=project.id,
        repo_type=RepositoryType.CHANNEL_APP,
        branch_name="feature/payment-api",
        base_branch="develop",
    )
    assert branch_name == "feature/payment-api"

    # Write a new file
    (repo_path / "payment.py").write_text("# payment logic\n", encoding="utf-8")

    # Commit with Conventional Commit message
    commit_hash = service.commit_changes(
        project_id=project.id,
        repo_type=RepositoryType.CHANNEL_APP,
        message="feat: implement initial payment api",
    )
    assert len(commit_hash) == 40

    # Verify HEAD commit hash matches
    current_hash = service.get_current_commit_hash(project.id, RepositoryType.CHANNEL_APP)
    assert current_hash == commit_hash


def test_commit_rejects_non_conventional_commit_message(db_session, temp_workspace):
    project = db_session.query(ProjectORM).first()
    service = GitService(db=db_session, base_workspace_dir=temp_workspace)

    service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)
    repo_path = Path(service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))
    (repo_path / "dummy.txt").write_text("dummy", encoding="utf-8")

    with pytest.raises(ValueError, match="Conventional Commits"):
        service.commit_changes(
            project_id=project.id,
            repo_type=RepositoryType.CHANNEL_APP,
            message="updated some files without proper prefix",
        )


def test_checkout_branch(db_session, temp_workspace):
    project = db_session.query(ProjectORM).first()
    service = GitService(db=db_session, base_workspace_dir=temp_workspace)

    service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)
    service.create_branch(project.id, RepositoryType.CHANNEL_APP, "fix/test-bug")
    service.checkout_branch(project.id, RepositoryType.CHANNEL_APP, "develop")

    # Current branch should now be develop
    res = service._run_git(
        Path(service.get_repository_path(project.id, RepositoryType.CHANNEL_APP)),
        ["rev-parse", "--abbrev-ref", "HEAD"],
    )
    assert res.stdout.strip() == "develop"


def test_create_release_manifest_channel_only(db_session, temp_workspace):
    project = ProjectORM(name="Channel Only Project", target_framework="fastapi")
    db_session.add(project)
    db_session.commit()

    service = GitService(db=db_session, base_workspace_dir=temp_workspace)

    service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)
    manifest = service.create_release_manifest(
        project_id=project.id,
        release_tag="v1.0.0",
    )
    db_session.commit()

    assert manifest.id is not None
    assert manifest.release_tag == "v1.0.0"
    assert len(manifest.channel_commit_hash) == 40
    assert manifest.mock_commit_hash is None


def test_create_release_manifest_dual_repo(db_session, temp_workspace):
    project = ProjectORM(name="Dual Repo Project", target_framework="fastapi")
    db_session.add(project)
    db_session.commit()

    service = GitService(db=db_session, base_workspace_dir=temp_workspace)

    service.initialize_repository(project.id, RepositoryType.CHANNEL_APP)
    service.initialize_repository(project.id, RepositoryType.MOCK_VENDOR_API)

    manifest = service.create_release_manifest(
        project_id=project.id,
        release_tag="v1.1.0",
    )
    db_session.commit()

    assert manifest.id is not None
    assert manifest.release_tag == "v1.1.0"
    assert len(manifest.channel_commit_hash) == 40
    assert len(manifest.mock_commit_hash) == 40


def test_git_service_custom_local_path(db_session, temp_workspace):
    project = db_session.query(ProjectORM).first()
    custom_dir = Path(temp_workspace) / "my_custom_folder"
    custom_dir.mkdir(parents=True, exist_ok=True)

    repo_orm = GitRepositoryORM(
        project_id=project.id,
        repo_type=RepositoryType.CHANNEL_APP.value,
        local_path=str(custom_dir),
    )
    db_session.add(repo_orm)
    db_session.commit()

    service = GitService(db=db_session, base_workspace_dir=temp_workspace)
    resolved_path = service.get_repository_path(project.id, RepositoryType.CHANNEL_APP)
    assert resolved_path == str(custom_dir)


def test_git_service_merge_branch(db_session, temp_workspace):
    project = db_session.query(ProjectORM).first()
    service = GitService(db=db_session, base_workspace_dir=temp_workspace)
    service.initialize_repository(project.id, RepositoryType.CHANNEL_APP, "python")

    # Create feature branch and commit file
    feature_branch = "feature/test-feature-1"
    service.create_branch(project.id, RepositoryType.CHANNEL_APP, feature_branch, base_branch="develop")
    repo_path = Path(service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))
    (repo_path / "feature.txt").write_text("feature content", encoding="utf-8")
    service.commit_changes(project.id, RepositoryType.CHANNEL_APP, "feat: implement test feature")

    # Merge feature branch back to develop
    service.merge_branch(project.id, RepositoryType.CHANNEL_APP, source_branch=feature_branch, target_branch="develop")

    # Verify develop is checked out and has the feature file
    current_branch = service.get_current_branch(project.id, RepositoryType.CHANNEL_APP)
    assert current_branch == "develop"
    assert (repo_path / "feature.txt").exists()


