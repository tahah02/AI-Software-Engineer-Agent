# XUNIT TEST SPECIFICATION DOCUMENT: AAISE 2+2+1 CALCULATION ENGINE & API BASELINE

**Document Reference:** `docs/XUNIT_TEST_SPEC.md`  
**System Scope:** AAISE 2+2+1 Calculation Engine, Persistence Domain, & Downstream Mock Integration  
**Target Framework:** .NET 8.0 SDK / C# 12 / xUnit 2.8+ / FluentAssertions / Microsoft.AspNetCore.Mvc.Testing  
**Document Status:** Pending Human Approval (Revision 3.1.0)  
**Revision:** 3.1.0  

---

## 1. Document Overview & Traceability Matrix

This document defines the complete xUnit test specification for the system. It covers unit testing (Moq/In-Memory context isolation) and integration testing (in-process `WebApplicationFactory` with real SQLite database persistence and HTTP mock server integration).

### 1.1 Requirements Traceability Matrix

| Requirement ID | Requirement Description | Test Case Mapping | Test Type |
| :--- | :--- | :--- | :--- |
| **FR-01** | Student / Payload Entity Creation | UT-01, UT-06, UT-07, IT-01, IT-10 | Unit / Integration |
| **FR-02** | Mandatory Field Validation | UT-02, IT-04, IT-09 | Unit / Integration |
| **FR-03** | Range & Numerical Constraints | UT-03 | Unit |
| **FR-04** | Email Format Validation | UT-04 | Unit |
| **FR-05** | Text Length Constraints | UT-05 | Unit |
| **FR-06** | UTC Timestamp Persistence | UT-06 | Unit |
| **FR-07** | Authenticated User Identity Audit | UT-07, IT-12 | Unit / Integration |
| **FR-08** | Nullable Audit Fields Initialization | UT-08 | Unit |
| **FR-09** | Read-Only Audit & ID Protection | UT-09 | Unit |
| **FR-10** | Uniqueness Constraint & Conflict Handling | UT-10, IT-08, IT-13 | Unit / Integration |
| **NFR-01** | High Reliability & Error Handling | UT-11, IT-04, IT-09 | Unit / Integration |
| **NFR-02** | String Sanitization & Data Normalization | UT-12 | Unit |
| **NFR-03** | Authentication Infrastructure | IT-02 | Integration |
| **NFR-04** | Authorization & Permission Enforcement | IT-03 | Integration |
| **NFR-05** | Request Size Limitation | IT-05 | Integration |
| **NFR-06** | Content-Type & Media Type Strictness | IT-06 | Integration |
| **NFR-07** | Rate Limiting & Throttling | IT-07 | Integration |
| **NFR-08** | Data Persistence & Transactional Atomicity | IT-10, IT-11, IT-13, IT-14 | Integration |

---

## 2. Test Architecture & Execution Environment

### 2.1 Test Framework Configuration
* **Test Runner:** `xUnit v2.8.0+`
* **Assertion Engine:** `FluentAssertions v6.12.0+`
* **Mocking Framework:** `Moq v4.20.0+`
* **Integration Driver:** `Microsoft.AspNetCore.Mvc.Testing v8.0.0`
* **Database Driver:** `Microsoft.EntityFrameworkCore.Sqlite v8.0.0`

### 2.2 Execution Command
All unit and integration tests are executed via the standard .NET CLI command in Release configuration:

```bash
dotnet test --configuration Release
```

---

## 3. Unit Test Specifications (UT-01 through UT-12)

### UT-01: Valid Registration - Verify Entity Created with Correct Audit Fields and Persistence

* **Test ID & Name:** `UT-01_ValidRegistration_CreatesEntityWithAuditFields`
* **Preconditions & Mock Configuration:**
  * Mock `ICalculationRepository` initialized. Setup `AddAsync` to return the saved entity with assigned Identity ID `101`.
  * Mock `IUserContext` configured to return `user-guid-001` for the authenticated identity.
* **Input Payload / Test Data:**
  ```json
  {
    "fullName": "Alice Smith",
    "email": "alice.smith@example.com",
    "age": 22,
    "department": "Computer Science",
    "enrollmentDate": "2024-09-01T00:00:00Z"
  }
  ```
* **Execution Steps:**
  1. Instantiate `StudentService` passing mocked repository and user context dependencies.
  2. Invoke `CreateStudentAsync(dto)`.
  3. Capture the returned domain result.
* **Expected Result & Exact Assertions:**
  * Result is non-null.
  * `result.Id` equals `101`.
  * `result.FullName` equals `"Alice Smith"`.
  * `result.Email` equals `"alice.smith@example.com"`.
  * `result.CreatedAt` is within 2 seconds of `DateTime.UtcNow`.
  * `result.CreatedBy` equals `"user-guid-001"`.
  * Direct assertion:
    ```csharp
    result.Should().NotBeNull();
    result.Id.Should().Be(101);
    result.CreatedBy.Should().Be("user-guid-001");
    result.CreatedAt.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(2));
    ```
* **Database State Verification:**
  * Verify `ICalculationRepository.AddAsync` was invoked exactly once (`Times.Once()`) with an entity matching `Email == "alice.smith@example.com"`.

---

### UT-02: Missing Required Fields - Verify Validation Fails for Missing Fields

* **Test ID & Name:** `UT-02_MissingRequiredFields_ThrowsValidationException`
* **Preconditions & Mock Configuration:**
  * Inject standard `StudentValidator` (using FluentValidation / DataAnnotations).
* **Input Payload / Test Data:**
  ```json
  {
    "fullName": "",
    "email": null,
    "age": 0,
    "department": null,
    "enrollmentDate": "0001-01-01T00:00:00Z"
  }
  ```
* **Execution Steps:**
  1. Instantiate `StudentValidator`.
  2. Perform validation `validator.Validate(dto)`.
* **Expected Result & Exact Assertions:**
  * Validation result `IsValid` is `false`.
  * Errors contain failures for `FullName`, `Email`, `Age`, `Department`, and `EnrollmentDate`.
  * Direct assertion:
    ```csharp
    result.IsValid.Should().BeFalse();
    result.Errors.Should().Contain(e => e.PropertyName == "FullName");
    result.Errors.Should().Contain(e => e.PropertyName == "Email");
    result.Errors.Should().Contain(e => e.PropertyName == "Age");
    result.Errors.Should().Contain(e => e.PropertyName == "Department");
    ```
* **Database State Verification:**
  * Repository `AddAsync` must NEVER be called (`Times.Never()`).

---

### UT-03: Age Validation - Verify Validation Fails for Age < 16 or Age > 100

* **Test ID & Name:** `UT-03_AgeOutOfRange_TriggersValidationError`
* **Preconditions & Mock Configuration:**
  * Setup parameterized unit test Theory (`[Theory]`) with boundaries: `15`, `101`, `0`, `-5`.
* **Input Payload / Test Data:**
  * Test Case A: `Age = 15`
  * Test Case B: `Age = 101`
* **Execution Steps:**
  1. Construct `StudentRegistrationDto` with boundary `Age`.
  2. Invoke validator.
* **Expected Result & Exact Assertions:**
  * `result.IsValid` is `false`.
  * Failure message contains `"Age must be between 16 and 100"`.
  * Direct assertion:
    ```csharp
    result.Errors.Should().Contain(e => e.PropertyName == "Age" && e.ErrorMessage.Contains("16 and 100"));
    ```
* **Database State Verification:**
  * Zero repository interaction.

---

### UT-04: Invalid Email Format - Verify Validation Fails for Invalid Email Syntax

* **Test ID & Name:** `UT-04_InvalidEmailFormat_FailsValidation`
* **Preconditions & Mock Configuration:**
  * Validator initialized.
* **Input Payload / Test Data:**
  * Inputs: `"plainaddress"`, `"@missinguser.com"`, `"user@.com"`, `"user@domain..com"`
* **Execution Steps:**
  1. Iterate through invalid email format strings.
  2. Execute validation for each DTO instance.
* **Expected Result & Exact Assertions:**
  * Validation fails for all invalid strings.
  * Direct assertion:
    ```csharp
    result.IsValid.Should().BeFalse();
    result.Errors.Should().Contain(e => e.PropertyName == "Email");
    ```
* **Database State Verification:**
  * No database context calls initiated.

---

### UT-05: Department Validation - Verify Validation Fails for Department > 100 Characters

* **Test ID & Name:** `UT-05_DepartmentExceedsMaxLength_FailsValidation`
* **Preconditions & Mock Configuration:**
  * Standard validator setup.
* **Input Payload / Test Data:**
  * `Department` = new string('A', 101) (101 characters).
* **Execution Steps:**
  1. Build DTO with 101-character string for `Department`.
  2. Execute validation.
* **Expected Result & Exact Assertions:**
  * `result.IsValid` is `false`.
  * Error registered for `Department` property regarding max length.
  * Direct assertion:
    ```csharp
    result.Errors.Should().Contain(e => e.PropertyName == "Department" && e.ErrorMessage.Contains("100"));
    ```
* **Database State Verification:**
  * Repository uninvoked.

---

### UT-06: UTC Timestamp Verification - Verify CreatedAt and EnrollmentDate Set to UTC

* **Test ID & Name:** `UT-06_Timestamps_MustBeUtc`
* **Preconditions & Mock Configuration:**
  * Mock repository returning saved entity.
* **Input Payload / Test Data:**
  * `EnrollmentDate` = `"2024-09-01T08:00:00+02:00"` (Local offset).
* **Execution Steps:**
  1. Invoke service registration with local time offset input.
  2. Inspect domain entity passed to repository `AddAsync`.
* **Expected Result & Exact Assertions:**
  * `entity.EnrollmentDate.Kind` equals `DateTimeKind.Utc`.
  * `entity.CreatedAt.Kind` equals `DateTimeKind.Utc`.
  * Direct assertion:
    ```csharp
    entity.EnrollmentDate.Kind.Should().Be(DateTimeKind.Utc);
    entity.CreatedAt.Kind.Should().Be(DateTimeKind.Utc);
    ```
* **Database State Verification:**
  * Entity passed to DB layer possesses strict UTC metadata.

---

### UT-07: CreatedBy User Identity - Verify CreatedBy Mapped from Authenticated Identity

* **Test ID & Name:** `UT-07_CreatedBy_MappedFromUserIdentity`
* **Preconditions & Mock Configuration:**
  * Mock `IUserContext` configured to return subject claim `"auth0|987654321"`.
* **Input Payload / Test Data:**
  * Valid student registration DTO.
* **Execution Steps:**
  1. Execute service method `CreateStudentAsync`.
* **Expected Result & Exact Assertions:**
  * Created record `CreatedBy` field strictly matches `"auth0|987654321"`.
  * Direct assertion:
    ```csharp
    capturedEntity.CreatedBy.Should().Be("auth0|987654321");
    ```
* **Database State Verification:**
  * DB entity captured in Moq verification retains exact identity string.

---

### UT-08: Nullable Audit Fields - Verify UpdatedAt and UpdatedBy Initialized as Null

* **Test ID & Name:** `UT-08_NullableAuditFields_DefaultToNullOnCreation`
* **Preconditions & Mock Configuration:**
  * Standard service setup.
* **Input Payload / Test Data:**
  * Valid creation request payload.
* **Execution Steps:**
  1. Execute creation pipeline.
  2. Retrieve instantiated entity before database commit.
* **Expected Result & Exact Assertions:**
  * `entity.UpdatedAt` is `null`.
  * `entity.UpdatedBy` is `null`.
  * Direct assertion:
    ```csharp
    entity.UpdatedAt.Should().BeNull();
    entity.UpdatedBy.Should().BeNull();
    ```
* **Database State Verification:**
  * DB persistence call verifies null values for update metadata.

---

### UT-09: Client Audit Injection - Verify Client-Supplied Id or Audit Fields Ignored/Rejected

* **Test ID & Name:** `UT-09_ClientAuditInjection_IgnoredOrOverwritten`
* **Preconditions & Mock Configuration:**
  * Mock identity returns `"system-auth-user"`.
* **Input Payload / Test Data:**
  * Request attempting to inject custom values:
    * `Id` = `99999`
    * `CreatedAt` = `2000-01-01T00:00:00Z`
    * `CreatedBy` = `"hacker-user"`
* **Execution Steps:**
  1. Pass DTO containing malicious audit overrides to service creation logic.
* **Expected Result & Exact Assertions:**
  * Returned record ID assigned by DB sequence (not `99999`).
  * `CreatedBy` is `"system-auth-user"`, completely overwriting `"hacker-user"`.
  * `CreatedAt` set to current UTC timestamp.
  * Direct assertion:
    ```csharp
    record.Id.Should().NotBe(99999);
    record.CreatedBy.Should().Be("system-auth-user");
    record.CreatedAt.Should().BeAfter(DateTime.UtcNow.AddMinutes(-1));
    ```
* **Database State Verification:**
  * Repository receives sanitized entity with backend-managed timestamps and user context.

---

### UT-10: Duplicate Email Conflict - Verify Duplicate Email Throws Conflict Exception

* **Test ID & Name:** `UT-10_DuplicateEmail_ThrowsConflictException`
* **Preconditions & Mock Configuration:**
  * Repository setup to throw `DuplicateEntityException` or `DbUpdateException` when `alice@example.com` exists.
* **Input Payload / Test Data:**
  * Payload with `email` = `"alice@example.com"`.
* **Execution Steps:**
  1. Call service method with pre-existing email.
* **Expected Result & Exact Assertions:**
  * Throws `ConflictException` (or domain-specific duplicate exception).
  * Direct assertion:
    ```csharp
    var act = async () => await service.CreateStudentAsync(dto);
    await act.Should().ThrowAsync<ConflictException>()
             .WithMessage("*email already exists*");
    ```
* **Database State Verification:**
  * Underlying store transaction rolls back.

---

### UT-11: Database Exception Handling - Verify Repository/DB Exceptions Handled Gracefully

* **Test ID & Name:** `UT-11_DatabaseException_HandledGracefully`
* **Preconditions & Mock Configuration:**
  * Mock `ICalculationRepository.AddAsync` configured to throw `DbUpdateException("Database connection failure", new Exception())`.
* **Input Payload / Test Data:**
  * Standard valid DTO.
* **Execution Steps:**
  1. Execute service registration call.
* **Expected Result & Exact Assertions:**
  * Exception caught and wrapped into domain `DataAccessException` or handled without leaking raw SQL details.
  * Direct assertion:
    ```csharp
    var act = async () => await service.CreateStudentAsync(dto);
    await act.Should().ThrowAsync<DataAccessException>()
             .WithMessage("An error occurred while persisting data.");
    ```
* **Database State Verification:**
  * Database state remains uncorrupted.

---

### UT-12: String Sanitization & Email Normalization - Verify Whitespace Trimmed and Email Lowercased

* **Test ID & Name:** `UT-12_Sanitization_TrimsWhitespaceAndLowercasesEmail`
* **Preconditions & Mock Configuration:**
  * Mock repository capturing entity parameter.
* **Input Payload / Test Data:**
  ```json
  {
    "fullName": "   John Doe   ",
    "email": "   JOHN.DOE@EXAMPLE.COM   ",
    "department": "  Physics  ",
    "age": 25,
    "enrollmentDate": "2024-09-01T00:00:00Z"
  }
  ```
* **Execution Steps:**
  1. Call service creation method with padded/uppercase payload.
* **Expected Result & Exact Assertions:**
  * Entity passed to repository has sanitized strings:
    * `FullName` = `"John Doe"`
    * `Email` = `"john.doe@example.com"`
    * `Department` = `"Physics"`
  * Direct assertion:
    ```csharp
    capturedEntity.FullName.Should().Be("John Doe");
    capturedEntity.Email.Should().Be("john.doe@example.com");
    capturedEntity.Department.Should().Be("Physics");
    ```
* **Database State Verification:**
  * Sanitized strings persisted into repository state.

---

## 4. Integration Test Specifications (IT-01 through IT-14)

### IT-01: POST /api/students Returns 201 Created and Location Header for Valid Request

* **Test ID & Name:** `IT-01_PostStudent_Returns201CreatedAndLocationHeader`
* **Preconditions & Mock Configuration:**
  * `WebApplicationFactory<Program>` boots host with SQLite in-memory instance.
  * Valid JWT Bearer token attached (`Authorization: Bearer <valid_token>`).
* **Input Payload / Test Data:**
  ```json
  {
    "fullName": "Robert Johnson",
    "email": "robert.johnson@example.com",
    "age": 28,
    "department": "Mathematics",
    "enrollmentDate": "2024-09-01T00:00:00Z"
  }
  ```
* **Execution Steps:**
  1. Create HTTP POST request to `/api/students` (or `/api/calculations`).
  2. Set JSON content and Authorization headers.
  3. Send request via `HttpClient`.
* **Expected Result & Exact Assertions:**
  * Response Status Code: `201 Created`.
  * `Location` header present and formatted as `/api/students/{id}` (or `/api/calculations/{id}/sum`).
  * Body contains populated `id`.
  * Direct assertion:
    ```csharp
    response.StatusCode.Should().Be(HttpStatusCode.Created);
    response.Headers.Location.Should().NotBeNull();
    response.Headers.Location.ToString().Should().MatchRegex(@"/api/(students|calculations)/\d+");
    ```
* **Database State Verification:**
  * Query SQLite DB via EF `AppDbContext`: record exists with `email = "robert.johnson@example.com"`.

---

### IT-02: 401 Unauthorized Returned When Authorization Header is Missing

* **Test ID & Name:** `IT-02_PostStudent_MissingAuthHeader_Returns401`
* **Preconditions & Mock Configuration:**
  * Test server initialized with authentication middleware enabled.
* **Input Payload / Test Data:**
  * Valid payload, but zero HTTP Authorization headers provided.
* **Execution Steps:**
  1. Dispatch HTTP POST to `/api/students` without `Authorization` header.
* **Expected Result & Exact Assertions:**
  * Response Status Code: `401 Unauthorized`.
  * Direct assertion:
    ```csharp
    response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);
    ```
* **Database State Verification:**
  * Database state unchanged.

---

### IT-03: 403 Forbidden Returned When User Lacks student:create Permission

* **Test ID & Name:** `IT-03_PostStudent_LacksPermission_Returns403`
* **Preconditions & Mock Configuration:**
  * Test JWT token issued with scope `student:read` (lacking `student:create`).
* **Input Payload / Test Data:**
  * Valid request JSON.
* **Execution Steps:**
  1. Attach low-privilege JWT header.
  2. Execute POST to `/api/students`.
* **Expected Result & Exact Assertions:**
  * Response Status Code: `403 Forbidden`.
  * Direct assertion:
    ```csharp
    response.StatusCode.Should().Be(HttpStatusCode.Forbidden);
    ```
* **Database State Verification:**
  * No entity created.

---

### IT-04: 400 Bad Request Returned for Malformed JSON Payload

* **Test ID & Name:** `IT-04_PostStudent_MalformedJson_Returns400BadRequest`
* **Preconditions & Mock Configuration:**
  * In-process integration test client.
* **Input Payload / Test Data:**
  * Invalid JSON string: `"{ "fullName": "Bad Json", "age": }"`
* **Execution Steps:**
  1. Send POST request with raw malformed string as `application/json`.
* **Expected Result & Exact Assertions:**
  * Response Status Code: `400 Bad Request`.
  * Problem Details response includes syntax error details.
  * Direct assertion:
    ```csharp
    response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    ```
* **Database State Verification:**
  * No database interaction.

---

### IT-05: 413 Payload Too Large Returned When Request Body Exceeds 16 KB

* **Test ID & Name:** `IT-05_PostStudent_PayloadExceeds16KB_Returns413`
* **Preconditions & Mock Configuration:**
  * Server endpoint configured with Kestrel / Middleware size limit (16 KB = 16,384 bytes).
* **Input Payload / Test Data:**
  * JSON payload with oversized string field exceeding 16,384 bytes.
* **Execution Steps:**
  1. Construct 20 KB payload.
  2. Issue POST request.
* **Expected Result & Exact Assertions:**
  * Response Status Code: `413 PayloadTooLarge`.
  * Direct assertion:
    ```csharp
    response.StatusCode.Should().Be(HttpStatusCode.RequestEntityTooLarge);
    ```
* **Database State Verification:**
  * Request terminated prior to reaching pipeline controllers.

---

### IT-06: 415 Unsupported Media Type Returned for Non-JSON Content Type

* **Test ID & Name:** `IT-06_PostStudent_NonJsonContentType_Returns415`
* **Preconditions & Mock Configuration:**
  * Test web server running.
* **Input Payload / Test Data:**
  * Body: `fullName=John+Doe&age=25`
  * Header: `Content-Type: application/x-www-form-urlencoded` or `text/plain`
* **Execution Steps:**
  1. Send request with non-JSON content type header.
* **Expected Result & Exact Assertions:**
  * Response Status Code: `415 UnsupportedMediaType`.
  * Direct assertion:
    ```csharp
    response.StatusCode.Should().Be(HttpStatusCode.UnsupportedMediaType);
    ```
* **Database State Verification:**
  * DB unmodified.

---

### IT-07: 429 Too Many Requests Returned When Rate Limit Exceeded

* **Test ID & Name:** `IT-07_RateLimiting_ExceededQuota_Returns429`
* **Preconditions & Mock Configuration:**
  * Rate limiter middleware configured for 5 requests per minute per IP.
* **Input Payload / Test Data:**
  * Valid payload executed rapidly in a loop.
* **Execution Steps:**
  1. Issue 6 rapid HTTP POST requests sequentially.
* **Expected Result & Exact Assertions:**
  * Requests 1-5 return `201 Created` (or expected business response).
  * Request 6 returns `429 Too Many Requests`.
  * `Retry-After` header present.
  * Direct assertion:
    ```csharp
    responses.Last().StatusCode.Should().Be((HttpStatusCode)429);
    responses.Last().Headers.Should().ContainKey("Retry-After");
    ```
* **Database State Verification:**
  * Exactly 5 records saved in SQLite DB.

---

### IT-08: 409 Conflict Returned on Duplicate Email via SQLite Unique Constraint

* **Test ID & Name:** `IT-08_PostStudent_DuplicateEmail_Returns409Conflict`
* **Preconditions & Mock Configuration:**
  * SQLite database initialized with unique index on `CalculationRecords` / `Students` (`Email` field).
  * Record with `email = "duplicate@example.com"` pre-seeded in SQLite.
* **Input Payload / Test Data:**
  ```json
  {
    "fullName": "Duplicate User",
    "email": "duplicate@example.com",
    "age": 30,
    "department": "Biology",
    "enrollmentDate": "2024-09-01T00:00:00Z"
  }
  ```
* **Execution Steps:**
  1. Execute HTTP POST to register duplicate email payload.
* **Expected Result & Exact Assertions:**
  * Response Status Code: `409 Conflict`.
  * Problem details response payload returned.
  * Direct assertion:
    ```csharp
    response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    ```
* **Database State Verification:**
  * Database count for `duplicate@example.com` remains exactly `1`.

---

### IT-09: RFC 9457 Problem Details Format Verified on Validation Errors

* **Test ID & Name:** `IT-09_ValidationError_ReturnsRfc9457ProblemDetails`
* **Preconditions & Mock Configuration:**
  * Test server with ASP.NET Core Problem Details middleware active.
* **Input Payload / Test Data:**
  * Payload missing `fullName` and invalid `age`: `{ "email": "invalid-email" }`
* **Execution Steps:**
  1. POST invalid JSON payload.
  2. Parse HTTP response content.
* **Expected Result & Exact Assertions:**
  * Status Code: `400 Bad Request`.
  * Content-Type: `application/problem+json`.
  * JSON body contains `type`, `title`, `status`, `detail`, and `errors` dictionary.
  * Direct assertion:
    ```csharp
    response.Content.Headers.ContentType.MediaType.Should().Be("application/problem+json");
    var problem = await response.Content.ReadFromJsonAsync<ValidationProblemDetails>();
    problem.Errors.Should().ContainKey("FullName");
    problem.Errors.Should().ContainKey("Email");
    ```
* **Database State Verification:**
  * Zero records written.

---

### IT-10: SQLite Database Persistence Verified by Querying Database After 201 Created

* **Test ID & Name:** `IT-10_PostStudent_PersistsToSqliteDatabase`
* **Preconditions & Mock Configuration:**
  * In-Memory SQLite connection bound to host context (`DataSource=:memory:`).
* **Input Payload / Test Data:**
  ```json
  {
    "fullName": "Database User",
    "email": "db.user@example.com",
    "age": 24,
    "department": "Chemistry",
    "enrollmentDate": "2024-09-01T00:00:00Z"
  }
  ```
* **Execution Steps:**
  1. POST valid record to endpoint.
  2. Extract created ID from JSON response.
  3. Create isolated `DbContext` scope to query SQLite DB file/memory directly.
* **Expected Result & Exact Assertions:**
  * Record found in SQLite table `CalculationRecords` / `Students`.
  * All fields match original payload exactly.
  * Direct assertion:
    ```csharp
    using var scope = factory.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    var entity = await db.CalculationRecords.FindAsync(createdId);
    entity.Should().NotBeNull();
    entity.Email.Should().Be("db.user@example.com");
    ```
* **Database State Verification:**
  * Direct physical SQLite verification confirmed via independent `DbContext` query.

---

### IT-11: Atomicity Verification - Verify No Partial Records Inserted on Transaction Failure

* **Test ID & Name:** `IT-11_Atomicity_TransactionRollsBackOnFailure`
* **Preconditions & Mock Configuration:**
  * SQLite database with strict foreign key constraints and transactional boundary.
* **Input Payload / Test Data:**
  * Compound operation payload designed to fail halfway (e.g., secondary record insert trigger failure).
* **Execution Steps:**
  1. Initiate POST endpoint that executes multiple entity inserts within `IDbContextTransaction`.
  2. Force fault injection on secondary entity insert.
* **Expected Result & Exact Assertions:**
  * Operation fails with HTTP 500 or 409 error.
  * Transaction rolls back entirely.
  * Direct assertion:
    ```csharp
    using var scope = factory.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    var count = await db.CalculationRecords.CountAsync(x => x.Email == "atomic.test@example.com");
    count.Should().Be(0);
    ```
* **Database State Verification:**
  * Zero partial entities persisted in SQLite tables.

---

### IT-12: Audit Identity Verification - Verify CreatedBy in Database Matches JWT Sub Claim

* **Test ID & Name:** `IT-12_AuditIdentity_MatchesJwtSubClaim`
* **Preconditions & Mock Configuration:**
  * Test JWT issued with `sub: "usr_token_claim_777"`.
* **Input Payload / Test Data:**
  * Standard valid request payload.
* **Execution Steps:**
  1. Include Bearer token containing `sub: "usr_token_claim_777"`.
  2. Execute HTTP POST to endpoint.
  3. Inspect persisted database entry.
* **Expected Result & Exact Assertions:**
  * `CreatedBy` field in database table contains `"usr_token_claim_777"`.
  * Direct assertion:
    ```csharp
    var entity = await db.CalculationRecords.FirstAsync(x => x.Email == payload.Email);
    entity.CreatedBy.Should().Be("usr_token_claim_777");
    ```
* **Database State Verification:**
  * SQLite DB column `CreatedBy` holds exact identity string extracted from authentication context.

---

### IT-13: Concurrent Duplicate Registrations - Verify SQLite Unique Index Prevents Race Condition

* **Test ID & Name:** `IT-13_ConcurrentDuplicateRegistrations_PreventedBySqliteUniqueIndex`
* **Preconditions & Mock Configuration:**
  * Active SQLite DB with UNIQUE index on `Email` (or target unique constraint).
* **Input Payload / Test Data:**
  * Two identical POST request payloads with `email = "race@example.com"`.
* **Execution Steps:**
  1. Issue 10 concurrent HTTP POST requests in parallel using `Task.WhenAll`.
* **Expected Result & Exact Assertions:**
  * Exactly ONE request succeeds with HTTP `201 Created`.
  * Remaining 9 requests fail with HTTP `409 Conflict`.
  * Direct assertion:
    ```csharp
    var statusCodes = await Task.WhenAll(tasks);
    statusCodes.Count(c => c == HttpStatusCode.Created).Should().Be(1);
    statusCodes.Count(c => c == HttpStatusCode.Conflict).Should().Be(9);
    ```
* **Database State Verification:**
  * Database query confirms exactly one record exists in `CalculationRecords` with `email = "race@example.com"`.

---

### IT-14: GET /health Returns 200 OK and Healthy Status

* **Test ID & Name:** `IT-14_GetHealth_Returns200OKAndHealthyStatus`
* **Preconditions & Mock Configuration:**
  * ASP.NET Core Health Checks endpoint enabled at `/health`.
  * SQLite health check provider registered.
* **Input Payload / Test Data:**
  * `HTTP GET /health`
* **Execution Steps:**
  1. Issue HTTP GET request to `/health`.
* **Expected Result & Exact Assertions:**
  * Status Code: `200 OK`.
  * Body response equals `"Healthy"` or contains JSON `{ "status": "Healthy" }`.
  * Direct assertion:
    ```csharp
    response.StatusCode.Should().Be(HttpStatusCode.OK);
    var content = await response.Content.ReadAsStringAsync();
    content.Should().Contain("Healthy");
    ```
* **Database State Verification:**
  * SQLite connectivity health probe returns operational state.

---

## 5. Compliance & Execution Summary

1. All 26 test specifications (UT-01 through UT-12, IT-01 through IT-14) are detailed above with concrete execution steps, mock settings, exact assertions, and database state verifications.
2. The complete test suite is verified via the standard CLI command:
   ```bash
   dotnet test --configuration Release
   ```
3. Target status remains `Pending Human Approval` pending final human sign-off.