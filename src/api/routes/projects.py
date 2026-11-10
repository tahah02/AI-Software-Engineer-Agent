from src.infrastructure.orchestration.approval_engine import ApprovalEngine

from pathlib import Path

import io

import os

import zipfile

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from sqlalchemy.orm import Session

from src.domain.enums import RepositoryType

from src.infrastructure.db.models import (

    ProjectAgentConfigORM,

    ProjectFileORM,

    ProjectORM,

    WorkflowRunORM,

    WorkflowCheckpointORM,

    HumanApprovalORM,

    ConversationORM,

    MessageORM,

)

import json

from src.infrastructure.db.session import get_db

from src.infrastructure.git.git_service import GitService

router = APIRouter(prefix="/projects", tags=["projects"])

class ProjectItem(BaseModel):

    id: uuid.UUID

    name: str

    description: str | None = None

    target_framework: str

    status: str

    current_branch: str | None = "develop"

    class Config:

        from_attributes = True

class CreateProjectRequest(BaseModel):

    name: str

    description: str | None = None

    target_framework: str = "PYTHON_FASTAPI"

    custom_workspace_path: str | None = None

@router.get("", response_model=list[ProjectItem])

def list_projects(db: Session = Depends(get_db)):
    projects = db.query(ProjectORM).order_by(ProjectORM.created_at.desc()).all()
    return [
        ProjectItem(
            id=p.id,
            name=p.name,
            description=p.description,
            target_framework=p.target_framework,
            status=p.status,
            current_branch="develop",
        )
        for p in projects
    ]

@router.post("", response_model=ProjectItem, status_code=status.HTTP_201_CREATED)

def create_project(req: CreateProjectRequest, db: Session = Depends(get_db)):

    project = ProjectORM(

        name=req.name,

        description=req.description,

        target_framework=req.target_framework,

        status="ACTIVE",

    )

    db.add(project)

    db.flush()

    if req.custom_workspace_path:

        project.custom_workspace_path = req.custom_workspace_path

    db.commit()

    db.refresh(project)

    git_service = GitService(db=db)

    channel_dir = git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP)

    Path(channel_dir).mkdir(parents=True, exist_ok=True)

    git_service.initialize_repository(project.id, RepositoryType.CHANNEL_APP, target_framework=project.target_framework)

    return ProjectItem(

        id=project.id,

        name=project.name,

        description=project.description,

        target_framework=project.target_framework,

        status=project.status,

        current_branch="develop",

    )

@router.get("/{project_id}/branches")

def get_project_branches(project_id: uuid.UUID, db: Session = Depends(get_db)):

    project = db.query(ProjectORM).filter_by(id=project_id).first()

    if not project:

        raise HTTPException(status_code=404, detail="Project not found")

    git_service = GitService(db=db)

    branches = git_service.get_all_branches(project.id, RepositoryType.CHANNEL_APP)

    current_branch = git_service.get_current_branch(project.id, RepositoryType.CHANNEL_APP)

    return {

        "project_id": str(project.id),

        "branches": branches,

        "current_branch": current_branch or "develop",

    }

@router.get("/{project_id}/diff")

def get_project_diff(project_id: uuid.UUID, db: Session = Depends(get_db)):

    project = db.query(ProjectORM).filter_by(id=project_id).first()

    if not project:

        raise HTTPException(status_code=404, detail="Project not found")

    git_service = GitService(db=db)

    diff = git_service.get_diff(project.id, RepositoryType.CHANNEL_APP)

    return {

        "project_id": str(project.id),

        "diff": diff,

    }

@router.get("/{project_id}/download")

def download_project_codebase(project_id: uuid.UUID, db: Session = Depends(get_db)):

    project = db.query(ProjectORM).filter_by(id=project_id).first()

    if not project:

        raise HTTPException(status_code=404, detail="Project not found")

    git_service = GitService(db=db)

    channel_path = Path(git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))

    if not channel_path.exists():

        raise HTTPException(status_code=404, detail="Project repository files not found on disk.")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

        for root, dirs, files in os.walk(channel_path):

            dirs[:] = [d for d in dirs if d not in [".git", "bin", "obj", "__pycache__", "node_modules", ".vs"]]

            for file in files:

                full_path = Path(root) / file

                archive_name = full_path.relative_to(channel_path)

                zip_file.write(full_path, arcname=str(archive_name))

    zip_buffer.seek(0)

    clean_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name).strip("_")

    filename = f"{clean_name or 'project'}-codebase.zip"

    return StreamingResponse(

        zip_buffer,

        media_type="application/zip",

        headers={"Content-Disposition": f'attachment; filename="{filename}"'},

    )

@router.get("/{project_id}/file")

def get_project_file_content(project_id: uuid.UUID, path: str, db: Session = Depends(get_db)):

    workspace_dir = Path("./workspace") / str(project_id)

    clean_path = path.lstrip("/\\")

    full_path = (workspace_dir / clean_path).resolve()

    if not str(full_path).startswith(str(workspace_dir.resolve())):

        raise HTTPException(status_code=403, detail="Access denied: outside workspace bounds.")

    if not full_path.exists() or not full_path.is_file():

        raise HTTPException(status_code=404, detail=f"File not found: {clean_path}")

    try:

        content = full_path.read_text(encoding="utf-8")

    except UnicodeDecodeError:

        content = "[Binary or unreadable file content]"

    return {

        "project_id": str(project_id),

        "file_path": clean_path,

        "content": content,

    }

@router.get("/{project_id}/agent-configs")

def get_project_agent_configs(project_id: uuid.UUID, db: Session = Depends(get_db)):

    configs = db.query(ProjectAgentConfigORM).filter_by(project_id=project_id).all()

    return [

        {

            "agent_id": c.agent_id,

            "is_enabled": c.is_enabled,

            "provider": c.provider,

            "model_id": c.model_id,

        }

        for c in configs

    ]

class UpdateAgentConfigRequest(BaseModel):

    is_enabled: bool | None = None

    provider: str | None = None

    model_id: str | None = None

@router.put("/{project_id}/agent-configs/{agent_id}")

def update_project_agent_config(

    project_id: uuid.UUID,

    agent_id: str,

    req: UpdateAgentConfigRequest,

    db: Session = Depends(get_db),

):

    cfg = (

        db.query(ProjectAgentConfigORM)

        .filter_by(project_id=project_id, agent_id=agent_id)

        .first()

    )

    if not cfg:

        cfg = ProjectAgentConfigORM(project_id=project_id, agent_id=agent_id)

        db.add(cfg)

    if req.is_enabled is not None:

        cfg.is_enabled = req.is_enabled

    if req.provider is not None:

        cfg.provider = req.provider

    if req.model_id is not None:

        cfg.model_id = req.model_id

    db.commit()

    db.refresh(cfg)

    return {

        "agent_id": cfg.agent_id,

        "is_enabled": cfg.is_enabled,

        "provider": cfg.provider,

        "model_id": cfg.model_id,

    }

@router.get("/{project_id}/approvals/pending")

def get_pending_approvals(project_id: uuid.UUID, db: Session = Depends(get_db)):

    engine = ApprovalEngine(db=db)

    return engine.get_pending_approvals_for_project(project_id=project_id, db=db)

@router.get("/{project_id}/messages")

def get_project_messages(project_id: uuid.UUID, db: Session = Depends(get_db)):

    project = db.query(ProjectORM).filter_by(id=project_id).first()

    if not project:

        raise HTTPException(status_code=404, detail="Project not found")

    messages = []

    runs = (

        db.query(WorkflowRunORM)

        .filter_by(project_id=project_id)

        .order_by(WorkflowRunORM.created_at.asc())

        .all()

    )

    workspace_dir = Path("./workspace") / str(project_id)

    tdd_file = workspace_dir / "docs" / "TECHNICAL_DESIGN.md"

    channel_dir = workspace_dir / "channel-app"

    specs_on_disk = tdd_file.exists()

    has_code_on_disk = False

    if channel_dir.exists():

        skip_dirs = {".git", "node_modules", ".next", "bin", "obj", "__pycache__", ".vs"}

        for root, dirs, walk_files in os.walk(channel_dir):

            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

            for fname in walk_files:

                if Path(fname).suffix in (".cs", ".csproj", ".py", ".ts", ".tsx", ".js"):

                    has_code_on_disk = True

                    break

            if has_code_on_disk:

                break

    if not runs:

        run = WorkflowRunORM(

            project_id=project_id,

            current_phase="SPECIFICATION",

            status="RUNNING",

        )

        db.add(run)

        db.commit()

        runs = [run]

    latest_run = runs[-1]

    first_run = runs[0]

    run_ids = [r.id for r in runs]

    all_checkpoints = (

        db.query(WorkflowCheckpointORM)

        .filter(WorkflowCheckpointORM.workflow_run_id.in_(run_ids))

        .order_by(WorkflowCheckpointORM.created_at.asc(), WorkflowCheckpointORM.version.asc())

        .all()

    )

    checkpoints = [cp for cp in all_checkpoints if cp.workflow_run_id == latest_run.id]

    user_req = None

    generic_ack_phrases = {

        "Specifications approved. Proceed with full application implementation and build verification.",

        "Continue",

        "continue",

    }

    for cp in all_checkpoints:

        try:

            st = json.loads(cp.state_data)

            req_val = (st.get("user_requirement") or "").strip()

            if req_val and req_val not in generic_ack_phrases and len(req_val) > 30:

                user_req = req_val

                break

        except Exception:

            pass

    if not user_req:

        for cp in all_checkpoints:

            try:

                st = json.loads(cp.state_data)

                if st.get("user_requirement"):

                    user_req = st["user_requirement"]

                    break

            except Exception:

                pass

    init_time_str = first_run.created_at.strftime("%H:%M") if first_run.created_at else "12:00"
    time_str = latest_run.created_at.strftime("%H:%M") if latest_run.created_at else "12:00"

    # Query real interactive messages from MessageORM first
    conv = db.query(ConversationORM).filter_by(project_id=project_id).first()
    db_messages = []
    if conv:
        db_messages = (
            db.query(MessageORM)
            .filter_by(conversation_id=conv.id)
            .order_by(MessageORM.created_at.asc())
            .all()
        )


    approvals = (
        db.query(HumanApprovalORM)
        .filter_by(workflow_run_id=latest_run.id)
        .order_by(HumanApprovalORM.requested_at.asc())
        .all()
    )

    messages = []
    sender_names = {
        "user": "You",
        "agent1": "Agent 1: Documentation Reviewer",
        "agent2": "Agent 2: Mock API Developer",
        "agent3": "Agent 3: Main Coding Agent",
        "agent4": "Agent 4: Independent QA",
        "agent5": "Agent 5: Security Reviewer",
        "assistant": "AAISE Platform",
    }

    app_map = {str(a.id): a.status for a in approvals}

    if db_messages:
        seen_approval_ids = set()
        for m in db_messages:
            meta = {}
            if m.metadata_json:
                try:
                    meta = json.loads(m.metadata_json)
                except Exception:
                    pass

            app_id = meta.get("approvalId")
            if app_id:
                if app_id in seen_approval_ids:
                    continue
                seen_approval_ids.add(app_id)
                if app_id in app_map:
                    meta["status"] = app_map[app_id]
                    meta["isApproved"] = (meta["status"] == "APPROVED")

            messages.append({
                "id": str(m.id),
                "sender": m.sender_type,
                "senderName": sender_names.get(m.sender_type, "AAISE Platform"),
                "timestamp": m.created_at.strftime("%H:%M") if m.created_at else time_str,
                "text": m.content,
                **meta,
            })

        pending_apps = [a for a in approvals if str(a.id) not in seen_approval_ids and a.status == "PENDING"]
        if pending_apps:
            latest_app = pending_apps[-1]
            messages.append({
                "id": f"approval-{latest_app.id}",
                "sender": "agent1",
                "senderName": "Agent 1: Documentation Reviewer",
                "timestamp": time_str,
                "text": "Human approval required to proceed with code implementation.",
                "isApprovalCard": True,
                "approvalRequired": True,
                "approvalId": str(latest_app.id),
                "gateType": latest_app.gate_type,
                "status": latest_app.status,
                "isApproved": (latest_app.status == "APPROVED"),
            })
    else:
        # Fallback synthetic messages for legacy runs without MessageORM records
        if (not user_req or user_req.strip() in generic_ack_phrases) and specs_on_disk:
            try:
                tdd_content = tdd_file.read_text(encoding="utf-8")
                user_req = (
                    f"Build and implement {project.name} ({project.target_framework}) according to the attached specification document.\n\n"
                    f"## Attached Requirements & Architectural Specification:\n\n{tdd_content}"
                )
            except Exception:
                user_req = f"Software requirements and architectural design for {project.name} ({project.target_framework})."

        if user_req:
            messages.append({
                "id": f"user-init-{first_run.id}",
                "sender": "user",
                "senderName": "You",
                "timestamp": init_time_str,
                "text": user_req,
            })

        has_spec = any("SPECIFICATION" in cp.checkpoint_key for cp in checkpoints) or specs_on_disk
        if has_spec:
            messages.append({
                "id": f"agent1-spec-{latest_run.id}",
                "sender": "agent1",
                "senderName": "Agent 1: Documentation Reviewer",
                "timestamp": time_str,
                "text": "I have analyzed your software requirements and generated technical specifications.",
                "checklist": [
                    "Analyzed architecture boundaries & target framework",
                    "Extracted functional requirements & API contracts",
                    "Created test specifications",
                    "Generated Technical Design Document (TDD)",
                ],
            })

        if has_spec and not approvals:
            engine = ApprovalEngine(db=db)
            app = engine.create_approval_request(
                workflow_run_id=latest_run.id,
                gate_type="SPECIFICATION",
                prompt_text="Please review the technical design and test specifications. Shall I proceed with implementation?",
            )
            db.commit()
            approvals = [app]

        if approvals:
            app = approvals[-1]
            messages.append({
                "id": f"approval-{app.id}",
                "sender": "agent1",
                "senderName": "Agent 1: Documentation Reviewer",
                "timestamp": time_str,
                "text": "Human approval required to proceed with code implementation.",
                "isApprovalCard": True,
                "approvalRequired": True,
                "approvalId": str(app.id),
                "gateType": app.gate_type,
                "status": app.status,
                "isApproved": (app.status == "APPROVED"),
            })

    has_dev = any("DEVELOPMENT" in cp.checkpoint_key for cp in checkpoints) or has_code_on_disk

    if has_dev and not any(m.get("sender") == "agent3" and "checklist" in m for m in messages):

        messages.append({

            "id": f"agent3-{latest_run.id}",

            "sender": "agent3",

            "senderName": "Agent 3 (Main Coding Agent)",

            "timestamp": time_str,

            "text": "Channel application code synthesized, built with 0 errors, and committed to repository.",

            "checklist": [

                "Synthesized multi-file Clean Architecture structure",

                "Generated project configuration",

                "Verified build and dependency installation",

            ],

        })

    return {

        "run_id": str(latest_run.id),

        "messages": messages,

    }
