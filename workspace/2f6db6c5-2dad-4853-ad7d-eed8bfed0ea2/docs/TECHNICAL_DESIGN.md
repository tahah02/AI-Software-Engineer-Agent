# Technical Design Document: Student Management System (DOTNET_CSHARP)

## 1. System Architecture & Component Design
The system follows a strict N-Tier architecture utilizing the Controller-Service-Repository pattern to ensure separation of concerns and testability.

### Component Layers
*   **API Layer (Controllers):** Handles HTTP request routing, model validation, and mapping to DTOs. Uses `ProblemDetails` for error reporting.
*   **Service Layer:** Contains business logic, validation rules, and orchestration. Injected as `Scoped` services.
*   **Repository Layer:** Abstracts EF Core data access. Implements the Unit of Work pattern implicitly via `DbContext`.
*   **Dependency Injection (DI):** Configured in `Program.cs` using `builder.Services`.
    *   `DbContext`: Scoped.
    *   `IStudentService`: Scoped.
    *   `IStudentRepository`: Scoped.

### Async Flow
All I/O operations (Database, Logging) are strictly asynchronous using `Task` and `await` keywords to ensure non-blocking execution and high throughput.

---

## 2. Database Design & Domain Model
The system uses SQLite with EF Core.

### Entity: Student
*   `Id` (Guid, Primary Key)
*   `Email` (string, Required, Unique Index - normalized to lowercase)
*   `FullName` (string, Required, MaxLength 256)
*   `CreatedAt` (DateTime, UTC, Immutable)
*   `CreatedBy` (string, Required, Immutable)
*   `UpdatedAt` (DateTime, Nullable)
*   `UpdatedBy` (string, Nullable)

### Constraints & Migrations
*   **Unique Index:** `builder.Entity<Student>().HasIndex(s => s.Email).IsUnique();`
*   **Atomic Persistence:** All operations are wrapped in `SaveChangesAsync()` within the service layer to ensure transaction integrity.

---

## 3. API Specifications
### POST /api/students
*   **Request Body:** `StudentCreateDto` (Max 16KB).
*   **Response:** 201 Created (with Location header).
*   **Error Handling:** All errors return `application/problem+json` (RFC 9457).

### HTTP Status Codes
*   201: Success
*   400: Bad Request (Validation failure)
*   401: Unauthorized
*   403: Forbidden (Insufficient claims)
*   409: Conflict (Email already exists)
*   413: Payload Too Large (Exceeds 16KB)
*   415: Unsupported Media Type
*   429: Too Many Requests
*   500: Internal Server Error
*   503: Service Unavailable

---

## 4. Authentication & Authorization
*   **Mechanism:** JWT Bearer Authentication.
*   **Policy:** `RequireClaim("permission", "student:create")`.
*   **Identity Extraction:** The `CreatedBy` field is populated by extracting the `sub` or `preferred_username` claim from the `ClaimsPrincipal` injected into the service layer.

---

## 5. Audit Field Lifecycle
*   **CreatedAt:** Set to `DateTime.UtcNow` during entity instantiation.
*   **CreatedBy:** Set from `User.Identity.Name` during the initial persistence.
*   **Immutability:** EF Core `PropertyBuilder` is configured to ignore updates to `CreatedAt` and `CreatedBy` during `Update` operations.
*   **Nullable Fields:** `UpdatedAt` and `UpdatedBy` are initialized as `null` and only populated on subsequent modifications.

---

## 6. Production Readiness
*   **Rate Limiting:** Configured via `Microsoft.AspNetCore.RateLimiting` (Fixed Window: 100 requests per minute per IP).
*   **Logging:** Structured logging via Serilog, including `TraceId` in every log entry.
*   **Tracing:** `Activity.Current` used for distributed tracing.
*   **Health Endpoint:** `/health` endpoint returning 200 OK with status "Healthy" for liveness/readiness probes.

---

## 7. Git Workflow & Branching
*   **Main Branch:** Production-ready code only.
*   **Develop Branch:** Integration branch for features.
*   **Feature Branches:** `feature/JIRA-ID-description`.
*   **Pull Requests:** Mandatory peer review and CI pipeline success (Build, Test, Lint) before merging to `develop`.
*   **Conventional Commits:** `type(scope): description` (e.g., `feat(api): add student creation endpoint`).

---

## 8. Requirement Traceability Matrix

| Requirement ID | Description | Implementation Status |
| :--- | :--- | :--- |
| REQ-001 | SQLite Database Integration | Implemented |
| REQ-002 | JWT Authentication | Implemented |
| REQ-003 | 16KB Request Limit | Implemented (Middleware) |
| REQ-004 | RFC 9457 Problem Details | Implemented |
| REQ-005 | Audit Field Lifecycle | Implemented |
| REQ-006 | Rate Limiting | Implemented |
| REQ-007 | Health Check Endpoint | Implemented |