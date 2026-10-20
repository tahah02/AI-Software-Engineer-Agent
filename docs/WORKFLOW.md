# Autonomous Multi-Agent Workflow — AAISE

## 1. Overview
The AAISE workflow is orchestrated via **LangGraph**, providing a deterministic state machine, checkpointed execution, parallel branch coordination, human-in-the-loop approval interrupts, and bounded defect retry loops.

---

## 2. End-to-End Workflow Diagram

```
[Start: Project Created]
         |
         v
[Node 1: Ingest Requirements] (Agent 1)
         |
         v
[Node 2: Generate Specifications] (Agent 1)
  - Generate Technical Design Document (TDD)
  - Generate xUnit-Style Test Specification
         |
         v
[Node 3: Human Approval Gate 1] <--- INTERRUPT / AWAIT USER
  - User reviews specs & approves/edits in chat
         |
         v
[Node 4: Parallel Implementation] (Safe Fork)
  +---------------------------------------+
  |                                       |
  v                                       v
[Node 4A: Mock API Dev] (Agent 2)      [Node 4B: Channel App Dev] (Agent 3)
  - Init `mock-vendor-api` repo           - Init `channel-app` repo
  - Implement mock vendor endpoints       - Implement business services & client
  - Run dev tests & commit                - Run dev tests & commit
  |                                       |
  +-------------------+-------------------+
                      | (Join / Barrier)
                      v
[Node 5: Docker Sandbox Provisioning]
  - Launch Mock API container (aaise_mock_<id>)
  - Launch Channel App container (aaise_app_<id>) on shared bridge network
                      |
                      v
[Node 6: Independent Verification] (Parallel Execution)
  +---------------------------------------+
  |                                       |
  v                                       v
[Node 6A: Black-Box QA] (Agent 4)      [Node 6B: Security Review] (Agent 5)
  - HTTP test suite execution             - Read-only SAST & secret scan
  - Record status, payload, latency       - Categorize findings (CRITICAL/HIGH/MED)
  |                                       |
  +-------------------+-------------------+
                      | (Join / Barrier)
                      v
[Node 7: Quality Gate Evaluation]
  - Did all QA tests pass?
  - Are there zero CRITICAL/HIGH security findings?
         |
         +-----------------------+
         | NO (Defects Found)    | YES (All Gates Passed)
         v                       v
[Node 8: Defect Dispatch]     [Node 10: Release Manifest & Pre-Release Tag]
  (Agent 1)                     - Pair compatible commit hashes
  - Parse QA failures & SAST    - Generate Release Summary
  - Create Fix Tasks                     |
  - Check iteration count                v
         |                    [Node 11: Human Approval Gate 2] <--- INTERRUPT
         +---------------+      - User approves release promotion
         |               |               |
         | < Max (3)     | >= Max        v
         v               v    [Node 12: Production Promotion & Tagging]
[Node 9: Apply Fixes] [Escalate to]     - Fast-forward merge to `main`
  - Agent 2 (mock fix)  [Human User]     - Apply release tag (e.g., v1.0.0)
  - Agent 3 (app fix)                    - Emit Completion Event
         |
         v
  [Loop back to Node 5: Sandbox & Retest]
```

---

## 3. LangGraph State Schema (`AAISEWorkflowState`)

```python
class AAISEWorkflowState(TypedDict):
    project_id: str
    workflow_run_id: str
    status: Literal["RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED", "CANCELLED"]
    current_phase: str
    iteration_count: int
    max_iterations: int
    requirements_text: str
    uploaded_files: list[str]
    
    # Specification Artifacts
    technical_design_id: str | None
    test_specification_id: str | None
    spec_approval_status: Literal["PENDING", "APPROVED", "REJECTED"]
    
    # Git & Repository State
    mock_repo_path: str
    channel_repo_path: str
    mock_commit_hash: str | None
    channel_commit_hash: str | None
    
    # Runtime Sandboxes
    mock_container_id: str | None
    mock_container_port: int | None
    channel_container_id: str | None
    channel_container_port: int | None
    
    # QA & Security Verification Results
    test_run_id: str | None
    qa_passed: bool
    qa_failed_count: int
    security_scan_id: str | None
    security_passed: bool
    unresolved_defects: list[dict[str, Any]]
    
    # Release Promotion
    release_tag: str | None
    release_approval_status: Literal["PENDING", "APPROVED", "REJECTED"]
```

---

## 4. Checkpointing & Resume Strategy

### SQL Server Durable Checkpointer
Standard LangGraph memory checkpoints are volatile. AAISE implements a custom durable checkpointer backed by SQL Server:
- **Table**: `WorkflowCheckpoints`
- **Stored Data**: Serialized state JSON, channel versions, node execution history, pending approval payloads.
- **Resumption**: When the server restarts or a human user approves an action via chat, the orchestrator loads the checkpoint from SQL Server by `workflow_run_id` and resumes execution precisely at the interrupted node.

---

## 5. Human-in-the-Loop Approval Points

The workflow defines two mandatory human approval checkpoints:
1. **Specification Approval Gate (Node 3)**:
   - Triggered when Agent 1 finishes the Technical Design Document and Test Specifications.
   - User reviews API endpoints, data models, and test matrices.
   - User can approve, request modifications, or clarify ambiguous requirements.
2. **Release Promotion Approval Gate (Node 11)**:
   - Triggered when all QA tests pass and zero CRITICAL/HIGH security findings remain.
   - User reviews the test evidence, security report, and paired Git commit hashes before the orchestrator merges changes to `main`.
