# XUnit Test Specification: Student Registration System (SRS v2.0)

**Document Version:** 2.0  
**Target Framework:** .NET 8  
**Test Framework:** xUnit  
**Execution Command:** `dotnet test --configuration Release`

---

## 1. Unit Tests (UT-01 – UT-12)
*Focus: Service logic, validation, and audit field assignment using `TimeProvider` and mocked repositories.*

### UT-01: Successful Service Creation
*   **Preconditions:** Mock `IStudentRepository` returns success; `TimeProvider` set to fixed UTC.
*   **Input:** Valid `CreateStudentRequest` object.
*   **Steps:** Invoke `StudentService.RegisterAsync`.
*   **Assertions:** Assert returned ID > 0; Assert `CreatedAt` == `EnrollmentDate` == `TimeProvider.GetUtcNow()`.

### UT-02: Missing Required Fields
*   **Preconditions:** `FluentValidation` configured.
*   **Input:** JSON with null/empty `FullName`, `Email`, `Age`, `Department`.
*   **Steps:** Validate DTO via `CreateStudentRequestValidator`.
*   **Assertions:** Assert validation failure for all missing fields.

### UT-03: Age Validation
*   **Preconditions:** None.
*   **Input:** Age = 0, Age = 121.
*   **Steps:** Validate DTO.
*   **Assertions:** Assert validation failure for out-of-bounds values.

### UT-04: Invalid Email Format
*   **Preconditions:** None.
*   **Input:** Email = "invalid-email-format".
*   **Steps:** Validate DTO.
*   **Assertions:** Assert validation failure.

### UT-05: Department Validation
*   **Preconditions:** None.
*   **Input:** Department = "A" (too short), Department = [101 chars].
*   **Steps:** Validate DTO.
*   **Assertions:** Assert validation failure.

### UT-06: UTC Timestamp Verification
*   **Preconditions:** `TimeProvider` injected with specific `DateTimeOffset`.
*   **Input:** Valid request.
*   **Steps:** Execute service registration.
*   **Assertions:** Assert `CreatedAt` and `EnrollmentDate` match the injected UTC instant.

### UT-07: CreatedBy User Identity
*   **Preconditions:** `IUserContext` returns "test-user-001".
*   **Input:** Valid request.
*   **Steps:** Execute service registration.
*   **Assertions:** Assert `CreatedBy` property equals "test-user-001".

### UT-08: Nullable Audit Fields
*   **Preconditions:** None.
*   **Input:** Valid request.
*   **Steps:** Execute service registration.
*   **Assertions:** Assert `UpdatedAt` is null and `UpdatedBy` is null.

### UT-09: Client Audit Injection
*   **Preconditions:** None.
*   **Input:** Request containing `Id`, `CreatedAt`, or `CreatedBy`.
*   **Steps:** Attempt binding/validation.
*   **Assertions:** Assert validation failure (400) due to unknown/protected properties.

### UT-10: Duplicate Email Conflict
*   **Preconditions:** Mock `IStudentRepository.ExistsByNormalizedEmailAsync` returns `true`.
*   **Input:** Valid request.
*   **Steps:** Execute service registration.
*   **Assertions:** Assert `ConflictException` (mapped to 409).

### UT-11: Database Exception Handling
*   **Preconditions:** Mock `IStudentRepository` throws `DbUpdateException`.
*   **Input:** Valid request.
*   **Steps:** Execute service registration.
*   **Assertions:** Assert service catches exception and rethrows as domain-specific "DatabaseUnavailable" exception.

### UT-12: String Sanitization & Email Normalization
*   **Preconditions:** None.
*   **Input:** `FullName` = "  Ali  ", `Email` = "ALI@Example.com".
*   **Steps:** Execute normalization logic.
*   **Assertions:** Assert `FullName` == "Ali", `Email` == "ali@example.com".

---

## 2. Integration Tests (IT-01 – IT-14)
*Focus: HTTP pipeline, SQLite persistence, and security middleware using `WebApplicationFactory`.*

### IT-01: Valid Registration (201 Created)
*   **Preconditions:** Valid JWT with `student:create` permission.
*   **Input:** Valid JSON payload.
*   **Steps:** POST to `/api/students`.
*   **Assertions:** Status 201; Location header present; Response body matches input + generated fields.

### IT-02: Missing Authorization
*   **Preconditions:** No Authorization header.
*   **Input:** Valid JSON.
*   **Steps:** POST to `/api/students`.
*   **Assertions:** Status 401.

### IT-03: Missing Permission
*   **Preconditions:** JWT present but lacks `student:create` claim.
*   **Input:** Valid JSON.
*   **Steps:** POST to `/api/students`.
*   **Assertions:** Status 403.

### IT-04: Malformed JSON
*   **Preconditions:** Valid Auth.
*   **Input:** `{ "fullName": "Ali", ` (incomplete JSON).
*   **Steps:** POST to `/api/students`.
*   **Assertions:** Status 400.

### IT-05: Payload Too Large
*   **Preconditions:** Valid Auth.
*   **Input:** JSON string > 16,384 bytes.
*   **Steps:** POST to `/api/students`.
*   **Assertions:** Status 413.

### IT-06: Unsupported Media Type
*   **Preconditions:** Valid Auth.
*   **Input:** XML payload.
*   **Steps:** POST with `Content-Type: application/xml`.
*   **Assertions:** Status 415.

### IT-07: Rate Limit Exceeded
*   **Preconditions:** Valid Auth.
*   **Input:** 21 requests within 60 seconds.
*   **Steps:** Loop POST requests.
*   **Assertions:** 21st request returns 429.

### IT-08: Duplicate Email Conflict
*   **Preconditions:** Valid Auth; Database contains email "test@example.com".
*   **Input:** Request with email "TEST@example.com".
*   **Steps:** POST to `/api/students`.
*   **Assertions:** Status 409.

### IT-09: RFC 9457 Problem Details
*   **Preconditions:** Valid Auth.
*   **Input:** Invalid `Age`.
*   **Steps:** POST to `/api/students`.
*   **Assertions:** Response `Content-Type` is `application/problem+json`; contains `type`, `title`, `status`, `detail`, `traceId`.

### IT-10: SQLite Persistence
*   **Preconditions:** Valid Auth.
*   **Input:** Valid request.
*   **Steps:** POST; then query `AppDbContext` directly.
*   **Assertions:** Record exists in SQLite with correct values.

### IT-11: Atomicity Verification
*   **Preconditions:** Valid Auth; Force DB failure during `SaveChangesAsync`.
*   **Input:** Valid request.
*   **Steps:** POST.
*   **Assertions:** Status 500/503; Database count remains unchanged.

### IT-12: Audit Identity Verification
*   **Preconditions:** JWT `sub` = "admin-123".
*   **Input:** Valid request.
*   **Steps:** POST; query DB.
*   **Assertions:** `CreatedBy` column in DB equals "admin-123".

### IT-13: Concurrent Duplicate Registrations
*   **Preconditions:** Valid Auth.
*   **Input:** 5 parallel requests with same email.
*   **Steps:** `Task.WhenAll` POST requests.
*   **Assertions:** Exactly one 201; others 409; DB contains exactly one row.

### IT-14: Health Check
*   **Preconditions:** None.
*   **Input:** GET `/health`.
*   **Steps:** Request endpoint.
*   **Assertions:** Status 200; Body indicates healthy.