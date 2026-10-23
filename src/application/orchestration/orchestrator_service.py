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
from src.infrastructure.db.models import (
    AgentExecutionORM,
    AgentTaskORM,
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
        return enabled_map

    async def start_workflow(
        self,
        project_id: uuid.UUID,
        user_requirement: str,
    ) -> WorkflowState:
        project = self.db.query(ProjectORM).filter_by(id=project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        # Create WorkflowRunORM
        run = WorkflowRunORM(
            project_id=project_id,
            current_phase="SPECIFICATION",
            status="RUNNING",
        )
        self.db.add(run)
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
            "spec_approved": True,  # initial auto-pass for end-to-end execution unless gated
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
            ctx = _make_context(s, "Agent 1: Documentation Reviewer", "SPECIFICATION")
            res = await agent1.execute(ctx, s["user_requirement"])
            s["tdd_path"] = "docs/TECHNICAL_DESIGN.md"
            s["xunit_spec_path"] = "docs/XUNIT_TEST_SPEC.md"
            s["current_phase"] = "SPECIFICATION"
            self.checkpoint_service.save_checkpoint(run.id, "SPECIFICATION", s)
            return s

        async def mock_node(s: WorkflowState) -> WorkflowState:
            ctx = _make_context(s, "Agent 2: Mock Vendor API Developer", "MOCK_DEVELOPMENT")
            res = await agent2.execute(ctx, s.get("tdd_path") or "")
            s["mock_commit_hash"] = res.metadata.get("commit_hash")
            s["current_phase"] = "MOCK_DEVELOPMENT"
            self.checkpoint_service.save_checkpoint(run.id, "MOCK_DEVELOPMENT", s)
            return s

        async def code_node(s: WorkflowState) -> WorkflowState:
            ctx = _make_context(s, "Agent 3: Main Coding Agent", "DEVELOPMENT")
            res = await agent3.execute(ctx, s["user_requirement"])
            s["channel_commit_hash"] = res.metadata.get("commit_hash")
            s["current_phase"] = "DEVELOPMENT"
            self.checkpoint_service.save_checkpoint(run.id, "DEVELOPMENT", s)
            return s

        async def qa_node(s: WorkflowState) -> WorkflowState:
            ctx = _make_context(s, "Agent 4: Independent QA Engineer", "QA_VERIFICATION")
            res = await agent4.execute(ctx, "Evaluate contract compliance")
            s["qa_status"] = res.metadata.get("overall_status", "PASSED")
            s["qa_passed_count"] = res.metadata.get("passed_count", 0)
            s["qa_failed_count"] = res.metadata.get("failed_count", 0)
            s["current_phase"] = "QA_VERIFICATION"
            self.checkpoint_service.save_checkpoint(run.id, "QA_VERIFICATION", s)
            return s

        async def sec_node(s: WorkflowState) -> WorkflowState:
            ctx = _make_context(s, "Agent 5: Security Reviewer", "SECURITY_AUDIT")
            res = await agent5.execute(ctx, "Evaluate source security")
            s["security_status"] = res.metadata.get("scan_status", "PASSED")
            s["security_findings_count"] = res.metadata.get("total_findings", 0)
            s["current_phase"] = "SECURITY_AUDIT"
            self.checkpoint_service.save_checkpoint(run.id, "SECURITY_AUDIT", s)
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
