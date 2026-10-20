---
name: verify-deliverables
description: Validates completed development phases against approved deliverables, acceptance criteria, and quality gates.
---

# Verify Deliverables Skill

## When to Use
Use this skill at the conclusion of each development phase, major milestone, or before presenting phase completion reports to the user.

## Required Inputs
- Target phase number and description.
- Master deliverables checklist (`docs/DELIVERABLES.md`).
- Master implementation plan (`docs/IMPLEMENTATION_PLAN.md`).
- Execution records and test results.

## Execution Steps
1. **Load Phase Acceptance Criteria**:
   - Extract the exact deliverables defined for the target phase in `docs/DELIVERABLES.md`.
2. **Audit Deliverable Artifacts**:
   - Check existence, structure, and integrity of all required files, modules, database tables, and documentation.
   - Confirm all planned endpoints, models, and UI views exist.
3. **Validate Quality Gates**:
   - Verify unit and integration test pass rates.
   - Verify security audit scan results.
   - Confirm zero unresolved Blocker/High defects.
4. **Compile Phase Audit Report**:
   - Mark deliverables as Verified, Incomplete, or Blocked.
   - Document any known technical debt or deferred items.

## Constraints
- Do not mark deliverables complete based on assumption. Verify file existence and test runs.
- Escalate any unmet acceptance criteria to the user before proceeding.

## Verification
- Run automated check scripts or verify file paths and test outputs directly.

## Expected Outputs
- Phase Deliverables Verification Report.
- Gate status: PASS, CONDITIONAL PASS, or FAIL.
