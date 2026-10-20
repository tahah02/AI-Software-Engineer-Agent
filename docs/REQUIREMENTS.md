# System Requirements Specification — AAISE

## 1. Functional Requirements (FR)

### FR-01: Conversational Project Management
- **FR-01.1**: The system shall allow users to create, view, list, and switch between software engineering projects via a chat-based interface.
- **FR-01.2**: The system shall support uploading requirements documents (Markdown, TXT, PDF, Word) into project contexts.
- **FR-01.3**: The system shall maintain complete chat history and execution state across multiple user sessions.

### FR-02: Requirements Analysis & Specification (Agent 1)
- **FR-02.1**: The system shall analyze uploaded business and technical requirements to extract system boundaries, data models, workflows, and APIs.
- **FR-02.2**: The system shall classify APIs into Channel APIs (implemented in the main app) vs. Vendor APIs (mocked external dependencies).
- **FR-02.3**: The system shall generate a structured Technical Design Document (TDD) including architecture, data models, and endpoint contracts.
- **FR-02.4**: The system shall generate an xUnit-style Test Specification Document with positive, negative, boundary, validation, and error test cases for every API.
- **FR-02.5**: The system shall request explicit human approval on generated specifications before initiating code implementation.

### FR-03: Mock Vendor API Development (Agent 2)
- **FR-03.1**: The system shall initialize and manage a dedicated, isolated Git repository named `mock-vendor-api` for external integrations.
- **FR-03.2**: Agent 2 shall implement deterministic mock REST endpoints simulating vendor behaviors (success, validation error, service unavailable, rate limits).
- **FR-03.3**: Agent 2 shall execute developer tests inside Docker containers and commit verified changes with conventional commit messages.
- **FR-03.4**: Agent 2 shall never alter files or branches in the `channel-app` repository.

### FR-04: Main Channel Application Development (Agent 3)
- **FR-04.1**: The system shall initialize and manage a dedicated Git repository named `channel-app`.
- **FR-04.2**: Agent 3 shall implement application source code matching the approved Technical Design Document.
- **FR-04.3**: Agent 3 shall support multiple target languages (initially Python/FastAPI, C#/.NET Core, TypeScript/Node.js) via toolchain templates.
- **FR-04.4**: Agent 3 shall integrate outbound calls with Agent 2's mock endpoints rather than external production systems.
- **FR-04.5**: Agent 3 shall run developer builds and unit tests in Docker sandboxes and commit verified code to `feature/*` branches.

### FR-05: Independent Black-Box QA (Agent 4)
- **FR-05.1**: Agent 4 shall execute automated HTTP test suites strictly against running Docker containers.
- **FR-05.2**: The system shall enforce zero access to application source code for Agent 4 at the tool and workspace level.
- **FR-05.3**: Agent 4 shall record request/response payloads, HTTP status codes, latencies, and assertion failures.
- **FR-05.4**: Test results and structured defect logs shall be submitted to Agent 1 for defect remediation dispatch.

### FR-06: Independent Security Review (Agent 5)
- **FR-06.1**: Agent 5 shall inspect generated codebases across both repositories in strictly read-only mode.
- **FR-06.2**: Agent 5 shall perform automated static analysis for OWASP Top 10 vulnerabilities (SQLi, SSRF, command injection, auth bypass, secret exposure, insecure deserialization).
- **FR-06.3**: Agent 5 shall categorize findings into Blocker, High, Medium, and Low severities and route them to Agent 1.
- **FR-06.4**: Agent 5 shall never edit code directly.

### FR-07: Defect Remediation Loop
- **FR-07.1**: Agent 1 shall ingest QA defect reports and Security findings to generate prioritized remediation tasks.
- **FR-07.2**: The orchestrator shall dispatch fixes to Agent 2 (for mock bugs) or Agent 3 (for channel bugs).
- **FR-07.3**: Coding agents shall apply fixes in dedicated `fix/*` or `security/*` branches.
- **FR-07.4**: Re-tested builds shall iterate up to a configurable maximum limit (default: 3 iterations) before escalating to the user.

### FR-08: Model Provider Abstraction
- **FR-08.1**: The system shall support local Ollama (`qwen2.5:3b` in Docker) and cloud providers (Gemini, Groq, OpenRouter).
- **FR-08.2**: Each agent shall allow independent LLM provider and model configuration.
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
- Orchestrator graph state and task checkpoints must be durably persisted to SQL Server (`AI_SoftwareEngineer`).
- Workflows must support pause, resume, cancel, and crash recovery from the latest durable checkpoint.

### NFR-04: Maintainability & Clean Architecture
- Backend code must adhere to Clean / Hexagonal Architecture with strict typing and Pydantic v2 schemas.
- 100% type annotations on all public classes, functions, and API schemas.
