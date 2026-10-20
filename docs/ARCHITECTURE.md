# System Architecture Specification — AAISE

## 1. Architectural Style & Boundaries

The Autonomous AI Software Engineer (AAISE) platform is engineered as a **Modular Monolith** applying **Clean Architecture** and **Hexagonal Architecture (Ports and Adapters)** principles. This pattern guarantees strict decoupling of business rules from database technologies, LLM providers, and execution runtimes.

```
+---------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER                                 |
|  Next.js App Router (React 19, TypeScript, Tailwind CSS, Lucide, Recharts)             |
|  - Governed by docs/FRONTEND_DESIGN_SYSTEM.md ("Developer's Workshop", Anti-Slop)      |
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
|      ProjectService, ConversationService, WorkflowEngine (LangGraph Orchestrator)      |
|      DefectCoordinator, GitReleaseManager, ApprovalGateService                        |
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
|  - SQL Server Adapter (SQLAlchemy 2.x, pyodbc, Alembic migrations)                    |
|  - LLM Gateway Adapter (LiteLLM, Ollama Docker adapter, Gemini/Groq/OpenRouter)       |
|  - Git Adapter (Local Git CLI, Git worktrees, dual repository management)             |
|  - Sandbox Adapter (Docker SDK, container isolation, resource caps)                   |
|  - LangGraph Durable Checkpointer (SQL Server custom checkpointer implementation)     |
+---------------------------------------------------------------------------------------+
```

---

## 2. Component Breakdown

### 2.1 Backend Core Components
1. **API Layer (`src/api/`)**:
   - `projects.py`: Project lifecycle endpoints (create, list, get, delete).
   - `conversations.py`: Chat endpoints, message posting, SSE stream subscription.
   - `workflows.py`: Triggering workflows, pause, resume, cancel, and human approvals.
   - `artifacts.py`: Code browsing, file tree exploration, test logs, security scan results.
   - `settings.py`: Provider keys, agent model mappings, runtime options.
2. **Application Layer (`src/application/`)**:
   - `workflow/`: LangGraph state graph definitions, nodes, conditional edges, checkpoint manager.
   - `services/`: Project orchestrator, artifact service, Git release coordinator, approval service.
3. **Domain Layer (`src/domain/`)**:
   - Pure Python dataclasses / Pydantic models: `Project`, `AgentTask`, `WorkflowState`, `Artifact`, `TestCase`, `Defect`, `SecurityFinding`.
   - Domain exceptions: `ProjectNotFoundError`, `ApprovalPendingError`, `WorkflowExecutionError`.
4. **Ports Layer (`src/ports/`)**:
   - Protocol definitions establishing contracts for persistence, Git, LLM calls, and sandboxing.
5. **Infrastructure Layer (`src/infrastructure/`)**:
   - `db/`: SQLAlchemy 2.x models, session factory with `pyodbc`, Alembic migrations for SQL Server (`AI_SoftwareEngineer`).
   - `llm/`: Unified LLM Gateway wrapping LiteLLM, local Ollama handler (`qwen2.5-coder:7b` / `qwen2.5:3b`), and cloud providers.
   - `git/`: Git CLI manager, branch and worktree creator, release manifest generator.
   - `sandbox/`: Docker SDK manager, container spin-up, command execution, log capture.

### 2.2 Frontend Core Components & Design System
- **Framework**: Next.js App Router, React 19, TypeScript, Tailwind CSS, Lucide React, Recharts.
- **Design System Authority**: [docs/FRONTEND_DESIGN_SYSTEM.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/FRONTEND_DESIGN_SYSTEM.md).
- **Anti-Slop Directives**: No generic purple/indigo gradients, no oversized cards (`shadow-2xl` banned), no sluggish animations (>250ms prohibited).
- **Toolkit & Verification**: [docs/FRONTEND_TOOLKIT.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/FRONTEND_TOOLKIT.md) governs the activation of Emil Kowalski motion skills, Impeccable critique, Taste Skill layout, Figma MCP, and Playwright verification.

---

## 3. Five Specialized Agents Topology & Models

```
                  +----------------------------------------------+
                  |           LangGraph Central Orchestrator      |
                  +----------------------------------------------+
                         |                    |             |
           +-------------+                    |             +-------------+
           v                                  v                           v
+-----------------------+          +--------------------+       +-------------------+
|  Agent 1: Doc Review  |          | Agent 2: Mock API  |       | Agent 3: Main App |
| Google Gemini         |          | Groq               |       | Local Ollama      |
| gemini-3.8-flash      |          | openai/gpt-oss-120b|       | qwen2.5-coder:7b  |
+-----------------------+          +--------------------+       +-------------------+
           ^                                  |                           |
           | Handoff                          +-------------+-------------+
           | Findings                                       | Integrated Apps
           |                                                v
+-----------------------+                         +-------------------+
|   Agent 5: Security   |<------------------------| Agent 4: Black-Box|
| Google Gemini         |                         | Groq              |
| gemini-3.5-flash-lite |                         | qwen/qwen3.8-27b  |
+-----------------------+                         +-------------------+
```

- **Agent 1 (Doc Reviewer & Defect Manager)**: Ingests requirements, classifies Channel vs. Vendor APIs, generates TDD & Test Specs, produces defect remediation tasks.
- **Agent 2 (Mock Vendor API Dev)**: Implements deterministic mock endpoints in the isolated `mock-vendor-api` Git repo.
- **Agent 3 (Main Coding Agent)**: Implements business logic in the isolated `channel-app` Git repo across multiple languages (Python, C#, TypeScript).
- **Agent 4 (Independent QA)**: Black-box HTTP testing strictly against running Docker containers. Zero source-code access.
- **Agent 5 (Security Reviewer)**: Read-only SAST & AST security scanner across both repositories.

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

---

## 5. Sandboxed Runtime Execution Architecture

Generated code is executed strictly inside Docker containers created per project and task:
- **Isolated Docker Network**: `aaise_net_<project_id>` with internal DNS resolution.
- **Port Isolation**: Container ports dynamically mapped to host ports for Agent 4's black-box testing.
- **Resource Constraints**: Memory max 2048 MB, CPU max 2.0 cores per container.
- **Workspace Access**:
  - `Agent 2 Container`: Mounts `<project_dir>/mock-vendor-api/`.
  - `Agent 3 Container`: Mounts `<project_dir>/channel-app/`.
  - `Agent 4 (QA)`: **No directory mounts.** Connected solely to the Docker virtual network to send HTTP requests.
