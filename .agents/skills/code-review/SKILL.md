---
name: code-review
description: Inspects code quality, architecture compliance, security vulnerabilities, performance, and style consistency.
---

# Code Review Skill

## When to Use
Use this skill before merging branches into `develop`, prior to release promotion, or during quality audits to review code for correctness, security, and architectural integrity.

## Required Inputs
- Git diff or list of modified/added files.
- Architectural guidelines and coding standards (`.agents/rules/`).
- Security rules and threat model (`.agents/rules/security.md`).

## Execution Steps
1. **Scope & Diff Analysis**:
   - Inspect `git diff` against base branch.
   - Confirm all changes are directly related to the approved task.
2. **Architecture & Standards Check**:
   - Check Clean Architecture boundary compliance (no domain-to-infra coupling).
   - Verify Pydantic v2 schemas and strict Python type annotations.
   - Ensure proper error handling, docstrings, and logging.
3. **Security Audit**:
   - Check for OWASP vulnerabilities: SQL injection, SSRF, command injection, path traversal, hardcoded secrets.
   - Confirm safe parameterized queries and environment-based secrets.
4. **Performance & Reliability**:
   - Inspect resource leaks (unclosed sessions, unreleased connections).
   - Check query efficiency (avoid N+1 queries in SQLAlchemy).
5. **Formulate Findings**:
   - Classify findings: Blocker, High, Medium, Low, or Nitpick.
   - Provide concrete, actionable remediation suggestions with code examples.

## Constraints
- Reviewers must not alter code during the review; remediation must be done through appropriate fix branches.
- Do not approve code that contains unaddressed security risks or missing test coverage.

## Verification
- Cross-reference diff against `.agents/rules/coding-standards.md` and `.agents/rules/security.md`.

## Expected Outputs
- Structured Code Review Report with categorized findings and approval/rejection recommendation.
