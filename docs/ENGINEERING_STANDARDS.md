# Engineering Standards & Senior Craftsmanship — AAISE

## 1. Core Engineering Mindset
Every line of code in the Autonomous AI Software Engineer (AAISE) project must reflect the craft, restraint, and discipline of an experienced Principal Software Engineer. We build software meant to be maintained, operated, and extended reliably over years.

### The Pre-Implementation Checklist
Before writing or modifying any code, evaluate:
1. **Necessity**: Is this code genuinely necessary, or does it solve a problem we do not yet have (YAGNI)?
2. **Simplicity**: Is there a simpler, more direct approach that meets requirements (KISS)? If a feature can be expressed clearly in 5 lines, writing 15 lines without a compelling technical justification is unacceptable.
3. **Reusability**: Does the project already contain an existing utility, model, or pattern that solves this cleanly (DRY)?
4. **Architectural Coherence**: Does this fit cleanly into the established Modular Monolith and Clean/Hexagonal Architecture boundaries?
5. **Dependency Discipline**: Does this introduce external dependencies or abstractions that carry hidden maintenance liabilities?
6. **Verifiability**: Is this change easily testable, observable, and debuggable in production?

---

## 2. Senior Code Quality Standards

### 2.1 Simplicity over Premature Abstraction
- **No Overengineering**: Avoid generic factories, abstract base classes for single implementations, unnecessary wrapper functions, and deep inheritance trees.
- **Self-Documenting Code**: Choose expressive, intention-revealing variable, function, and class names.
- **Restrained Comments**: Write comments only to explain non-obvious business invariants, subtle constraints, architectural decisions, or performance trade-offs. Never explain what obvious code does.
- **Concise Implementations**: Prefer standard library capabilities, modern language idioms, and concise list/dict comprehensions over multi-line imperative boilerplate where readability is enhanced.

### 2.2 Strict Typing & Schema Rigor
- **Python Backend**:
  - Python 3.11+ standard generics (`list[str]`, `dict[str, Any]`, `X | None`).
  - 100% type annotations on all public functions, methods, classes, and router handlers.
  - All external schemas and configuration objects defined via **Pydantic v2** (`BaseModel`, `Field`, `ConfigDict`).
- **Frontend (TypeScript & Next.js)**:
  - TypeScript strict mode enabled (`noImplicitAny`, `strictNullChecks`).
  - Explicit prop types for all React components. No `any` types in application code.

### 2.3 Incremental Changes & Non-Destructive Refactoring
- Implement modifications incrementally. Never rewrite whole modules when targeted edits suffice.
- Preserve existing docstrings, comments, and public APIs unless explicitly approved for modification.

### 2.4 Authenticity & Execution Verification
- **Zero Phantom Implementations**: Never leave `TODO`, `pass`, or mock stub implementations masquerading as completed features.
- **Zero Fabricated Tests**: Every test reported as passing must be backed by authentic CLI execution outputs.
- **Zero Unverified Benchmarks**: Never claim performance metrics or benchmark numbers without running verifiable measurements.

---

## 3. Clean & Hexagonal Architecture Boundaries

```
+-------------------------------------------------------------------------+
|                                API Layer                                |
|        FastAPI Routers, SSE Endpoints, Next.js React Components         |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                           Application Layer                             |
|          Use Cases, LangGraph Orchestration, Workflow Nodes             |
+-------------------------------------------------------------------------+
       |                                                    |
       v                                                    v
+-----------------------+                         +-----------------------+
|      Domain Core      |                         |         Ports         |
|  Entities, Invariants |                         | Protocol Interfaces   |
|  (Zero dependencies)  |                         | (DB, Git, LLM, Docker)|
+-----------------------+                         +-----------------------+
                                                            ^
                                                            | Implements
                                                  +-----------------------+
                                                  |     Infrastructure    |
                                                  | SQL Server, LiteLLM   |
                                                  | Docker SDK, Git CLI   |
                                                  +-----------------------+
```

1. **Domain Core**: Business entities and value objects have **zero external imports** (no FastAPI, SQLAlchemy, Docker, or LiteLLM).
2. **Ports**: Interface protocols (`Protocol` or `ABC`) defining contracts.
3. **Application Layer**: Coordinates domain use cases and LangGraph state. Depends only on Domain Core and Ports.
4. **Infrastructure Layer**: Implements Ports using concrete libraries.
5. **API Layer**: Exposes endpoints, validates inputs via Pydantic, and returns typed responses.

---

## 4. Error Handling & Observability
1. **Domain Exceptions**: Use explicit, custom domain exceptions deriving from a base `AAISEException` (e.g., `EntityNotFoundError`, `ValidationError`, `WorkflowConflictError`).
2. **No Silent Failures**: Never catch generic `Exception` without structured logging or re-raising. Never swallow errors silently.
3. **RFC 7807 Problem Details**: Map domain exceptions to standardized HTTP responses in FastAPI.
4. **Structured Logging**: Log meaningful execution context (run IDs, task IDs, durations) while strictly omitting API keys, tokens, or PII.
