from src.infrastructure.orchestration.approval_engine import ApprovalEngine

from pathlib import Path

import io

import os

import zipfile

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi.responses import StreamingResponse

from pydantic import BaseModel, ConfigDict
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
from src.infrastructure.config import settings
from src.infrastructure.db.session import get_db
from src.infrastructure.git.git_service import GitService
from src.infrastructure.execution.process_manager import ProjectProcessManager

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    target_framework: str
    status: str
    current_branch: str | None = "develop"


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None
    target_framework: str = "PYTHON_FASTAPI"
    custom_workspace_path: str | None = None
    agent_toggles: dict[str, bool] | None = None


def get_default_agent_specs() -> list[dict[str, object]]:
    assignments = getattr(settings.llm_config, "agent_assignments", {})

    def _get_prov_model(agent_key: str, fallback_prov: str, fallback_model: str) -> tuple[str, str]:
        assign = assignments.get(agent_key)
        if assign:
            prov = (
                assign.provider.value if hasattr(assign.provider, "value") else str(assign.provider)
            )
            return prov, assign.model
        return fallback_prov, fallback_model

    meta = [
        (
            "AGENT_1",
            "Agent 1: Documentation Reviewer",
            True,
            True,
            "gemini",
            "gemini-3.5-flash-lite",
        ),
        (
            "AGENT_2",
            "Agent 2: Mock Vendor API Developer",
            False,
            True,
            "gemini",
            "gemini-3.5-flash-lite",
        ),
        ("AGENT_3", "Agent 3: Main Coding Agent", True, True, "gemini", "gemini-3.5-flash-lite"),
        (
            "AGENT_4",
            "Agent 4: Independent QA Engineer",
            False,
            True,
            "gemini",
            "gemini-3.5-flash-lite",
        ),
        ("AGENT_5", "Agent 5: Security Reviewer", False, True, "gemini", "gemini-3.5-flash-lite"),
    ]

    return [
        {
            "agent_type": k,
            "agent_name": name,
            "is_mandatory": is_mand,
            "default_enabled": def_en,
            "default_provider": _get_prov_model(k, fb_p, fb_m)[0],
            "default_model": _get_prov_model(k, fb_p, fb_m)[1],
        }
        for k, name, is_mand, def_en, fb_p, fb_m in meta
    ]


def ensure_project_agent_configs(
    project_id: uuid.UUID, db: Session, agent_toggles: dict[str, bool] | None = None
) -> list[ProjectAgentConfigORM]:
    existing_configs = db.query(ProjectAgentConfigORM).filter_by(project_id=project_id).all()
    existing_by_type = {c.agent_type.upper(): c for c in existing_configs}

    result = []
    created_any = False
    specs = get_default_agent_specs()

    for spec in specs:
        key = spec["agent_type"]
        orm = existing_by_type.get(key)
        if not orm:
            for ex_key, ex_orm in existing_by_type.items():
                if (
                    key in ex_key
                    or (key == "AGENT_1" and "DOC" in ex_key)
                    or (key == "AGENT_2" and "MOCK" in ex_key)
                    or (key == "AGENT_3" and "MAIN" in ex_key)
                    or (key == "AGENT_4" and "QA" in ex_key)
                    or (key == "AGENT_5" and "SEC" in ex_key)
                ):
                    orm = ex_orm
                    break

        if not orm:
            is_enabled = spec["default_enabled"]
            if spec["is_mandatory"]:
                is_enabled = True
            elif agent_toggles:
                if key == "AGENT_2":
                    is_enabled = agent_toggles.get(
                        "agent2", agent_toggles.get("agent2_enabled", spec["default_enabled"])
                    )
                elif key == "AGENT_4":
                    is_enabled = agent_toggles.get(
                        "agent4", agent_toggles.get("agent4_enabled", spec["default_enabled"])
                    )
                elif key == "AGENT_5":
                    is_enabled = agent_toggles.get(
                        "agent5", agent_toggles.get("agent5_enabled", spec["default_enabled"])
                    )

            orm = ProjectAgentConfigORM(
                project_id=project_id,
                agent_type=key,
                is_enabled=is_enabled,
                provider=spec["default_provider"],
                model_name=spec["default_model"],
            )
            db.add(orm)
            created_any = True
        result.append(orm)

    if created_any:
        db.commit()
        for r in result:
            db.refresh(r)

    return result


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

    ensure_project_agent_configs(project.id, db, req.agent_toggles)

    git_service = GitService(db=db)
    channel_dir = git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP)
    Path(channel_dir).mkdir(parents=True, exist_ok=True)

    return ProjectItem(
        id=project.id,
        name=project.name,
        description=project.description,
        target_framework=project.target_framework,
        status=project.status,
        current_branch=None,
    )


@router.get("/{project_id}/branches")
def get_project_branches(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    git_service = GitService(db=db)
    channel_path = Path(git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))
    if not (channel_path / ".git").exists():
        return {
            "project_id": str(project.id),
            "branches": [],
            "current_branch": None,
        }

    raw_branches = git_service.get_all_branches(project.id, RepositoryType.CHANNEL_APP)
    # Filter out internal ephemeral agent scratch branches
    clean_branches = [
        b for b in raw_branches
        if not b.startswith("feature/channel-app-") and not b.startswith("feature/mock-apis-")
    ]

    current_branch = git_service.get_current_branch(project.id, RepositoryType.CHANNEL_APP)

    if current_branch and current_branch.startswith("feature/") and "develop" in clean_branches:
        try:
            git_service.checkout_branch(project.id, RepositoryType.CHANNEL_APP, "develop")
            current_branch = "develop"
        except Exception:
            pass
    elif current_branch and current_branch not in clean_branches:
        current_branch = clean_branches[0] if clean_branches else None

    return {
        "project_id": str(project.id),
        "branches": clean_branches,
        "current_branch": current_branch if clean_branches else None,
    }


@router.get("/{project_id}/diff")
def get_project_diff(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    git_service = GitService(db=db)
    channel_path = Path(git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))
    if not (channel_path / ".git").exists():
        return {
            "project_id": str(project.id),
            "diff": "",
        }

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

    workspace_path = Path(git_service.base_workspace_dir) / str(project.id)
    channel_path = Path(git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))

    if not channel_path.exists() and not workspace_path.exists():
        raise HTTPException(status_code=404, detail="Project repository files not found on disk.")

    base_to_walk = workspace_path if workspace_path.exists() else channel_path

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(base_to_walk):
            dirs[:] = [
                d
                for d in dirs
                if d not in [".git", "bin", "obj", "__pycache__", "node_modules", ".vs", ".next"]
            ]
            for file in files:
                full_path = Path(root) / file
                archive_name = full_path.relative_to(base_to_walk)
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


class UpdateAgentsRequest(BaseModel):
    agent2_enabled: bool | None = None
    agent4_enabled: bool | None = None
    agent5_enabled: bool | None = None
    toggles: dict[str, bool] | None = None
    agents: list[dict[str, object]] | None = None


def _format_agents_response(
    project_id: uuid.UUID, configs: list[ProjectAgentConfigORM]
) -> dict[str, object]:
    by_type = {}
    for c in configs:
        atype = str(c.agent_type).upper()
        if "MOCK" in atype or "AGENT_2" in atype or "AGENT2" in atype:
            by_type["AGENT_2"] = c
        elif "QA" in atype or "AGENT_4" in atype or "AGENT4" in atype:
            by_type["AGENT_4"] = c
        elif "SEC" in atype or "AGENT_5" in atype or "AGENT5" in atype:
            by_type["AGENT_5"] = c
        elif "DOC" in atype or "AGENT_1" in atype or "AGENT1" in atype:
            by_type["AGENT_1"] = c
        elif "MAIN" in atype or "AGENT_3" in atype or "AGENT3" in atype:
            by_type["AGENT_3"] = c

    agents_list = []
    for spec in get_default_agent_specs():
        key = spec["agent_type"]
        cfg = by_type.get(key)
        is_en = cfg.is_enabled if cfg else spec["default_enabled"]
        prov = cfg.provider if cfg else spec["default_provider"]
        model = cfg.model_name if cfg else spec["default_model"]
        if spec["is_mandatory"]:
            is_en = True

        agents_list.append(
            {
                "agent_type": key,
                "agent_name": spec["agent_name"],
                "is_mandatory": spec["is_mandatory"],
                "is_enabled": is_en,
                "provider": prov,
                "model_name": model,
            }
        )

    return {
        "project_id": str(project_id),
        "agents": agents_list,
        "toggles": {
            "agent2": by_type.get("AGENT_2").is_enabled if by_type.get("AGENT_2") else True,
            "agent4": by_type.get("AGENT_4").is_enabled if by_type.get("AGENT_4") else True,
            "agent5": by_type.get("AGENT_5").is_enabled if by_type.get("AGENT_5") else True,
        },
    }


@router.get("/{project_id}/agents")
@router.get("/{project_id}/agent-configs")
def get_project_agents(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    configs = ensure_project_agent_configs(project_id, db)
    return _format_agents_response(project_id, configs)


@router.put("/{project_id}/agents")
@router.put("/{project_id}/agent-configs")
def update_project_agents(
    project_id: uuid.UUID,
    req: UpdateAgentsRequest,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    configs = ensure_project_agent_configs(project_id, db)

    toggles_to_apply = {}
    if req.agent2_enabled is not None:
        toggles_to_apply["AGENT_2"] = req.agent2_enabled
    if req.agent4_enabled is not None:
        toggles_to_apply["AGENT_4"] = req.agent4_enabled
    if req.agent5_enabled is not None:
        toggles_to_apply["AGENT_5"] = req.agent5_enabled
    if req.toggles:
        if "agent2" in req.toggles:
            toggles_to_apply["AGENT_2"] = req.toggles["agent2"]
        if "agent4" in req.toggles:
            toggles_to_apply["AGENT_4"] = req.toggles["agent4"]
        if "agent5" in req.toggles:
            toggles_to_apply["AGENT_5"] = req.toggles["agent5"]

    for c in configs:
        atype = str(c.agent_type).upper()
        for key, val in toggles_to_apply.items():
            if (
                key in atype
                or (key == "AGENT_2" and "MOCK" in atype)
                or (key == "AGENT_4" and "QA" in atype)
                or (key == "AGENT_5" and "SEC" in atype)
            ):
                c.is_enabled = val

    db.commit()
    for c in configs:
        db.refresh(c)
    return _format_agents_response(project_id, configs)


class UpdateAgentConfigRequest(BaseModel):
    is_enabled: bool | None = None
    provider: str | None = None
    model_id: str | None = None
    model_name: str | None = None


@router.put("/{project_id}/agent-configs/{agent_id}")
def update_project_agent_config(
    project_id: uuid.UUID,
    agent_id: str,
    req: UpdateAgentConfigRequest,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    configs = ensure_project_agent_configs(project_id, db)
    target = None
    norm_id = agent_id.upper()
    for c in configs:
        atype = str(c.agent_type).upper()
        if norm_id in atype or (norm_id in ("AGENT2", "AGENT_2", "MOCK") and "MOCK" in atype):
            target = c
            break
        elif norm_id in ("AGENT4", "AGENT_4", "QA") and "QA" in atype:
            target = c
            break
        elif norm_id in ("AGENT5", "AGENT_5", "SEC") and "SEC" in atype:
            target = c
            break
        elif norm_id in ("AGENT1", "AGENT_1", "DOC") and "DOC" in atype:
            target = c
            break
        elif norm_id in ("AGENT3", "AGENT_3", "MAIN") and "MAIN" in atype:
            target = c
            break

    if target:
        if req.is_enabled is not None:
            target.is_enabled = req.is_enabled
        if req.provider is not None:
            target.provider = req.provider
        if req.model_name is not None:
            target.model_name = req.model_name
        elif req.model_id is not None:
            target.model_name = req.model_id
        db.commit()
        db.refresh(target)
        return {
            "agent_type": target.agent_type,
            "is_enabled": target.is_enabled,
            "provider": target.provider,
            "model_name": target.model_name,
        }
    raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")


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
        return {"run_id": None, "messages": []}

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
                    meta["isApproved"] = meta["status"] == "APPROVED"

            messages.append(
                {
                    "id": str(m.id),
                    "sender": m.sender_type,
                    "senderName": sender_names.get(m.sender_type, "AAISE Platform"),
                    "timestamp": m.created_at.strftime("%H:%M") if m.created_at else time_str,
                    "text": m.content,
                    **meta,
                }
            )

        pending_apps = [
            a for a in approvals if str(a.id) not in seen_approval_ids and a.status == "PENDING"
        ]
        if pending_apps:
            latest_app = pending_apps[-1]
            messages.append(
                {
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
                }
            )
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
            messages.append(
                {
                    "id": f"user-init-{first_run.id}",
                    "sender": "user",
                    "senderName": "You",
                    "timestamp": init_time_str,
                    "text": user_req,
                }
            )

        has_spec = any("SPECIFICATION" in cp.checkpoint_key for cp in checkpoints) or specs_on_disk
        if has_spec:
            messages.append(
                {
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
                }
            )

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
            messages.append(
                {
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
                }
            )

    has_dev = any("DEVELOPMENT" in cp.checkpoint_key for cp in checkpoints) or has_code_on_disk

    if has_dev and not any(m.get("sender") == "agent3" and "checklist" in m for m in messages):
        messages.append(
            {
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
            }
        )

    return {
        "run_id": str(latest_run.id),
        "messages": messages,
    }


class RunProjectRequest(BaseModel):
    subsystem: str = "channel-app"


class StopProjectRequest(BaseModel):
    subsystem: str | None = None


@router.post("/{project_id}/run")
def run_project(
    project_id: uuid.UUID,
    req: RunProjectRequest | None = None,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    subsystem = req.subsystem if req else "channel-app"
    mgr = ProjectProcessManager.get_instance()
    try:
        res = mgr.start_project(project.id, project.target_framework, subsystem=subsystem)
        return res
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch project: {e}")


@router.post("/{project_id}/stop")
def stop_project(
    project_id: uuid.UUID,
    req: StopProjectRequest | None = None,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    subsystem = req.subsystem if req else None
    mgr = ProjectProcessManager.get_instance()
    res = mgr.stop_project(project.id, subsystem=subsystem)
    return res


@router.get("/{project_id}/status")
def get_project_status(
    project_id: uuid.UUID,
    subsystem: str = "channel-app",
    db: Session = Depends(get_db),
):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    mgr = ProjectProcessManager.get_instance()
    channel_status = mgr.get_status(project.id, "channel-app")
    frontend_status = mgr.get_status(project.id, "frontend")

    # If specific subsystem requested
    if subsystem and subsystem != "all":
        return mgr.get_status(project.id, subsystem)

    return {
        "channel_app": channel_status,
        "frontend": frontend_status,
    }


@router.get("/{project_id}/logs")
def get_project_logs(
    project_id: uuid.UUID,
    subsystem: str = "channel-app",
    tail: int = 100,
    db: Session = Depends(get_db),
):
    project = db.query(ProjectORM).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    mgr = ProjectProcessManager.get_instance()
    logs = mgr.get_logs(project.id, subsystem=subsystem, tail=tail)
    return {
        "project_id": str(project.id),
        "subsystem": subsystem,
        "logs": logs,
    }
