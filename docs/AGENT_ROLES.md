# Specialized AI Agent Roles, Boundaries & Invocations — AAISE

## 1. Overview
AAISE deploys five specialized engineering agents collaborating under a central LangGraph orchestrator. The orchestrator is a deterministic state machine, **not** an LLM agent. 

To support diverse project scopes (such as internal services without external banking mocks or rapid prototyping without automated QA), **agents can be independently enabled or disabled per project**.

---

## 2. Invocation Cardinality Matrix

| Agent | Default Role | Invocation Status | Invariant / Optional Rule | Default Model |
| :--- | :--- | :--- | :--- | :--- |
| **Agent 1** | Documentation Reviewer & Defect Manager | **MANDATORY** | Architectural Invariant: Must always analyze requirements and author contracts before development. | `gemini-3.8-flash` |
| **Agent 2** | Mock Vendor API Developer | **CONFIGURABLE** | Optional: Enabled when external third-party vendor APIs or banking cores must be simulated. | `openai/gpt-oss-120b` |
| **Agent 3** | Main Coding Agent | **MANDATORY** | Architectural Invariant: Must always implement application code for the target channel repository. | `qwen2.5-coder:7b` |
| **Agent 4** | Independent QA Engineer | **CONFIGURABLE** | Optional: Enabled for automated black-box API testing. When disabled, status recorded as `SKIPPED`. | `qwen/qwen3.8-27b` |
| **Agent 5** | Security Reviewer | **CONFIGURABLE** | Optional: Enabled for automated SAST/AST scans. When disabled, release gate flags missing security audit. | `gemini-3.5-flash-lite` |

---

## 3. Agent 1 — Documentation Reviewer & Defect Manager (Mandatory)
- **Role**: Technical architect and specification guardian. Ingests requirements, classifies Channel vs. Vendor APIs, generates Technical Design Documents and Test Specifications.
- **Defect Coordination**: Ingests test failures from Agent 4 (if enabled) and security findings from Agent 5 (if enabled) to formulate structured remediation instructions for Agent 2 or Agent 3.
- **Strict Constraints**: Never fabricate banking or enterprise business rules. Escalate ambiguities to human user via an approval gate. Never write application code directly.

---

## 4. Agent 2 — Mock Vendor API Developer (Configurable)
- **Role**: Implements and maintains deterministic mock servers representing external vendors, banking cores, and third-party gateways.
- **Workflow When Enabled**: Manages the isolated `mock-vendor-api` Git repository; implements mock REST endpoints; runs developer unit tests in Docker; commits verified changes.
- **Workflow When Disabled**: No mock repository or mock Docker container is provisioned. The orchestrator instructs Agent 3 that the project operates without external mock dependencies.
- **Strict Constraints**: Strictly prohibited from viewing or modifying files in `channel-app`. Never make outbound calls to live external banking or payment APIs.

---

## 5. Agent 3 — Main Coding Agent (Mandatory)
- **Role**: Implements the core business application in the target language and framework (Python/FastAPI, C#/.NET Core, TypeScript/Node.js).
- **Workflow**: Manages the isolated `channel-app` Git repository; integrates with Agent 2's mock vendor endpoints if Agent 2 is enabled; compiles and tests in Docker sandboxes; commits verified code to `feature/*` branches.
- **Strict Constraints**: Strictly prohibited from viewing or modifying files in `mock-vendor-api`.

---

## 6. Agent 4 — Independent QA Engineer (Configurable)
- **Role**: Performs unbiased, black-box API testing against running applications.
- **Workflow When Enabled**: Receives approved test specs and running container URLs; executes automated HTTP test suites; records actual response payloads, status codes, and assertion failures.
- **Workflow When Disabled**: The orchestrator records test status as `SKIPPED (MANUAL_QA_ELECTED)`. **Never recorded as PASSED.**
- **STRICT ENFORCED RULE**: **ZERO CODE ACCESS**. Agent 4 is strictly prohibited from accessing, reading, or inspecting source code files in either repository.

---

## 7. Agent 5 — Security Reviewer (Configurable)
- **Role**: Independent static security analysis (SAST) and threat modeling across both codebases.
- **Workflow When Enabled**: Scans codebases for OWASP Top 10 vulnerabilities (SQLi, SSRF, command injection, path traversal, secrets); reviews dependencies; routes findings to Agent 1.
- **Workflow When Disabled**: The release promotion gate displays an explicit warning stating that automated security audits were bypassed, requiring human risk sign-off.
- **Strict Constraints**: Strictly read-only access. Never modifies application code directly.
