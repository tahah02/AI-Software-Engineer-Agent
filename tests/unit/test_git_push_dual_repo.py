import uuid
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.models import Base, ProjectORM
from src.domain.enums import RepositoryType
from src.api.routes.workflow import handle_git_push_intent


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_push.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def project(test_db):
    proj = ProjectORM(
        id=uuid.uuid4(),
        name="Test Dual Repo Project",
        target_framework="csharp",
        status="ACTIVE",
    )
    test_db.add(proj)
    test_db.commit()
    return proj


def test_push_single_repo_channel_app(test_db, project, tmp_path):
    channel_dir = tmp_path / "channel"
    channel_dir.mkdir()
    (channel_dir / ".git").mkdir()

    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()  # no .git

    with patch("src.api.routes.workflow.GitService") as mock_git_service_cls:
        mock_git = MagicMock()
        mock_git_service_cls.return_value = mock_git

        def get_path(proj_id, repo_type):
            if "channel" in str(repo_type).lower():
                return str(channel_dir)
            return str(mock_dir)

        mock_git.get_repository_path.side_effect = get_path
        mock_git.push_to_remote.return_value = {
            "success": True,
            "remote_url": "https://github.com/org/student-app.git",
            "branch": "develop",
            "output": "Pushed to develop",
        }

        resp = handle_git_push_intent(
            "Please push this to https://github.com/org/student-app",
            str(project.id),
            test_db,
        )

        assert resp is not None
        assert resp.status == "PUSH_SUCCESS"
        mock_git.push_to_remote.assert_called_once_with(
            project_id=project.id,
            repo_type=RepositoryType.CHANNEL_APP,
            remote_url="https://github.com/org/student-app.git",
        )
        assert "Channel Application" in resp.assistant_reply


def test_push_dual_repo_ambiguity_guard(test_db, project, tmp_path):
    channel_dir = tmp_path / "channel"
    channel_dir.mkdir()
    (channel_dir / ".git").mkdir()

    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    (mock_dir / ".git").mkdir()

    with patch("src.api.routes.workflow.GitService") as mock_git_service_cls:
        mock_git = MagicMock()
        mock_git_service_cls.return_value = mock_git

        def get_path(proj_id, repo_type):
            if "channel" in str(repo_type).lower():
                return str(channel_dir)
            return str(mock_dir)

        mock_git.get_repository_path.side_effect = get_path

        # User provides single URL without specifying channel vs mock
        resp = handle_git_push_intent(
            "push https://github.com/org/ambiguous-repo",
            str(project.id),
            test_db,
        )

        assert resp is not None
        assert resp.status == "AMBIGUOUS_PUSH_TARGET"
        mock_git.push_to_remote.assert_not_called()
        assert "Dual-Repository Ambiguity Guard" in resp.assistant_reply
        assert "push channel" in resp.assistant_reply
        assert "push mock" in resp.assistant_reply


def test_push_dual_repo_target_channel(test_db, project, tmp_path):
    channel_dir = tmp_path / "channel"
    channel_dir.mkdir()
    (channel_dir / ".git").mkdir()

    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    (mock_dir / ".git").mkdir()

    with patch("src.api.routes.workflow.GitService") as mock_git_service_cls:
        mock_git = MagicMock()
        mock_git_service_cls.return_value = mock_git

        def get_path(proj_id, repo_type):
            if "channel" in str(repo_type).lower():
                return str(channel_dir)
            return str(mock_dir)

        mock_git.get_repository_path.side_effect = get_path
        mock_git.push_to_remote.return_value = {
            "success": True,
            "remote_url": "https://github.com/org/student-app.git",
            "branch": "develop",
            "output": "Pushed to develop",
        }

        resp = handle_git_push_intent(
            "push channel https://github.com/org/student-app",
            str(project.id),
            test_db,
        )

        assert resp is not None
        assert resp.status == "PUSH_SUCCESS"
        mock_git.push_to_remote.assert_called_once_with(
            project_id=project.id,
            repo_type=RepositoryType.CHANNEL_APP,
            remote_url="https://github.com/org/student-app.git",
        )


def test_push_dual_repo_target_mock(test_db, project, tmp_path):
    channel_dir = tmp_path / "channel"
    channel_dir.mkdir()
    (channel_dir / ".git").mkdir()

    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    (mock_dir / ".git").mkdir()

    with patch("src.api.routes.workflow.GitService") as mock_git_service_cls:
        mock_git = MagicMock()
        mock_git_service_cls.return_value = mock_git

        def get_path(proj_id, repo_type):
            if "channel" in str(repo_type).lower():
                return str(channel_dir)
            return str(mock_dir)

        mock_git.get_repository_path.side_effect = get_path
        mock_git.push_to_remote.return_value = {
            "success": True,
            "remote_url": "https://github.com/org/mock-vendor.git",
            "branch": "develop",
            "output": "Pushed to develop",
        }

        resp = handle_git_push_intent(
            "push mock https://github.com/org/mock-vendor",
            str(project.id),
            test_db,
        )

        assert resp is not None
        assert resp.status == "PUSH_SUCCESS"
        mock_git.push_to_remote.assert_called_once_with(
            project_id=project.id,
            repo_type=RepositoryType.MOCK_VENDOR_API,
            remote_url="https://github.com/org/mock-vendor.git",
        )


def test_push_dual_repo_both_urls(test_db, project, tmp_path):
    channel_dir = tmp_path / "channel"
    channel_dir.mkdir()
    (channel_dir / ".git").mkdir()

    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    (mock_dir / ".git").mkdir()

    with patch("src.api.routes.workflow.GitService") as mock_git_service_cls:
        mock_git = MagicMock()
        mock_git_service_cls.return_value = mock_git

        def get_path(proj_id, repo_type):
            if "channel" in str(repo_type).lower():
                return str(channel_dir)
            return str(mock_dir)

        mock_git.get_repository_path.side_effect = get_path
        mock_git.push_to_remote.side_effect = [
            {"success": True, "remote_url": "https://github.com/org/app.git", "branch": "develop", "output": "ok"},
            {"success": True, "remote_url": "https://github.com/org/mock.git", "branch": "develop", "output": "ok"},
        ]

        resp = handle_git_push_intent(
            "channel: https://github.com/org/app.git mock: https://github.com/org/mock.git",
            str(project.id),
            test_db,
        )

        assert resp is not None
        assert resp.status == "PUSH_SUCCESS"
        assert mock_git.push_to_remote.call_count == 2
        assert "Channel Application" in resp.assistant_reply
        assert "Mock Vendor API" in resp.assistant_reply


def test_push_mock_when_mock_not_applicable(test_db, project, tmp_path):
    channel_dir = tmp_path / "channel"
    channel_dir.mkdir()
    (channel_dir / ".git").mkdir()

    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()  # no .git

    with patch("src.api.routes.workflow.GitService") as mock_git_service_cls:
        mock_git = MagicMock()
        mock_git_service_cls.return_value = mock_git

        def get_path(proj_id, repo_type):
            if "channel" in str(repo_type).lower():
                return str(channel_dir)
            return str(mock_dir)

        mock_git.get_repository_path.side_effect = get_path

        resp = handle_git_push_intent(
            "push mock https://github.com/org/mock.git",
            str(project.id),
            test_db,
        )

        assert resp is not None
        assert resp.status == "NO_MOCK_REPO"
        mock_git.push_to_remote.assert_not_called()
