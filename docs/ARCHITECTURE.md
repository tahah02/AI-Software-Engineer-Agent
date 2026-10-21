# System Architecture Specification — AAISE

## 1. Architectural Style & Boundaries

The Autonomous AI Software Engineer (AAISE) platform is engineered as a **Modular Monolith** applying **Clean Architecture** and **Hexagonal Architecture (Ports and Adapters)** principles. This pattern guarantees strict decoupling of business rules from database technologies, LLM providers, and execution runtimes.

```
+---------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER                                 |
|  Next.js App Router (React 19, TypeScript, Tailwind CSS, Lucide, Recharts)             |
|  - Governed by docs/FRONTEND_DESIGN_SYSTEM.md ("Developer's Workshop", Anti-Slop)      |
|  - Dynamic Agent Enable/Disable Toggle Controls per Project                          |
|  - Verified via Playwright MCP & Playwright CLI (Responsive, Visual Regression)       |
|  - Integrated with Figma MCP (figma-developer-mcp stdio bridge for design tokens)    |
+---------------------------------------------------------------------------------------+
                                           | HTTP / REST & Server-Sent Events (SSE)
                                           v
+---------------------------------------------------------------------------------------+
|                                  API / ADAPTERS LAYER                                 |
|             FastAPI Endpoints, SSE Event Streaming, Pydantic v2 Request Validation    |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                APPLICATION SERVICES LAYER                             |
|      ProjectService, ConversationService, WorkflowEngine (Dynamic LangGraph)          |
|      WorkflowRouter (Evaluates Enabled Agents), GitReleaseManager, ApprovalService    |
+---------------------------------------------------------------------------------------+
                  |                                                  |
                  v                                                  v
+-----------------------------------+              +------------------------------------+
|            DOMAIN CORE            |              |           PORTS (INTERFACES)       |
| Entities, State Models, Value     |              | IProjectRepository, ICheckpointer  |
| Objects, Domain Events, Invariants|              | ILLMGateway, IGitManager,          |
| (Zero external dependencies)      |              | ISandboxRunner, IToolExecutor      |
+-----------------------------------+              +------------------------------------+
                                                                     ^
                                                                     | Implements
+--------------------------------------------------------------------+------------------+
|                                INFRASTRUCTURE ADAPTERS LAYER                          |
|  - Persistence Adapter: SQLite for POC (SQLAlchemy 2.x, Alembic, foreign_keys=ON)     |
|    *Enterprise targets: SQL Server / PostgreSQL                                       |
|  - LLM Gateway Adapter (LiteLLM, Ollama Docker adapter, Gemini/Groq/OpenRouter)       |
|  - Git Adapter (Local Git CLI, Git worktrees, dual repository management)             |
|  - Sandbox Adapter (Docker SDK, container isolation, resource caps)                   |
|  - LangGraph Durable Checkpointer (Persistent checkpointer implementation)            |
+---------------------------------------------------------------------------------------+
```

---

## 2. Component Breakdown

### 2.1 Backend Core Components
1. **API Layer (`src/api/`)**:
   - `projects.py`: Project lifecycle endpoints (create, list, get, delete, update agent configs).
   - `conversations.py`: Chat endpoints, message posting, SSE stream subscription.
   - `workflows.py`: Triggering dynamic workflows, pause, resume, cancel, and human approvals.
   - `artifacts.py`: Code browsing, file tree exploration, test logs, security scan results.
   - `settings.py`: Provider keys, agent model mappings, runtime options.
2. **Application Layer (`src/application/`)**:
   - `workflow/`: LangGraph dynamic state graph definitions, conditional router edges, checkpoint manager.
   - `services/`: Project orchestrator, artifact service, Git release coordinator, approval service.
3. **Domain Layer (`src/domain/`)**:
   - Pure Python dataclasses / Pydantic models: `Project`, `ProjectAgentConfig`, `AgentTask`, `WorkflowState`, `Artifact`, `TestCase`, `Defect`, `SecurityFinding`.
   - Domain exceptions: `ProjectNotFoundError`, `ApprovalPendingError`, `WorkflowExecutionError`, `InvalidWorkflowConfigurationError`.
4. **Ports Layer (`src/ports/`)**:
   - Protocol definitions establishing contracts for persistence, Git, LLM calls, and sandboxing.
5. **Infrastructure Layer (`src/infrastructure/`)**:
   - `db/`: SQLAlchemy 2.x models, SQLite session factory (`./data/aaise.db`), Alembic migrations.
   - `llm/`: Unified LLM Gateway wrapping LiteLLM, local Ollama handler (`qwen2.5-coder:7b` / `qwen2.5:3b`), and cloud providers.
   - `git/`: Git CLI manager, branch and worktree creator, release manifest generator.
   - `sandbox/`: Docker SDK manager, dynamic container spin-up based on enabled agents.

---

## 3. Dynamic Multi-Agent Orchestration & Data Flow

```
                      User (Chat UI / Project Settings)
                                    |
            1. Configure Enabled Agents (e.g., Disable Agent 2 or 4)
                                    v
                         FastAPI Project Service
                                    |
            2. Persist to Database (ProjectAgentConfigs)
                                    v
                      LangGraph Central Orchestrator
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
    [Agent 1: Doc Reviewer]                       [Requirements Analysis]
      (Always Enabled)                                      |
            |                                               v
            +----------------------------------> [Human Approval Gate 1: Specs]
                                                            |
                     +--------------------------------------+--------------------------------------+
                     | (Conditional Edge)                                                          | (Conditional Edge)
                     | IF Agent 2 ENABLED                                                          | Always (Agent 3)
                     v                                                                             v
           [Agent 2: Mock API Dev]                                                       [Agent 3: Main Coding Agent]
          (Generates mock-vendor-api)                                                    (Generates channel-app)
                     |                                                                             |
                     +--------------------------------------+--------------------------------------+
                                                            | (Barrier / Join)
                                                            v
                                            [Docker Sandbox Provisioning]
                                     (Starts Mock container ONLY if Agent 2 enabled)
                                                            |
                     +--------------------------------------+--------------------------------------+
                     | (Conditional Edge)                                                          | (Conditional Edge)
                     | IF Agent 4 ENABLED                                                          | IF Agent 5 ENABLED
                     v                                                                             v
           [Agent 4: Black-Box QA]                                                       [Agent 5: Security Reviewer]
           (Zero source code access)                                                     (Read-only SAST & Secrets)
           *If Disabled: Status = SKIPPED                                                *If Disabled: Status = NOT_SCANNED
                     |                                                                             |
                     +--------------------------------------+--------------------------------------+
                                                            | (Barrier / Join)
                                                            v
                                                [Quality Gate Evaluation]
                                                            |
                                                            v
                                        [Human Approval Gate 2: Release Promotion]
```

---

## 4. LLM Gateway & Provider Abstraction

The LLM Gateway (`ILLMGateway`) provides a unified, provider-agnostic interface across local and cloud models:

```
                          +------------------------+
                          |      ILLMGateway       |
                          +------------------------+
                                      |
                 +--------------------+--------------------+
                 |                                         |
                 v                                         v
   +----------------------------+            +----------------------------+
   |   Local Ollama Adapter     |            |    LiteLLM Cloud Adapter   |
   | (Docker `dobai-ollama`)    |            | (Gemini, Groq, OpenRouter) |
   | Port 11434                 |            | Dynamic API Key Injection  |
   | qwen2.5-coder:7b & 3b      |            | gemini-3.8-flash, etc.     |
   +----------------------------+            +----------------------------+
                 |                                         |
                 +--------------------+--------------------+
                                      |
                                      v
                          +------------------------+
                          | Token Metric Tracker & |
                          | Invocation Audit Logger|
                          +------------------------+
```

Every agent's provider and model identifier are configured dynamically per project in `ProjectAgentConfigs` in the database, avoiding any hardcoded provider bindings in business logic.
