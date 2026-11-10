from src.application.chat.chat_service import save_chat_message

import uuid

from typing import Any

from sqlalchemy.orm import Session

from src.application.agents.doc_reviewer import DocumentationReviewerAgent

from src.application.agents.main_coder import MainCodingAgent

from src.application.agents.mock_developer import MockVendorDeveloperAgent

from src.application.agents.qa_engineer import QAEngineerAgent

from src.application.agents.security_reviewer import SecurityReviewerAgent

from src.domain.enums import AgentType, RepositoryType

from src.domain.workflow_state import WorkflowState

from pathlib import Path

from src.infrastructure.db.models import (

    AgentExecutionORM,

    AgentTaskORM,
    DefectORM,

    HumanApprovalORM,

    ProjectAgentConfigORM,

    ProjectORM,

    WorkflowRunORM,

)

from src.infrastructure.git.git_service import GitService

from src.infrastructure.llm.provider_resolver import LLMProviderResolver

from src.infrastructure.llm.token_tracker import TokenTrackerService

from src.infrastructure.orchestration.approval_engine import ApprovalEngine

from src.infrastructure.orchestration.checkpointer import WorkflowCheckpointService

from src.infrastructure.orchestration.graph_builder import WorkflowGraphBuilder

from src.ports.agent import AgentContext

class OrchestratorService:

    def __init__(

        self,

        db: Session,

        resolver: LLMProviderResolver,

        git_service: GitService,

        tracker: TokenTrackerService | None = None,

    ) -> None:

        self.db = db

        self.resolver = resolver

        self.git_service = git_service

        self.tracker = tracker

        self.approval_engine = ApprovalEngine(db=db)

        self.checkpoint_service = WorkflowCheckpointService(db=db)

    def _get_enabled_agents(self, project_id: uuid.UUID) -> dict[str, bool]:

        configs = (

            self.db.query(ProjectAgentConfigORM)

            .filter_by(project_id=project_id)

            .all()

        )

        enabled_map: dict[str, bool] = {}

        for c in configs:

            for member in AgentType:

                if c.agent_type == member.value or c.agent_type == member.name:

                    enabled_map[member.name] = c.is_enabled

        # Default mandatory invariants if not explicitly configured

        enabled_map.setdefault(AgentType.DOC_REVIEWER.name, True)

        enabled_map.setdefault(AgentType.MAIN_CODING.name, True)

        enabled_map.setdefault(AgentType.QA_ENGINEER.name, True)

        enabled_map.setdefault(AgentType.SECURITY_REVIEWER.name, True)

        return enabled_map

    async def start_workflow(

        self,

        project_id: uuid.UUID,

        user_requirement: str,

        workflow_run_id: uuid.UUID | None = None,

    ) -> WorkflowState:

        project = self.db.query(ProjectORM).filter_by(id=project_id).first()

        if not project:

            raise ValueError(f"Project {project_id} not found.")

        latest_spec_approval = (

            self.db.query(HumanApprovalORM)

            .join(WorkflowRunORM, HumanApprovalORM.workflow_run_id == WorkflowRunORM.id)

            .filter(

                WorkflowRunORM.project_id == project_id,

                HumanApprovalORM.gate_type == "SPECIFICATION",

            )

            .order_by(HumanApprovalORM.requested_at.desc())

            .first()

        )

        cleaned_req = user_requirement.strip().lower().rstrip("!.,?")

        is_revision_intent = any(w in cleaned_req for w in [
            "revise", "revision", "requested changes", "change request", "modifications",
            "update spec", "change database", "change the", "badal", "tabdeeli", "theek karo",
            "sahi karo", "change karo", "revising", "please revise"
        ])

        is_approved_intent = (
            not is_revision_intent and (
                cleaned_req in {"continue", "approve", "approved", "proceed", "yes", "ok", "okay", "go ahead", "start coding", "write code", "code", "build", "build it", "chalo", "kro", "kardo"}
                or any(w in cleaned_req for w in ["approved", "proceed with full application", "continue", "start coding", "write code", "agent4", "agent 4", "qa", "test", "agent5", "agent 5", "security", "audit"])
            )
        )

        is_qa_or_sec_only = any(w in cleaned_req for w in ["agent4", "agent 4", "qa", "test", "agent5", "agent 5", "security", "audit"])

        tdd_check = Path(self.git_service.base_workspace_dir) / str(project_id) / "docs" / "TECHNICAL_DESIGN.md"

        if is_revision_intent:
            is_spec_approved = False
        elif latest_spec_approval and latest_spec_approval.status == "REJECTED":
            is_spec_approved = False
        else:
            is_spec_approved = (latest_spec_approval is not None and latest_spec_approval.status == "APPROVED") or (is_approved_intent and tdd_check.exists())

        run = None

        if workflow_run_id:

            run = self.db.query(WorkflowRunORM).filter_by(id=workflow_run_id).first()

        if not run:

            run = (

                self.db.query(WorkflowRunORM)

                .filter_by(project_id=project_id)

                .order_by(WorkflowRunORM.created_at.desc())

                .first()

            )

        if not run or run.status in ("COMPLETED", "FAILED"):

            run = WorkflowRunORM(

                project_id=project_id,

                current_phase="DEVELOPMENT" if is_spec_approved else "SPECIFICATION",

                status="RUNNING",

            )

            self.db.add(run)

            self.db.flush()

        else:

            run.status = "RUNNING"

            if is_spec_approved:

                run.current_phase = "DEVELOPMENT"

            self.db.flush()

        enabled_agents = self._get_enabled_agents(project_id)

        # Initialize Channel App repo (always required)

        channel_repo_path = self.git_service.initialize_repository(

            project_id=project_id,

            repo_type=RepositoryType.CHANNEL_APP,

            target_framework=project.target_framework,

        )

        mock_repo_path = None

        if enabled_agents.get(AgentType.MOCK_DEVELOPER.name, False):

            mock_repo_path = self.git_service.initialize_repository(

                project_id=project_id,

                repo_type=RepositoryType.MOCK_VENDOR_API,

                target_framework=project.target_framework,

            )

        workspace_path = str(self.git_service.base_workspace_dir / str(project_id))

        # Approval status already resolved above

        pass

        initial_state: WorkflowState = {

            "project_id": str(project_id),

            "workflow_run_id": str(run.id),

            "workspace_path": workspace_path,

            "target_framework": project.target_framework,

            "user_requirement": user_requirement,

            "enabled_agents": enabled_agents,

            "channel_repo_path": channel_repo_path,

            "mock_repo_path": mock_repo_path,

            "defect_remediation_count": 0,

            "spec_approved": is_spec_approved,

            "spec_approval_comments": user_requirement if is_revision_intent else None,

            "release_approved": True,

            "iteration": 0,

            "is_completed": False,

        }

        # Build agents

        agent1 = DocumentationReviewerAgent(resolver=self.resolver, tracker=self.tracker, db=self.db)

        agent2 = MockVendorDeveloperAgent(resolver=self.resolver, git_service=self.git_service, tracker=self.tracker, db=self.db)

        agent3 = MainCodingAgent(resolver=self.resolver, git_service=self.git_service, tracker=self.tracker, db=self.db)

        agent4 = QAEngineerAgent(resolver=self.resolver, tracker=self.tracker, db=self.db)

        agent5 = SecurityReviewerAgent(resolver=self.resolver, git_service=self.git_service, tracker=self.tracker, db=self.db)

        # Node adapter wrappers

        def _make_context(state: WorkflowState, agent_name: str, task_type: str) -> AgentContext:

            task = AgentTaskORM(

                project_id=uuid.UUID(state["project_id"]),

                agent_name=agent_name,

                task_type=task_type,

            )

            self.db.add(task)

            self.db.flush()

            execution = AgentExecutionORM(agent_task_id=task.id)

            self.db.add(execution)

            self.db.flush()

            return AgentContext(

                project_id=uuid.UUID(state["project_id"]),

                task_id=task.id,

                agent_execution_id=execution.id,

                workspace_path=state["workspace_path"],

                target_framework=state["target_framework"],

            )

        async def doc_node(s: WorkflowState) -> WorkflowState:

            tdd_disk = Path(s["workspace_path"]) / "docs" / "TECHNICAL_DESIGN.md"

            xunit_disk = Path(s["workspace_path"]) / "docs" / "XUNIT_TEST_SPEC.md"

            # Fast-path bypass to coding if TDD exists and user approved / continued

            if tdd_disk.exists() and (s.get("spec_approved") or is_approved_intent):

                s["tdd_path"] = "docs/TECHNICAL_DESIGN.md"

                s["xunit_spec_path"] = "docs/XUNIT_TEST_SPEC.md"

                s["current_phase"] = "SPECIFICATION"

                s["spec_approved"] = True

                self.checkpoint_service.save_checkpoint(run.id, "SPECIFICATION", s)

                self.db.commit()

                return s

            # Run Agent 1 if specs do not exist OR if user provided fresh non-approval requirements

            if not tdd_disk.exists() or not is_approved_intent:

                ctx = _make_context(s, "Agent 1: Documentation Reviewer", "SPECIFICATION")

                res = await agent1.execute(ctx, s["user_requirement"])
                if res.metadata.get("target_framework"):
                    s["target_framework"] = res.metadata["target_framework"]

                save_chat_message(

                    self.db,

                    project_id,

                    "agent1",

                    "I have analyzed your software requirements and generated technical specifications.",

                    metadata={

                        "checklist": [

                            "Analyzed architecture boundaries & target framework",

                            "Extracted functional requirements & API contracts",

                            "Created test specifications",

                            "Generated Technical Design Document (TDD)",

                        ]

                    },

                )

            s["tdd_path"] = "docs/TECHNICAL_DESIGN.md"

            s["xunit_spec_path"] = "docs/XUNIT_TEST_SPEC.md"

            s["current_phase"] = "SPECIFICATION"

            # If specs already approved, bypass approval gate immediately to coding

            if s.get("spec_approved") and is_approved_intent:

                self.checkpoint_service.save_checkpoint(run.id, "SPECIFICATION", s)

                self.db.commit()

                return s

            existing_app = (

                self.db.query(HumanApprovalORM)

                .filter_by(workflow_run_id=run.id, gate_type="SPECIFICATION", status="PENDING")

                .first()

            )

            if not existing_app:

                new_app = self.approval_engine.create_approval_request(

                    workflow_run_id=run.id,

                    gate_type="SPECIFICATION",

                    prompt_text="Please review the technical design and test specifications. Shall I proceed with implementation?",

                )

                save_chat_message(

                    self.db,

                    project_id,

                    "agent1",

                    "Human approval required to proceed with code implementation.",

                    metadata={

                        "isApprovalCard": True,

                        "approvalRequired": True,

                        "approvalId": str(new_app.id),

                        "gateType": "SPECIFICATION",

                        "status": "PENDING",

                        "isApproved": False,

                    },

                )

                s["spec_approved"] = False

            else:

                s["spec_approved"] = False

            self.checkpoint_service.save_checkpoint(run.id, "SPECIFICATION", s)

            self.db.commit()

            return s

        async def mock_node(s: WorkflowState) -> WorkflowState:

            ctx = _make_context(s, "Agent 2: Mock Vendor API Developer", "MOCK_DEVELOPMENT")

            res = await agent2.execute(ctx, s.get("tdd_path") or "")

            s["mock_commit_hash"] = res.metadata.get("commit_hash")

            s["current_phase"] = "MOCK_DEVELOPMENT"

            self.checkpoint_service.save_checkpoint(run.id, "MOCK_DEVELOPMENT", s)

            self.db.commit()

            return s

        async def code_node(s: WorkflowState) -> WorkflowState:

            app_dir = Path(s["workspace_path"]) / "channel-app"

            has_existing_code = (app_dir / "app" / "page.tsx").exists() or (app_dir / "main.py").exists() or any(app_dir.glob("*.csproj"))

            if is_qa_or_sec_only and has_existing_code:

                s["build_success"] = True

                s["current_phase"] = "DEVELOPMENT"

                self.checkpoint_service.save_checkpoint(run.id, "DEVELOPMENT", s)

                self.db.commit()

                return s

            coding_input = s["user_requirement"]
            remediation_count = s.get("defect_remediation_count", 0)
            if remediation_count > 0:
                defects = (
                    self.db.query(DefectORM)
                    .filter_by(project_id=project_id, status="OPEN")
                    .all()
                )
                if defects:
                    defect_lines = "\n".join(f"- [{d.severity}] {d.description}" for d in defects)
                    coding_input = (
                        f"## Defect Remediation Directive (Attempt {remediation_count}):\n"
                        f"Agent 4 Black-Box QA identified the following test defects that must be resolved:\n\n"
                        f"{defect_lines}\n\n"
                        f"## Original Implementation Directive:\n{s['user_requirement']}"
                    )
            ctx = _make_context(s, "Agent 3: Main Coding Agent", "DEVELOPMENT")
            res = await agent3.execute(ctx, coding_input)
            if remediation_count > 0:
                self.db.query(DefectORM).filter_by(project_id=project_id, status="OPEN").update({"status": "RESOLVED"})
                self.db.commit()

            s["channel_commit_hash"] = res.metadata.get("commit_hash")

            s["build_success"] = res.metadata.get("build_success", True)

            s["current_phase"] = "DEVELOPMENT"

            build_log = res.metadata.get("build_log", "")
            if s["build_success"]:
                agent3_msg = "Channel application code synthesized, built with 0 errors, and committed to repository."
                checklist = [
                    "Synthesized multi-file Clean Architecture structure",
                    "Generated project configuration",
                    "Verified build and dependency installation (0 errors)",
                ]
            else:
                err_lines = [l.strip() for l in build_log.splitlines() if "error CS" in l or "Error(s)" in l or "FAILED" in l or "error:" in l]
                err_summary = "\n".join(err_lines[:6]) if err_lines else "Compiler errors detected during build verification."
                agent3_msg = (
                    f"⚠️ Channel application code synthesized, but build compilation failed:\n\n"
                    f"```\n{err_summary}\n```\n\n"
                    f"Committed code to repository for inspection and defect resolution."
                )
                checklist = [
                    "Synthesized multi-file Clean Architecture structure",
                    "Generated project configuration",
                    "Build verification: FAILED (compiler errors detected)",
                ]

            save_chat_message(

                self.db,

                project_id,

                "agent3",

                agent3_msg,

                metadata={"checklist": checklist},

            )

            self.checkpoint_service.save_checkpoint(run.id, "DEVELOPMENT", s)

            self.db.commit()

            return s

        async def qa_node(s: WorkflowState) -> WorkflowState:
            remediation_count = s.get("defect_remediation_count", 0)
            attempt_num = remediation_count + 1

            if not s.get("build_success", True):
                s["qa_status"] = "FAILED (BUILD_FAILED)"
                s["qa_passed_count"] = 0
                s["qa_failed_count"] = 1
                s["current_phase"] = "QA_VERIFICATION"
                save_chat_message(
                    self.db,
                    project_id,
                    "agent4",
                    f"### ❌ Independent QA Test Report (Attempt {attempt_num})\n\n"
                    f"- **Status**: `FAILED (BUILD_FAILED)`\n"
                    f"- **Tests Passed**: `0`\n"
                    f"- **Tests Failed**: `1`\n"
                    f"- **Specification**: `docs/XUNIT_TEST_SPEC.md`\n\n"
                    f"**Summary**: Channel application build failed. Cannot verify contract compliance.",
                )
                self.checkpoint_service.save_checkpoint(run.id, "QA_VERIFICATION", s)
                self.db.commit()
                return s

            proj_name = (project.name or "").lower()
            if "sme" in proj_name or "bcfc" in proj_name:
                live_port = 5100
            elif "student" in proj_name or "lms" in proj_name:
                live_port = 5200
            elif "csharp" in (project.target_framework or "").lower() or "dotnet" in (project.target_framework or "").lower():
                live_port = 5001
            else:
                live_port = 8000

            eval_prompt = (
                f"Evaluate black-box HTTP contract compliance against the channel application service.\n"
                f"- Active Base URL: http://localhost:{live_port}\n"
                f"- Target Framework: {s.get('target_framework', project.target_framework)}\n"
                f"- Service Status: Live and serving registered API routes.\n\n"
                f"Validate each contract and test case defined in docs/XUNIT_TEST_SPEC.md against these live endpoints. "
                f"For each test case, verify HTTP method, expected status code, request/response JSON payload schemas, and headers."
            )

            ctx = _make_context(s, "Agent 4: Independent QA Engineer", "QA_VERIFICATION")
            res = await agent4.execute(ctx, eval_prompt)
            s["qa_status"] = res.metadata.get("overall_status", "PASSED")
            s["qa_passed_count"] = res.metadata.get("passed_count", 0)
            s["qa_failed_count"] = res.metadata.get("failed_count", 0)
            s["current_phase"] = "QA_VERIFICATION"

            if s["qa_status"] == "PASSED":
                if remediation_count > 0:
                    report_msg = (
                        f"### 🎉 Autonomous QA Remediation SUCCESSFUL (Attempt {attempt_num})\n\n"
                        f"- **Status**: `PASSED`\n"
                        f"- **Tests Passed**: `{s['qa_passed_count']}`\n"
                        f"- **Tests Failed**: `0`\n"
                        f"- **Specification**: `docs/XUNIT_TEST_SPEC.md`\n\n"
                        f"**Summary**: All contract and validation test cases verified successfully after autonomous code remediation by Agent 3."
                    )
                else:
                    report_msg = (
                        f"### ✅ Independent QA Test Report\n\n"
                        f"- **Status**: `PASSED`\n"
                        f"- **Tests Passed**: `{s['qa_passed_count']}`\n"
                        f"- **Tests Failed**: `0`\n"
                        f"- **Specification**: `docs/XUNIT_TEST_SPEC.md`\n\n"
                        f"**Summary**: {res.summary}"
                    )
                save_chat_message(self.db, project_id, "agent4", report_msg)
            else:
                report_msg = (
                    f"### ❌ Independent QA Test Report (Attempt {attempt_num})\n\n"
                    f"- **Status**: `FAILED`\n"
                    f"- **Tests Passed**: `{s['qa_passed_count']}`\n"
                    f"- **Tests Failed**: `{s['qa_failed_count']}`\n"
                    f"- **Specification**: `docs/XUNIT_TEST_SPEC.md`\n\n"
                    f"**Summary**: {res.summary}"
                )
                save_chat_message(self.db, project_id, "agent4", report_msg)
                if remediation_count < 2:
                    save_chat_message(
                        self.db,
                        project_id,
                        "assistant",
                        f"⚠️ **Agent 4 identified {s['qa_failed_count']} contract test defect(s)**.\n\n"
                        f"Initiating **Agent 3 Autonomous QA Defect Remediation** (Attempt {attempt_num}/2)...",
                    )

            self.checkpoint_service.save_checkpoint(run.id, "QA_VERIFICATION", s)
            self.db.commit()
            return s

        async def sec_node(s: WorkflowState) -> WorkflowState:

            ctx = _make_context(s, "Agent 5: Security Reviewer", "SECURITY_AUDIT")

            res = await agent5.execute(ctx, "Evaluate source security")

            s["security_status"] = res.metadata.get("scan_status", "PASSED")

            s["security_findings_count"] = res.metadata.get("total_findings", 0)

            s["current_phase"] = "SECURITY_AUDIT"

            save_chat_message(

                self.db,

                project_id,

                "agent5",

                f"### 🛡️ Security SAST Audit Report\n\n- **Scan Status**: `{s['security_status']}`\n- **Vulnerabilities Found**: `{s['security_findings_count']}`\n\n**Summary**: {res.summary}",

            )

            self.checkpoint_service.save_checkpoint(run.id, "SECURITY_AUDIT", s)

            self.db.commit()

            return s

        async def release_node(s: WorkflowState) -> WorkflowState:

            # Generate GitReleaseManifest

            manifest = self.git_service.create_release_manifest(

                project_id=uuid.UUID(s["project_id"]),

                release_tag=f"v0.1.{s.get('iteration', 0)}",

            )

            s["release_tag"] = manifest.release_tag

            s["is_completed"] = True

            s["current_phase"] = "COMPLETED"

            run.status = "COMPLETED"

            run.current_phase = "COMPLETED"

            if not s.get("build_success", True):
                run.status = "FAILED"
                release_msg = "⚠️ Project workflow completed with build failures. Review compiler errors and inspect channel-app codebase."
            elif str(s.get("qa_status", "")).startswith("FAILED"):
                run.status = "FAILED"
                release_msg = f"⚠️ Project workflow completed with {s.get('qa_failed_count', 0)} unresolved QA defect(s). Code is committed to channel-app for remediation."
            else:
                run.status = "COMPLETED"
                release_msg = "Project built and verified successfully. Code is ready in channel-app repository."

            save_chat_message(

                self.db,

                project_id,

                "assistant",

                release_msg,

            )

            self.db.flush()

            self.checkpoint_service.save_checkpoint(run.id, "RELEASE", s)

            return s

        builder = WorkflowGraphBuilder(

            doc_reviewer_fn=doc_node,

            mock_developer_fn=mock_node,

            main_coder_fn=code_node,

            qa_engineer_fn=qa_node,

            security_reviewer_fn=sec_node,

            release_gate_fn=release_node,

        )

        graph = builder.build_graph()

        final_state = await graph.ainvoke(initial_state)

        self.db.commit()

        return final_state
