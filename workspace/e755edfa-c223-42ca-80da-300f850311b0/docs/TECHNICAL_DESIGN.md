# Technical Design Document: Student Registration System (SRS)

**Project:** Student Registration System (SRS)  
**Stack:** DOTNET_CSHARP (ASP.NET Core Web API, EF Core, SQLite)  
**Version:** 1.0.0  
**Status:** Production-Grade Specification

---

## 1. System Architecture & Component Design

The system follows a clean, layered architecture to ensure separation of concerns, testability, and maintainability.

### 1.1 Layered Structure
*   **API Layer (Controllers):** Handles HTTP request routing, model validation, and mapping to DTOs. Uses `ProblemDetails` for error reporting.
*   **Service Layer (Business Logic):** Orchestrates domain logic, performs validation, and interacts with the repository.
*   **Data Access Layer (Repository/EF Core):** Manages SQLite persistence using the Repository pattern and Unit of Work.
*   **Dependency Injection (DI):** All services and repositories are registered in `Program.cs` with scoped lifetimes.

### 1.2 Async Flow
All I/O-bound operations (database access, logging) are implemented using `async/await` to ensure non-blocking execution, maximizing throughput under load.

---

## 2. Database Design & Domain Model

### 2.1 Entity: Student
*   `Id` (Guid, Primary Key)
*   `FullName` (string, Required, MaxLength 200)
*   `Email` (string, Required, Unique Index, Case-Insensitive)
*   `DateOfBirth` (DateTime, Required)
*   `RegistrationDate` (DateTime, UTC, Required)
*   `CreatedBy` (string, Required, Immutable)
*   `LastModifiedAt` (DateTime?, Nullable)
*   `LastModifiedBy` (string?, Nullable)

### 2.2 SQLite Constraints & Migrations
*   **Unique Index:** `CREATE UNIQUE INDEX IX_Students_Email ON Students(LOWER(Email));`
*   **Atomic Persistence:** EF Core `SaveChangesAsync()` is wrapped in an implicit transaction.

---

## 3. API Specifications

### 3.1 Endpoint: `POST /api/students`
*   **Request DTO:** `StudentRegistrationRequest` (FullName, Email, DateOfBirth)
*   **Response DTO:** `StudentResponse` (Id, FullName, Email, RegistrationDate)
*   **Constraints:** 16KB request body limit enforced via `[RequestSizeLimit(16384)]`.

### 3.2 HTTP Status Codes & RFC 9457
*   **201 Created:** Successful registration.
*   **400 Bad Request:** Validation failure.
*   **401 Unauthorized:** Missing/Invalid JWT.
*   **403 Forbidden:** Insufficient claims (missing `student:create`).
*   **409 Conflict:** Email already exists.
*   **413 Payload Too Large:** Exceeds 16KB.
*   **415 Unsupported Media Type:** Non-JSON content.
*   **429 Too Many Requests:** Rate limit exceeded.
*   **500 Internal Server Error:** Unhandled exception.
*   **503 Service Unavailable:** Database connection failure.

---

## 4. Authentication & Authorization

*   **Mechanism:** JWT Bearer Authentication.
*   **Validation:** `Issuer`, `Audience`, and `Lifetime` are validated via `JwtBearerOptions`.
*   **Authorization:** Policy-based authorization requiring the `student:create` claim.
*   **Identity Extraction:** The `CreatedBy` field is populated by extracting the `sub` (Subject) claim from the `ClaimsPrincipal` of the authenticated user.

---

## 5. Audit Field Lifecycle

*   **CreatedBy:** Set once during entity creation; marked as immutable in the service layer.
*   **RegistrationDate:** Set to `DateTime.UtcNow` upon record creation.
*   **Update Fields:** `LastModifiedAt` and `LastModifiedBy` are updated only during `PUT/PATCH` operations.

---

## 6. Production Readiness

*   **Rate Limiting:** `Microsoft.AspNetCore.RateLimiting` middleware configured for 100 requests per minute per IP.
*   **Logging:** Structured logging via Serilog, including `TraceId` and `CorrelationId` in every log entry.
*   **Health Checks:** `/health` endpoint returning `200 OK` for liveness and readiness probes (checking SQLite connectivity).
*   **Observability:** Middleware to inject `X-Trace-Id` into response headers.

---

## 7. Git Workflow & Branching

*   **Main Branch:** Production-ready code.
*   **Develop Branch:** Integration branch for features.
*   **Feature Branches:** `feature/SRS-[ID]-[Description]` format.
*   **Pull Requests:** Mandatory peer review and CI/CD pipeline pass (Build, Test, Lint) required for merging.

---

## 8. Requirement Traceability Matrix

| Req ID | Description | Implementation |
| :--- | :--- | :--- |
| REQ-01 | Student Registration | `POST /api/students` |
| REQ-02 | Email Uniqueness | SQLite Unique Index (LOWER) |
| REQ-03 | Audit Tracking | `CreatedBy` / `LastModifiedAt` |
| REQ-04 | Security | JWT + `student:create` claim |
| REQ-05 | Production Limits | 16KB limit + Rate Limiting |

---
*End of Document*