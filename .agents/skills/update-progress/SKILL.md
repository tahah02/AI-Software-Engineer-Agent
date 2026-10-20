---
name: update-progress
description: Updates development tracking, records completed steps, notes test results, logs blockers, and plans next steps.
---

# Update Progress Skill

## When to Use
Use this skill immediately upon completing an approved development step, resolving a defect, or concluding a phase to keep `docs/PROGRESS.md` accurate and up to date.

## Required Inputs
- Step number and description.
- List of modified, created, or deleted files.
- Command outputs, test pass counts, and verification logs.
- Next scheduled step details.

## Execution Steps
1. **Open Progress Log**:
   - Access `docs/PROGRESS.md`.
2. **Log Completed Step**:
   - Add entry under current phase section with timestamp.
   - Record what was implemented, files modified, and commands executed.
   - Attach test evidence summary (e.g., "14 unit tests passed, 0 failures").
3. **Update Status Table**:
   - Mark the step status as `COMPLETED`.
   - Update current active step to the next upcoming step.
4. **Log Blockers or Technical Notes**:
   - Record any architectural observations, performance notes, or dependencies for future steps.

## Constraints
- Never update progress to `COMPLETED` if tests failed or verification was skipped.
- Keep the log concise, factual, and strictly chronological.

## Verification
- Review `docs/PROGRESS.md` formatting and ensure no broken links or inconsistent step numbering.

## Expected Outputs
- Updated `docs/PROGRESS.md` reflecting the exact state of project implementation.
