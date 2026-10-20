# Architectural Decision Records (ADRs) — AAISE

## ADR-001: Selection of Modular Monolith with Clean / Hexagonal Architecture

### Status
Accepted

### Context
AAISE is an enterprise platform coordinating five specialized AI agents. A distributed microservices architecture introduces significant operational overhead (distributed transactions, complex local development, network latency between orchestrator and services) without clear benefits for the initial platform. Conversely, a monolithic architecture without clear module boundaries risks severe spaghetti code and coupling between LLM adapters, persistence layers, and business rules.

### Decision
We adopt a **Modular Monolith** organized under **Clean Architecture / Hexagonal Architecture (Ports and Adapters)**:
- Pure Domain Core models business entities and workflow states with zero external framework dependencies.
- Application Services orchestrate use cases and LangGraph execution.
- Ports define strict abstractions (`Protocol` / `ABC`) for persistence, LLMs, Git, and Docker sandboxes.
- Infrastructure Adapters implement concrete integrations (SQLAlchemy/pyodbc for SQL Server, LiteLLM/Ollama, Docker SDK, Git CLI).

### Consequences
- **Positive**: Strict boundaries enable replacing SQL Server, Docker, or LLM providers without touching domain rules. High developer productivity and simple local execution.
- **Negative**: Requires discipline to prevent developers/agents from importing infrastructure libraries directly into domain core models.

---

## ADR-002: Dual-Repository Model per Generated Project

### Status
Accepted

### Context
Generated applications typically require interactions with third-party vendors (e.g., core banking APIs, SMS gateways, payment processors). Mixing mock vendor code into the main channel application risks accidental deployment of mock endpoints to production or polluting production application code with simulation harnesses.

### Decision
Every generated project will maintain two physically separate local Git repositories:
1. `mock-vendor-api`: Owned and modified exclusively by Agent 2.
2. `channel-app`: Owned and modified exclusively by Agent 3.
The compatibility between the two repositories is tracked via `GitReleaseManifests` storing paired commit hashes verified by QA and Security.

### Consequences
- **Positive**: Complete isolation. Zero risk of mock endpoints shipping in the channel application. Enforces clear network contract boundaries.
- **Negative**: Requires orchestrating concurrent Git operations and maintaining release manifests to track matching versions.

---

## ADR-003: Strict Black-Box QA Isolation for Agent 4

### Status
Accepted

### Context
When testing agents have access to source code, they are prone to confirmation bias—tailoring test cases to match the existing implementation bugs rather than validating the business requirements.

### Decision
Agent 4 (Independent QA Engineer) is granted **zero access to source code**:
- No filesystem mounts to `channel-app` or `mock-vendor-api`.
- Agent 4 receives only the approved test specifications and running HTTP container endpoints.
- Enforced at the Docker sandbox and tool-permission level, not solely through LLM system prompts.

### Consequences
- **Positive**: Unbiased, authentic black-box verification of running services matching actual user/client experience.
- **Negative**: Agent 4 cannot provide code-level line references for bugs; it provides HTTP request/response failure evidence, which Agent 1 then translates into code defect tasks.

---

## ADR-004: Durable LangGraph Checkpointing via Microsoft SQL Server

### Status
Accepted

### Context
LangGraph provides native in-memory checkpointers for graph state, but these do not survive application restarts. Furthermore, official SQL Server checkpointers are not standard in community LangGraph releases.

### Decision
We implement a custom, durable LangGraph checkpointer backed by Microsoft SQL Server (`WorkflowCheckpoints` table). State updates are serialized to JSON alongside checkpoint keys, run IDs, and version numbers.

### Consequences
- **Positive**: Durable pause/resume across server restarts and during human approval gates. Full compliance with the mandatory Microsoft SQL Server enterprise database stack.
- **Negative**: Requires maintaining and unit-testing custom checkpoint serialization and deserialization routines.

---

## ADR-005: Sandboxed Code Execution via Docker

### Status
Accepted

### Context
Agents 2 and 3 generate and execute arbitrary user code in multiple languages (Python, C#, TypeScript). Executing untrusted code directly on the host machine presents severe security risks (filesystem tampering, environment corruption, resource exhaustion).

### Decision
All builds, server startups, and developer tests must run inside ephemeral Docker containers with CPU limits, memory caps (2GB), and private Docker bridge networks. Direct host OS execution of generated code is strictly prohibited.

### Consequences
- **Positive**: Strong process and network isolation. Predictable multi-language toolchain environments.
- **Negative**: Requires Docker engine running on the host and adds slight latency during container spin-up.
