from src.application.chat.chat_service import save_chat_message

import re

import asyncio

import io

import json

import uuid

from pathlib import Path

from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

import pdfplumber

from src.application.orchestration.orchestrator_service import OrchestratorService

from src.domain.enums import ProjectStatus, RepositoryType

from src.infrastructure.config import settings

from src.infrastructure.db.models import HumanApprovalORM, ProjectFileORM, ProjectORM, WorkflowEventORM, WorkflowRunORM

from src.infrastructure.db.session import SessionLocal, get_db

from src.infrastructure.git.git_service import GitService

from src.infrastructure.llm.provider_resolver import LLMProviderResolver

from src.infrastructure.llm.token_tracker import TokenTrackerService

from src.infrastructure.orchestration.approval_engine import ApprovalEngine

router = APIRouter(prefix="/workflow", tags=["workflow"])

GREETING_WORDS = {

    "hi", "hello", "hey", "salam", "assalam", "assalam o alaikum",

    "aoa", "good morning", "good evening", "good afternoon", "hola", "kese ho", "kaise ho"

}

def extract_text_from_file(filename: str, content: bytes) -> str:

    ext = Path(filename).suffix.lower()

    if ext == ".pdf":

        try:

            with pdfplumber.open(io.BytesIO(content)) as pdf:

                extracted = []

                for idx, page in enumerate(pdf.pages, start=1):

                    txt = page.extract_text(layout=True) or page.extract_text() or ""

                    tables = page.extract_tables()

                    if tables:

                        table_strs = []

                        for t in tables:

                            clean_rows = [" | ".join([cell if cell else "" for cell in row]) for row in t if any(row)]

                            if clean_rows:

                                table_strs.append("\n".join(clean_rows))

                        if table_strs:

                            txt += "\n\nTables:\n" + "\n\n".join(table_strs)

                    if txt.strip():

                        extracted.append(f"--- Page {idx} ---\n{txt}")

                return "\n\n".join(extracted)

        except Exception as e:

            return f"[Error parsing PDF {filename}: {e}]"

    else:

        try:

            return content.decode("utf-8")

        except UnicodeDecodeError:

            return content.decode("latin-1", errors="replace")

def detect_target_framework(text: str, default: str = "DOTNET_CSHARP") -> str:
    lower = text.lower()

    # 1. Check for C# / .NET indicators using word boundaries
    dotnet_patterns = [
        r"\basp\.net\b", r"\bc#\b", r"\bcsharp\b", r"\b\.net\b", r"\bdotnet\b",
        r"\bef core\b", r"\bentity framework\b", r"\bxunit\b", r"\bnunit\b"
    ]
    dotnet_score = sum(len(re.findall(p, lower)) for p in dotnet_patterns)

    # 2. Check for Python indicators using word boundaries
    python_patterns = [
        r"\bfastapi\b", r"\bpydantic\b", r"\bsqlalchemy\b", r"\bpython\b",
        r"\bflask\b", r"\bdjango\b", r"\bpytest\b", r"\buvicorn\b"
    ]
    python_score = sum(len(re.findall(p, lower)) for p in python_patterns)

    # 3. Check for Ruby on Rails using word boundaries
    ruby_patterns = [r"\brails\b", r"\bruby\b", r"\brspec\b", r"\bgemfile\b"]
    ruby_score = sum(len(re.findall(p, lower)) for p in ruby_patterns)

    # 4. Check for Next.js / React / TypeScript indicators (explicit tokens, no substring 'ui')
    next_patterns = [
        r"\bnext\.js\b", r"\bnextjs\b", r"\breact\b", r"\btypescript\b",
        r"\btailwind\b", r"\blucide\b", r"\bfrontend portal\b", r"\bclient component\b"
    ]
    next_score = sum(len(re.findall(p, lower)) for p in next_patterns)

    scores = {
        "DOTNET_CSHARP": dotnet_score,
        "PYTHON_FASTAPI": python_score,
        "RUBY_RAILS": ruby_score,
        "TYPESCRIPT_NEXTJS": next_score,
    }
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return default

class StartWorkflowRequest(BaseModel):

    project_id: str | None = None

    project_name: str | None = None

    user_requirement: str = Field(min_length=1)

class StartWorkflowResponse(BaseModel):

    workflow_run_id: uuid.UUID | None = None

    project_id: uuid.UUID | None = None

    status: str

    message: str

    is_greeting: bool = False

    assistant_reply: str | None = None

class ResolveApprovalRequest(BaseModel):

    approval_id: uuid.UUID

    approved: bool

    comments: str | None = None

class ResolveApprovalResponse(BaseModel):

    approval_id: uuid.UUID

    status: str

    reviewer_comments: str | None

def get_orchestrator(db: Session = Depends(get_db)) -> OrchestratorService:

    resolver = LLMProviderResolver()

    git_service = GitService(db=db)

    tracker = TokenTrackerService(db=db)

    return OrchestratorService(db=db, resolver=resolver, git_service=git_service, tracker=tracker)

async def _run_orchestrator_job(project_id: uuid.UUID, requirement: str, run_id: uuid.UUID | None = None):

    db = SessionLocal()

    try:

        resolver = LLMProviderResolver()

        git_service = GitService(db=db)

        tracker = TokenTrackerService(db=db)

        orchestrator = OrchestratorService(db=db, resolver=resolver, git_service=git_service, tracker=tracker)

        await orchestrator.start_workflow(project_id=project_id, user_requirement=requirement, workflow_run_id=run_id)

    except Exception as e:

        print(f"Background orchestrator failed: {e}")

        try:

            save_chat_message(db, project_id, "assistant", f"⚠️ Workflow Execution Error: {e}")

        except Exception:

            pass

    finally:

        db.close()

GIT_URL_REGEX = re.compile(r'https?://(?:www\.)?(?:github\.com|gitlab\.com)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?')

def handle_git_push_intent(user_text: str, project_id: str | None, db: Session) -> StartWorkflowResponse | None:

    match = GIT_URL_REGEX.search(user_text)

    if not match:

        return None

    repo_url = match.group(0).rstrip(".,;!?:")

    if not repo_url.endswith(".git"):

        repo_url = repo_url + ".git"

    # Identify target project

    project = None

    if project_id:

        try:

            p_uuid = uuid.UUID(project_id)

            project = db.query(ProjectORM).filter_by(id=p_uuid).first()

        except ValueError:

            pass

    if not project:

        project = db.query(ProjectORM).order_by(ProjectORM.created_at.desc()).first()

    if not project:

        return StartWorkflowResponse(

            status="ERROR",

            message="No active project found.",

            is_greeting=True,

            assistant_reply="❌ No active project found to push. Please select a project or describe your requirements first.",

        )

    git_service = GitService(db=db)

    channel_repo_path = Path(git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP))

    if not (channel_repo_path / ".git").exists():

        return StartWorkflowResponse(

            project_id=project.id,

            status="ERROR",

            message="Repository not initialized.",

            is_greeting=True,

            assistant_reply=(

                f"❌ Local Git repository for **{project.name}** has not been initialized yet.\n\n"

                "Please describe your requirements first so that code can be generated and committed before pushing to remote."

            ),

        )

    # Perform remote push

    push_result = git_service.push_to_remote(

        project_id=project.id,

        repo_type=RepositoryType.CHANNEL_APP,

        remote_url=repo_url,

    )

    if push_result.get("success"):

        branch = push_result.get("branch", "develop")

        reply = (

            f"✅ Git Push Successful!\n\n"

            f"```\n"

            f"branch '{branch}' set up to track 'origin/{branch}'.\n\n"

            f"To {repo_url}\n"

            f" * [new branch]      {branch} -> {branch}\n"

            f"```\n"

            f"All local commits have been pushed to remote repository."

        )

        save_chat_message(db, project.id, "user", user_text)

        save_chat_message(db, project.id, "assistant", reply)

        return StartWorkflowResponse(

            project_id=project.id,

            status="PUSH_SUCCESS",

            message="Git push completed successfully.",

            is_greeting=True,

            assistant_reply=reply,

        )

    else:

        err = push_result.get("error", "Unknown push error")

        reply = (

            f"⚠️ Git Push encountered an issue:\n\n"

            f"```\n{err}\n```\n\n"

            f"🔗 **Remote URL:** `{repo_url}`\n"

            f"📁 **Branch:** `{push_result.get('branch', 'develop')}`\n\n"

            f"Please verify that the repository exists on GitHub and that your environment has push access."

        )

        save_chat_message(db, project.id, "user", user_text)

        save_chat_message(db, project.id, "assistant", reply)

        return StartWorkflowResponse(

            project_id=project.id,

            status="PUSH_FAILED",

            message="Git push failed.",

            is_greeting=True,

            assistant_reply=reply,

        )

@router.post("/start", response_model=StartWorkflowResponse, status_code=status.HTTP_200_OK)

def start_workflow_endpoint(

    req: StartWorkflowRequest,

    background_tasks: BackgroundTasks,

    db: Session = Depends(get_db),

):

    cleaned = req.user_requirement.strip().lower().rstrip("!.,?")

    # Check for Git Push Intent

    git_push_resp = handle_git_push_intent(req.user_requirement, req.project_id, db)

    if git_push_resp:

        return git_push_resp

    # 1. Conversational Greeting check

    if cleaned in GREETING_WORDS or len(cleaned) < 3:

        return StartWorkflowResponse(

            status="CONVERSATION",

            message="Greeting received.",

            is_greeting=True,

            assistant_reply=(

                "Hello! I am your Autonomous AI Software Engineer (AAISE). "

                "You can describe any application or feature you'd like to build. "

                "I will coordinate the specialized agents to review specs, write code, run contract tests, and perform security audits. "

                "What would you like to build today?"

            ),

        )

    # 2. Dynamic target framework detection

    detected_framework = detect_target_framework(req.user_requirement)

    project = None

    if req.project_id:

        try:

            p_uuid = uuid.UUID(req.project_id)

            project = db.query(ProjectORM).filter_by(id=p_uuid).first()

            if not project:

                raise HTTPException(

                    status_code=status.HTTP_404_NOT_FOUND,

                    detail=f"Project {req.project_id} not found.",

                )

        except ValueError:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail=f"Invalid project_id {req.project_id}.",

            )

    if not project:

        proj_name = req.project_name or req.user_requirement[:30].strip()

        project = ProjectORM(

            name=proj_name,

            target_framework=detected_framework,

            status=ProjectStatus.ACTIVE.value,

        )

        db.add(project)

        db.commit()

    else:

        # Dynamically adopt detected framework if project has default framework

        if project.target_framework == "PYTHON_FASTAPI" and detected_framework != "PYTHON_FASTAPI":

            project.target_framework = detected_framework

            db.commit()

    run = (

        db.query(WorkflowRunORM)

        .filter_by(project_id=project.id)

        .order_by(WorkflowRunORM.created_at.desc())

        .first()

    )

    if not run or run.status in ("COMPLETED", "FAILED"):

        run = WorkflowRunORM(

            project_id=project.id,

            current_phase="SPECIFICATION",

            status="RUNNING",

        )

        db.add(run)

        db.commit()

    save_chat_message(db, project.id, "user", req.user_requirement)

    tdd_exists = (Path("./workspace") / str(project.id) / "docs" / "TECHNICAL_DESIGN.md").exists()

    is_qa_or_sec_intent = any(w in cleaned for w in ["agent4", "agent 4", "qa", "test", "agent5", "agent 5", "security", "audit"])

    is_qa_or_sec_intent = any(w in cleaned for w in ["agent4", "agent 4", "qa", "test", "agent5", "agent 5", "security", "audit"])

    is_continue_or_approve = (

        cleaned in {"continue", "approve", "approved", "proceed", "yes", "ok", "okay", "go ahead", "start coding", "write code", "code", "build", "build it", "chalo", "kro", "kardo"}

        or any(w in cleaned for w in ["approved", "proceed", "continue", "start coding", "write code"])

        or is_qa_or_sec_intent

    )

    if tdd_exists and is_continue_or_approve:

        pending_apps = (

            db.query(HumanApprovalORM)

            .join(WorkflowRunORM, HumanApprovalORM.workflow_run_id == WorkflowRunORM.id)

            .filter(WorkflowRunORM.project_id == project.id, HumanApprovalORM.status == "PENDING")

            .all()

        )

        for pa in pending_apps:

            pa.status = "APPROVED"

        run.current_phase = "QA_VERIFICATION" if is_qa_or_sec_intent else "DEVELOPMENT"

        run.status = "RUNNING"

        db.commit()

        if is_qa_or_sec_intent:

            save_chat_message(

                db,

                project.id,

                "agent4",

                "Running Agent 4 (Independent Black-Box QA) and Agent 5 (Security SAST Audit) against the application...",

            )

        else:

            save_chat_message(

                db,

                project.id,

                "agent3",

                "Specifications approved. Agent 3 (Main Coding Agent) is now synthesizing full application code and verifying build...",

            )

        background_tasks.add_task(

            _run_orchestrator_job,

            project.id,

            req.user_requirement if is_qa_or_sec_intent else "Specifications approved. Proceed with full application implementation and build verification.",

            run.id,

        )
    else:

        save_chat_message(

            db,

            project.id,

            "agent1",

            "Analyzing software requirements and architecture boundaries. Generating Technical Design Document (TDD) and Test Specifications...",

        )

        background_tasks.add_task(_run_orchestrator_job, project.id, req.user_requirement, run.id)

    return StartWorkflowResponse(

        workflow_run_id=run.id,

        project_id=project.id,

        status="RUNNING",

        message=f"Workflow initialized successfully. Detected target framework: {detected_framework}",

        is_greeting=False,

    )

@router.post("/start-multipart", response_model=StartWorkflowResponse, status_code=status.HTTP_200_OK)

async def start_workflow_multipart_endpoint(

    background_tasks: BackgroundTasks,

    project_id: str | None = Form(None),

    project_name: str | None = Form(None),

    user_requirement: str = Form(""),

    files: list[UploadFile] = File(None),

    db: Session = Depends(get_db),

):

    extracted_docs: list[str] = []

    if files:

        for f in files:

            content = await f.read()

            doc_text = extract_text_from_file(f.filename or "document", content)

            extracted_docs.append(f"### Document: {f.filename}\n\n{doc_text}")

    full_requirement = user_requirement.strip()

    if extracted_docs:

        docs_block = "\n\n".join(extracted_docs)

        if full_requirement:

            full_requirement = f"{full_requirement}\n\n## Attached Specifications:\n\n{docs_block}"

        else:

            full_requirement = docs_block

    # Check for Git Push Intent

    git_push_resp = handle_git_push_intent(full_requirement, project_id, db)

    if git_push_resp:

        return git_push_resp

    detected_framework = detect_target_framework(full_requirement)

    project = None

    if project_id:

        try:

            p_uuid = uuid.UUID(project_id)

            project = db.query(ProjectORM).filter_by(id=p_uuid).first()

        except ValueError:

            pass

    if not project:

        proj_name = project_name or (files[0].filename if files else "New Project")

        project = ProjectORM(

            name=proj_name,

            target_framework=detected_framework,

            status=ProjectStatus.ACTIVE.value,

        )

        db.add(project)

        db.commit()

    else:

        project.target_framework = detected_framework

        db.commit()

    run = (

        db.query(WorkflowRunORM)

        .filter_by(project_id=project.id)

        .order_by(WorkflowRunORM.created_at.desc())

        .first()

    )

    if not run or run.status in ("COMPLETED", "FAILED"):

        run = WorkflowRunORM(

            project_id=project.id,

            current_phase="SPECIFICATION",

            status="RUNNING",

        )

        db.add(run)

        db.commit()

    save_chat_message(db, project.id, "user", full_requirement)

    save_chat_message(

        db,

        project.id,

        "agent1",

        "Analyzing software requirements and architecture boundaries. Generating Technical Design Document (TDD) and Test Specifications...",

    )

    background_tasks.add_task(_run_orchestrator_job, project.id, full_requirement, run.id)

    return StartWorkflowResponse(

        workflow_run_id=run.id,

        project_id=project.id,

        status="RUNNING",

        message=f"Workflow initialized with documents. Target framework: {detected_framework}",

        is_greeting=False,

    )

@router.get("/{project_id}/artifacts")

def get_project_artifacts(project_id: uuid.UUID, db: Session = Depends(get_db)):

    files = db.query(ProjectFileORM).filter_by(project_id=project_id).all()

    result = []

    seen_paths = set()

    for f in files:

        rel = f.file_name or Path(f.file_path).name

        if "TECHNICAL_DESIGN" in f.file_type:

            rel = "docs/TECHNICAL_DESIGN.md"

        elif "TEST_SPECIFICATION" in f.file_type:

            rel = "docs/XUNIT_TEST_SPEC.md"

        seen_paths.add(rel)

        result.append({

            "id": str(f.id),

            "file_path": rel,

            "file_type": f.file_type,

            "created_at": f.created_at.isoformat() if f.created_at else None,

        })

    workspace_dir = Path("./workspace") / str(project_id)

    if workspace_dir.exists():

        docs_dir = workspace_dir / "docs"

        if docs_dir.exists():

            for p in docs_dir.glob("*.md"):

                rel = f"docs/{p.name}"

                if rel not in seen_paths:

                    seen_paths.add(rel)

                    result.append({

                        "id": str(uuid.uuid4()),

                        "file_path": rel,

                        "file_type": "TECHNICAL_DESIGN" if "DESIGN" in p.name else "TEST_SPECIFICATION",

                        "created_at": None,

                    })

        channel_dir = workspace_dir / "channel-app"

        if channel_dir.exists():

            import os

            skip_dirs = {".git", "node_modules", ".next", "bin", "obj", "__pycache__", ".vs"}

            for root, dirs, walk_files in os.walk(channel_dir):

                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]

                for fname in walk_files:

                    if fname.startswith("."):

                        continue

                    p = Path(root) / fname

                    rel_p = str(p.relative_to(workspace_dir)).replace("\\", "/")

                    if rel_p not in seen_paths:

                        seen_paths.add(rel_p)

                        result.append({

                            "id": str(uuid.uuid4()),

                            "file_path": rel_p,

                            "file_type": "CODE",

                            "created_at": None,

                        })

    return result

@router.post("/approval/resolve", response_model=ResolveApprovalResponse)

def resolve_approval_endpoint(

    req: ResolveApprovalRequest,

    background_tasks: BackgroundTasks,

    db: Session = Depends(get_db),

):

    engine = ApprovalEngine(db=db)

    try:

        resolved = engine.resolve_approval(

            approval_id=req.approval_id,

            approved=req.approved,

            reviewer_comments=req.comments,

        )

        db.commit()

        if req.approved:

            run = db.query(WorkflowRunORM).filter_by(id=resolved.workflow_run_id).first()

            if run:

                run.status = "RUNNING"

                run.current_phase = "DEVELOPMENT"

                db.commit()

                save_chat_message(

                    db,

                    run.project_id,

                    "user",

                    "Specifications approved. Proceed with full application implementation and build verification.",

                )

                save_chat_message(

                    db,

                    run.project_id,

                    "agent3",

                    "Starting application implementation, Clean Architecture directory setup, and component synthesis...",

                )

                background_tasks.add_task(

                    _run_orchestrator_job,

                    run.project_id,

                    "Specifications approved. Proceed with full application implementation and build verification.",

                    run.id,

                )

        return ResolveApprovalResponse(

            approval_id=resolved.id,

            status=resolved.status,

            reviewer_comments=resolved.reviewer_comments,

        )

    except ValueError as e:

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/{run_id}/stream")

async def stream_workflow_events(

    run_id: uuid.UUID,

    db: Session = Depends(get_db),

):

    run = db.query(WorkflowRunORM).filter_by(id=run_id).first()

    if not run:

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")

    async def event_generator() -> AsyncGenerator[str, None]:

        yield f"data: {json.dumps({'event': 'phase_started', 'phase': run.current_phase, 'status': run.status})}\n\n"

        approval = (

            db.query(HumanApprovalORM)

            .filter_by(workflow_run_id=run.id, status="PENDING")

            .order_by(HumanApprovalORM.requested_at.desc())

            .first()

        )

        if approval:

            yield f"data: {json.dumps({'event': 'approval_requested', 'approval_id': str(approval.id), 'gate_type': approval.gate_type})}\n\n"

        await asyncio.sleep(0.5)

        yield f"data: {json.dumps({'event': 'stream_end', 'status': 'connected'})}\n\n"

    return StreamingResponse(

        event_generator(),

        media_type="text/event-stream",

        headers={

            "Cache-Control": "no-cache",

            "Connection": "keep-alive",

            "X-Accel-Buffering": "no",

        },

    )