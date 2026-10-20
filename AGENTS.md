# AGENTS.md — Autonomous AI Software Engineer (AAISE)

## 1. Project Mission & Overview
**Autonomous AI Software Engineer (AAISE)** is an enterprise-grade, chat-based, multi-agent AI Software Engineering platform. It autonomously transforms business requirements into production-ready software systems with rigorous human-in-the-loop controls. AAISE coordinates five specialized AI agents via a central deterministic orchestrator (LangGraph) to perform specification analysis, mock API generation, channel code implementation, black-box QA testing, and source-code security scanning across separate Git repositories.

---

## 2. Mandatory Technology Stack

| Layer | Component / Technology | Enforced Specifications |
| :--- | :--- | :--- |
| **Platform Backend** | Python 3.11+, FastAPI, Pydantic v2 | Modular Monolith, Hexagonal Architecture, Strict Typing |
| **Orchestration** | LangGraph, LiteLLM | Deterministic graph state, provider-agnostic LLM gateway |
| **Platform Frontend** | Next.js (App Router), React 19, TypeScript, Tailwind CSS | Lucide React, Recharts, EventSource streaming chat UI |
| **Database** | Microsoft SQL Server (Local instance: `MSSQLSERVER` / `MSSQLSERVER01`) | Database name: `AI_SoftwareEngineer`, SQLAlchemy 2.x + `pyodbc`, Alembic |
| **Local LLM** | Ollama in Docker (`dobai-ollama`, port `11434`) | Dual model setup: `qwen2.5:3b` (supporting) & `qwen2.5-coder:7b` (Agent 3 coding). |
| **Cloud LLMs** | Google Gemini, Groq, OpenRouter | Validated initial models: `gemini-3.8-flash`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `gemini-3.5-flash-lite` |
| **Execution** | Docker Containers (isolated sandboxes) | No host-level untrusted code execution |
| **VCS & Isolation** | Local Git, Git Worktrees | Two repos per project: `mock-vendor-api` and `channel-app` |

---

## 3. Five Specialized AI Agents (Runtime)

The central orchestrator is an execution-control engine (LangGraph), **not** an LLM agent. The platform contains exactly five specialized engineering agents:

```
                  +----------------------------------------------+
                  |           LangGraph Central Orchestrator      |
                  +----------------------------------------------+
                         |                    |             |
           +-------------+                    |             +-------------+
           v                                  v                           v
+-----------------------+          +--------------------+       +-------------------+
|  Agent 1: Doc Review  |          | Agent 2: Mock API  |       | Agent 3: Main App |
| (Specs & Defect Assign|          | (Vendor Mocks Repo)|       | (Channel App Repo)|
+-----------------------+          +--------------------+       +-------------------+
           ^                                  |                           |
           | Handoff                          +-------------+-------------+
           | Findings                                       | Integrated Apps
           |                                                v
+-----------------------+                         +-------------------+
|   Agent 5: Security   |<------------------------| Agent 4: Black-Box|
| (Read-Only Code Audit)|                         |   QA (Zero Code)  |
+-----------------------+                         +-------------------+
```

### Initial Model Assignments

| Agent | Role | Assigned Provider | Model Identifier |
| :--- | :--- | :--- | :--- |
| **Agent 1** | Documentation Reviewer & Defect Manager | Google Gemini | `gemini-3.8-flash` |
| **Agent 2** | Mock Vendor API Developer | Groq | `openai/gpt-oss-120b` |
| **Agent 3** | Main Coding Agent | Local Ollama (`dobai-ollama`) | `qwen2.5-coder:7b` |
| **Agent 4** | Independent QA Engineer | Groq | `qwen/qwen3.8-27b` |
| **Agent 5** | Security Reviewer | Google Gemini | `gemini-3.5-flash-lite` |

---

## 4. Senior Engineering Standards & Operating Principles

Every engineer and agent working on AAISE must strictly observe these senior craftsmanship standards:

1. **Simplicity over Premature Abstraction (KISS & YAGNI)**:
   - Prefer simple, expressive implementations over unnecessarily complex abstractions.
   - If functionality can be implemented clearly in 5 lines, do not write 15 lines without a compelling technical justification.
   - Avoid generic factories, single-implementation abstract classes, redundant helper wrappers, repetitive logic, and premature abstractions.
2. **Clean & Hexagonal Architecture**: Core business logic has zero direct dependencies on frameworks, databases, or external I/O. Communication passes through defined Ports & Adapters.
3. **Engineering Mindset**: Evaluate necessity, simplicity, reusability, and maintainability before implementation.
4. **Authenticity & Zero Fabrication**:
   - Never generate placeholder implementations (`pass`, `TODO`, mocked returns) and present them as complete.
   - Never fabricate successful builds, tests, or benchmark results.
   - Quality is proven through authentic execution evidence, not claims.
5. **Deterministic State & Persistence**: All agent sessions, workflow checkpoints, tokens, and merge requests are durably persisted to SQL Server (`AI_SoftwareEngineer`).
6. **Dual-Repository Isolation**: Every generated project maintains two independent local Git repositories (`mock-vendor-api` and `channel-app`). No cross-repository contamination.
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

Every commit must follow Conventional Commits (`feat:`, `fix:`, `test:`, `sec:`, `docs:`). Exact commit hashes for compatible mock-channel pairs are recorded in SQL Server `GitReleaseManifests`.

---

## 7. Required Documentation References
- Engineering Standards: [docs/ENGINEERING_STANDARDS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/ENGINEERING_STANDARDS.md)
- Architecture & Module Boundaries: [docs/ARCHITECTURE.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/ARCHITECTURE.md)
- System Requirements: [docs/REQUIREMENTS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/REQUIREMENTS.md)
- Agent Roles & Boundaries: [docs/AGENT_ROLES.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/AGENT_ROLES.md)
- LangGraph Orchestration & Workflows: [docs/WORKFLOW.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/WORKFLOW.md)
- SQL Server Database Schema: [docs/DATABASE_DESIGN.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/DATABASE_DESIGN.md)
- Git & Worktree Strategy: [docs/GIT_STRATEGY.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/GIT_STRATEGY.md)
- Project Deliverables & Quality Gates: [docs/DELIVERABLES.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/DELIVERABLES.md)
- Master Step-by-Step Implementation Plan: [docs/IMPLEMENTATION_PLAN.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/IMPLEMENTATION_PLAN.md)
- Live Development Progress Log: [docs/PROGRESS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/PROGRESS.md)
- Architectural Decision Records: [docs/DECISIONS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/DECISIONS.md)
