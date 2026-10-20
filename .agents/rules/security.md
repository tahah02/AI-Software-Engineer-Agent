# Antigravity Rule: Security, Sandboxing, and Governance

## Purpose
This rule defines the security policies, execution boundaries, credential handling rules, and verification standards to prevent vulnerabilities, secret leakage, and unauthorized system access.

---

## 1. Sandboxed Code Execution
1. **Zero Host Execution**: Never execute generated code, developer builds, mock servers, or test scripts directly on the host operating system.
2. **Docker Isolation**: All user-generated code must compile, run, and test inside isolated Docker containers:
   - Resource limits enforced (CPU limits, memory capped at 2GB per container).
   - Restricted network: Containers attach to isolated internal Docker bridge networks; no unauthorized external WAN access.
   - Filesystem isolation: Bind mounts must be restricted strictly to the generated project directory.
3. **Agent 4 (QA) Isolation**: Agent 4 must not have read or write access to the source code repository. Its tools allow only network-level HTTP requests and contract verification against running container ports.

---

## 2. Secrets Management & Zero Plain-Text Credentials
1. **Database Storage**:
   - Plain-text API keys, passwords, and tokens must NEVER be stored in SQL Server tables.
   - Use environment variables or encrypted secrets references (`AES-256-GCM` or platform keystore).
2. **Git Commit Scrubbing**:
   - Git commits in both generated repos and the platform repository must be verified free of API tokens, private keys, or passwords.
   - `.gitignore` must strictly ignore `.env`, `*.pem`, `*.key`, `__pycache__`, and credentials files.
3. **LLM Provider API Keys**:
   - Provider keys (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`) are loaded via environment variables or encrypted configuration at runtime.

---

## 3. Agent 5 Security Scanning Standards
Agent 5 operates as an independent, read-only auditor inspecting generated code:
1. **OWASP Top 10 Coverage**:
   - SQL Injection (detect raw string formatting in SQL statements).
   - Server-Side Request Forgery (SSRF) in outbound HTTP clients.
   - Command Injection in `subprocess` or shell invocations.
   - Path Traversal in file access operations.
   - Authentication & Authorization bypass.
   - Insecure deserialization (e.g., `pickle.loads`).
2. **Vulnerability Severity Classification**:
   - `CRITICAL`: Immediate blocker. Requires human escalation or immediate fix cycle.
   - `HIGH`: Blocks release promotion. Must be remediated in a `security/*` branch.
   - `MEDIUM` / `LOW`: Flagged in reports for developer review.

---

## 4. Prohibited System Actions
- Modifying system services or registry keys.
- Executing unauthorized PowerShell commands outside workspace boundaries.
- Connecting to production banking systems or live payment gateways.
