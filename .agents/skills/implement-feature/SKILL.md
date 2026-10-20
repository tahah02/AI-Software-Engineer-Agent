---
name: implement-feature
description: Implements approved features adhering to architecture contracts, typing standards, and existing codebase conventions.
---

# Implement Feature Skill

## When to Use
Use this skill when implementing an approved development step or feature within the AAISE platform backend or frontend.

## Required Inputs
- Approved step specification and user confirmation.
- Domain models and port contracts.
- Relevant documentation references (`docs/ARCHITECTURE.md`, `docs/REQUIREMENTS.md`).

## Execution Steps
1. **Pre-Implementation Verification**:
   - Verify all prerequisite steps and dependencies are in place.
   - Confirm target files and directories.
2. **Domain & Application Logic**:
   - Implement domain entities, value objects, and application use cases first.
   - Enforce Pydantic v2 schemas and 100% type annotations.
3. **Infrastructure & Adapters**:
   - Implement or update adapters implementing the defined ports.
   - Ensure clean error handling and structured logging.
4. **API & Interface Layer**:
   - Expose endpoints via FastAPI routers or React components.
   - Validate payload schemas and error responses.
5. **Unit Verification**:
   - Write corresponding unit tests covering happy paths, edge cases, and failure modes.

## Constraints
- Execute strictly within the approved step scope. Do not bundle unapproved changes.
- Never write credentials, plain-text API keys, or raw SQL queries.
- Follow Clean Architecture and existing project conventions.

## Verification
- Run static type checks (`mypy` or `pyright` where configured).
- Execute unit tests using `pytest` to verify the implementation.

## Expected Outputs
- Fully implemented source code files with docstrings and type annotations.
- Comprehensive unit tests matching the new feature.
