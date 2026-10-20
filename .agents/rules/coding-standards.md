# Antigravity Rule: Coding Standards and Senior Engineering Craftsmanship

## Purpose
This rule establishes senior engineering standards, code quality expectations, formatting, typing, error handling, and testing disciplines for all Python and TypeScript code written for AAISE.

---

## 1. Senior Engineering Principles & Craftsmanship
1. **Simplicity over Premature Abstraction (KISS & YAGNI)**:
   - Prefer simple, expressive implementations over unnecessarily complex abstractions.
   - If functionality can be implemented clearly in 5 lines, do not write 15 lines without a meaningful reason.
   - Avoid generic factories, single-implementation abstract classes, redundant helper wrappers, repetitive logic, and premature abstractions.
2. **Readability & Self-Documenting Code**:
   - Write clean, concise, production-grade code comparable to that of an experienced senior software engineer.
   - Use meaningful, intention-revealing names for variables, functions, and classes.
   - Comments must be used only to explain non-obvious business decisions, invariants, constraints, or trade-offs—never what obvious code does.
3. **Execution Integrity**:
   - Never generate placeholder implementations (`pass`, `TODO`, mocked returns) and present them as complete.
   - Never fabricate successful builds, tests, or benchmark results.
   - Implement incremental, targeted modifications rather than rewriting whole modules.
4. **Pre-Implementation Evaluation**:
   - Before implementing, evaluate: Is the solution necessary? Is there a simpler approach? Can existing code be reused (DRY)? Does it fit the architecture? Does it introduce unneeded dependencies?

---

## 2. Python Backend Standards (FastAPI & Services)
1. **Target Runtime**: Python 3.11+.
2. **Type Annotations**:
   - 100% type annotation coverage across public functions, methods, and classes.
   - Use standard library generics: `list[str]`, `dict[str, Any]`, `tuple[int, ...]`, `T | None` (avoid deprecated `typing.List`, `typing.Optional`).
   - All external payloads, configurations, and state schemas must use **Pydantic v2** (`BaseModel`, `Field`, `ConfigDict`).
3. **Database Operations**:
   - Use **SQLAlchemy 2.x declarative models** with `Mapped[...]` and `mapped_column(...)`.
   - All database sessions must be asynchronous where applicable or safely scoped via context managers (`sessionmaker`).
   - Zero raw string SQL concatenation. Always use parameterized queries or ORM expressions.
4. **Error Handling**:
   - Never use bare `except:` or catch generic `Exception` without re-raising or logging structured context.
   - Use custom domain exceptions deriving from an application base exception (`AAISEException`).
   - API endpoints must convert domain exceptions into RFC 7807 compliant Problem Details responses.
5. **Logging & Observability**:
   - Use structured logging with JSON formatting.
   - Never log plain-text passwords, LLM API keys, JWT tokens, or PII.

---

## 3. Frontend Standards (Next.js & React)
1. **Framework**: Next.js (App Router), React 19, TypeScript.
2. **Components**:
   - Functional components only with strict TypeScript props typing. No `any` types.
   - Lucide React for iconography.
   - Tailwind CSS for utility styling (avoid ad-hoc inline styles).
   - Recharts for metrics, token usage, and timeline visualizations.
   - Maintain concise, modular React components. Avoid giant monolithic JSX components.
3. **State Management & Streaming**:
   - React hooks (`useState`, `useReducer`, `useEffect`, `useCallback`) for local state.
   - Server-Sent Events (SSE) stream consumption with automatic reconnection and typed payload parsing.

---

## 4. Testing Standards
1. **Pytest Suite**:
   - Every domain entity, service, and utility must have accompanying unit tests in `tests/unit/`.
   - Integration tests covering FastAPI endpoints, SQL Server database queries, and Docker manager operations in `tests/integration/`.
2. **Execution Reality**:
   - Never fabricate test execution or mock away the component under test.
   - All tests must be executed using `pytest -v` and results verified before marking a task complete.

---

## 5. References
- Master Engineering Standards: [docs/ENGINEERING_STANDARDS.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/ENGINEERING_STANDARDS.md)
- Architectural Boundaries: [docs/ARCHITECTURE.md](file:///d:/AI%20Software%20Engineer%20Agent/docs/ARCHITECTURE.md)
- Step Approval Protocol: [.agents/rules/implementation-process.md](file:///d:/AI%20Software%20Engineer%20Agent/.agents/rules/implementation-process.md)
