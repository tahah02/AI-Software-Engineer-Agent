import os
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.application.agents.supervisor import SupervisorAgent, SupervisorDecision
from src.domain.enums import LLMProvider, RepositoryType
from src.infrastructure.db.models import Base, ProjectORM, GitRepositoryORM
from src.infrastructure.git.git_service import GitService
from src.ports.llm_gateway import LLMResponse, TokenUsage


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_git_service_set_remote_and_push(test_db):
    temp_dir = tempfile.mkdtemp(prefix="aaise_git_test_")
    try:
        project_id = uuid.uuid4()
        project = ProjectORM(
            id=project_id,
            name="Test Remote Project",
            status="INITIALIZED",
            target_framework="PYTHON",
        )
        test_db.add(project)

        repo_orm = GitRepositoryORM(
            project_id=project_id,
            repo_type=RepositoryType.CHANNEL_APP.value if hasattr(RepositoryType.CHANNEL_APP, "value") else str(RepositoryType.CHANNEL_APP),
            local_path=temp_dir,
        )
        test_db.add(repo_orm)
        test_db.commit()

        git_svc = GitService(db=test_db)

        # 1. Set Remote
        remote_url = "https://github.com/tahah02/Test-AAISE.git"
        configured = git_svc.set_remote(
            project_id=project_id,
            repo_type=RepositoryType.CHANNEL_APP,
            remote_url=remote_url,
            remote_name="origin",
        )
        assert configured == remote_url

        # Check git remote -v output
        res = git_svc._run_git(Path(temp_dir), ["remote", "-v"])
        assert "https://github.com/tahah02/Test-AAISE.git" in res.stdout

        # 2. Update remote to different URL
        updated_url = "https://github.com/tahah02/New-Repo.git"
        configured2 = git_svc.set_remote(
            project_id=project_id,
            repo_type=RepositoryType.CHANNEL_APP,
            remote_url=updated_url,
            remote_name="origin",
        )
        assert configured2 == updated_url
        res2 = git_svc._run_git(Path(temp_dir), ["remote", "-v"])
        assert "https://github.com/tahah02/New-Repo.git" in res2.stdout

        # 3. Create dummy file and commit
        dummy_file = Path(temp_dir) / "README.md"
        dummy_file.write_text("# Test Repo")
        commit_hash = git_svc.commit_changes(
            project_id=project_id,
            repo_type=RepositoryType.CHANNEL_APP,
            message="feat: initial test commit",
        )
        assert len(commit_hash) == 40

        # 4. Attempt push - must fail authentically without hanging (GIT_TERMINAL_PROMPT=0)
        success, log = git_svc.push(project_id, RepositoryType.CHANNEL_APP)
        assert success is False
        assert len(log) > 0  # Contains authentic git error output

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_supervisor_set_remote_and_path_grounding():
    mock_litellm = MagicMock()
    mock_litellm.complete = AsyncMock(side_effect=Exception("Simulated Sandbox Network Isolation"))
    mock_ollama = MagicMock()
    mock_ollama.complete = AsyncMock(side_effect=Exception("Simulated Sandbox Network Isolation"))

    supervisor = SupervisorAgent(litellm_adapter=mock_litellm, ollama_adapter=mock_ollama)
    workspace_path = r"D:\AI Software Engineer Agent\workspace\test-proj\channel-app"

    # Test 1: Setting remote URL
    user_msg = "https://github.com/tahah02/Test-AAISE.git"
    decision = await supervisor.evaluate(
        user_message=user_msg,
        workspace_path=workspace_path,
        project_name="Test Project",
    )
    assert decision.action == "SET_REMOTE"
    assert "github.com/tahah02/Test-AAISE.git" in (decision.git_remote_url or "")

    # Test 2: Push remote
    push_msg = "push krdia git pe?"
    decision_push = await supervisor.evaluate(
        user_message=push_msg,
        workspace_path=workspace_path,
        project_name="Test Project",
    )
    assert decision_push.action == "PUSH_REMOTE"

    # Test 3: Path Grounding
    path_msg = "knsi repo me hai mera codebase btana zra"
    decision_path = await supervisor.evaluate(
        user_message=path_msg,
        workspace_path=workspace_path,
        project_name="Test Project",
    )
    assert decision_path.action == "CONVERSE"
    assert "D:\\AI Software Engineer Agent\\workspace\\test-proj\\channel-app" in decision_path.reply_to_user
