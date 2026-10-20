# Database Design Specification — AAISE

## 1. Overview
The database engine for AAISE is **Microsoft SQL Server**, using the normalized database `AI_SoftwareEngineer`. It stores all project metadata, conversational history, agent tasks, token metrics, workflow checkpoints, Git references, test executions, and security audit records.

---

## 2. Entity-Relationship Overview

```
[Projects]
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
- **Columns**:
  - `name` (`NVARCHAR(200)`, NOT NULL)
  - `description` (`NVARCHAR(MAX)`, NULL)
  - `target_framework` (`NVARCHAR(100)`, NOT NULL, e.g., "fastapi", "dotnet-core", "nodejs")
  - `status` (`NVARCHAR(50)`, NOT NULL, e.g., "ACTIVE", "ARCHIVED", "ERROR")
  - `created_at` (`DATETIME2`, NOT NULL, default `SYSUTCDATETIME()`)
  - `updated_at` (`DATETIME2`, NOT NULL, default `SYSUTCDATETIME()`)
- **Indexes**: `IX_Projects_Status` (`status`), `IX_Projects_CreatedAt` (`created_at`)

### 3.2 `ProjectFiles`
- **Purpose**: Tracks uploaded requirements documents and reference files.
- **Primary Key**: `id` (`UNIQUEIDENTIFIER`)
- **Foreign Keys**: `project_id` REFERENCES `Projects(id)` ON DELETE CASCADE
- **Columns**: `file_name` (`NVARCHAR(260)`), `file_path` (`NVARCHAR(1000)`), `file_type` (`NVARCHAR(50)`), `file_size_bytes` (`BIGINT`), `created_at` (`DATETIME2`).

### 3.3 `Conversations` & `Messages`
- **Purpose**: Persistent chat interactions between users and agents.
- **`Conversations`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `title` (`NVARCHAR(200)`), `created_at` (`DATETIME2`).
- **`Messages`**: `id` (`UNIQUEIDENTIFIER`), `conversation_id` REFERENCES `Conversations(id)` ON DELETE CASCADE, `sender_type` (`NVARCHAR(50)`: "USER", "AGENT", "SYSTEM", "ORCHESTRATOR"), `agent_id` (`NVARCHAR(100)`, NULL), `content` (`NVARCHAR(MAX)`), `metadata_json` (`NVARCHAR(MAX)`, NULL), `created_at` (`DATETIME2`).

### 3.4 `WorkflowRuns`, `WorkflowEvents` & `WorkflowCheckpoints`
- **Purpose**: Orchestrator state tracking, execution event logging, and durable resumption.
- **`WorkflowRuns`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `status` (`NVARCHAR(50)`: "PENDING", "RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED"), `current_phase` (`NVARCHAR(100)`), `iteration_count` (`INT`), `created_at` (`DATETIME2`), `completed_at` (`DATETIME2`, NULL).
- **`WorkflowEvents`**: `id` (`BIGINT IDENTITY(1,1)`), `workflow_run_id` REFERENCES `WorkflowRuns(id)`, `event_type` (`NVARCHAR(100)`), `event_payload` (`NVARCHAR(MAX)`), `created_at` (`DATETIME2`).
- **`WorkflowCheckpoints`**: `id` (`UNIQUEIDENTIFIER`), `workflow_run_id` REFERENCES `WorkflowRuns(id)`, `checkpoint_key` (`NVARCHAR(200)`), `state_data` (`NVARCHAR(MAX)`), `version` (`INT`), `created_at` (`DATETIME2`).

### 3.5 `HumanApprovals`
- **Purpose**: Records human-in-the-loop decisions (specs approval, release promotion).
- **Primary Key**: `id` (`UNIQUEIDENTIFIER`)
- **Foreign Keys**: `workflow_run_id` REFERENCES `WorkflowRuns(id)`
- **Columns**: `gate_type` (`NVARCHAR(100)`: "SPECIFICATION_APPROVAL", "RELEASE_PROMOTION"), `status` (`NVARCHAR(50)`: "PENDING", "APPROVED", "REJECTED"), `prompt_text` (`NVARCHAR(MAX)`), `reviewer_comments` (`NVARCHAR(MAX)`, NULL), `requested_at` (`DATETIME2`), `resolved_at` (`DATETIME2`, NULL).

### 3.6 `AgentTasks`, `AgentExecutions`, `LLMInvocations` & `TokenUsage`
- **Purpose**: Tracks agent task scheduling, tool usage, LLM calls, and token consumption without duplication.
- **`AgentTasks`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `agent_name` (`NVARCHAR(100)`), `task_type` (`NVARCHAR(100)`), `status` (`NVARCHAR(50)`).
- **`AgentExecutions`**: `id` (`UNIQUEIDENTIFIER`), `agent_task_id` REFERENCES `AgentTasks(id)`, `status` (`NVARCHAR(50)`), `started_at` (`DATETIME2`), `finished_at` (`DATETIME2`).
- **`LLMInvocations`**: `id` (`UNIQUEIDENTIFIER`), `agent_execution_id` REFERENCES `AgentExecutions(id)`, `provider` (`NVARCHAR(50)`: "ollama", "gemini", "groq", "openrouter"), `model_name` (`NVARCHAR(100)`), `latency_ms` (`INT`), `success` (`BIT`), `error_message` (`NVARCHAR(MAX)`, NULL), `invoked_at` (`DATETIME2`).
- **`TokenUsage`**: `id` (`UNIQUEIDENTIFIER`), `llm_invocation_id` REFERENCES `LLMInvocations(id)` ON DELETE CASCADE, `prompt_tokens` (`INT`), `completion_tokens` (`INT`), `total_tokens` (`INT`), `estimated_cost_usd` (`DECIMAL(10,6)`, default 0.0).

### 3.7 `ToolExecutions`
- **Purpose**: Audit trail of tool/sandbox calls (file creation, git execution, docker runs).
- **Primary Key**: `id` (`UNIQUEIDENTIFIER`), `agent_execution_id` REFERENCES `AgentExecutions(id)`, `tool_name` (`NVARCHAR(100)`), `input_arguments` (`NVARCHAR(MAX)`), `output_result` (`NVARCHAR(MAX)`), `exit_code` (`INT`), `executed_at` (`DATETIME2`).

### 3.8 `GitRepositories`, `GitBranches`, `GitCommits` & `GitReleaseManifests`
- **Purpose**: Local Git version tracking and cross-repository synchronization.
- **`GitRepositories`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `repo_type` (`NVARCHAR(50)`: "MOCK_VENDOR_API", "CHANNEL_APP"), `local_path` (`NVARCHAR(1000)`), `created_at` (`DATETIME2`).
- **`GitReleaseManifests`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `release_tag` (`NVARCHAR(100)`), `channel_commit_hash` (`CHAR(40)`), `mock_commit_hash` (`CHAR(40)`), `test_run_id` (`UNIQUEIDENTIFIER`, NULL), `security_scan_id` (`UNIQUEIDENTIFIER`, NULL), `created_at` (`DATETIME2`).

### 3.9 `TestCases`, `TestRuns`, `TestResults` & `Defects`
- **Purpose**: Independent QA verification, test matrix storage, and bug tracking.
- **`TestCases`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `test_key` (`NVARCHAR(100)`), `category` (`NVARCHAR(50)`: "POSITIVE", "NEGATIVE", "BOUNDARY", "SECURITY"), `endpoint` (`NVARCHAR(500)`), `http_method` (`VARCHAR(10)`), `expected_status` (`INT`).
- **`TestRuns`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `execution_type` (`NVARCHAR(50)`: "DEV_UNIT", "INDEPENDENT_QA"), `passed_count` (`INT`), `failed_count` (`INT`), `executed_at` (`DATETIME2`).
- **`TestResults`**: `id` (`UNIQUEIDENTIFIER`), `test_run_id` REFERENCES `TestRuns(id)` ON DELETE CASCADE, `test_case_id` (`UNIQUEIDENTIFIER`), `status` (`NVARCHAR(50)`: "PASSED", "FAILED", "SKIPPED"), `actual_status_code` (`INT`), `response_body` (`NVARCHAR(MAX)`, NULL), `error_details` (`NVARCHAR(MAX)`, NULL).
- **`Defects`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `assigned_agent` (`NVARCHAR(100)`: "Agent 2", "Agent 3"), `severity` (`NVARCHAR(50)`), `description` (`NVARCHAR(MAX)`), `status` (`NVARCHAR(50)`: "OPEN", "IN_PROGRESS", "FIXED", "VERIFIED").

### 3.10 `SecurityScans` & `SecurityFindings`
- **Purpose**: Security auditing and vulnerability reporting.
- **`SecurityScans`**: `id` (`UNIQUEIDENTIFIER`), `project_id` REFERENCES `Projects(id)`, `scanner_type` (`NVARCHAR(100)`: "AGENT_5_AST_SAST"), `scanned_at` (`DATETIME2`).
- **`SecurityFindings`**: `id` (`UNIQUEIDENTIFIER`), `security_scan_id` REFERENCES `SecurityScans(id)` ON DELETE CASCADE, `severity` (`NVARCHAR(50)`: "CRITICAL", "HIGH", "MEDIUM", "LOW"), `vulnerability_type` (`NVARCHAR(100)`: "SQLI", "SSRF", "COMMAND_INJECTION", "SECRET_LEAK"), `target_repo` (`NVARCHAR(50)`), `file_path` (`NVARCHAR(1000)`), `line_number` (`INT`, NULL), `description` (`NVARCHAR(MAX)`), `remediation_advice` (`NVARCHAR(MAX)`), `status` (`NVARCHAR(50)`: "OPEN", "RESOLVED").
