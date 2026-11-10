# Technical Design Document: Student Registration System (SRS v2.0)

**Status:** Proposed Baseline (Requires Human Approval)  
**System:** ASP.NET Core 8 Web API  
**Database:** SQLite (EF Core)  
**Date:** 06 November 2026

---

## 1. System Architecture & Component Design
The system follows a strict layered architecture to ensure separation of concerns and testability.

*   **StudentsController:** Handles HTTP routing, request binding, and authorization. It delegates business logic to the `IStudentService`. It does not contain database logic.
*   **IStudentService / StudentService:** Orchestrates the registration process. It performs normalization, invokes the `IStudentRepository`, and manages the audit field assignment using an injected `TimeProvider`.
*   **IStudentRepository / StudentRepository:** Manages data access via EF Core. It encapsulates `ExistsByNormalizedEmailAsync`, `AddAsync`, and `SaveChangesAsync`.
*   **Dependency Injection (DI):**
    *   `AddDbContext<AppDbContext>`: Configured for SQLite.
    *   `AddScoped<IStudentRepository, StudentRepository>`
    *   `AddScoped<IStudentService, StudentService>`
    *   `AddScoped<IUserContext, HttpUserContext>`: Extracts the `sub` claim from the JWT.
    *   `AddSingleton<TimeProvider>(TimeProvider.System)`: Ensures deterministic time handling.

---

## 2. Database Design & Domain Model
The `Student` entity is mapped to the `Students` table.

| Field | Type | Constraints |
| :--- | :--- | :--- |
| Id | int | PRIMARY KEY, AUTOINCREMENT |
| FullName | string | NOT NULL, 2–100 chars |
| Email | string | NOT NULL, UNIQUE, 254 chars (lowercase) |
| Age | int | NOT NULL, 1–120 |
| Department | string | NOT NULL, 2–100 chars |
| EnrollmentDate | DateTime | NOT NULL, UTC |
| CreatedAt | DateTime | NOT NULL, UTC |
| CreatedBy | string | NOT NULL, 128 chars |
| UpdatedAt | DateTime? | NULL |
| UpdatedBy | string? | NULL |

**Persistence Logic:**
*   **Normalization:** Email is trimmed and converted to `ToLowerInvariant()` before any database check.
*   **Atomic Persistence:** A single `SaveChangesAsync` call is used to ensure the record and audit fields are committed as a single transaction.
*   **Migrations:** Managed via `dotnet ef migrations add InitialCreate`.

---

## 3. API Specifications
*   **Endpoint:** `POST /api/students`
*   **Request DTO:** `FullName`, `Email`, `Age`, `Department`.
*   **Response DTO:** Includes all 10 entity fields.
*   **Constraints:**
    *   **Body Size:** Max 16,384 bytes.
    *   **Content-Type:** `application/json`.
*   **HTTP Status Codes:**
    *   `201 Created`: Success, includes `Location` header.
    *   `400 Bad Request`: Validation errors (RFC 9457).
    *   `401 Unauthorized`: Missing/invalid JWT.
    *   `403 Forbidden`: Missing `student:create` claim.
    *   `409 Conflict`: Duplicate email.
    *   `413 Payload Too Large`: > 16 KiB.
    *   `415 Unsupported Media Type`: Non-JSON.
    *   `429 Too Many Requests`: Rate limit exceeded.
    *   `500 Internal Server Error`: Unexpected failure.
    *   `503 Service Unavailable`: Database contention/failure.

---

## 4. Authentication & Authorization
*   **Mechanism:** JWT Bearer authentication.
*   **Policy:** `student:create` permission required.
*   **Identity:** The `sub` claim from the JWT is extracted via `IUserContext` and mapped to `CreatedBy`.
*   **Security:** HTTPS is mandatory. No hardcoded secrets; use environment-based configuration.

---

## 5. Audit Field Lifecycle
*   **EnrollmentDate & CreatedAt:** Assigned the same UTC timestamp at the moment of service execution.
*   **CreatedBy:** Populated from the validated JWT `sub` claim.
*   **UpdatedAt/UpdatedBy:** Explicitly set to `null` on creation.

---

## 6. Production Readiness
*   **Rate Limiting:** Fixed window, 20 requests per 60 seconds per IP.
*   **Logging:** `ILogger` with structured JSON output. Includes `traceId`, `endpoint`, `status`, and `durationMs`.
*   **Health Check:** `GET /health` returns 200 (Healthy) or 503 (Unhealthy) based on database connectivity.
*   **Observability:** All errors return RFC 9457 `ProblemDetails` with a `traceId`.

---

## 7. Git Workflow & Branching
*   **Main Branch:** Protected.
*   **Feature Branch:** `feature/student-registration`.
*   **PR Requirements:** Approved SRS, TDD, xUnit specs, successful CI build/test, and security sign-off.
*   **Exclusions:** Never commit `appsettings.json` with secrets or the SQLite database file.

---

## 8. Requirement Traceability Matrix

| Requirement | Design Section | Test ID |
| :--- | :--- | :--- |
| FR-01 / FR-05 | 3, 4 | UT-01, IT-01, IT-07 |
| FR-02 | 2 | IT-07–IT-11 |
| FR-03 | 3, 5 | UT-07–UT-10, IT-08–IT-10 |
| FR-04 | 4 | UT-02–UT-05, IT-03, IT-14 |
| FR-06 | 2, 3 | UT-06, IT-02, IT-06 |
| FR-07 | 3 | IT-03, IT-12, IT-14 |
| FR-08 | 4 | IT-04, IT-05, IT-09 |
| FR-09 | 6 | EXT-08, EXT-11 |
| NFR-01 | 4, 5, 6 | IT-04–IT-06, IT-13 |
| NFR-02 | 6 | EXT-12 |
| NFR-03 | 2, 6 | IT-06, IT-11, IT-12 |

---

# xUnit Testing Specification

## 1. Unit Tests (UT-01 – UT-12)
*   **UT-01 (Successful Creation):** Mock repository; verify Id is positive and audit fields match.
*   **UT-02 (Missing FullName):** Verify validation failure.
*   **UT-03 (Invalid Email):** Verify malformed email rejection.
*   **UT-04 (Invalid Age):** Verify 0 and 121 rejection; 1 and 120 acceptance.
*   **UT-05 (Missing Department):** Verify validation failure.
*   **UT-06 (Duplicate Email):** Verify service-level pre-check triggers conflict.
*   **UT-07 (CreatedAt UTC):** Verify `CreatedAt` == `EnrollmentDate` == `TimeProvider` clock.
*   **UT-08 (CreatedBy Identity):** Verify `CreatedBy` matches JWT `sub`.
*   **UT-09 (Nullable Audit):** Verify `UpdatedAt` and `UpdatedBy` are null.
*   **UT-10 (Protected Fields):** Verify rejection of client-supplied Id/Audit fields.
*   **UT-11 (DB Exception):** Verify 503 mapping on repository failure.
*   **UT-12 (Normalization):** Verify trim/lowercase logic.

## 2. Integration Tests (IT-01 – IT-14)
*   **IT-01 (Valid Registration):** `WebApplicationFactory` test; 201 response.
*   **IT-02 (Duplicate Email):** Verify 409 response.
*   **IT-03 (Invalid Payload):** Verify 400 field errors.
*   **IT-04 (Missing Auth):** Verify 401 response.
*   **IT-05 (Missing Permission):** Verify 403 response.
*   **IT-06 (Concurrent Duplicates):** Verify one 201, others 409.
*   **IT-07 (DB-Generated Id):** Verify server-side ID assignment.
*   **IT-08 (UTC Timestamps):** Verify DB matches response.
*   **IT-09 (CreatedBy Identity):** Verify JWT `sub` in DB.
*   **IT-10 (Null Audit):** Verify nulls in DB.
*   **IT-11 (SQLite Persistence):** Verify data persists across `DbContext` instances.
*   **IT-12 (DB Failure):** Verify 503 response.
*   **IT-13 (Rate Limit):** Verify 429 response.
*   **IT-14 (Malformed JSON):** Verify 400 response.