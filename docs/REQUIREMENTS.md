# System Requirements Specification — AAISE

## 1. Functional Requirements (FR)

### FR-01: Conversational Project Management & Dynamic Agent Configuration
- **FR-01.1**: The system shall allow users to create, view, list, and switch between software engineering projects via a chat-based interface.
- **FR-01.2**: The system shall support uploading requirements documents (Markdown, TXT, PDF, Word) into project contexts.
- **FR-01.3**: The system shall maintain complete chat history and execution state across multiple user sessions.
- **FR-01.4 (Configurable Agent Topology)**: The system shall allow users to independently enable or disable any of the specialized agents per project or per workflow run:
  - Agent 1 (Doc Reviewer) and Agent 3 (Main Coding) are mandatory architectural invariants.
  - Agent 2 (Mock Dev), Agent 4 (QA), and Agent 5 (Security) are independently configurable.
  - Disabled agents must never be scheduled, allocated container resources, or invoked.
  - Incompatible workflow configurations must produce clear validation errors prior to execution.

### FR-02: Requirements Analysis & Specification (Agent 1)
- **FR-02.1**: The system shall analyze uploaded business and technical requirements to extract system boundaries, data models, workflows, and APIs.
- **FR-02.2**: The system shall classify APIs into Channel APIs (implemented in the main app) vs. Vendor APIs (mocked external dependencies).
- **FR-02.3**: The system shall generate a structured Technical Design Document (TDD) including architecture, data models, and endpoint contracts.
- **FR-02.4**: The system shall generate an xUnit-style Test Specification Document with positive, negative, boundary, validation, and error test cases for every API.
- **FR-02.5**: The system shall request explicit human approval on generated specifications before initiating code implementation.

### FR-03: Mock Vendor API Development (Agent 2 - Configurable)
- **FR-03.1**: When enabled, the system shall initialize and manage an isolated Git repository named `mock-vendor-api` for external integrations.
- **FR-03.2**: Agent 2 shall implement deterministic mock REST endpoints simulating vendor behaviors (success, validation error, service unavailable, rate limits).
- **FR-03.3**: Agent 2 shall execute developer tests inside Docker containers and commit verified changes with conventional commit messages.
- **FR-03.4**: When disabled, no mock repository or mock Docker container shall be provisioned, and Agent 3 shall be configured without external mock dependencies.

### FR-04: Main Channel Application Development (Agent 3)
- **FR-04.1**: The system shall initialize and manage a dedicated Git repository named `channel-app`.
- **FR-04.2**: Agent 3 shall implement application source code matching the approved Technical Design Document.
- **FR-04.3**: Agent 3 shall support multiple target languages (initially Python/FastAPI, C#/.NET Core, TypeScript/Node.js) via toolchain templates.
- **FR-04.4**: Agent 3 shall integrate outbound calls with Agent 2's mock endpoints if Agent 2 is enabled.
- **FR-04.5**: Agent 3 shall run developer builds and unit tests in Docker sandboxes and commit verified code to `feature/*` branches.

### FR-05: Independent Black-Box QA (Agent 4 - Configurable)
- **FR-05.1**: When enabled, Agent 4 shall execute automated HTTP test suites strictly against running Docker containers.
- **FR-05.2**: The system shall enforce zero access to application source code for Agent 4 at the tool and workspace level.
- **FR-05.3**: When disabled for rapid developer iteration, test run records must be explicitly marked as `SKIPPED (MANUAL_QA_ELECTED)`. The system shall **never** record disabled QA as `PASSED`.
- **FR-05.4**: Test results and structured defect logs shall be submitted to Agent 1 for defect remediation dispatch.

### FR-06: Independent Security Review (Agent 5 - Configurable)
- **FR-06.1**: When enabled, Agent 5 shall inspect generated codebases across both repositories in strictly read-only mode.
- **FR-06.2**: Agent 5 shall perform automated static analysis for OWASP Top 10 vulnerabilities (SQLi, SSRF, command injection, auth bypass, secret exposure, insecure deserialization).
- **FR-06.3**: When disabled, the release promotion gate shall explicitly display a warning stating that automated security audits were bypassed, requiring human risk sign-off.
- **FR-06.4**: Agent 5 shall never edit code directly.

### FR-07: Defect Remediation & Quality Gate Evaluation
- **FR-07.1**: Agent 1 shall ingest QA defect reports and Security findings from enabled verification agents to generate prioritized remediation tasks.
- **FR-07.2**: The orchestrator shall dispatch fixes to Agent 2 (for mock bugs) or Agent 3 (for channel bugs).
- **FR-07.3**: Retested builds shall iterate up to a configurable maximum limit (default: 3 iterations) before escalating to the user.

### FR-08: Model Provider Abstraction & Dynamic Resolution
- **FR-08.1**: The system shall support local Ollama (`dobai-ollama`) and cloud providers (Gemini, Groq, OpenRouter).
- **FR-08.2**: Each agent's provider and model identifier shall be dynamically configurable per project in SQL Server, without requiring hardcoded changes in agent logic.
- **FR-08.3**: The system shall track token usage (prompt, completion, total) and latency per agent invocation.

---

## 2. Non-Functional Requirements (NFR)

### NFR-01: Security & Sandboxing
- All user-generated code builds, test executions, and mock services must run inside sandboxed Docker containers.
- No plain-text API secrets, passwords, or credentials stored in SQL Server tables or Git commits.

### NFR-02: Performance & Scalability
- The chat interface must stream agent reasoning and output in real time using Server-Sent Events (SSE).
- API latency for orchestrator status and message dispatch must remain under 200ms (excluding LLM inference latency).

### NFR-03: Reliability & Determinism
- Orchestrator graph state, agent configuration flags, and task checkpoints must be durably persisted to SQLite for the POC (`./data/aaise.db`), with architectural compatibility preserved for production enterprise databases (SQL Server / PostgreSQL).
- Workflows must support pause, resume, cancel, and crash recovery from the latest durable checkpoint.

### NFR-04: Maintainability & Clean Architecture
- Backend code must adhere to Clean / Hexagonal Architecture with strict typing and Pydantic v2 schemas.
- 100% type annotations on all public classes, functions, and API schemas.
