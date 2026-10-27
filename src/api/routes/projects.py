import io
import os
import zipfile
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.domain.enums import RepositoryType
from src.infrastructure.db.models import ProjectAgentConfigORM, ProjectFileORM, ProjectORM
from src.infrastructure.db.session import get_db
from src.infrastructure.git.git_service import GitService

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    target_framework: str
    status: str
    current_branch: str = "develop"


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None
    target_framework: str = "PYTHON_FASTAPI"


class AgentConfigItem(BaseModel):
    model_config = {"protected_namespaces": ()}
    agent_type: str
    is_enabled: bool
    is_mandatory: bool
    provider: str
    model_name: str


class ProjectConfigResponse(BaseModel):
    project_id: uuid.UUID
    agents: list[AgentConfigItem]


class UpdateProjectConfigRequest(BaseModel):
    agent2_enabled: bool
    agent4_enabled: bool
    agent5_enabled: bool


@router.get("", response_model=list[ProjectItem])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(ProjectORM).order_by(ProjectORM.created_at.desc()).all()
    git_service = GitService(db=db)
    items = []
    for p in projects:
        branch = "develop"
        try:
            repo_path = git_service.get_repository_path(p.id, RepositoryType.CHANNEL_APP)
            if repo_path.exists():
                branch = "develop"
        except Exception:
            branch = "develop"
        items.append(
            ProjectItem(
                id=p.id,
                name=p.name,
                description=p.description,
                target_framework=p.target_framework,
                status=p.status,
                current_branch=branch,
            )
        )
    return items


@router.post("", response_model=ProjectItem, status_code=status.HTTP_201_CREATED)
def create_project(req: CreateProjectRequest, db: Session = Depends(get_db)):
    proj = ProjectORM(
        name=req.name,
        description=req.description,
        target_framework=req.target_framework,
        status="ACTIVE",
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return ProjectItem(
        id=proj.id,
        name=proj.name,
        description=proj.description,
        target_framework=proj.target_framework,
        status=proj.status,
        current_branch="develop",
    )


@router.get("/{project_id}/diff")
def get_project_diff(project_id: uuid.UUID, db: Session = Depends(get_db)):
    git_service = GitService(db=db)
    try:
        repo_path = git_service.get_repository_path(project_id, RepositoryType.CHANNEL_APP)
        if not repo_path.exists():
            return {"diff": "", "message": "Repository not created yet."}

        # Read actual git diff or recent commit
        import subprocess
        res = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        if not res.stdout:
            res = subprocess.run(
                ["git", "show", "--stat", "--patch", "HEAD"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
            )
        return {"diff": res.stdout or "No changes detected on HEAD.", "status": "ok"}
    except Exception as e:
        return {"diff": "", "error": str(e)}


@router.get("/{project_id}/download")
def download_project_zip(project_id: uuid.UUID, db: Session = Depends(get_db)):
    git_service = GitService(db=db)
    repo_path = git_service.get_repository_path(project_id, RepositoryType.CHANNEL_APP)
    if not repo_path.exists():
        raise HTTPException(status_code=404, detail="Workspace directory not found.")

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(repo_path):
            if ".git" in dirs:
                dirs.remove(".git")
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path)
                zf.write(full_path, arcname=rel_path)

    mem_zip.seek(0)
    return StreamingResponse(
        mem_zip,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename=project-{project_id}.zip"},
    )


@router.get("/{project_id}/agents", response_model=ProjectConfigResponse)
def get_project_agent_configs(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )

    configs = db.query(ProjectAgentConfigORM).filter_by(project_id=project_id).all()

    if not configs:
        default_agents = [
            ("AGENT_1", True, "gemini", "gemini-3.8-flash"),
            ("AGENT_2", True, "groq", "openai/gpt-oss-120b"),
            ("AGENT_3", True, "ollama", "qwen2.5-coder:7b"),
            ("AGENT_4", True, "groq", "qwen/qwen3.8-27b"),
            ("AGENT_5", True, "gemini", "gemini-3.5-flash-lite"),
        ]
        created_configs = []
        for atype, is_en, prov, model in default_agents:
            cfg = ProjectAgentConfigORM(
                project_id=project_id,
                agent_type=atype,
                is_enabled=is_en,
                provider=prov,
                model_name=model,
            )
            db.add(cfg)
            created_configs.append(cfg)
        db.commit()
        configs = created_configs

    items = [
        AgentConfigItem(
            agent_type=c.agent_type,
            is_enabled=c.is_enabled,
            is_mandatory=(c.agent_type in ("AGENT_1", "AGENT_3")),
            provider=c.provider,
            model_name=c.model_name,
        )
        for c in configs
    ]

    return ProjectConfigResponse(project_id=project.id, agents=items)


@router.put("/{project_id}/agents", response_model=ProjectConfigResponse)
def update_project_agent_configs(
    project_id: uuid.UUID,
    req: UpdateProjectConfigRequest,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )

    configs = db.query(ProjectAgentConfigORM).filter_by(project_id=project_id).all()
    if not configs:
        get_project_agent_configs(project_id=project_id, db=db)
        configs = db.query(ProjectAgentConfigORM).filter_by(project_id=project_id).all()

    config_map = {c.agent_type: c for c in configs}

    if "AGENT_2" in config_map:
        config_map["AGENT_2"].is_enabled = req.agent2_enabled
    if "AGENT_4" in config_map:
        config_map["AGENT_4"].is_enabled = req.agent4_enabled
    if "AGENT_5" in config_map:
        config_map["AGENT_5"].is_enabled = req.agent5_enabled

    db.commit()

    return get_project_agent_configs(project_id=project_id, db=db)
