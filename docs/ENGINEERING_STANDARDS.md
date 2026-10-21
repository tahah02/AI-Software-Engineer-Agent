# Engineering Standards & Senior Craftsmanship — AAISE

## 1. Core Engineering Mindset
Every line of code in the Autonomous AI Software Engineer (AAISE) project must reflect the craft, restraint, and discipline of an experienced Principal Software Engineer. We build software meant to be maintained, operated, and extended reliably over years.

### Pre-Implementation Checklist
Before writing or modifying any code, evaluate:
1. **Necessity**: Is this code genuinely necessary, or does it solve a problem we do not yet have (YAGNI)?
2. **Simplicity**: Is there a simpler, more direct approach that meets requirements (KISS)? If a feature can be expressed clearly in 5 lines, writing 15 lines without compelling justification is unacceptable.
3. **Reusability**: Does the project already contain an existing utility, model, or pattern that solves this cleanly (DRY)?
4. **Architectural Coherence**: Does this fit cleanly into the established Modular Monolith and Clean/Hexagonal Architecture boundaries?
5. **Dependency Discipline**: Does this introduce external dependencies or abstractions that carry hidden maintenance liabilities?
6. **Verifiability**: Is this change easily testable, observable, and debuggable in production?

---

## 2. Senior Code Quality Standards: Minimal, Self-Documenting Code

1. **Zero Decorative Comments**:
   - Do not add comments such as `# Database Settings`, `# LLM Settings`, `# Initialize Service`, or similar obvious annotations.
   - Do not use comments to visually divide code into sections (`# -----`, `# =====`).
2. **No Decorative Docstrings**:
   - Do not add triple-quoted module, class, or function docstrings when the purpose is already clear from naming and typing.
   - Retain comments or docstrings only when essential for non-obvious security requirements, business rules, complex algorithms, public API contracts, or framework/tool requirements.
3. **Self-Documenting Code**:
   - Use meaningful, intention-revealing names for variables, functions, and classes.
   - Prefer expressive naming, strict typing, straightforward logic, and minimal boilerplate.
4. **No Overengineering**:
   - Avoid generic factories, single-implementation abstract classes, redundant helper wrappers, repetitive logic, and premature abstractions.
   - Never compromise correctness, security, readability, or maintainability merely to reduce line count.
5. **Universal Application**:
   - Apply this standard to Python, TypeScript, React, C#, and all generated application code.

---

## 3. Strict Typing & Schema Rigor
- **Python Backend**:
  - Python 3.11+ standard generics (`list[str]`, `dict[str, Any]`, `X | None`).
  - 100% type annotations on all public functions, methods, classes, and router handlers.
  - All external schemas and configuration objects defined via **Pydantic v2** (`BaseModel`, `Field`, `ConfigDict`).
- **Frontend (TypeScript & Next.js)**:
  - TypeScript strict mode enabled (`noImplicitAny`, `strictNullChecks`).
  - Explicit prop types for all React components. No `any` types in application code.

---

## 4. Incremental Changes & Authenticity
- Implement modifications incrementally. Never rewrite whole modules when targeted edits suffice.
- **Zero Phantom Implementations**: Never leave `TODO`, `pass`, or mock stub implementations masquerading as completed features.
- **Zero Fabricated Tests**: Every test reported as passing must be backed by authentic CLI execution outputs.
- **Zero Unverified Benchmarks**: Never claim performance metrics or benchmark numbers without running verifiable measurements.

---

## 5. Clean & Hexagonal Architecture Boundaries
1. **Domain Core**: Business entities and value objects have zero external imports (no FastAPI, SQLAlchemy, Docker, or LiteLLM).
2. **Ports**: Interface protocols (`Protocol` or `ABC`) defining contracts.
3. **Application Layer**: Coordinates domain use cases and LangGraph state. Depends only on Domain Core and Ports.
4. **Infrastructure Layer**: Implements Ports using concrete libraries.
5. **API Layer**: Exposes endpoints, validates inputs via Pydantic, and returns typed responses.
