import asyncio
import json
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.application.orchestration.orchestrator_service import OrchestratorService
from src.domain.enums import ProjectStatus
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


async def _run_orchestrator_job(project_id: uuid.UUID, requirement: str):
    db = SessionLocal()
    try:
        resolver = LLMProviderResolver()
        git_service = GitService(db=db)
        tracker = TokenTrackerService(db=db)
        orchestrator = OrchestratorService(db=db, resolver=resolver, git_service=git_service, tracker=tracker)
        await orchestrator.start_workflow(project_id=project_id, user_requirement=requirement)
    except Exception as e:
        print(f"Background orchestrator failed: {e}")
    finally:
        db.close()


@router.post("/start", response_model=StartWorkflowResponse, status_code=status.HTTP_200_OK)
def start_workflow_endpoint(
    req: StartWorkflowRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    cleaned = req.user_requirement.strip().lower().rstrip("!.,?")

    # 1. Conversational Greeting check
    if cleaned in GREETING_WORDS or len(cleaned) < 3:
        return StartWorkflowResponse(
            status="CONVERSATION",
            message="Greeting received.",
            is_greeting=True,
            assistant_reply=(
                "Hello! I am your Autonomous AI Software Engineer (AAISE). "
                "You can describe any application or feature you'd like to build (e.g. 'Build a Student Management CRUD API with FastAPI and SQLite'). "
                "I will coordinate the specialized agents to review specs, write code, run contract tests, and perform security audits. "
                "What would you like to build today?"
            ),
        )

    # 2. Genuine Requirement -> Create/Find Project & Trigger Orchestrator
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
        proj_name = req.project_name or req.user_requirement[:30]
        project = ProjectORM(
            name=proj_name,
            target_framework="PYTHON_FASTAPI",
            status=ProjectStatus.ACTIVE.value,
        )
        db.add(project)
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

    background_tasks.add_task(_run_orchestrator_job, project.id, req.user_requirement)

    return StartWorkflowResponse(
        workflow_run_id=run.id,
        project_id=project.id,
        status="RUNNING",
        message="Workflow initialized successfully and agent loop started.",
        is_greeting=False,
    )


@router.get("/{project_id}/artifacts")
def get_project_artifacts(project_id: uuid.UUID, db: Session = Depends(get_db)):
    files = db.query(ProjectFileORM).filter_by(project_id=project_id).all()
    return [
        {
            "id": str(f.id),
            "file_path": f.file_path,
            "file_type": f.file_type,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]


@router.post("/approval/resolve", response_model=ResolveApprovalResponse)
def resolve_approval_endpoint(
    req: ResolveApprovalRequest,
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
