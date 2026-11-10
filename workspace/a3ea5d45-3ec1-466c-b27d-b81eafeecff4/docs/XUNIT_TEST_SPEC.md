# XUnit Test Specification: Student Registration System (SRS v2.0)

This document defines the exhaustive test suite for the Student Registration System. All tests must be executed using: `dotnet test --configuration Release`.

---

## 1. Unit Tests (UT-01 – UT-12)
*Focus: Business logic, validation, and service orchestration.*

### UT-01: Successful Service Creation
*   **Preconditions:** Mock `IStudentRepository` returns success; `TimeProvider` set to fixed UTC.
*   **Input:** Valid `CreateStudentRequest` DTO.
*   **Execution:** Invoke `StudentService.RegisterAsync`.
*   **Assertions:** Verify returned `Student` has positive ID, `CreatedAt` == `EnrollmentDate` == `TimeProvider.GetUtcNow()`.

### UT-02: Missing Required Fields
*   **Preconditions:** `FluentValidation` configured.
*   **Input:** JSON with null/empty `FullName`, `Email`, `Age`, `Department`.
*   **Execution:** Validate DTO via `CreateStudentRequestValidator`.
*   **Assertions:** Assert `ValidationResult.IsValid` is `false`; verify error collection contains required field keys.

### UT-03: Age Validation
*   **Preconditions:** None.
*   **Input:** Age values: `0`, `1`, `120`, `121`.
*   **Execution:** Validate DTO.
*   **Assertions:** `0` and `121` return `false`; `1` and `120` return `true`.

### UT-04: Invalid Email Format
*   **Preconditions:** None.
*   **Input:** `invalid-email`, `user@`, `@domain.com`.
*   **Execution:** Validate DTO.
*   **Assertions:** `ValidationResult.IsValid` is `false`.

### UT-05: Department Validation
*   **Preconditions:** None.
*   **Input:** String length 1, 101.
*   **Execution:** Validate DTO.
*   **Assertions:** `ValidationResult.IsValid` is `false`.

### UT-06: UTC Timestamp Verification
*   **Preconditions:** `TimeProvider` injected with `DateTimeOffset(2026, 11, 6, 9, 0, 0, TimeSpan.Zero)`.
*   **Input:** Valid DTO.
*   **Execution:** Service registration.
*   **Assertions:** `CreatedAt` and `EnrollmentDate` match the injected provider value exactly.

### UT-07: CreatedBy User Identity
*   **Preconditions:** `IUserContext` returns `sub` claim "student-001".
*   **Input:** Valid DTO.
*   **Execution:** Service registration.
*   **Assertions:** `Student.CreatedBy` == "student-001".

### UT-08: Nullable Audit Fields
*   **Preconditions:** None.
*   **Input:** Valid DTO.
*   **Execution:** Service registration.
*   **Assertions:** `UpdatedAt` is `null`, `UpdatedBy` is `null`.

### UT-09: Client Audit Injection
*   **Preconditions:** None.
*   **Input:** DTO containing `Id` or `CreatedAt` fields.
*   **Execution:** Model binding/Validation.
*   **Assertions:** Reject request (400) as per "no client-supplied audit" rule.

### UT-10: Duplicate Email Conflict
*   **Preconditions:** `IStudentRepository.ExistsByNormalizedEmailAsync` returns `true`.
*   **Input:** Valid DTO.
*   **Execution:** Service registration.
*   **Assertions:** Throw `ConflictException` (mapped to 409).

### UT-11: Database Exception Handling
*   **Preconditions:** Repository throws `DbUpdateException`.
*   **Input:** Valid DTO.
*   **Execution:** Service registration.
*   **Assertions:** Catch and rethrow as `ServiceUnavailableException` (mapped to 503).

### UT-12: String Sanitization & Email Normalization
*   **Preconditions:** None.
*   **Input:** `FullName` = "  Ali  ", `Email` = "ALI@Example.com".
*   **Execution:** Service normalization logic.
*   **Assertions:** `FullName` == "Ali", `Email` == "ali@example.com".

---

## 2. Integration Tests (IT-01 – IT-14)
*Focus: API contract, HTTP pipeline, and SQLite persistence.*

### IT-01: Valid Registration (201 Created)
*   **Preconditions:** Authenticated user with `student:create` claim.
*   **Input:** Valid JSON.
*   **Execution:** `POST /api/students`.
*   **Assertions:** Status 201, `Location` header present, response body contains generated ID.

### IT-02: 401 Unauthorized
*   **Preconditions:** No `Authorization` header.
*   **Input:** Valid JSON.
*   **Execution:** `POST /api/students`.
*   **Assertions:** Status 401.

### IT-03: 403 Forbidden
*   **Preconditions:** Valid JWT, but missing `student:create` claim.
*   **Input:** Valid JSON.
*   **Execution:** `POST /api/students`.
*   **Assertions:** Status 403.

### IT-04: 400 Bad Request (Malformed JSON)
*   **Preconditions:** None.
*   **Input:** `{ "fullName": "Ali", ` (incomplete).
*   **Execution:** `POST /api/students`.
*   **Assertions:** Status 400.

### IT-05: 413 Payload Too Large
*   **Preconditions:** None.
*   **Input:** JSON body > 16,384 bytes.
*   **Execution:** `POST /api/students`.
*   **Assertions:** Status 413.

### IT-06: 415 Unsupported Media Type
*   **Preconditions:** None.
*   **Input:** Valid XML.
*   **Execution:** `POST /api/students` with `Content-Type: application/xml`.
*   **Assertions:** Status 415.

### IT-07: 429 Too Many Requests
*   **Preconditions:** Rate limit configured (20/min).
*   **Input:** 21 valid requests in < 60s.
*   **Execution:** Loop POST requests.
*   **Assertions:** 21st request returns 429.

### IT-08: 409 Conflict (Duplicate Email)
*   **Preconditions:** Database contains email "test@test.com".
*   **Input:** DTO with "test@test.com".
*   **Execution:** `POST /api/students`.
*   **Assertions:** Status 409.

### IT-09: RFC 9457 Problem Details
*   **Preconditions:** Trigger validation error.
*   **Input:** Invalid DTO.
*   **Execution:** `POST /api/students`.
*   **Assertions:** Response `Content-Type` is `application/problem+json`, contains `traceId` and `errors` object.

### IT-10: SQLite Database Persistence
*   **Preconditions:** None.
*   **Input:** Valid DTO.
*   **Execution:** `POST /api/students`.
*   **Assertions:** Query SQLite directly; verify row exists with correct fields.

### IT-11: Atomicity Verification
*   **Preconditions:** Force DB failure during `SaveChangesAsync`.
*   **Input:** Valid DTO.
*   **Execution:** `POST /api/students`.
*   **Assertions:** Verify no record exists in DB (transaction rollback).

### IT-12: Audit Identity Verification
*   **Preconditions:** JWT `sub` = "user-123".
*   **Input:** Valid DTO.
*   **Execution:** `POST /api/students`.
*   **Assertions:** DB `CreatedBy` column == "user-123".

### IT-13: Concurrent Duplicate Registrations
*   **Preconditions:** Two parallel threads.
*   **Input:** Same email.
*   **Execution:** Simultaneous POST requests.
*   **Assertions:** One 201, one 409; exactly one row in DB.

### IT-14: GET /health
*   **Preconditions:** DB reachable.
*   **Input:** `GET /health`.
*   **Execution:** Request health endpoint.
*   **Assertions:** Status 200. If DB disconnected, Status 503.