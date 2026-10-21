# Antigravity Rule: Coding Standards and Senior Engineering Craftsmanship

## Purpose
This rule establishes senior engineering standards, code quality expectations, formatting, typing, error handling, and testing disciplines for all code written across AAISE.

---

## 1. Senior Craftsmanship: Minimal, Self-Documenting Code
1. **Zero Decorative Comments & Section Banners**:
   - Do not add obvious comments such as `# Database Settings`, `# LLM Settings`, `# Initialize Service`, or similar annotations.
   - Do not use comments to visually divide code into sections (`# -----`, `# =====`).
   - Prefer expressive naming, strict typing, and clean logic over explanatory text.
2. **Restrained Docstrings**:
   - Do not add decorative triple-quoted module, class, or function docstrings when the purpose is evident from naming and typing.
   - Retain comments or docstrings only when essential for non-obvious security requirements, business invariants, complex algorithms, public API contracts, or tool requirements.
3. **Simplicity over Premature Abstraction (KISS & YAGNI)**:
   - Prefer simple, expressive implementations over unnecessarily complex abstractions.
   - If functionality can be implemented clearly in 5 lines, do not write 15 lines without compelling justification.
   - Avoid generic factories, single-implementation abstract classes, redundant helper wrappers, repetitive logic, and premature abstractions.
4. **Execution Integrity**:
   - Never generate placeholder implementations (`pass`, `TODO`, mocked returns) and present them as complete.
   - Never fabricate successful builds, tests, or benchmark results.
   - Implement incremental, targeted modifications rather than rewriting whole modules.
5. **Cross-Language Enforcement**:
   - Apply these standards across Python, TypeScript, React, C#, and any generated application code.

---

## 2. Python Backend Standards (FastAPI & Services)
1. **Target Runtime**: Python 3.11+.
2. **Type Annotations**:
   - 100% type annotation coverage across public functions, methods, and classes.
   - Use standard library generics: `list[str]`, `dict[str, Any]`, `tuple[int, ...]`, `T | None`.
   - External payloads, configurations, and state schemas modeled via **Pydantic v2** (`BaseModel`, `Field`, `ConfigDict`).
3. **Database Operations**:
   - Use **SQLAlchemy 2.x declarative models** with `Mapped[...]` and `mapped_column(...)`.
   - Database sessions safely scoped via context managers or dependencies.
   - Zero raw string SQL concatenation. Always use parameterized queries or ORM expressions.
4. **Error Handling**:
   - Never use bare `except:` or catch generic `Exception` without structured context or re-raising.
   - Use custom domain exceptions deriving from `AAISEException`.
   - API endpoints convert domain exceptions into RFC 7807 Problem Details.
5. **Logging & Observability**:
   - Structured JSON logging. Never log plain-text passwords, LLM API keys, JWT tokens, or PII.

---

## 3. Frontend Standards (Next.js & React)
1. **Framework**: Next.js (App Router), React 19, TypeScript.
2. **Components**:
   - Functional components with strict TypeScript props typing. No `any` types.
   - Lucide React for iconography, Tailwind CSS for utility styling.
   - Recharts for metrics and timelines.
   - Concise, modular components without monolithic JSX bloat.
3. **State Management & Streaming**:
   - React hooks for local state.
   - Server-Sent Events (SSE) stream consumption with typed payload parsing.

---

## 4. Testing Standards
1. **Pytest Suite**:
   - Unit tests in `tests/unit/`, integration tests in `tests/integration/`.
2. **Execution Reality**:
   - Never fabricate test execution or mock away the component under test.
   - Verify every test execution using `pytest -v`.
