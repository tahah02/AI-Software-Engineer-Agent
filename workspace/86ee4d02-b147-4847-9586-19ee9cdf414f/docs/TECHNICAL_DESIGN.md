# Technical Design Document: Student Registration System (SRS v2.0)

**Status:** Proposed Baseline (Requires Human Approval)  
**Stack:** ASP.NET Core 8, C#, EF Core, SQLite  
**Version:** 2.0

---

## 1. System Architecture & Component Design
The system follows a strict layered architecture to ensure separation of concerns and testability.

*   **StudentsController:** Handles HTTP routing, model binding, and request validation. It delegates business logic to the `IStudentService`.
*   **IStudentService / StudentService:** Orchestrates the registration process, including normalization, duplicate checking, audit field assignment, and repository interaction.
*   **IStudentRepository / StudentRepository:** Manages data access via EF Core, abstracting SQLite-specific operations.
*   **AppDbContext:** Defines the EF Core model, including unique constraints, check constraints, and migration configuration.
*   **Dependency Injection (DI):** All components are registered in `Program.cs` with scoped lifetimes for services and repositories, and a singleton `TimeProvider` for deterministic testing.

## 2. Database Design & Domain Model
The `Student` entity is mapped to a SQLite table with the following schema:

| Field | Type | Constraints |
| :--- | :--- | :--- |
| Id | int | PRIMARY KEY AUTOINCREMENT |
| FullName | string | NOT NULL, CHECK(length(FullName) >= 2 AND length(FullName) <= 100) |
| Email | string | NOT NULL, UNIQUE (UX_Students_Email) |
| Age | int | NOT NULL, CHECK(Age >= 1 AND Age <= 120) |
| Department | string | NOT NULL, CHECK(length(Department) >= 2 AND length(Department) <= 100) |
| EnrollmentDate | DateTime | NOT NULL (UTC) |
| CreatedAt | DateTime | NOT NULL (UTC) |
| CreatedBy | string | NOT NULL, max 128 chars |
| UpdatedAt | DateTime? | NULL |
| UpdatedBy | string? | NULL |

**Persistence Strategy:** Atomic `SaveChangesAsync` call. Email normalization (trim + `ToLowerInvariant`) is performed in the service layer before the repository check.

## 3. API Specifications
*   **Endpoint:** `POST /api/students`
*   **Request DTO:** `FullName`, `Email`, `Age`, `Department`.
*   **Constraints:** Max body size 16,384 bytes. Unknown properties trigger 400 Bad Request.
*   **Error Handling:** All non-2xx responses return `application/problem+json` (RFC 9457) containing `type`, `title`, `status`, `detail`, and `traceId`.

### HTTP Status Codes
*   **201:** Created. Returns Location header `/api/students/{id}`.
*   **400:** Validation errors (field-specific) or malformed JSON.
*   **401:** Missing/Invalid JWT.
*   **403:** Missing `student:create` permission.
*   **409:** Duplicate email (normalized).
*   **413:** Payload > 16 KiB.
*   **415:** Unsupported Media Type.
*   **429:** Rate limit exceeded (20 req/60s).
*   **500/503:** Internal error or DB unavailability.

## 4. Authentication & Authorization
*   **Mechanism:** JWT Bearer authentication.
*   **Policy:** `student:create` permission required via `permissions` claim.
*   **Identity:** `CreatedBy` is extracted from the `sub` claim of the JWT. If `sub` is missing or blank, the request is rejected with 401.

## 5. Audit Field Lifecycle
*   **Timestamping:** A single `TimeProvider.GetUtcNow()` value is assigned to both `EnrollmentDate` and `CreatedAt` at the moment of processing.
*   **Immutability:** `CreatedBy` is set once from the authenticated `sub`.
*   **Nullability:** `UpdatedAt` and `UpdatedBy` are explicitly initialized to `null`.

## 6. Production Readiness
*   **Rate Limiting:** Fixed window (20 requests/60 seconds) using `Microsoft.AspNetCore.RateLimiting`.
*   **Observability:** `ILogger` with structured JSON formatting. `TraceId` is propagated through logs and Problem Details.
*   **Health Check:** `/health` endpoint verifies database connectivity via `DbContext.Database.CanConnectAsync()`.

## 7. Git Workflow & Branching
*   **Main Branch:** Protected.
*   **Feature Branch:** `feature/student-registration`.
*   **PR Requirements:** Approved SRS/TDD, successful CI build, passing xUnit test suite, and security review.
*   **Exclusions:** Never commit `appsettings.Development.json` containing secrets or the SQLite database file.

## 8. Requirement Traceability Matrix

| Requirement | Design Section | Test ID |
| :--- | :--- | :--- |
| FR-01 / FR-05 | 2, 4, 7 | UT-01, IT-01, IT-07 |
| FR-02 | 3 | IT-07–IT-11, EXT-07 |
| FR-03 | 3, 5 | UT-07–UT-10, IT-08–IT-10 |
| FR-04 | 4 | UT-02–UT-05, UT-10, UT-12, IT-03, IT-14 |
| FR-06 | 3, 4 | UT-06, IT-02, IT-06 |
| FR-07 | 4 | IT-03, IT-12, IT-14, EXT-05, EXT-06 |
| FR-08 | 5 | IT-04, IT-05, IT-09, EXT-02, EXT-09 |
| FR-09 | 6, 9 | EXT-08, EXT-11 |
| NFR-01 | 4, 5, 6 | IT-04–IT-06, IT-13, EXT-01–EXT-06 |
| NFR-02 | 6 | EXT-12 |
| NFR-03 | 3, 6 | IT-06, IT-11, IT-12, EXT-11 |
| NFR-04 | 6 | Observability Review |
| NFR-05 | 7, 8 | Architecture Review |
| NFR-06 | 6, 9 | README/Smoke Test |
| NFR-07 | 8, 9 | CI Pipeline Evidence |

---

# xUnit Testing Specification (Summary of Mandate)

All tests must be implemented using `WebApplicationFactory<Program>` for integration tests and mocked dependencies for unit tests.

*   **UT-01 to UT-12:** Focus on service logic, validation rules, and audit field assignment using `TimeProvider` injection.
*   **IT-01 to IT-14:** Focus on HTTP pipeline, database persistence, concurrency, and security middleware.
*   **EXT-01 to EXT-12:** Focus on edge cases (payload size, malformed JSON, boundary values, and performance benchmarks).

*Note: All tests must be executed in the `Release` configuration. Evidence of test execution (TRX files) is required for the Definition of Done.*