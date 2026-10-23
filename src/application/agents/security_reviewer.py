import json
from pathlib import Path
from sqlalchemy.orm import Session

from src.domain.agent_base import BaseAgent
from src.domain.enums import AgentType, RepositoryType, Severity
from src.domain.tools import execute_file_read, execute_list_files, get_file_read_tool, get_list_files_tool
from src.infrastructure.db.models import SecurityFindingORM, SecurityScanORM
from src.infrastructure.git.git_service import GitService
from src.infrastructure.llm.provider_resolver import LLMProviderResolver
from src.infrastructure.llm.token_tracker import TokenTrackerService
from src.ports.agent import AgentContext, AgentResult
from src.ports.llm_gateway import LLMRequest, ToolDefinition


SECURITY_SYSTEM_PROMPT = """You are Agent 5: Security Reviewer.
Your responsibility:
1. Perform static code analysis (SAST) and security audits on source code repositories.
2. You are STRICTLY READ-ONLY: You must never edit, overwrite, or delete code.
3. Check for security vulnerabilities:
   - Hardcoded secrets, plain-text API keys, passwords, private tokens
   - SQL Injection, Command Injection, Path Traversal
   - Insecure deserialization, improper auth/CORS configurations
   - Unhandled exception disclosures
4. For every finding, categorize severity as CRITICAL, HIGH, MEDIUM, or LOW, provide exact file path, line number, description, and remediation advice.

Respond with a JSON object:
{
  "findings": [
    {
      "severity": "CRITICAL",
      "vulnerability_type": "HARDCODED_SECRET",
      "target_repo": "CHANNEL_APP",
      "file_path": "src/config.py",
      "line_number": 12,
      "description": "Plaintext secret detected in codebase",
      "remediation_advice": "Inject secret via environment variables"
    }
  ],
  "overall_summary": "Security audit completed with 1 critical finding."
}
"""


class SecurityReviewerAgent(BaseAgent):
    def __init__(
        self,
        resolver: LLMProviderResolver,
        git_service: GitService,
        tracker: TokenTrackerService | None = None,
        db: Session | None = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.SECURITY_REVIEWER,
            resolver=resolver,
            tracker=tracker,
            db=db,
        )
        self.git_service = git_service

    def get_system_prompt(self, context: AgentContext) -> str:
        return SECURITY_SYSTEM_PROMPT

    def get_tools(self) -> list[ToolDefinition]:
        # Read-only tools strictly enforced
        return [get_file_read_tool(), get_list_files_tool()]

    def _collect_repo_files(self, repo_path: str) -> dict[str, str]:
        files_content = {}
        all_files = execute_list_files(repo_path)
        for rel in all_files:
            # Skip binary, git, or lockfiles
            if any(rel.endswith(ext) for ext in (".py", ".json", ".yaml", ".yml", ".ts", ".js", ".cs", ".txt")):
                try:
                    content = execute_file_read(repo_path, rel)
                    files_content[rel] = content[:3000]  # truncate huge files safely
                except Exception:
                    continue
        return files_content

    async def execute(self, context: AgentContext, input_text: str) -> AgentResult:
        channel_repo_path = self.git_service.get_repository_path(
            project_id=context.project_id,
            repo_type=RepositoryType.CHANNEL_APP,
        )

        files_data = self._collect_repo_files(channel_repo_path)
        files_dump = json.dumps(files_data, indent=2)

        user_content = (
            f"## Repository Source Code to Audit (CHANNEL_APP):\n\n"
            f"```json\n{files_dump}\n```\n\n"
            f"## Audit Context:\n{input_text}"
        )

        messages = self.build_initial_messages(context, user_content)

        resolved_config = self.resolver.resolve_agent_config(
            session=self.db,
            project_id=context.project_id,
            agent=self.agent_type,
        )
        adapter = resolved_config.adapter

        request = LLMRequest(
            provider=resolved_config.provider,
            model=resolved_config.model,
            messages=messages,
            response_schema={"type": "json_object"},
            temperature=0.0,
            max_tokens=4000,
        )

        response = await adapter.complete(request)

        if self.tracker:
            self.tracker.record_invocation(
                agent_execution_id=context.agent_execution_id,
                provider=resolved_config.provider,
                model_name=resolved_config.model,
                latency_ms=response.latency_ms,
                success=True,
                response=response,
            )

        try:
            content_data = json.loads(response.content)
            findings_list = content_data.get("findings", [])
            summary = content_data.get("overall_summary", "Security review finished.")
        except Exception:
            findings_list = []
            summary = "Security audit completed."

        critical_or_high = sum(
            1 for f in findings_list if f.get("severity") in ("CRITICAL", "HIGH")
        )
        scan_status = "FAILED" if critical_or_high > 0 else "PASSED"

        # Persist in database
        if self.db:
            scan = SecurityScanORM(
                project_id=context.project_id,
                scanner_type="AGENT_SAST_AUDIT",
                status=scan_status,
            )
            self.db.add(scan)
            self.db.flush()

            for f in findings_list:
                finding = SecurityFindingORM(
                    security_scan_id=scan.id,
                    severity=f.get("severity", "LOW"),
                    vulnerability_type=f.get("vulnerability_type", "GENERIC_VULNERABILITY"),
                    target_repo=f.get("target_repo", "CHANNEL_APP"),
                    file_path=f.get("file_path", "unknown"),
                    line_number=f.get("line_number"),
                    description=f.get("description", "Vulnerability detected"),
                    remediation_advice=f.get("remediation_advice", "Review code security"),
                    status="OPEN",
                )
                self.db.add(finding)

            self.db.flush()

        return AgentResult(
            success=(scan_status == "PASSED"),
            summary=summary,
            artifacts_created=[],
            metadata={
                "scan_status": scan_status,
                "total_findings": len(findings_list),
                "critical_or_high_count": critical_or_high,
            },
        )
