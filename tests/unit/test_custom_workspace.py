import tempfile
import uuid
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.db.models import Base, ProjectORM, GitRepositoryORM, ProjectFileORM
from src.api.routes.projects import create_project, CreateProjectRequest, list_projects
from src.domain.enums import RepositoryType
from src.infrastructure.git.git_service import GitService
from src.application.agents.supervisor import _detect_framework_heuristically, SupervisorAgent


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_project_with_custom_local_folder_auto_detects_python(db_session, tmp_path):
    custom_dir = tmp_path / "my_existing_app"
    custom_dir.mkdir(parents=True, exist_ok=True)
    (custom_dir / "main.py").write_text("print('test')", encoding="utf-8")
    (custom_dir / "config.json").write_text("{}", encoding="utf-8")

    req = CreateProjectRequest(
        name="Linked Local Project",
        description="Testing local folder attach",
        target_framework="AUTO",
        custom_workspace_path=str(custom_dir),
    )

    proj_item = create_project(req, db=db_session)

    assert proj_item.name == "Linked Local Project"
    assert proj_item.workspace_path == str(custom_dir)
    assert proj_item.target_framework == "PYTHON"

    # Verify GitRepositoryORM was created with local_path
    repo = db_session.query(GitRepositoryORM).filter_by(project_id=proj_item.id).first()
    assert repo is not None
    assert repo.local_path == str(custom_dir)

    # Verify files were auto-indexed into ProjectFileORM
    indexed_files = db_session.query(ProjectFileORM).filter_by(project_id=proj_item.id).all()
    file_names = [f.file_name for f in indexed_files]
    assert "main.py" in file_names
    assert "config.json" in file_names

    # Verify GitService dynamically returns custom path
    git_svc = GitService(db=db_session)
    resolved = git_svc.get_repository_path(proj_item.id, RepositoryType.CHANNEL_APP)
    assert resolved == str(custom_dir)

    # Verify list_projects reflects the custom workspace path and detected framework
    projects_list = list_projects(db=db_session)
    matching = [p for p in projects_list if p.id == proj_item.id]
    assert len(matching) == 1
    assert matching[0].workspace_path == str(custom_dir)
    assert matching[0].target_framework == "PYTHON"


def test_create_project_csharp_auto_detect(db_session, tmp_path):
    cs_dir = tmp_path / "csharp_app"
    cs_dir.mkdir(parents=True, exist_ok=True)
    (cs_dir / "App.csproj").write_text("<Project />", encoding="utf-8")
    (cs_dir / "Program.cs").write_text("Console.WriteLine();", encoding="utf-8")

    req = CreateProjectRequest(
        name="CSharp Proj",
        custom_workspace_path=str(cs_dir),
    )
    item = create_project(req, db=db_session)
    assert item.target_framework == "DOTNET_CSHARP"


def test_supervisor_dynamic_codebase_inspection():
    detected = _detect_framework_heuristically(
        message="Can you check wht are the issues in this project and in what language its written?",
        existing_artifacts=["app.py", "pyproject.toml", "Dockerfile", "data/transactions.csv"],
    )
    assert detected == "PYTHON"


def test_csharp_csproj_scaffolding_guarantee(tmp_path):
    from src.application.orchestration.orchestrator_service import OrchestratorService

    # Simulate C# project folder with Program.cs but missing .csproj
    cs_dir = tmp_path / "MyBackend"
    cs_dir.mkdir(parents=True, exist_ok=True)
    (cs_dir / "Program.cs").write_text("var builder = WebApplication.CreateBuilder(args);", encoding="utf-8")

    # Mock git_service to return cs_dir
    class FakeGit:
        def get_repository_path(self, project_id=None, repo_type=None, *args, **kwargs):
            return str(cs_dir)

    service = OrchestratorService(db=None, resolver=None, git_service=FakeGit())
    # Run _verify_build which should auto-scaffold .csproj
    service._verify_build(uuid.uuid4(), "DOTNET_CSHARP")

    # Verify .csproj was created automatically
    csprojs = list(cs_dir.glob("*.csproj"))
    assert len(csprojs) == 1
    content = csprojs[0].read_text(encoding="utf-8")
    assert "Microsoft.NET.Sdk.Web" in content
    assert "net8.0" in content

