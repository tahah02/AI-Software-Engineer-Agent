---
name: run-tests
description: Executes automated unit, integration, and black-box tests, capturing CLI output and verifying test evidence.
---

# Run Tests Skill

## When to Use
Use this skill whenever verifying implemented code, validating API endpoints, running test suites before integration, or verifying defect remediations.

## Required Inputs
- Test runner type (`pytest`, `npm test`, `dotnet test`, `curl/httpx`).
- Test suite path or target module.
- Environment variables or test configuration parameters.

## Execution Steps
1. **Prepare Environment**:
   - Verify dependencies, services, or test database containers are active and accessible.
   - Configure test environment flags (e.g., `TESTING=True`, test database connection string).
2. **Execute Test Suite**:
   - Run tests with verbose reporting: e.g., `pytest -v --tb=short tests/unit/`.
   - Capture full standard output and error streams.
3. **Analyze Results**:
   - Verify total passed, failed, and skipped counts.
   - For any failed test: inspect assertion failures, stack traces, and relevant code.
4. **Record Evidence**:
   - Document the test execution command, duration, and pass/fail counts.
   - Never report tests as passed without actual execution output.

## Constraints
- Never mock the system under test to force a pass.
- Never ignore or silence genuine assertion failures.
- Black-box QA tests (Agent 4) must execute strictly against running HTTP endpoints without accessing source code.

## Verification
- Confirm exit code 0 for passing suites.
- Review failure logs and tracebacks to ensure root cause is understood.

## Expected Outputs
- Detailed test execution summary with pass/fail counts.
- Verifiable CLI execution transcript.
