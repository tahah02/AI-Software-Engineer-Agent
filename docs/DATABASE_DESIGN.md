# Database Design Specification — AAISE

## 1. Overview
The database engine for AAISE is configured with a portable schema designed for enterprise relational engines. For the Proof of Concept (POC), **SQLite** serves as the primary persistence engine (`./data/aaise.db`), with strict foreign-key enforcement enabled (`PRAGMA foreign_keys=ON`). The schema and SQLAlchemy 2.x declarative definitions are written portably to support seamless future deployment to **Microsoft SQL Server** (`AI_SoftwareEngineer`) or PostgreSQL. It stores all project metadata, configurable agent settings, conversational history, agent tasks, token metrics, workflow checkpoints, Git references, test executions, and security audit records.

---

## 2. Entity-Relationship Overview

```
[Projects]
   |--- 1:N ---> [ProjectAgentConfigs]  <-- Per-Project Agent Enablement & Models
   |--- 1:N ---> [ProjectFiles]
   |--- 1:N ---> [Conversations] --- 1:N ---> [Messages]
   |--- 1:N ---> [WorkflowRuns]
   |                |--- 1:N ---> [WorkflowEvents]
   |                |--- 1:N ---> [WorkflowCheckpoints]
   |                |--- 1:N ---> [HumanApprovals]
   |--- 1:N ---> [AgentTasks]
   |                |--- 1:N ---> [AgentExecutions]
   |                                 |--- 1:N ---> [LLMInvocations] --- 1:1 ---> [TokenUsage]
   |                                 |--- 1:N ---> [ToolExecutions]
   |--- 1:N ---> [GitRepositories]
   |                |--- 1:N ---> [GitBranches]
   |                |--- 1:N ---> [GitCommits]
   |--- 1:N ---> [GitReleaseManifests]
   |--- 1:N ---> [Artifacts]
   |--- 1:N ---> [TestCases]
   |--- 1:N ---> [TestRuns] --- 1:N ---> [TestResults]
   |--- 1:N ---> [Defects]
   |--- 1:N ---> [SecurityScans] --- 1:N ---> [SecurityFindings]
```

---

## 3. Normalized Table Specifications

### 3.1 `Projects`
- **Purpose**: Stores top-level metadata for software projects created by users.
- **Primary Key**: `id` (`UNIQUEIDENTIFIER`, default `NEWSEQUENTIALID()`)
- **Columns**: `name` (`NVARCHAR(200)`), `description` (`NVARCHAR(MAX)`), `target_framework` (`NVARCHAR(100)`), `status` (`NVARCHAR(50)`), `created_at` (`DATETIME2`), `updated_at` (`DATETIME2`).

### 3.2 `ProjectAgentConfigs` (Configurable Workflow & Dynamic LLM Assignment)
- **Purpose**: Stores per-project agent configuration, enable/disable status, provider, and model assignments.
- **Primary Key**: `id` (`UNIQUEIDENTIFIER`)
- **Foreign Keys**: `project_id` REFERENCES `Projects(id)` ON DELETE CASCADE
- **Columns**:
  - `agent_type` (`NVARCHAR(100)`, NOT NULL: "Agent 1", "Agent 2", etc.)
  - `is_enabled` (`BIT`, NOT NULL, default 1)
  - `provider` (`NVARCHAR(50)`, NOT NULL: "gemini", "groq", "ollama", "openrouter")
  - `model_name` (`NVARCHAR(100)`, NOT NULL: e.g., "gemini-3.8-flash", "qwen2.5-coder:7b")
  - `custom_system_prompt` (`NVARCHAR(MAX)`, NULL)
  - `created_at` (`DATETIME2`, NOT NULL, default `SYSUTCDATETIME()`)
  - `updated_at` (`DATETIME2`, NOT NULL, default `SYSUTCDATETIME()`)
- **Unique Constraint**: `UQ_Project_Agent` (`project_id`, `agent_type`)

### 3.3 `ProjectFiles`
- **Purpose**: Tracks uploaded requirements documents and reference files.
- **Primary Key**: `id` (`UNIQUEIDENTIFIER`)
- **Foreign Keys**: `project_id` REFERENCES `Projects(id)` ON DELETE CASCADE
- **Columns**: `file_name` (`NVARCHAR(260)`), `file_path` (`NVARCHAR(1000)`), `file_type` (`NVARCHAR(50)`), `file_size_bytes` (`BIGINT`), `created_at` (`DATETIME2`).

### 3.4 `Conversations` & `Messages`
- **`Conversations`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `title` (`NVARCHAR(200)`), `created_at` (`DATETIME2`).
- **`Messages`**: `id` (`UNIQUEIDENTIFIER`), `conversation_id` REFERENCES `Conversations(id)` ON DELETE CASCADE, `sender_type` (`NVARCHAR(50)`), `agent_id` (`NVARCHAR(100)`, NULL), `content` (`NVARCHAR(MAX)`), `metadata_json` (`NVARCHAR(MAX)`, NULL), `created_at` (`DATETIME2`).

### 3.5 `WorkflowRuns`, `WorkflowEvents` & `WorkflowCheckpoints`
- **`WorkflowRuns`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `status` (`NVARCHAR(50)`), `current_phase` (`NVARCHAR(100)`), `iteration_count` (`INT`), `created_at` (`DATETIME2`), `completed_at` (`DATETIME2`, NULL).
- **`WorkflowEvents`**: `id` (`BIGINT IDENTITY(1,1)` / `INTEGER AUTOINCREMENT` for SQLite), `workflow_run_id` REFERENCES `WorkflowRuns(id)`, `event_type` (`NVARCHAR(100)`), `event_payload` (`NVARCHAR(MAX)`), `created_at` (`DATETIME2`). Note: sensitive keys and credentials must be redacted before persistence.
- **`WorkflowCheckpoints`**: `id` (`UNIQUEIDENTIFIER`), `workflow_run_id` REFERENCES `WorkflowRuns(id)`, `checkpoint_key` (`NVARCHAR(200)`), `state_data` (`NVARCHAR(MAX)`), `version` (`INT`), `created_at` (`DATETIME2`).
  - *Unique Constraint*: `uq_run_checkpoint_version` (`workflow_run_id`, `checkpoint_key`, `version`).
  - *Checkpoint Architecture Note*: This table persists application-level workflow state checkpoints and milestone metadata. LangGraph's internal low-level execution state uses LangGraph's dedicated persistent checkpointer (`SqliteSaver`). Sensitive state values must be sanitized prior to durable checkpointing.

### 3.6 `HumanApprovals`
- **Purpose**: Records human-in-the-loop decisions (specs approval, release promotion).
- **Primary Key**: `id` (`UNIQUEIDENTIFIER`)
- **Foreign Keys**: `workflow_run_id` REFERENCES `WorkflowRuns(id)`
- **Columns**: `gate_type` (`NVARCHAR(100)`: "SPECIFICATION_APPROVAL", "RELEASE_PROMOTION"), `status` (`NVARCHAR(50)`), `prompt_text` (`NVARCHAR(MAX)`), `reviewer_comments` (`NVARCHAR(MAX)`, NULL), `requested_at` (`DATETIME2`), `resolved_at` (`DATETIME2`, NULL).

### 3.7 `AgentTasks`, `AgentExecutions`, `LLMInvocations` & `TokenUsage`
- **`AgentTasks`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `agent_name` (`NVARCHAR(100)`), `task_type` (`NVARCHAR(100)`), `status` (`NVARCHAR(50)`).
- **`AgentExecutions`**: `id` (`UNIQUEIDENTIFIER`), `agent_task_id` REFERENCES `AgentTasks(id)`, `status` (`NVARCHAR(50)`), `started_at` (`DATETIME2`), `finished_at` (`DATETIME2`).
- **`LLMInvocations`**: `id` (`UNIQUEIDENTIFIER`), `agent_execution_id` REFERENCES `AgentExecutions(id)`, `provider` (`NVARCHAR(50)`), `model_name` (`NVARCHAR(100)`), `latency_ms` (`INT`), `success` (`BIT`), `error_message` (`NVARCHAR(MAX)`, NULL), `invoked_at` (`DATETIME2`).
- **`TokenUsage`**: `id` (`UNIQUEIDENTIFIER`), `llm_invocation_id` REFERENCES `LLMInvocations(id)` ON DELETE CASCADE, `prompt_tokens` (`INT`), `completion_tokens` (`INT`), `total_tokens` (`INT`), `estimated_cost_usd` (`DECIMAL(10,6)`, default 0.0).

### 3.8 `ToolExecutions`
- **Purpose**: Audit trail of tool/sandbox calls (file creation, git execution, docker runs).
- **Primary Key**: `id` (`UNIQUEIDENTIFIER`), `agent_execution_id` REFERENCES `AgentExecutions(id)`, `tool_name` (`NVARCHAR(100)`), `input_arguments` (`NVARCHAR(MAX)`), `output_result` (`NVARCHAR(MAX)`), `exit_code` (`INT`), `executed_at` (`DATETIME2`). Note: tool inputs and outputs must pass through sensitive parameter redaction prior to database write.

### 3.9 `GitRepositories`, `GitBranches`, `GitCommits` & `GitReleaseManifests`
- **`GitRepositories`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `repo_type` (`NVARCHAR(50)`: "MOCK_VENDOR_API", "CHANNEL_APP"), `local_path` (`NVARCHAR(1000)`), `created_at` (`DATETIME2`).
- **`GitReleaseManifests`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `release_tag` (`NVARCHAR(100)`), `channel_commit_hash` (`CHAR(40)`), `mock_commit_hash` (`CHAR(40)`, NULL), `test_run_id` (`UNIQUEIDENTIFIER`, NULL), `security_scan_id` (`UNIQUEIDENTIFIER`, NULL), `created_at` (`DATETIME2`). Note: `mock_commit_hash` is NULL if Agent 2 was disabled.

### 3.10 `TestCases`, `TestRuns`, `TestResults` & `Defects`
- **`TestCases`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `test_key` (`NVARCHAR(100)`), `category` (`NVARCHAR(50)`), `endpoint` (`NVARCHAR(500)`), `http_method` (`VARCHAR(10)`), `expected_status` (`INT`).
- **`TestRuns`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `execution_type` (`NVARCHAR(50)`), `passed_count` (`INT`), `failed_count` (`INT`), `status` (`NVARCHAR(50)`: "PASSED", "FAILED", "SKIPPED"), `executed_at` (`DATETIME2`).
- **`TestResults`**: `id` (`UNIQUEIDENTIFIER`), `test_run_id` REFERENCES `TestRuns(id)` ON DELETE CASCADE, `test_case_id` (`UNIQUEIDENTIFIER`), `status` (`NVARCHAR(50)`), `actual_status_code` (`INT`), `response_body` (`NVARCHAR(MAX)`, NULL).
- **`Defects`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `assigned_agent` (`NVARCHAR(100)`), `severity` (`NVARCHAR(50)`), `description` (`NVARCHAR(MAX)`), `status` (`NVARCHAR(50)`).

### 3.11 `SecurityScans` & `SecurityFindings`
- **`SecurityScans`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `scanner_type` (`NVARCHAR(100)`), `status` (`NVARCHAR(50)`: "PASSED", "FAILED", "NOT_SCANNED"), `scanned_at` (`DATETIME2`).
- **`SecurityFindings`**: `id` (`UNIQUEIDENTIFIER`), `security_scan_id` REFERENCES `SecurityScans(id)` ON DELETE CASCADE, `severity` (`NVARCHAR(50)`), `vulnerability_type` (`NVARCHAR(100)`), `target_repo` (`NVARCHAR(50)`), `file_path` (`NVARCHAR(1000)`), `line_number` (`INT`, NULL), `description` (`NVARCHAR(MAX)`), `remediation_advice` (`NVARCHAR(MAX)`), `status` (`NVARCHAR(50)`).
