# Master Step-by-Step Implementation Plan — AAISE

## 1. Overview & Protocol Enforcement
This document outlines the master implementation sequence for engineering the **Autonomous AI Software Engineer (AAISE)** platform. Every phase and step must strictly adhere to the **Antigravity Step-by-Step Development Approval Protocol**:
1. Phase planning is presented to the user.
2. Before every individual implementation step, an explicit approval request is submitted.
3. Antigravity waits for explicit user approval before modifying files, running commands, or creating database objects.
4. Upon step completion, real CLI execution and test evidence is reported and logged in `docs/PROGRESS.md`.
5. The next step is presented for approval.

---

## 2. Phase Breakdown & Implementation Sequence

### Phase 0: Project Governance, Rules & Architecture Documentation (Completed)
- **Step 0.1**: Workspace audit and Docker Ollama container verification (`dobai-ollama`). [COMPLETED]
- **Step 0.2**: Create root `AGENTS.md` and Antigravity rules (`.agents/rules/`). [COMPLETED]
- **Step 0.3**: Create base Antigravity development skills (`.agents/skills/`). [COMPLETED]
- **Step 0.4**: Author complete architectural and governance documentation (`docs/`). [COMPLETED]
- **Step 0.5**: Establish Senior Engineering Standards, Frontend Design Toolkit (5 design skills, Figma MCP, Playwright), and finalize Phase 0. [COMPLETED]

---

### Phase 1: Platform Foundation, FastAPI Scaffold & SQL Server Database Engine
- **Step 1.1**: Initialize Python project structure (`pyproject.toml`, virtual environment, directory layout adhering to Clean Architecture).
- **Step 1.2**: Implement core Domain Entities and Enums (`src/domain/`) with strict typing and Pydantic v2 schemas.
- **Step 1.3**: Configure SQLAlchemy 2.x engine and session factory for SQL Server with `pyodbc` (`AI_SoftwareEngineer`).
- **Step 1.4**: Define SQLAlchemy ORM declarative models matching `docs/DATABASE_DESIGN.md`.
- **Step 1.5**: Configure Alembic and generate initial database migration script.
- **Step 1.6**: Apply migration to local SQL Server instance (`AI_SoftwareEngineer` database) and verify schema via CLI query.
- **Step 1.7**: Implement FastAPI application scaffold, health check, CORS, and dependency injection setup.
- **Step 1.8**: Write unit and integration tests for database connectivity and CRUD operations (`pytest -v`).

---

### Phase 2: LLM Gateway & Provider Abstraction
- **Step 2.1**: Define `ILLMGateway` port interface, request/response models, and token metrics schema.
- **Step 2.2**: Implement local Dockerized Ollama adapter (`dobai-ollama:11434`, default `qwen2.5-coder:7b` with `qwen2.5:3b` fallback) with JSON repair parser.
- **Step 2.3**: Implement LiteLLM cloud adapter for Google Gemini (`gemini-3.8-flash`, `gemini-3.5-flash-lite`), Groq (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`), and OpenRouter.
- **Step 2.4**: Implement dynamic provider switching and per-agent model configuration resolver.
- **Step 2.5**: Implement Token Tracking and Invocation Logging service persisted to SQL Server (`TokenUsage`, `LLMInvocations`).
- **Step 2.6**: Execute live connectivity and validation tests across active providers.

---

### Phase 3: Git Operations & Docker Sandbox Infrastructure
- **Step 3.1**: Define `IGitManager` port interface and domain models.
- **Step 3.2**: Implement local Git manager with dual-repository support (`mock-vendor-api` and `channel-app`).
- **Step 3.3**: Implement Git worktree creation, cleanup, and branch management (`feature/*`, `fix/*`, `security/*`, `release/*`).
- **Step 3.4**: Implement Git release manifest pairing and commit hash recorder (`GitReleaseManifests`).
- **Step 3.5**: Define `ISandboxRunner` port and Docker execution abstraction.
- **Step 3.6**: Implement Docker Sandbox Manager (container spin-up, resource caps, network isolation, log streaming).
- **Step 3.7**: Write integration tests verifying isolated Git operations and container execution.

---

### Phase 4: Five Specialized AI Agents Implementation
- **Step 4.1**: Implement Agent 1 (Documentation Reviewer & Defect Manager) prompt templates, tools, and output parsers.
- **Step 4.2**: Implement Agent 2 (Mock Vendor API Developer) prompt templates, mock generation tools, and Docker dev-test tools.
- **Step 4.3**: Implement Agent 3 (Main Coding Agent) prompt templates, multi-language toolchain runners (Python, C#, TypeScript), and channel repo tools.
- **Step 4.4**: Implement Agent 4 (Independent QA Engineer) with black-box HTTP testing tools and strict source-code exclusion.
- **Step 4.5**: Implement Agent 5 (Security Reviewer) with read-only AST/SAST scanning tools and OWASP vulnerability categorizer.
- **Step 4.6**: Write comprehensive unit tests for each agent verifying tool boundaries, system prompts, and permissions.

---

### Phase 5: LangGraph Multi-Agent Orchestration & Workflow Engine
- **Step 5.1**: Define LangGraph State schema (`AAISEWorkflowState`) and port interfaces.
- **Step 5.2**: Implement SQL Server Durable Checkpointer for LangGraph state persistence (`WorkflowCheckpoints`).
- **Step 5.3**: Build orchestrator workflow nodes (Node 1 to Node 12) matching `docs/WORKFLOW.md`.
- **Step 5.4**: Implement Human Approval interrupt gates (Specification Gate & Release Gate) with resume capability.
- **Step 5.5**: Implement Defect Remediation routing loop with bounded iteration controls (max 3 retries).
- **Step 5.6**: Expose workflow execution, pause, resume, approval, and cancellation endpoints in FastAPI.
- **Step 5.7**: Write end-to-end integration tests simulating workflow cycles with mocked/live LLM responses.

---

### Phase 6: Next.js Frontend (Chat Workspace & Agent Dashboards)
- **Step 6.1**: Initialize Next.js App Router project with TypeScript, Tailwind CSS, and Lucide React adhering to `docs/FRONTEND_DESIGN_SYSTEM.md`.
- **Step 6.2**: Implement conversational Chat Workspace with real-time SSE streaming, agent identity badges, and collapsible reasoning.
- **Step 6.3**: Build Human Approval interactive modal cards (Specification review, Release promotion).
- **Step 6.4**: Build Generated Code & File Explorer with syntax-highlighted previews and diff viewer.
- **Step 6.5**: Build QA Test Execution Dashboard & Defect Tracker.
- **Step 6.6**: Build Security Vulnerability Report Viewer with severity classification.
- **Step 6.7**: Build Token Usage & Cost Analytics dashboard using Recharts.
- **Step 6.8**: Execute Playwright browser verification suite (responsive layout checks, accessibility tree audit, screenshot regression).

---

### Phase 7: End-to-End System Verification & Release
- **Step 7.1**: Ingest a sample Banking Integration Requirements document via Chat UI.
- **Step 7.2**: Verify autonomous specification generation and approve Specification Gate.
- **Step 7.3**: Verify parallel generation of Mock API and Channel App repositories.
- **Step 7.4**: Verify Docker sandbox launch, black-box QA execution, and security audit.
- **Step 7.5**: Verify simulated defect injection, Agent 1 remediation dispatch, and automated retest pass.
- **Step 7.6**: Verify paired Release Manifest creation and release promotion to `main`.
- **Step 7.7**: Compile Final Project Audit Report and documentation package.
