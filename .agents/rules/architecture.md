# Antigravity Rule: Architecture and Design Governance

## Purpose
This rule governs all structural decisions, architectural boundaries, dependency management, and design patterns implemented across the Autonomous AI Software Engineer (AAISE) codebase.

---

## 1. Architectural Style: Clean Modular Monolith
The platform backend is organized as a Modular Monolith with Clean / Hexagonal Architecture (Ports and Adapters):

```
+-------------------------------------------------------------------------+
|                              API Adapters                               |
|        FastAPI Routers, SSE Streaming Endpoints, Request Validation     |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                           Application Services                          |
|    Use Cases, LangGraph Orchestrator Driver, Agent Task Coordinators    |
+-------------------------------------------------------------------------+
       |                                                    |
       v                                                    v
+-----------------------+                         +-----------------------+
|     Domain Core       |                         |    Ports / Gateways   |
| Entities, State Models|                         | Interfaces for DB, Git|
| Value Objects, Invar. |                         | LLM, Sandboxes, Tools |
+-----------------------+                         +-----------------------+
                                                            ^
                                                            | Implements
                                                  +-----------------------+
                                                  | Infrastructure Adpt.  |
                                                  | SQL Server / pyodbc   |
                                                  | LiteLLM, Docker Engine|
                                                  | Git CLI / pygit2      |
                                                  +-----------------------+
```

### Layer Constraints
1. **Domain Core**: Contains pure business entities, value objects, domain exceptions, and invariants. Must NOT import FastAPI, SQLAlchemy, Docker, or LiteLLM.
2. **Ports (Interfaces)**: Python `Protocol` or `ABC` classes defining contracts for persistence, LLM execution, Git operations, and sandbox runtime.
3. **Application Layer**: Contains business workflows, use cases, and LangGraph workflow nodes. Depends strictly on Domain Core and Port abstractions.
4. **Infrastructure Layer**: Implements the Ports using concrete technologies (SQLAlchemy 2.x, pyodbc, LiteLLM, Docker SDK, Git CLI). No domain logic allowed in infrastructure.
5. **API Layer**: Exposes HTTP/REST and Server-Sent Events (SSE) via FastAPI. Translates HTTP requests to Application DTOs and handles exceptions.

---

## 2. Senior Engineering Restraint in Architecture
1. **Pragmatic SOLID & Clean Architecture**:
   - Clean Architecture provides separation of concerns, not an excuse for boilerplate explosion.
   - Do not create single-method interfaces or pass-through adapters that merely forward calls without value.
   - Prefer simple, expressive implementations over nested abstraction hierarchies.
2. **Dependency Injection**:
   - FastAPI endpoints inject application services using `fastapi.Depends`.
   - Application services receive interface ports via constructor injection (`__init__`).
   - Avoid global mutable state and singletons.
3. **Modularity over Distributed Services**:
   - Keep platform capabilities inside clearly defined modules within the monorepo.
   - No unnecessary microservices.

---

## 3. Five Specialized Agents Architecture
1. **Central Orchestrator is NOT an LLM Agent**: The orchestrator is a deterministic LangGraph state machine coordinating task transitions, state persistence, approval interrupts, and retry loops.
2. **Agent Isolation**:
   - `Agent 1 (Doc Reviewer)`: Analyzes specs, produces technical docs and test plans, processes QA/Security findings.
   - `Agent 2 (Mock API Developer)`: Operates exclusively on the `mock-vendor-api` Git repository.
   - `Agent 3 (Main Coding Agent)`: Operates exclusively on the `channel-app` Git repository.
   - `Agent 4 (Independent QA)`: Black-box testing ONLY. Never receives source code file access or repo paths.
   - `Agent 5 (Security Reviewer)`: Read-only AST and SAST scanning across both repositories. Direct editing strictly forbidden.

---

## 4. References
- Master Engineering Standards: [docs/ENGINEERING_STANDARDS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/ENGINEERING_STANDARDS.md)
- Detailed Architecture Specification: [docs/ARCHITECTURE.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/ARCHITECTURE.md)
- Database Design: [docs/DATABASE_DESIGN.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/DATABASE_DESIGN.md)
- Agent Roles & Boundaries: [docs/AGENT_ROLES.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/AGENT_ROLES.md)
