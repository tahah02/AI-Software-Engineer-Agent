---
name: architecture-design
description: Architecture reviews, module boundaries, dependency design, ADR creation, and Clean/Hexagonal Architecture verification.
---

# Architecture Design Skill

## When to Use
Use this skill when designing new modules, evaluating architectural boundaries, introducing new interfaces or ports, making decisions regarding Clean or Hexagonal Architecture, or creating Architectural Decision Records (ADRs).

## Required Inputs
- Target module or feature concept.
- Business requirements and invariants.
- Dependencies or external integration requirements.
- Existing domain entities and port interfaces.

## Execution Steps
1. **Analyze Requirements & Boundaries**:
   - Determine whether the capability belongs to Domain Core, Application Services, Ports/Gateways, or Infrastructure Adapters.
   - Verify that domain logic does not depend on external frameworks, databases, or third-party APIs.
2. **Define Port Interfaces**:
   - Create Python `Protocol` or `ABC` abstractions for all external interactions (database persistence, Git operations, LLM calls, Docker execution).
   - Ensure interfaces are decoupled from underlying implementations.
3. **Formulate Component Interactions**:
   - Draw or document sequence flows and component interactions using standard ASCII or Mermaid syntax.
   - Verify that dependency injection is preserved and single responsibility is respected.
4. **Draft Architectural Decision Record (ADR)**:
   - If introducing a significant design choice, document it in `docs/DECISIONS.md` following standard ADR format (Context, Decision, Consequences, Status).

## Constraints
- No direct coupling between Domain Core and Infrastructure adapters.
- No global mutable singletons.
- Maintain consistency with the AAISE Modular Monolith pattern.

## Verification
- Verify imports in domain modules: no `fastapi`, `sqlalchemy`, `docker`, or `litellm` in core business rules.
- Validate that all dependencies point inward towards the domain core.

## Expected Outputs
- Interface definition files (`ports/*.py`).
- Domain entity specifications.
- Updated `docs/DECISIONS.md` or component documentation.
