from src.application.chat.chat_service import save_chat_message

import re

import asyncio

import io

import json

import uuid

from pathlib import Path

from typing import AsyncGenerator

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

import pdfplumber

from src.application.orchestration.orchestrator_service import OrchestratorService

from src.domain.enums import ProjectStatus, RepositoryType

from src.infrastructure.config import settings

from src.infrastructure.db.models import (
    HumanApprovalORM,
    ProjectFileORM,
    ProjectORM,
    WorkflowEventORM,
    WorkflowRunORM,
)

from src.infrastructure.db.session import SessionLocal, get_db

from src.infrastructure.git.git_service import GitService
from src.infrastructure.execution.process_manager import ProjectProcessManager

from src.infrastructure.llm.provider_resolver import LLMProviderResolver

from src.infrastructure.llm.token_tracker import TokenTrackerService

from src.infrastructure.orchestration.approval_engine import ApprovalEngine

router = APIRouter(prefix="/workflow", tags=["workflow"])

GREETING_WORDS = {
    "hi",
    "hello",
    "hey",
    "heyy",
    "hiii",
    "salam",
    "assalam",
    "assalam o alaikum",
    "aoa",
    "good morning",
    "good evening",
    "good afternoon",
    "hola",
    "kese ho",
    "kaise ho",
    "kya haal hai",
    "kya hal hai",
    "what's up",
    "whats up",
    "sup",
    "yo",
    "test",
    "testing",
    "hi there",
    "hello there",
    "how are you",
    "who are you",
    "help",
    "ok",
    "okay",
    "thanks",
    "thank you",
    "bye",
    "goodbye",
}

TECHNICAL_KEYWORDS = {
    "api",
    "app",
    "crud",
    "endpoint",
    "backend",
    "frontend",
    "fastapi",
    "dotnet",
    "c#",
    "csharp",
    "python",
    "sqlite",
    "postgres",
    "sql",
    "database",
    "service",
    "system",
    "controller",
    "repository",
    "auth",
    "login",
    "jwt",
    "model",
    "build",
    "create",
    "develop",
    "implement",
    "spec",
    "srs",
    "requirements",
    "entity",
    "microservice",
}


def is_conversational_or_greeting(text: str) -> bool:
    import re

    raw = (text or "").strip()
    if not raw:
        return True

    cleaned = raw.lower().rstrip("!.,? \t\n")
    alpha_only = re.sub(r"[^a-zA-Z\s]", "", cleaned).strip()

    if cleaned in GREETING_WORDS or alpha_only in GREETING_WORDS:
        return True

    words = re.findall(r"[a-zA-Z0-9_#+]+", cleaned)
    if len(words) <= 3:
        if not any(w in TECHNICAL_KEYWORDS for w in words):
            return True

    return False


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
                            clean_rows = [
                                " | ".join([cell if cell else "" for cell in row])
                                for row in t
                                if any(row)
                            ]

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
        r"\basp\.net\b",
        r"\bc#\b",
        r"\bcsharp\b",
        r"\b\.net\b",
        r"\bdotnet\b",
        r"\bef core\b",
        r"\bentity framework\b",
        r"\bxunit\b",
        r"\bnunit\b",
    ]
    dotnet_score = sum(len(re.findall(p, lower)) for p in dotnet_patterns)

    # 2. Check for Python indicators using word boundaries
    python_patterns = [
        r"\bfastapi\b",
        r"\bpydantic\b",
        r"\bsqlalchemy\b",
        r"\bpython\b",
        r"\bflask\b",
        r"\bdjango\b",
        r"\bpytest\b",
        r"\buvicorn\b",
    ]
    python_score = sum(len(re.findall(p, lower)) for p in python_patterns)

    # 3. Check for Ruby on Rails using word boundaries
    ruby_patterns = [r"\brails\b", r"\bruby\b", r"\brspec\b", r"\bgemfile\b"]
    ruby_score = sum(len(re.findall(p, lower)) for p in ruby_patterns)

    # 4. Check for Next.js / React / TypeScript indicators (explicit tokens, no substring 'ui')
    next_patterns = [
        r"\bnext\.js\b",
        r"\bnextjs\b",
        r"\breact\b",
        r"\btypescript\b",
        r"\btailwind\b",
        r"\blucide\b",
        r"\bfrontend portal\b",
        r"\bclient component\b",
    ]
    next_score = sum(len(re.findall(p, lower)) for p in next_patterns)

    # 5. Check for Vue / Nuxt
    vue_patterns = [r"\bvue\b", r"\bnuxt\b", r"\bvuejs\b"]
    vue_score = sum(len(re.findall(p, lower)) for p in vue_patterns)

    # 6. Check for Angular
    angular_patterns = [r"\bangular\b"]
    angular_score = sum(len(re.findall(p, lower)) for p in angular_patterns)

    # 7. Check for Svelte
    svelte_patterns = [r"\bsvelte\b", r"\bsveltekit\b"]
    svelte_score = sum(len(re.findall(p, lower)) for p in svelte_patterns)

    scores = {
        "DOTNET_CSHARP": dotnet_score,
        "PYTHON_FASTAPI": python_score,
        "RUBY_RAILS": ruby_score,
        "TYPESCRIPT_NEXTJS": next_score,
        "VUE_NUXT": vue_score,
        "ANGULAR": angular_score,
        "SVELTE": svelte_score,
    }
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return default


def is_client_extension_intent(text: str) -> bool:
    lower = text.lower()
    client_patterns = [
        r"\bfrontend\b",
        r"\bfront-end\b",
        r"\bfront end\b",
        r"\bclient app\b",
        r"\buser interface\b",
        r"\bweb app\b",
        r"\bweb portal\b",
        r"\bdashboard\b",
        r"\bmobile app\b",
        r"\bgui\b",
    ]
    return any(re.search(p, lower) for p in client_patterns)


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


async def _run_orchestrator_job(
    project_id: uuid.UUID, requirement: str, run_id: uuid.UUID | None = None
):

    db = SessionLocal()

    try:
        resolver = LLMProviderResolver()

        git_service = GitService(db=db)

        tracker = TokenTrackerService(db=db)

        orchestrator = OrchestratorService(
            db=db, resolver=resolver, git_service=git_service, tracker=tracker
        )

        await orchestrator.start_workflow(
            project_id=project_id, user_requirement=requirement, workflow_run_id=run_id
        )

    except Exception as e:
        print(f"Background orchestrator failed: {e}")

        try:
            save_chat_message(db, project_id, "assistant", f"⚠️ Workflow Execution Error: {e}")

        except Exception:
            pass

    finally:
        db.close()


GIT_URL_REGEX = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?"
)


def _clean_git_url(raw_url: str) -> str:
    url = raw_url.rstrip(".,;!?:")
    if not url.endswith(".git"):
        url = url + ".git"
    return url


def handle_git_push_intent(
    user_text: str, project_id: str | None, db: Session
) -> StartWorkflowResponse | None:
    matches = GIT_URL_REGEX.findall(user_text)
    if not matches:
        return None

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
    channel_repo_path = Path(
        git_service.get_repository_path(project.id, RepositoryType.CHANNEL_APP)
    )
    mock_repo_path = Path(
        git_service.get_repository_path(project.id, RepositoryType.MOCK_VENDOR_API)
    )

    has_channel = (channel_repo_path / ".git").exists()
    has_mock = (mock_repo_path / ".git").exists()

    if not has_channel and not has_mock:
        return StartWorkflowResponse(
            project_id=project.id,
            status="ERROR",
            message="Repository not initialized.",
            is_greeting=True,
            assistant_reply=(
                f"❌ Local Git repositories for **{project.name}** have not been initialized yet.\n\n"
                "Please describe your requirements first so that code can be generated and committed before pushing to remote."
            ),
        )

    lower_text = user_text.lower()
    targets_to_push: list[tuple[RepositoryType, str]] = []

    # Check for labeled push commands: e.g. "channel: https://..." or "mock: https://..."
    channel_match = re.search(
        r"(?:channel|app|main)[\s:=]+(https?://[^\s,;]+)", user_text, re.IGNORECASE
    )
    mock_match = re.search(r"(?:mock|vendor)[\s:=]+(https?://[^\s,;]+)", user_text, re.IGNORECASE)

    if channel_match and has_channel:
        targets_to_push.append((RepositoryType.CHANNEL_APP, _clean_git_url(channel_match.group(1))))
    if mock_match and has_mock:
        targets_to_push.append(
            (RepositoryType.MOCK_VENDOR_API, _clean_git_url(mock_match.group(1)))
        )

    # If neither was parsed via key-value label:
    if not targets_to_push:
        clean_url = _clean_git_url(matches[0])
        is_mock_keyword = any(w in lower_text for w in ["mock", "vendor"]) and not any(
            w in lower_text for w in ["channel", "app"]
        )
        is_channel_keyword = any(w in lower_text for w in ["channel", "app", "main"]) and not any(
            w in lower_text for w in ["mock", "vendor"]
        )

        if has_channel and has_mock:
            # BOTH repositories exist on disk. Enforce ambiguity guard!
            if is_mock_keyword:
                targets_to_push.append((RepositoryType.MOCK_VENDOR_API, clean_url))
            elif is_channel_keyword:
                targets_to_push.append((RepositoryType.CHANNEL_APP, clean_url))
            else:
                reply = (
                    f"⚠️ **Dual-Repository Ambiguity Guard**\n\n"
                    f"Project **{project.name}** maintains **2 separate isolated Git repositories**:\n"
                    f"1. 📦 **`channel-app`** (Main application & core business logic)\n"
                    f"2. 🎭 **`mock-vendor-api`** (Mock vendor API simulator)\n\n"
                    f"To prevent branch collisions and guarantee dual-repository isolation, please specify which repository you are pushing:\n"
                    f"- `push channel {clean_url}`\n"
                    f"- `push mock {clean_url}`\n\n"
                    f"Or provide distinct repository URLs for both:\n"
                    f"`channel: <channel_repo_url> mock: <mock_vendor_url>`"
                )
                save_chat_message(db, project.id, "user", user_text)
                save_chat_message(db, project.id, "assistant", reply)
                return StartWorkflowResponse(
                    project_id=project.id,
                    status="AMBIGUOUS_PUSH_TARGET",
                    message="Multiple repositories exist. Specify target repository.",
                    is_greeting=True,
                    assistant_reply=reply,
                )
        elif has_channel and not has_mock:
            if is_mock_keyword:
                reply = (
                    f"ℹ️ Project **{project.name}** does not have a `mock-vendor-api` repository "
                    f"because third-party vendor mocks were not required / skipped for this project.\n\n"
                    f"Only **`channel-app`** is initialized."
                )
                save_chat_message(db, project.id, "user", user_text)
                save_chat_message(db, project.id, "assistant", reply)
                return StartWorkflowResponse(
                    project_id=project.id,
                    status="NO_MOCK_REPO",
                    message="Mock repository not applicable for this project.",
                    is_greeting=True,
                    assistant_reply=reply,
                )
            targets_to_push.append((RepositoryType.CHANNEL_APP, clean_url))
        elif has_mock and not has_channel:
            targets_to_push.append((RepositoryType.MOCK_VENDOR_API, clean_url))

    # Execute pushes
    results: list[dict[str, Any]] = []
    overall_success = True

    for repo_type, remote_url in targets_to_push:
        res = git_service.push_to_remote(
            project_id=project.id,
            repo_type=repo_type,
            remote_url=remote_url,
        )
        res["repo_type"] = repo_type.value if hasattr(repo_type, "value") else str(repo_type)
        results.append(res)
        if not res.get("success"):
            overall_success = False

    # Format assistant reply
    report_lines: list[str] = []
    if overall_success:
        report_lines.append("### ✅ Git Push Successful!\n")
        for r in results:
            repo_label = (
                "📦 **Channel Application**"
                if "channel" in r["repo_type"].lower()
                else "🎭 **Mock Vendor API**"
            )
            branch = r.get("branch", "develop")
            report_lines.append(f"{repo_label}:")
            report_lines.append(f"- **Remote URL:** `{r['remote_url']}`")
            report_lines.append(f"- **Branch:** `{branch}` -> `origin/{branch}`")
            report_lines.append(f"```\n{r.get('output', 'Pushed successfully.')}\n```\n")
        report_lines.append("All commits for the selected repositories have been pushed to remote.")
        reply_status = "PUSH_SUCCESS"
        reply_msg = "Git push completed successfully."
    else:
        report_lines.append("### ⚠️ Git Push Encountered Issues\n")
        for r in results:
            repo_label = (
                "📦 **Channel Application**"
                if "channel" in r["repo_type"].lower()
                else "🎭 **Mock Vendor API**"
            )
            branch = r.get("branch", "develop")
            if r.get("success"):
                report_lines.append(
                    f"{repo_label}: ✅ Pushed successfully to `{r['remote_url']}` (branch: `{branch}`)."
                )
            else:
                report_lines.append(
                    f"{repo_label}: ❌ Push failed to `{r['remote_url']}` (branch: `{branch}`)."
                )
                report_lines.append(f"```\n{r.get('error', 'Unknown push error')}\n```")
        report_lines.append("\nPlease verify repository permissions and network access.")
        reply_status = "PUSH_FAILED"
        reply_msg = "One or more git push operations failed."

    final_reply = "\n".join(report_lines)
    save_chat_message(db, project.id, "user", user_text)
    save_chat_message(db, project.id, "assistant", final_reply)

    return StartWorkflowResponse(
        project_id=project.id,
        status=reply_status,
        message=reply_msg,
        is_greeting=True,
        assistant_reply=final_reply,
    )


RUN_PROJECT_PATTERNS = [
    r"\brun\b.*\b(project|server|app|backend|frontend|service)\b",
    r"\bstart\b.*\b(project|server|app|backend|frontend|service)\b",
    r"\blaunch\b.*\b(project|server|app|backend|frontend|service)\b",
    r"\b(chala\s*do|chalao|chalayein|chalaen)\b",
    r"\b(run\s*karo|start\s*karo)\b",
]

STOP_PROJECT_PATTERNS = [
    r"\bstop\b.*\b(project|server|app|backend|frontend|service)\b",
    r"\bkill\b.*\b(project|server|app|backend|frontend|service)\b",
    r"\b(band\s*karo|rok\s*do|stop\s*karo)\b",
]


def handle_project_execution_intent(
    user_requirement: str,
    project_id: str | None,
    db: Session,
) -> StartWorkflowResponse | None:
    if not project_id:
        return None

    try:
        p_uuid = uuid.UUID(project_id)
    except (ValueError, TypeError):
        return None

    project = db.query(ProjectORM).filter_by(id=p_uuid).first()
    if not project:
        return None

    text_lower = user_requirement.lower().strip()
    is_stop = any(re.search(p, text_lower) for p in STOP_PROJECT_PATTERNS)
    is_run = any(re.search(p, text_lower) for p in RUN_PROJECT_PATTERNS)

    if not is_run and not is_stop:
        return None

    mgr = ProjectProcessManager.get_instance()

    if is_stop:
        res = mgr.stop_project(project.id)
        reply = (
            "### ⏹ Project Execution Stopped\n\n"
            f"{res.get('message', 'All project processes have been terminated.')}\n\n"
            "You can restart the project at any time by saying *'run project'* or clicking the **Run** button."
        )
        save_chat_message(db, project.id, "user", user_requirement)
        save_chat_message(db, project.id, "assistant", reply)
        return StartWorkflowResponse(
            project_id=project.id,
            status="STOPPED",
            message="Project stopped.",
            is_greeting=True,
            assistant_reply=reply,
        )

    subsystem = (
        "frontend"
        if any(k in text_lower for k in ("frontend", "ui", "client", "next"))
        else "channel-app"
    )

    try:
        launch_res = mgr.start_project(project.id, project.target_framework, subsystem=subsystem)
        info = launch_res.get("info", {})
        url = info.get("url", "")
        port = info.get("port", "")
        pid = info.get("pid", "")
        is_already = launch_res.get("status") == "ALREADY_RUNNING"

        header = (
            "### ℹ️ Project Service Already Running"
            if is_already
            else "### 🚀 Project Started Successfully!"
        )
        reply = (
            f"{header}\n\n"
            f"- **Subsystem:** `{subsystem}`\n"
            f"- **Port:** `{port}`\n"
            f"- **PID:** `{pid}`\n"
            f"- **Live Preview:** [{url}]({url})\n\n"
            f"Click the link above to view your live application in the browser."
        )
        save_chat_message(db, project.id, "user", user_requirement)
        save_chat_message(db, project.id, "assistant", reply)
        return StartWorkflowResponse(
            project_id=project.id,
            status="RUNNING",
            message="Project launched.",
            is_greeting=True,
            assistant_reply=reply,
        )
    except FileNotFoundError:
        reply = (
            "### ⚠️ Cannot Run Project Yet\n\n"
            f"The `{subsystem}` codebase has not been synthesized or built yet on disk.\n\n"
            "Please complete and approve the specification, then allow **Agent 3 (Main Coding Agent)** "
            "to implement the application code first."
        )
        save_chat_message(db, project.id, "user", user_requirement)
        save_chat_message(db, project.id, "assistant", reply)
        return StartWorkflowResponse(
            project_id=project.id,
            status="NOT_READY",
            message="Project files not found.",
            is_greeting=True,
            assistant_reply=reply,
        )
    except Exception as e:
        reply = f"### ❌ Error Launching Project\n\nFailed to start `{subsystem}`: {e}"
        save_chat_message(db, project.id, "user", user_requirement)
        save_chat_message(db, project.id, "assistant", reply)
        return StartWorkflowResponse(
            project_id=project.id,
            status="RUN_ERROR",
            message=str(e),
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

    # Check for Live Project Execution Intent (Run / Stop)
    exec_resp = handle_project_execution_intent(req.user_requirement, req.project_id, db)
    if exec_resp:
        return exec_resp

    # 1. Conversational Greeting check
    if is_conversational_or_greeting(req.user_requirement):
        reply = (
            "Welcome to AAISE! 👋\n\n"
            "Please upload your Software Requirements Specification (SRS) or describe the application "
            "you want to build below. Our multi-agent engineering team will design, implement, test, and verify it for you."
        )
        if req.project_id:
            try:
                p_uuid = uuid.UUID(req.project_id)
                proj = db.query(ProjectORM).filter_by(id=p_uuid).first()
                if proj:
                    save_chat_message(db, proj.id, "user", req.user_requirement)
                    save_chat_message(db, proj.id, "assistant", reply)
            except Exception:
                pass

        return StartWorkflowResponse(
            project_id=uuid.UUID(req.project_id) if req.project_id else None,
            status="CONVERSATION",
            message="Greeting received.",
            is_greeting=True,
            assistant_reply=reply,
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
        # Dynamically adopt detected framework if user explicitly requests a stack switch
        is_client_ext = is_client_extension_intent(req.user_requirement)
        if (
            not is_client_ext
            and detected_framework
            and detected_framework != project.target_framework
        ):
            project.target_framework = detected_framework
            db.commit()

    from src.api.routes.projects import ensure_project_agent_configs
    ensure_project_agent_configs(project.id, db)

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
    is_qa_or_sec_intent = any(
        w in cleaned
        for w in ["agent4", "agent 4", "qa", "test", "agent5", "agent 5", "security", "audit"]
    )

    is_continue_or_approve = (
        cleaned
        in {
            "continue",
            "approve",
            "approved",
            "proceed",
            "yes",
            "ok",
            "okay",
            "go ahead",
            "start coding",
            "write code",
            "code",
            "build",
            "build it",
            "chalo",
            "kro",
            "kardo",
        }
        or any(
            w in cleaned for w in ["approved", "proceed", "continue", "start coding", "write code"]
        )
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
            req.user_requirement
            if is_qa_or_sec_intent
            else "Specifications approved. Proceed with full application implementation and build verification.",
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


@router.post(
    "/start-multipart", response_model=StartWorkflowResponse, status_code=status.HTTP_200_OK
)
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

    if not files and is_conversational_or_greeting(full_requirement):
        reply = (
            "Welcome to AAISE! 👋\n\n"
            "Please upload your Software Requirements Specification (SRS) or describe the application "
            "you want to build below. Our multi-agent engineering team will design, implement, test, and verify it for you."
        )
        if project_id:
            try:
                p_uuid = uuid.UUID(project_id)
                proj = db.query(ProjectORM).filter_by(id=p_uuid).first()
                if proj:
                    save_chat_message(db, proj.id, "user", full_requirement)
                    save_chat_message(db, proj.id, "assistant", reply)
            except Exception:
                pass

        return StartWorkflowResponse(
            project_id=uuid.UUID(project_id) if project_id else None,
            status="CONVERSATION",
            message="Greeting received.",
            is_greeting=True,
            assistant_reply=reply,
        )

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

    from src.api.routes.projects import ensure_project_agent_configs
    ensure_project_agent_configs(project.id, db)

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

        result.append(
            {
                "id": str(f.id),
                "file_path": rel,
                "file_type": f.file_type,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
        )

    workspace_dir = Path("./workspace") / str(project_id)

    if workspace_dir.exists():
        docs_dir = workspace_dir / "docs"

        if docs_dir.exists():
            for p in docs_dir.glob("*.md"):
                rel = f"docs/{p.name}"

                if rel not in seen_paths:
                    seen_paths.add(rel)

                    result.append(
                        {
                            "id": str(uuid.uuid4()),
                            "file_path": rel,
                            "file_type": "TECHNICAL_DESIGN"
                            if "DESIGN" in p.name
                            else "TEST_SPECIFICATION",
                            "created_at": None,
                        }
                    )

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

                        result.append(
                            {
                                "id": str(uuid.uuid4()),
                                "file_path": rel_p,
                                "file_type": "CODE",
                                "created_at": None,
                            }
                        )

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

                background_tasks.add_task(
                    _run_orchestrator_job,
                    run.project_id,
                    "Specifications approved. Proceed with full application implementation and build verification.",
                    run.id,
                )

        else:
            run = db.query(WorkflowRunORM).filter_by(id=resolved.workflow_run_id).first()

            if run:
                run.status = "RUNNING"

                run.current_phase = "SPECIFICATION"

                db.commit()

                feedback = (
                    req.comments or ""
                ).strip() or "Please revise specifications according to requested changes."

                save_chat_message(
                    db,
                    run.project_id,
                    "user",
                    f"Requested Changes to Specifications:\n{feedback}",
                )

                save_chat_message(
                    db,
                    run.project_id,
                    "agent1",
                    "Analyzing requested changes. Revising Technical Design Document (TDD) and Test Specifications...",
                )

                background_tasks.add_task(
                    _run_orchestrator_job,
                    run.project_id,
                    f"Please revise the technical design and test specifications according to the following changes requested by the reviewer:\n\n{feedback}",
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
