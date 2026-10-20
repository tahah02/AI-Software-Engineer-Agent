# Antigravity Rule: Step-by-Step Development Approval Protocol

## Purpose
This rule establishes the mandatory development workflow and approval gates that Antigravity must follow during every development phase of the Autonomous AI Software Engineer (AAISE) project.

---

## 1. Core Principles
1. **Never Assume Approval**: Explicit human approval is required before executing any implementation step.
2. **Never Bundle Steps**: Each step must be planned, requested, approved, executed, verified, and reported individually.
3. **Never Fabricate Evidence**: All test executions, build statuses, and database migrations must be backed by real execution output.
4. **Scope Isolation**: Execute strictly what was approved in the specific step. Do not make out-of-scope modifications.

---

## 2. Step Lifecycle

```
[Phase Plan Approved]
        |
        v
[1. Step Submission]
  - Step Number & Title
  - Objective
  - Affected Files & Components
  - Tools & Tech
  - Verification Method
  - Explicit Prompt: "Do you approve proceeding with Step X?"
        |
        v
[2. Await User Response]
        |
        +---> [User Rejects/Modifies] ---> [Revise & Re-submit]
        |
        +---> [User Approves]
                    |
                    v
[3. Execution of Approved Step]
  - Create / Modify files
  - Run verification / tests
  - Resolve localized errors
                    |
                    v
[4. Completion Report]
  - Work Completed
  - Files Modified / Created
  - CLI / Test Evidence
  - Update docs/PROGRESS.md
                    |
                    v
[5. Transition to Step X+1]
  - Present next step & request approval
```

---

## 3. Explicit Approval Request Format
Before starting Step X, Antigravity must output:
```markdown
### Implementation Step X: [Step Title]

- **Objective**: [Clear statement of purpose]
- **Target Files / Directories**: [List of absolute/relative paths]
- **Technologies / Tools Involved**: [e.g., FastAPI, Alembic, Docker]
- **Expected Outcome**: [Deliverable description]
- **Verification Plan**: [Commands or tests to run]
- **Dependencies / Risks**: [Any prerequisites or notes]

Do you approve proceeding with Step X?
```
Antigravity must stop and await the user's explicit response before taking any further action.

---

## 4. Completion Report Format
After executing Step X, Antigravity must output:
```markdown
### Step X Completion Report: [Step Title]

- **Status**: Completed / Verified
- **Files Created / Modified**: [List of files]
- **Execution & Test Results**: [Exact command outputs and test passes]
- **Issues Resolved**: [Any errors encountered and fixed]
- **Progress Recorded**: [Updated docs/PROGRESS.md]
```

---

## 5. Scope Boundary
This protocol governs **Antigravity** during the engineering of the AAISE platform. It does not govern the five internal runtime agents of AAISE, which operate under the platform's autonomous LangGraph workflow and human-in-the-loop gates.
