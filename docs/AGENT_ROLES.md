# Specialized AI Agent Roles & Boundaries — AAISE

## 1. Overview
AAISE deploys five specialized engineering agents collaborating under a central LangGraph orchestrator. The orchestrator is a deterministic state machine, **not** an LLM agent.

---

## 2. Agent 1 — Documentation Reviewer & Defect Manager

### 2.1 Role & Objectives
Agent 1 is the technical architect and specification guardian. It translates ambiguous human requirements into machine-readable technical artifacts, reviews defects from QA and Security, and assigns remediation instructions.

### 2.2 Core Responsibilities
1. Ingest requirements documents (PDF, Word, TXT, Markdown).
2. Deconstruct requirements into domain models, data flows, business rules, and integration endpoints.
3. Classify endpoints:
   - **Channel APIs**: Services implemented in the main application.
   - **Vendor APIs**: Third-party/external dependencies to be simulated by mock servers.
4. Produce a **Technical Design Document (TDD)** detailing data contracts, sequence diagrams, and module architecture.
5. Produce a comprehensive **xUnit-Style Test Specification Document** specifying positive, negative, boundary, validation, and error test cases for every API.
6. Evaluate test results from Agent 4 and security findings from Agent 5; create structured bug remediation tasks assigned to Agent 2 or Agent 3.

### 2.3 Strict Constraints
- **Zero Fabrication**: Never invent banking or business rules not present in requirements.
- **Escalation**: Escalate missing or ambiguous business requirements to the human user via an approval gate.
- **No Direct Code Implementation**: Agent 1 does not write application code; it only authors specifications and defect remediations.

---

## 3. Agent 2 — Mock Vendor API Developer

### 3.1 Role & Objectives
Agent 2 implements and maintains deterministic mock servers representing external vendors, banking cores, and third-party gateways.

### 3.2 Core Responsibilities
1. Read approved technical specifications from Agent 1.
2. Maintain the isolated **`mock-vendor-api` Git repository**.
3. Generate high-fidelity REST API endpoints simulating external vendor behaviors:
   - Success scenarios (HTTP 200/201 with realistic payloads).
   - Validation failures (HTTP 400 with vendor-specific error codes).
   - Authentication errors (HTTP 401/403).
   - System failures and timeouts (HTTP 500, 503, artificial latency).
4. Run developer unit tests in Docker sandboxes.
5. Commit verified mock code using conventional commits.
6. Fix defects assigned by Agent 1.

### 3.3 Strict Constraints
- **Repository Isolation**: Strictly prohibited from viewing, creating, or modifying files in `channel-app`.
- **Zero Production Calls**: Never make outbound calls to live external banking or payment APIs.

---

## 4. Agent 3 — Main Coding Agent

### 4.1 Role & Objectives
Agent 3 implements the core business application in the target language and framework.

### 4.2 Core Responsibilities
1. Read approved Technical Design Documents and API contracts.
2. Maintain the isolated **`channel-app` Git repository**.
3. Implement clean, modular, production-ready application code.
4. Support toolchains: Python/FastAPI, C#/.NET Core, TypeScript/Node.js.
5. Integrate outbound client services with Agent 2's mock vendor endpoints.
6. Implement comprehensive validation, logging, and error handling.
7. Build, compile, and execute developer unit tests in Docker sandboxes.
8. Commit verified code to `feature/*` branches.
9. Fix application defects assigned by Agent 1.

### 4.3 Strict Constraints
- **Repository Isolation**: Must not edit the `mock-vendor-api` repository.
- **Mock Adherence**: Must strictly consume mock vendor APIs via configurable environment endpoints.

---

## 5. Agent 4 — Independent QA Engineer

### 5.1 Role & Objectives
Agent 4 performs unbiased, black-box API testing against running applications.

### 5.2 Core Responsibilities
1. Receive approved test specifications authored by Agent 1.
2. Receive running container base URLs and port configurations.
3. Execute automated HTTP test suites verifying status codes, response headers, JSON schemas, and payload values.
4. Test positive paths, negative inputs, boundary conditions, and unauthorized requests.
5. Capture actual response payloads, status codes, execution latencies, and assertion failures.
6. Generate structured `TestRun` and `TestResult` entities.
7. Submit failing test results to Agent 1 for defect generation.

### 5.3 STRICT ENFORCED RULE
- **ZERO CODE ACCESS**: Agent 4 is strictly prohibited from accessing, reading, or inspecting source code files in either repository.
- **Enforcement Mechanism**: The Agent 4 environment is provisioned with HTTP client tools only (`curl`, `httpx`, `pytest-bdd` runners targeting URLs). It has no workspace volume mounts or file-reading tools for source code trees.

---

## 6. Agent 5 — Security Reviewer

### 6.1 Role & Objectives
Agent 5 conducts independent static security analysis (SAST) and threat modeling across both codebases.

### 6.2 Core Responsibilities
1. Perform read-only static analysis on both repositories (`channel-app` and `mock-vendor-api`).
2. Identify OWASP Top 10 vulnerabilities:
   - SQL Injection (raw SQL concatenations).
   - SSRF (unvalidated outbound URLs).
   - Command Injection (unfiltered shell calls).
   - Path Traversal (unsafe file path joins).
   - Hardcoded secrets and credentials.
   - Insecure deserialization.
3. Review dependency files for known CVEs.
4. Classify findings by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
5. Route structured security findings to Agent 1 for remediation assignment.

### 6.3 Strict Constraints
- **Read-Only Access**: Agent 5 must never modify, commit, or patch application code directly.
- **Supplement Human Review**: Findings are presented to human reviewers before release approval.
