# Project Overview — Autonomous AI Software Engineer (AAISE)

## 1. Executive Summary
**Autonomous AI Software Engineer (AAISE)** is an autonomous multi-agent platform designed to automate the software development lifecycle from requirements ingestion through specification, implementation, mock API provisioning, independent QA testing, and security auditing.

AAISE delivers a conversational, chat-first experience inspired by leading AI developer environments (Cursor, Codex, Antigravity) while enforcing production-grade engineering rigor, dual-repository isolation, and human-in-the-loop governance.

---

## 2. Core Capabilities
- **Chat-First Interactive Interface**: Create software projects, upload natural language requirements, ask questions, review live progress, and approve critical development decisions directly through an intuitive conversational workspace.
- **Automated Specification & Design**: Agent 1 analyzes user requirements, extracts internal channel vs. external third-party vendor APIs, and generates formal Technical Design Documents and xUnit-style test specifications.
- **Dual-Repository Architecture**: Every generated software project maintains two separate Git repositories:
  1. `mock-vendor-api`: External bank/vendor API mocks with deterministic responses (Agent 2).
  2. `channel-app`: Main application implementing business logic and integrating with mock vendor endpoints (Agent 3).
- **Independent Black-Box QA**: Agent 4 runs automated HTTP/REST test suites against running services without access to application source code, preventing confirmation bias and testing realistic client interactions.
- **Automated Security Review**: Agent 5 conducts static security reviews (SAST), dependency checks, and OWASP vulnerability scans across generated codebases in read-only mode.
- **Autonomous Defect Remediation**: Failing tests and security vulnerabilities are automatically analyzed by Agent 1, converted into actionable fix specifications, assigned to the responsible coding agent, and verified through automated re-test loops.
- **Human-in-the-Loop Governance**: Human approvals are required for architecture specifications, destructive operations, and release promotion, ensuring engineering safety.

---

## 3. Five Runtime AI Agents
```
+-----------------------------------------------------------------------------------+
|                        LangGraph Central Orchestrator                             |
|      (State Graph, Durable Checkpointing, Approval Gates, Defect Dispatch)        |
+-----------------------------------------------------------------------------------+
       |                       |                       |                      |
       v                       v                       v                      v
+--------------+       +---------------+       +---------------+      +---------------+
|   Agent 1    |       |    Agent 2    |       |    Agent 3    |      |    Agent 4    |
| Doc Reviewer |       | Mock API Dev  |       | Main Coding   |      |   Black-Box   |
| & Defect Mgr |       | (Vendor Mocks)|       | (Channel App) |      | QA (No Code)  |
+--------------+       +---------------+       +---------------+      +---------------+
       ^                                                                      |
       | Findings & Remediations                                              |
       |                                                                      v
+--------------+                                                      +---------------+
|   Agent 5    |<-----------------------------------------------------| Running API   |
| Security     |                     Read-Only Source Audit           | Containers    |
| Reviewer     |                                                      +---------------+
+--------------+
```

---

## 4. Technology Stack Summary
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, LangGraph, LiteLLM.
- **Frontend**: Next.js (App Router), React 19, TypeScript, Tailwind CSS, Lucide React, Recharts.
- **Database**: Microsoft SQL Server (database name: `AI_SoftwareEngineer`).
- **Local LLM**: Dockerized Ollama (`dobai-ollama`, port `11434`, model: `qwen2.5:3b`).
- **Cloud LLMs**: Google Gemini, Groq, OpenRouter (free-tier eligible models).
- **Sandboxing**: Ephemeral Docker containers for runtime builds, test execution, and isolated mock services.
- **Version Control**: Local Git repositories, Git worktrees, modified GitFlow branching.

---

## 5. Antigravity Step-by-Step Approval Protocol
All engineering of the AAISE platform is governed by the Step-by-Step Development Approval Protocol:
- Antigravity never writes code, modifies schemas, or executes development steps without explicit human approval.
- Each step is proposed with its objective, target files, and verification plan.
- Upon completion, real execution evidence is reported and logged in `docs/PROGRESS.md`.
