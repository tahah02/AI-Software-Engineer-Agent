# Architectural Decision Records (ADRs) — AAISE

## ADR-001: Selection of Modular Monolith with Clean / Hexagonal Architecture

### Status
Accepted

### Context
AAISE is an enterprise platform coordinating specialized AI agents. A distributed microservices architecture introduces significant operational overhead (distributed transactions, complex local development, network latency between orchestrator and services) without clear benefits for the initial platform. Conversely, a monolithic architecture without clear module boundaries risks severe spaghetti code and coupling between LLM adapters, persistence layers, and business rules.

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
1. `mock-vendor-api`: Owned and modified exclusively by Agent 2 (when enabled).
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

---

## ADR-006: Dedicated Per-Agent LLM Model Selection & Dual-Model Ollama Setup

### Status
Accepted

### Context
Different software engineering tasks have vastly different intelligence and context length requirements. Document analysis and security auditing benefit from large context windows (1M+ tokens), while coding requires specialized reasoning and QA requires fast deterministic evaluation.

### Decision
We assign dedicated models per agent role:
- Agent 1: Google Gemini (`gemini-3.8-flash`)
- Agent 2: Groq (`openai/gpt-oss-120b`)
- Agent 3: Local Ollama (`qwen2.5-coder:7b`) with fallback (`qwen2.5:3b`)
- Agent 4: Groq (`qwen/qwen3.8-27b`)
- Agent 5: Google Gemini (`gemini-3.5-flash-lite`)

### Consequences
- **Positive**: Optimizes latency, cost, and task-specific performance across free-tier eligible providers.
- **Negative**: Requires handling different tool-calling and structured output capabilities across providers via adapter repair loops.

---

## ADR-007: Dynamic Multi-Agent Workflow Orchestration & Independent Agent Configurability

### Status
Accepted

### Context
Not all enterprise development projects require all five agents. Standalone services without third-party vendor APIs do not need Agent 2 (Mock Dev). Rapid prototyping iterations may disable automated QA (Agent 4) in favor of manual testing, or bypass security scanning (Agent 5). A hardcoded sequential workflow requiring all five agents forces unnecessary resource consumption, Docker container spin-up, and token costs.

### Decision
We introduce dynamic, configurable agent workflows:
1. **Per-Project Configuration**: Stored in `ProjectAgentConfigs` in SQL Server, allowing independent enable/disable toggles, provider, and model selection.
2. **Architectural Invariants**: Agent 1 (Doc Reviewer) and Agent 3 (Main Coding) are mandatory. Agents 2, 4, and 5 are configurable.
3. **Dynamic Conditional Edges in LangGraph**: LangGraph nodes dynamically evaluate enablement flags (`is_mock_enabled`, `is_qa_enabled`, `is_security_enabled`) rather than following static sequential edges.
4. **Authentic Audit Trail**: When an agent is disabled, the audit trail explicitly logs status as `SKIPPED (MANUAL_QA_ELECTED)` or `NOT_SCANNED`. Skipped checks are **never reported as passed**.

### Consequences
- **Positive**: Extreme architectural flexibility; eliminates wasted compute and tokens on unnecessary mock or QA containers; supports diverse project archetypes (standalone CRUD, enterprise integrations, rapid prototypes).
- **Negative**: Requires conditional edge routing logic and validation checks in LangGraph to prevent illegal states.

---

## ADR-008: Adoption of SQLite for Platform Proof of Concept (POC) Persistence

### Status
Accepted

### Context
During Phase 1 foundation development, Microsoft SQL Server required local instance service management and Windows-specific ODBC drivers (`pyodbc`). To accelerate Proof of Concept (POC) development, simplify multi-agent integration testing, and enable portable, self-contained execution without external database installation dependencies, a lightweight embedded persistence engine is required for the POC phase.

### Decision
We adopt **SQLite** as the primary persistence engine for the POC:
1. **Configurable Connection**: Default `DATABASE_URL` set to `sqlite:///./data/aaise.db`.
2. **Git-Ignored Local Data**: All SQLite database files reside in `./data/`, strictly ignored by Git.
3. **Clean Architecture Isolation**: Persistence specifics remain encapsulated in `src/infrastructure/db/`. Domain entities and port contracts remain completely database-agnostic.
4. **Standard Dialect Constructs**: All SQLAlchemy 2.x declarative models and Alembic migrations will use standard, portable types (`String`, `DateTime(timezone=True)`, `Boolean`, `Integer`, `Uuid`) to enable zero-friction production migration to SQL Server or PostgreSQL.
5. **Runtime Concurrency & Foreign Keys**: SQLite engine is configured with `connect_args={"check_same_thread": False}` for FastAPI asynchronous thread pools, and an engine connect hook enforces `PRAGMA foreign_keys=ON`.

### Consequences
- **Positive**: Zero external database dependencies for local runs and CI; fast automated test execution; portable local development.
- **Negative**: Limited concurrent write throughput compared to SQL Server or PostgreSQL; lacks native `DATETIME2` or clustered index optimizations (acceptable for POC workloads).
