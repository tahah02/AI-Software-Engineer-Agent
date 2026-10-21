# Dynamic Multi-Agent Workflow — AAISE

## 1. Overview
The AAISE workflow is orchestrated via **LangGraph**, providing a dynamic state machine with conditional routing, durable persistence checkpointing, parallel execution, human-in-the-loop approval interrupts, and configurable agent activation per project.

---

## 2. Dynamic Workflow Execution Graph

```
[Start: Project Created / Workflow Triggered]
                     |
                     v
  [Node 1: Validate Workflow Configuration]
    - Verify invariant agents (Agent 1 & Agent 3 enabled)
    - Check dependency compatibility
                     |
                     v
  [Node 2: Ingest Requirements & Generate Specs] (Agent 1 - Mandatory)
    - Generate Technical Design Document (TDD)
    - Generate xUnit-Style Test Specification
                     |
                     v
  [Node 3: Human Approval Gate 1: Specs] <--- INTERRUPT / AWAIT USER
    - User reviews specs & approves/edits in chat
                     |
                     +---------------------------------------+
                     | (Dynamic Conditional Fork)            |
                     |                                       |
    [Condition: Is Agent 2 Enabled?]                         | (Always Required)
          |                     |                            |
          | YES                 | NO                         |
          v                     v                            v
  [Node 4A: Mock API Dev]   [Skip Mock Node]     [Node 4B: Channel App Dev]
   (Agent 2 -> mock repo)                          (Agent 3 -> channel repo)
          |                     |                            |
          +----------+----------+                            |
                     |                                       |
                     +-------------------+-------------------+
                                         | (Join / Barrier)
                                         v
                     [Node 5: Docker Sandbox Provisioning]
                      - Launch Mock container (ONLY if Agent 2 ran)
                      - Launch Channel container (aaise_app_<id>)
                                         |
                     +-------------------+-------------------+
                     | (Dynamic Conditional Verification)    |
                     |                                       |
       [Condition: Is Agent 4 Enabled?]        [Condition: Is Agent 5 Enabled?]
             |                  |                     |                 |
             | YES              | NO                  | YES             | NO
             v                  v                     v                 v
     [Node 6A: QA Test] [Mark SKIPPED]        [Node 6B: Sec]    [Mark NOT_SCANNED]
      (Agent 4: HTTP)                          (Agent 5: SAST)
             |                  |                     |                 |
             +---------+--------+                     +--------+--------+
                       |                                       |
                       +-------------------+-------------------+
                                           | (Join / Barrier)
                                           v
                          [Node 7: Quality Gate Evaluation]
             - Evaluate defects from enabled verification agents
             - If defects exist: Dispatch to Agent 1 -> Fix -> Retest (max 3)
             - If all gates pass (or skipped per configuration):
                                           |
                                           v
                       [Node 8: Human Approval Gate 2: Release] <--- INTERRUPT
             - Displays test evidence (or SKIPPED notice)
             - Displays security report (or NOT_SCANNED warning)
             - User approves release promotion
                                           |
                                           v
                       [Node 9: Production Promotion & Tagging]
             - Tag release and record GitReleaseManifest
```

---

## 3. Dynamic State Schema (`AAISEWorkflowState`)

```python
class AAISEWorkflowState(TypedDict):
    project_id: str
    workflow_run_id: str
    status: Literal["RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED", "CANCELLED"]
    current_phase: str
    iteration_count: int
    max_iterations: int
    
    # Dynamic Agent Configuration Flags
    enabled_agents: list[str]  # e.g., ["Agent 1", "Agent 3", "Agent 5"]
    is_mock_enabled: bool
    is_qa_enabled: bool
    is_security_enabled: bool
    
    # Requirements & Specs
    requirements_text: str
    technical_design_id: str | None
    test_specification_id: str | None
    spec_approval_status: Literal["PENDING", "APPROVED", "REJECTED"]
    
    # Git & Sandboxes
    mock_repo_path: str | None
    channel_repo_path: str
    mock_commit_hash: str | None
    channel_commit_hash: str | None
    mock_container_id: str | None
    channel_container_id: str | None
    
    # Verification Results (Honest Reporting)
    qa_status: Literal["PASSED", "FAILED", "SKIPPED_BY_CONFIG"]
    security_status: Literal["PASSED", "FAILED", "NOT_SCANNED_BY_CONFIG"]
    unresolved_defects: list[dict[str, Any]]
    
    # Release Promotion
    release_tag: str | None
    release_approval_status: Literal["PENDING", "APPROVED", "REJECTED"]
```

---

## 4. Conditional Edge Routing Logic

```python
def should_run_mock_api(state: AAISEWorkflowState) -> Literal["mock_dev_node", "skip_mock_node"]:
    if state["is_mock_enabled"]:
        return "mock_dev_node"
    return "skip_mock_node"

def should_run_qa(state: AAISEWorkflowState) -> Literal["qa_test_node", "skip_qa_node"]:
    if state["is_qa_enabled"]:
        return "qa_test_node"
    return "skip_qa_node"

def should_run_security(state: AAISEWorkflowState) -> Literal["security_node", "skip_security_node"]:
    if state["is_security_enabled"]:
        return "security_node"
    return "skip_security_node"
```

---

## 5. Checkpointing & State Persistence (SQL Server)
- **Table**: `WorkflowCheckpoints` in database `AI_SoftwareEngineer`.
- Every state transition and conditional routing decision is serialized to JSON and durably persisted.
- Resumption after approval gates or server restarts accurately restores the exact set of enabled agents and execution branches.
