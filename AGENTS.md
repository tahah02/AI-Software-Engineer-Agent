# AGENTS.md — Autonomous AI Software Engineer (AAISE)

## 1. Project Mission & Overview
**Autonomous AI Software Engineer (AAISE)** is an enterprise-grade, chat-based, multi-agent AI Software Engineering platform. It autonomously transforms business requirements into production-ready software systems with rigorous human-in-the-loop controls. AAISE coordinates five specialized AI agents via a central deterministic orchestrator (LangGraph) to perform specification analysis, mock API generation, channel code implementation, black-box QA testing, and source-code security scanning across separate Git repositories.

---

## 2. Mandatory Technology Stack

| Layer | Component / Technology | Enforced Specifications |
| :--- | :--- | :--- |
| **Platform Backend** | Python 3.11+, FastAPI, Pydantic v2 | Modular Monolith, Hexagonal Architecture, Strict Typing |
| **Orchestration** | LangGraph, LiteLLM | Dynamic graph state, configurable agent topology, provider-agnostic LLM gateway |
| **Platform Frontend** | Next.js (App Router), React 19, TypeScript, Tailwind CSS | Lucide React, Recharts, EventSource streaming chat UI |
| **Database (POC)** | SQLite (`./data/aaise.db`) | SQLAlchemy 2.x, Alembic migrations, foreign keys enforced via PRAGMA (Enterprise targets: SQL Server / PostgreSQL) |
| **Local LLM** | Ollama in Docker (`dobai-ollama`, port `11434`) | Dual model setup: `qwen2.5:3b` (supporting) & `qwen2.5-coder:7b` (Agent 3 coding). |
| **Cloud LLMs** | Google Gemini, Groq, OpenRouter | Validated initial models: `gemini-3.8-flash`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `gemini-3.5-flash-lite` |
| **Execution** | Docker Containers (isolated sandboxes) | No host-level untrusted code execution |
| **VCS & Isolation** | Local Git, Git Worktrees | Dual repositories per project: `mock-vendor-api` (when Agent 2 enabled) and `channel-app` |

---

## 3. Five Specialized AI Agents & Configurable Workflow Topology

The central orchestrator is an execution-control engine (LangGraph), **not** an LLM agent. The platform contains exactly five specialized engineering agents whose participation is dynamically configurable per project:

```
                  +----------------------------------------------+
                  |           LangGraph Central Orchestrator      |
                  +----------------------------------------------+
                         |                    |             |
           +-------------+                    |             +-------------+
           v                                  v                           v
+-----------------------+          +--------------------+       +-------------------+
|  Agent 1: Doc Review  |          | Agent 2: Mock API  |       | Agent 3: Main App |
| (MANDATORY SPECS)     |          | (OPTIONAL VENDOR)  |       | (MANDATORY APP)   |
+-----------------------+          +--------------------+       +-------------------+
           ^                                  |                           |
           | Handoff                          +-------------+-------------+
           | Findings                                       | Integrated Apps
           |                                                v
+-----------------------+                         +-------------------+
|   Agent 5: Security   |<------------------------| Agent 4: Black-Box|
| (OPTIONAL AUDIT)      |                         | QA (OPTIONAL TEST)|
+-----------------------+                         +-------------------+
```

### Configurable Agent Topology & Roles

1. **Agent 1: Documentation Reviewer & Defect Manager (Mandatory)**:
   - Always enabled. Ingests requirements, classifies channel vs. vendor APIs, generates Technical Design Documents and Test Specifications.
2. **Agent 2: Mock Vendor API Developer (Configurable / Optional)**:
   - Enabled when third-party vendor APIs or banking cores must be simulated. If disabled (e.g. standalone microservice/CRUD), orchestrator skips mock repo provisioning and mock container startup.
3. **Agent 3: Main Coding Agent (Mandatory)**:
   - Always enabled. Implements core application logic across Python, C#, or TypeScript. Connects to mock vendor APIs only if Agent 2 is enabled.
4. **Agent 4: Independent QA Engineer (Configurable / Optional)**:
   - Enabled for automated black-box HTTP contract testing. When disabled for rapid iterations, test status is explicitly recorded as `SKIPPED (MANUAL_QA_ELECTED)`, **never reported as passed**. Agent 4 never receives source code access.
5. **Agent 5: Security Reviewer (Configurable / Optional)**:
   - Enabled for static AST/SAST vulnerability scans. When disabled, release gate warns human approvers that automated scanning was bypassed. Strictly read-only; never edits code directly.

### Initial Model & Provider Assignments (Fully Configurable)

| Agent | Default Role | Assigned Provider | Model Identifier | Configurable Scope |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 1** | Documentation Reviewer & Defect Manager | Google Gemini | `gemini-3.8-flash` | Per-Project Provider & Model Selection |
| **Agent 2** | Mock Vendor API Developer | Groq | `openai/gpt-oss-120b` | Per-Project Enable/Disable, Provider & Model |
| **Agent 3** | Main Coding Agent | Local Ollama (`dobai-ollama`) | `qwen2.5-coder:7b` | Per-Project Provider & Model Selection |
| **Agent 4** | Independent QA Engineer | Groq | `qwen/qwen3.8-27b` | Per-Project Enable/Disable, Provider & Model |
| **Agent 5** | Security Reviewer | Google Gemini | `gemini-3.5-flash-lite` | Per-Project Enable/Disable, Provider & Model |

---

## 4. Senior Engineering Standards & Operating Principles

1. **Simplicity over Premature Abstraction (KISS & YAGNI)**:
   - Prefer simple, expressive implementations over unnecessarily complex abstractions.
   - If functionality can be implemented clearly in 5 lines, do not write 15 lines without a compelling technical justification.
   - Avoid generic factories, single-implementation abstract classes, redundant helper wrappers, and repetitive logic.
2. **Minimal, Self-Documenting Code (Zero Decorative Boilerplate)**:
   - Do not add obvious comments such as `# Database Settings`, `# LLM Settings`, `# Initialize Service`.
   - Do not add decorative module, class, or function docstrings when purpose is evident from naming and typing.
   - Do not use comments to visually divide code into sections (`# -----`).
   - Retain comments/docstrings only when essential for non-obvious security requirements, business rules, complex algorithms, or tool requirements.
3. **Dynamic Orchestration without Hardcoding**:
   - The central orchestrator must evaluate project-level agent configuration flags dynamically.
   - Never hardcode a mandatory sequential run of all five agents. Incompatible configurations produce clear validation errors.
4. **Authenticity & Honest Status Reporting**:
   - Never report skipped checks as `PASSED`. A disabled QA run is recorded as `SKIPPED`.
   - Never generate placeholder implementations (`pass`, `TODO`, mocked returns) and present them as complete.
   - Quality is proven through authentic execution evidence, not claims.
5. **Deterministic State & Persistence**: All agent configurations, sessions, workflow checkpoints, tokens, and merge requests are durably persisted via SQLAlchemy 2.x.
6. **Dual-Repository Isolation**: Every generated project maintains independent local Git repositories (`mock-vendor-api` when Agent 2 enabled, and `channel-app`). No cross-repository contamination.
7. **Sandboxed Execution**: Generated code builds and runs inside ephemeral Docker containers with restricted network access and isolated CPU/memory quotas. Host execution is strictly forbidden.
8. **Security & Zero Secrets**: No plain-text API keys or tokens in database tables, commit histories, or client logs. Secrets are injected via environment configurations.

---

## 5. Antigravity Step-by-Step Development Approval Protocol

This protocol strictly governs Antigravity (the coding assistant) while building the AAISE platform. It does not constrain the runtime platform's internal agent loop.

```
+-------------------------------------------------------------------------------+
| PHASE PLANNING: Review Architecture -> Break into Steps -> Present Plan      |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| STEP APPROVAL REQUEST: Step No, Objective, Target Files, Verification, Prompt  |
| "Do you approve proceeding with Step X?"                                      |
+-------------------------------------------------------------------------------+
                                      |
               +----------------------+----------------------+
               | User Approves                              | User Rejects / Edits
               v                                            v
+-------------------------------+             +-------------------------------+
| EXECUTE APPROVED SCOPE ONLY   |             | Revise Scope & Resubmit Step  |
| - Make edits / run commands   |             +-------------------------------+
| - Run test verification       |
| - Resolve internal bugs       |
+-------------------------------+
               |
               v
+-------------------------------------------------------------------------------+
| COMPLETION REPORT: Implemented, Files, Test Evidence, Update PROGRESS.md      |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| PRESENT NEXT STEP -> Await explicit approval before next action                |
+-------------------------------------------------------------------------------+
```

### Mandatory Rules for Antigravity:
1. **Never proceed automatically**: Approval for Step X never grants approval for Step X+1.
2. **Never bundle multiple steps** into a single unapproved action.
3. **Never interpret silence as approval**.
4. **Never claim tests passed without executing them** and recording actual CLI output.
5. **Always update `docs/PROGRESS.md`** after completing an approved step.
6. **Stop immediately** when a step is completed and wait for user response.

---

## 6. Git Workflow & Branching Strategy

The platform enforces a modified GitFlow branching strategy on all generated project repositories:

- `main`: Production-ready, validated, human-approved releases only. Direct writes prohibited.
- `develop`: Primary integration branch for verified feature and fix branches.
- `feature/*`: Created by Agent 2 or Agent 3 for specific functional components.
- `fix/*`: Created for defect remediation assigned by Agent 1.
- `security/*`: Created specifically for vulnerability remediations.
- `release/*`: Created for candidate verification by Agent 4 and Agent 5 prior to promotion.

Every commit must follow Conventional Commits (`feat:`, `fix:`, `test:`, `sec:`, `docs:`). Exact commit hashes for compatible mock-channel pairs are recorded in `GitReleaseManifests`.

---

## 7. Required Documentation References
- Engineering Standards: [docs/ENGINEERING_STANDARDS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/ENGINEERING_STANDARDS.md)
- Architecture & Module Boundaries: [docs/ARCHITECTURE.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/ARCHITECTURE.md)
- System Requirements: [docs/REQUIREMENTS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/REQUIREMENTS.md)
- Agent Roles & Boundaries: [docs/AGENT_ROLES.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/AGENT_ROLES.md)
- LangGraph Orchestration & Workflows: [docs/WORKFLOW.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/WORKFLOW.md)
- Database Schema & Mapping: [docs/DATABASE_DESIGN.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/DATABASE_DESIGN.md)
- Git & Worktree Strategy: [docs/GIT_STRATEGY.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/GIT_STRATEGY.md)
- Project Deliverables & Quality Gates: [docs/DELIVERABLES.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/DELIVERABLES.md)
- Master Step-by-Step Implementation Plan: [docs/IMPLEMENTATION_PLAN.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/IMPLEMENTATION_PLAN.md)
- Live Development Progress Log: [docs/PROGRESS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/PROGRESS.md)
- Architectural Decision Records: [docs/DECISIONS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/DECISIONS.md)
