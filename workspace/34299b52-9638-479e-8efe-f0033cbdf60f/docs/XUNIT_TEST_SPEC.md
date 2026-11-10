# xUnit Test Specification Document

**Document Title:** xUnit Test Specification Document  
**File Path:** `docs/XUNIT_TEST_SPEC.md`  
**System Name:** AAISE Calculation & Enterprise API Platform  
**Document Version:** 1.1.0-REVISED  
**Date:** 06 November 2026  
**Status:** Pending Human Approval  
**Target Platform:** .NET 8.0 (C# 12) / xUnit 2.6+ / FluentAssertions / Moq / ASP.NET Core `TestServer` / EF Core SQLite  
**Test Execution Command:** `dotnet test --configuration Release`

---

## 1. Executive Summary & Test Strategy

### 1.1 Scope and Objective
This document defines the comprehensive xUnit testing specification for the application platform, encompassing Unit Verification (UT) and End-to-End Integration Verification (IT). The test suite guarantees strict compliance with business rules, data sanitization, schema validation, exception safety, auditability, and HTTP contract enforcement (RFC 9457 Problem Details).

### 1.2 Testing Strategy & Layered Isolation
- **Unit Tests (`Calculator.Tests/Unit/`):** Test isolated domain logic, service boundaries, data normalization, and validation rules using `Moq` or lightweight isolated implementations. No network or physical database connections occur during unit test execution.
- **Integration Tests (`Calculator.Tests/Integration/`):** Test end-to-end HTTP endpoint flows using `WebApplicationFactory<Program>`. Persistence is validated using actual SQLite file/in-memory SQLite connections (with open connection lifecycle management). The use of the EF Core `InMemory` provider is strictly prohibited to guarantee real relational integrity, foreign key checks, and unique constraint enforcement.

### 1.3 Execution Directive
All tests must compile cleanly against .NET 8.0 and pass when executed using:
```bash
dotnet test --configuration Release
```

---

## 2. Test Environment & Infrastructure Configuration

### 2.1 Technology Stack & Packages
- **Test Framework:** `xunit` (v2.6.x)
- **Test Runner:** `xunit.runner.visualstudio` (v2.5.x)
- **Assertion Library:** `FluentAssertions` (v6.12.x)
- **Mocking Framework:** `Moq` (v4.20.x)
- **Integration Harness:** `Microsoft.AspNetCore.Mvc.Testing` (v8.0.x)
- **Database Engine:** `Microsoft.Data.Sqlite` / EF Core SQLite (`Microsoft.EntityFrameworkCore.Sqlite`)

### 2.2 Integration Test Factory & SQLite Setup Pattern
Integration tests use a custom `IntegrationTestWebApplicationFactory` to boot the Web API pipeline with an isolated SQLite database connection.

```csharp
public class IntegrationTestWebApplicationFactory : WebApplicationFactory<Program>
{
    private SqliteConnection _connection;

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            // Remove existing DbContext registration
            var descriptor = services.SingleOrDefault(
                d => d.ServiceType == typeof(DbContextOptions<AppDbContext>));
            if (descriptor != null) services.Remove(descriptor);

            // Establish persistent in-memory SQLite connection for test lifetime
            _connection = new SqliteConnection("DataSource=:memory:");
            _connection.Open();

            services.AddDbContext<AppDbContext>(options =>
            {
                options.UseSqlite(_connection);
            });

            // Ensure database schema is created
            var sp = services.BuildServiceProvider();
            using var scope = sp.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            db.Database.EnsureCreated();
        });
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        _connection?.Close();
        _connection?.Dispose();
    }
}
```

---

## 3. Unit Test Specifications (UT-01 through UT-12)

### UT-01: Valid Registration - Student Record Creation & Audit Initialization
- **Test ID & Name:** `UT-01_ValidRegistration_CreatesStudentRecordWithCorrectAuditFields`
- **Preconditions & Mock Configuration:**
  - Mock `IStudentRepository` configured to accept `Student` model and return `Task.CompletedTask`.
  - Service initialized with mocked repository and `IUserContext` returning user identity `"usr_admin_01"`.
  - System clock frozen or fixed at UTC `2026-11-06T10:00:00Z`.
- **Input Payload / Test Data:**
  ```csharp
  var request = new CreateStudentRequestDto
  {
      FullName = "John Doe",
      Email = "john.doe@university.edu",
      Age = 20,
      Department = "Computer Science",
      EnrollmentDate = DateTime.SpecifyKind(new DateTime(2026, 9, 1), DateTimeKind.Utc)
  };
  ```
- **Execution Steps:**
  1. Instantiate `StudentService(mockRepo.Object, mockUserContext.Object, mockClock.Object)`.
  2. Invoke `await service.CreateStudentAsync(request)`.
  3. Capture the returned `StudentResponseDto` and inspect the domain model passed to `mockRepo.CreateAsync(It.IsAny<Student>())`.
- **Expected Result & Exact Assertions:**
  - Service method returns non-null response with generated non-empty `Id`.
  - Audit field `CreatedAtUtc` equals `2026-11-06T10:00:00Z` (`DateTimeKind.Utc`).
  - Audit field `CreatedBy` equals `"usr_admin_01"`.
  - `mockRepo.Verify(r => r.CreateAsync(It.Is<Student>(s => 
      s.FullName == "John Doe" && 
      s.Email == "john.doe@university.edu" && 
      s.CreatedBy == "usr_admin_01" && 
      s.CreatedAtUtc == new DateTime(2026, 11, 6, 10, 0, 0, DateTimeKind.Utc))), Times.Once);`
- **Database State Verification:** N/A (Unit Test - Mock Repository verified via `Times.Once`).

---

### UT-02: Missing Required Fields - Validation Failure Verification
- **Test ID & Name:** `UT-02_MissingRequiredFields_ValidationFails`
- **Preconditions & Mock Configuration:**
  - FluentValidation `CreateStudentRequestDtoValidator` instantiated.
  - No database mocks required.
- **Input Payload / Test Data:**
  ```csharp
  var request = new CreateStudentRequestDto
  {
      FullName = "",
      Email = null,
      Age = 0,
      Department = null,
      EnrollmentDate = default
  };
  ```
- **Execution Steps:**
  1. Instantiate `CreateStudentRequestDtoValidator`.
  2. Execute `var result = validator.Validate(request)`.
- **Expected Result & Exact Assertions:**
  - `result.IsValid.Should().BeFalse();`
  - `result.Errors.Should().Contain(e => e.PropertyName == "FullName" && e.ErrorMessage.Contains("required"));`
  - `result.Errors.Should().Contain(e => e.PropertyName == "Email" && e.ErrorMessage.Contains("required"));`
  - `result.Errors.Should().Contain(e => e.PropertyName == "Age");`
  - `result.Errors.Should().Contain(e => e.PropertyName == "Department");`
  - `result.Errors.Should().Contain(e => e.PropertyName == "EnrollmentDate");`
- **Database State Verification:** N/A (Validation layer test; service/database never called).

---

### UT-03: Age Validation - Boundary Limits Failure (Age < 16 or Age > 100)
- **Test ID & Name:** `UT-03_AgeValidation_FailsOutsideBoundaryLimits`
- **Preconditions & Mock Configuration:**
  - `CreateStudentRequestDtoValidator` instantiated.
- **Input Payload / Test Data:**
  - Case A (Underage): `Age = 15`
  - Case B (Overage): `Age = 101`
  - Case C (Valid Lower Bound): `Age = 16`
  - Case D (Valid Upper Bound): `Age = 100`
- **Execution Steps:**
  1. Pass each case to `validator.Validate(dto)`.
- **Expected Result & Exact Assertions:**
  - Case A (`15`): `result.IsValid.Should().BeFalse();` Error on `Age`: `"Age must be between 16 and 100."`
  - Case B (`101`): `result.IsValid.Should().BeFalse();` Error on `Age`: `"Age must be between 16 and 100."`
  - Case C (`16`): `result.Errors.Should().NotContain(e => e.PropertyName == "Age");`
  - Case D (`100`): `result.Errors.Should().NotContain(e => e.PropertyName == "Age");`
- **Database State Verification:** N/A.

---

### UT-04: Invalid Email Format - Syntax Validation Failure
- **Test ID & Name:** `UT-04_InvalidEmailFormat_FailsValidation`
- **Preconditions & Mock Configuration:**
  - Validator initialized.
- **Input Payload / Test Data:**
  - Inputs: `"plainaddress"`, `"@missinguser.com"`, `"john.doe@domain."`, `"john.doe@domain..com"`, `"john.doe@.com"`
- **Execution Steps:**
  1. Iterate over invalid email strings.
  2. Perform `validator.Validate(request)`.
- **Expected Result & Exact Assertions:**
  - For all invalid inputs:
    - `result.IsValid.Should().BeFalse();`
    - `result.Errors.Should().Contain(e => e.PropertyName == "Email" && e.ErrorMessage.Contains("valid email"));`
- **Database State Verification:** N/A.

---

### UT-05: Department Validation - Exceeding Maximum Length Limit
- **Test ID & Name:** `UT-05_DepartmentValidation_FailsWhenExceeding100Characters`
- **Preconditions & Mock Configuration:**
  - Validator initialized.
- **Input Payload / Test Data:**
  - Input: `Department = new string('A', 101)` (101 characters long).
- **Execution Steps:**
  1. Construct DTO with 101-character department string.
  2. Perform `var result = validator.Validate(request)`.
- **Expected Result & Exact Assertions:**
  - `result.IsValid.Should().BeFalse();`
  - `result.Errors.Should().Contain(e => e.PropertyName == "Department" && e.ErrorMessage.Contains("cannot exceed 100 characters"));`
- **Database State Verification:** N/A.

---

### UT-06: UTC Timestamp Verification - Ensure Utc Kind Enforcement
- **Test ID & Name:** `UT-06_UtcTimestampVerification_EnforcesUtcDateTimeKind`
- **Preconditions & Mock Configuration:**
  - Mock `IStudentRepository` setup.
  - Service configured with fixed system clock returning `DateTime.UtcNow`.
- **Input Payload / Test Data:**
  - `EnrollmentDate` supplied as Local or Unspecified DateTime: `new DateTime(2026, 9, 1, 8, 0, 0, DateTimeKind.Local)`.
- **Execution Steps:**
  1. Call `service.CreateStudentAsync(dto)`.
  2. Intercept `Student` instance passed to `repository.CreateAsync`.
- **Expected Result & Exact Assertions:**
  - `capturedStudent.CreatedAtUtc.Kind.Should().Be(DateTimeKind.Utc);`
  - `capturedStudent.EnrollmentDate.Kind.Should().Be(DateTimeKind.Utc);`
  - System correctly converts local `EnrollmentDate` to equivalent UTC instance.
- **Database State Verification:** Repository receives sanitized `DateTimeKind.Utc` objects exclusively.

---

### UT-07: CreatedBy User Identity - Mapping Authenticated Identity
- **Test ID & Name:** `UT-07_CreatedByUserIdentity_MapsFromUserContext`
- **Preconditions & Mock Configuration:**
  - Mock `IUserContext` configured to return `"jwt_sub_user_998877"`.
  - Mock `IStudentRepository` set up to store entity.
- **Input Payload / Test Data:**
  - Standard valid `CreateStudentRequestDto`.
- **Execution Steps:**
  1. Execute `await service.CreateStudentAsync(validDto)`.
- **Expected Result & Exact Assertions:**
  - `mockRepo.Verify(r => r.CreateAsync(It.Is<Student>(s => s.CreatedBy == "jwt_sub_user_998877")), Times.Once);`
  - When claims identity is unauthenticated, fallback mechanism defaults `CreatedBy` to `"Anonymous"`.
- **Database State Verification:** N/A.

---

### UT-08: Nullable Audit Fields - Initialization Verification
- **Test ID & Name:** `UT-08_NullableAuditFields_InitializedAsNullOnCreation`
- **Preconditions & Mock Configuration:**
  - Standard service setup with mock repository.
- **Input Payload / Test Data:**
  - Valid creation DTO.
- **Execution Steps:**
  1. Invoke `await service.CreateStudentAsync(validDto)`.
  2. Inspect domain entity passed to repository persistence layer.
- **Expected Result & Exact Assertions:**
  - `capturedStudent.UpdatedAtUtc.Should().BeNull();`
  - `capturedStudent.UpdatedBy.Should().BeNull();`
- **Database State Verification:** Initial database entity insertion contains NULL for `UpdatedAtUtc` and `UpdatedBy`.

---

### UT-09: Client Audit Injection - Rejection of Client-Supplied Audit Flags
- **Test ID & Name:** `UT-09_ClientAuditInjection_IgnoresClientSuppliedAuditData`
- **Preconditions & Mock Configuration:**
  - Controller & Service setup. The API contract `CreateStudentRequestDto` must not expose `Id`, `CreatedAtUtc`, or `CreatedBy`. If client attempts raw JSON payload injection, mapper must ignore them.
- **Input Payload / Test Data:**
  - Raw JSON containing untrusted system claims:
    ```json
    {
      "id": "00000000-0000-0000-0000-000000000001",
      "fullName": "Hacker One",
      "email": "hacker@domain.com",
      "age": 25,
      "department": "Security",
      "enrollmentDate": "2026-09-01T00:00:00Z",
      "createdAtUtc": "1999-01-01T00:00:00Z",
      "createdBy": "RootAdmin"
    }
    ```
- **Execution Steps:**
  1. Deserialize payload into controller input DTO / bind model.
  2. Map DTO to entity via service layer.
- **Expected Result & Exact Assertions:**
  - Generated entity `Id` is a new system-generated Guid (not `...0001`).
  - Entity `CreatedAtUtc` is current UTC timestamp (not `1999-01-01`).
  - Entity `CreatedBy` is authenticated user identity (not `"RootAdmin"`).
- **Database State Verification:** N/A.

---

### UT-10: Duplicate Email Conflict - Repository Exception Handling
- **Test ID & Name:** `UT-10_DuplicateEmailConflict_ThrowsConflictException`
- **Preconditions & Mock Configuration:**
  - Mock `IStudentRepository.GetByEmailAsync("duplicate@university.edu")` set up to return an existing `Student` entity.
- **Input Payload / Test Data:**
  - Request DTO with `Email = "duplicate@university.edu"`.
- **Execution Steps:**
  1. Execute `Func<Task> act = async () => await service.CreateStudentAsync(request);`
- **Expected Result & Exact Assertions:**
  - `await act.Should().ThrowAsync<DuplicateRecordException>()`
    `.WithMessage("*duplicate@university.edu*");`
  - `mockRepo.Verify(r => r.CreateAsync(It.IsAny<Student>()), Times.Never);`
- **Database State Verification:** Repository `CreateAsync` is never called.

---

### UT-11: Database Exception Handling - Repository Fault Resilience
- **Test ID & Name:** `UT-11_DatabaseExceptionHandling_WrapsGenericDbExceptions`
- **Preconditions & Mock Configuration:**
  - Mock `IStudentRepository.CreateAsync(It.IsAny<Student>())` configured to throw `DbUpdateException("Database disk image is malformed", innerException: new SqliteException("Disk write error", 10))`.
- **Input Payload / Test Data:**
  - Valid request DTO.
- **Execution Steps:**
  1. Execute `Func<Task> act = async () => await service.CreateStudentAsync(request);`
- **Expected Result & Exact Assertions:**
  - `await act.Should().ThrowAsync<RepositoryException>();`
  - Generic internal database exception details are logged internally; technical details are caught and wrapped to prevent infrastructure leakage.
- **Database State Verification:** Transaction aborts cleanly.

---

### UT-12: String Sanitization & Email Normalization
- **Test ID & Name:** `UT-12_StringSanitizationAndEmailNormalization_TrimsAndLowercasesInput`
- **Preconditions & Mock Configuration:**
  - Service setup with Mock Repository capture.
- **Input Payload / Test Data:**
  ```csharp
  var request = new CreateStudentRequestDto
  {
      FullName = "   Jane   Alice   Smith   ",
      Email = "  JANE.SMITH@University.EDU   ",
      Age = 22,
      Department = "   Software Engineering   ",
      EnrollmentDate = DateTime.SpecifyKind(new DateTime(2026, 9, 1), DateTimeKind.Utc)
  };
  ```
- **Execution Steps:**
  1. Invoke `await service.CreateStudentAsync(request);`
- **Expected Result & Exact Assertions:**
  - `capturedStudent.FullName.Should().Be("Jane Alice Smith");`
  - `capturedStudent.Email.Should().Be("jane.smith@university.edu");`
  - `capturedStudent.Department.Should().Be("Software Engineering");`
- **Database State Verification:** Database receives sanitized, normalized string attributes.

---

## 4. Integration Test Specifications (IT-01 through IT-14)

### IT-01: POST /api/students Returns 201 Created & Valid Location Header
- **Test ID & Name:** `IT-01_PostStudent_Returns201CreatedAndLocationHeader`
- **Preconditions & Mock Configuration:**
  - Functional API test server started using `IntegrationTestWebApplicationFactory`.
  - HTTP client configured with valid Bearer token (`sub = "admin_user_1"`).
- **Input Payload / Test Data:**
  ```json
  {
    "fullName": "Alice Johnson",
    "email": "alice.johnson@university.edu",
    "age": 21,
    "department": "Mathematics",
    "enrollmentDate": "2026-09-01T00:00:00Z"
  }
  ```
- **Execution Steps:**
  1. Send `POST /api/students` with JSON payload.
  2. Read response code, headers, and body.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.Created);`
  - `response.Headers.Location.Should().NotBeNull();`
  - `response.Headers.Location.ToString().Should().MatchRegex(@"http://localhost/api/students/[0-9a-fA-F\-]{36}");`
  - Response body contains generated `id`, matching `fullName`, `email`, and non-null `createdAtUtc`.
- **Database State Verification:** Querying SQLite directly confirms a record with the returned `id` exists in table `Students`.

---

### IT-02: 401 Unauthorized Returned When Authorization Header Missing
- **Test ID & Name:** `IT-02_PostStudent_MissingAuthHeader_Returns401Unauthorized`
- **Preconditions & Mock Configuration:**
  - API endpoint secured with JWT Authentication policy.
  - HTTP Client instantiated *without* default `Authorization` header.
- **Input Payload / Test Data:**
  - Valid `CreateStudentRequestDto` JSON payload.
- **Execution Steps:**
  1. Send `POST /api/students` without `Authorization` header.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.Unauthorized);`
  - Response header `WWW-Authenticate` is present.
- **Database State Verification:** Zero records added to SQLite database.

---

### IT-03: 403 Forbidden Returned When Authorization Has Insufficient Scope
- **Test ID & Name:** `IT-03_PostStudent_LacksPermission_Returns403Forbidden`
- **Preconditions & Mock Configuration:**
  - Client configured with valid JWT token lacking `student:create` scope/role (e.g., role = `"Guest"`).
- **Input Payload / Test Data:**
  - Valid creation JSON payload.
- **Execution Steps:**
  1. Send `POST /api/students` with standard guest auth token.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.Forbidden);`
- **Database State Verification:** SQLite database remains completely unmodified.

---

### IT-04: 400 Bad Request Returned for Malformed JSON Payload
- **Test ID & Name:** `IT-04_PostStudent_MalformedJson_Returns400BadRequest`
- **Preconditions & Mock Configuration:**
  - Authenticated HTTP client.
- **Input Payload / Test Data:**
  - Invalid JSON string: `"{ fullName: 'Missing Quotes', age: 20, email: }"`
- **Execution Steps:**
  1. Send `POST /api/students` with `Content-Type: application/json` containing the broken JSON.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.BadRequest);`
  - Response payload matches RFC 9457 Problem Details format (`type`, `title`, `status`, `traceId`).
- **Database State Verification:** No database transaction is initiated.

---

### IT-05: 413 Payload Too Large Returned When Request Body Exceeds 16 KB
- **Test ID & Name:** `IT-05_PostStudent_PayloadExceeds16KB_Returns413PayloadTooLarge`
- **Preconditions & Mock Configuration:**
  - Server middleware configured with strict body size limit `[RequestSizeLimit(16 * 1024)]`.
- **Input Payload / Test Data:**
  - JSON payload where `department` contains a repeated string exceeding 17 KB total request length.
- **Execution Steps:**
  1. Send oversized `POST /api/students` request.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.RequestEntityTooLarge);` (HTTP 413)
- **Database State Verification:** Server rejects payload at HTTP parsing layer; database pipeline not touched.

---

### IT-06: 415 Unsupported Media Type Returned for Non-JSON Content Type
- **Test ID & Name:** `IT-06_PostStudent_UnsupportedMediaType_Returns415`
- **Preconditions & Mock Configuration:**
  - Standard integration test client.
- **Input Payload / Test Data:**
  - XML or Plain Text string: `"<Student><FullName>Bob</FullName></Student>"`
  - Headers: `Content-Type: application/xml` or `text/plain`
- **Execution Steps:**
  1. Send `POST /api/students` with XML content type.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.UnsupportedMediaType);` (HTTP 415)
- **Database State Verification:** Database unchanged.

---

### IT-07: 429 Too Many Requests Returned When Rate Limit Exceeded
- **Test ID & Name:** `IT-07_PostStudent_RateLimitExceeded_Returns429TooManyRequests`
- **Preconditions & Mock Configuration:**
  - ASP.NET Core Rate Limiting configured with fixed window policy (e.g., limit = 5 requests/minute per IP).
- **Input Payload / Test Data:**
  - Valid `CreateStudentRequestDto` JSON payload.
- **Execution Steps:**
  1. Execute 6 consecutive `POST /api/students` calls in rapid succession within 1 second.
- **Expected Result & Exact Assertions:**
  - Calls 1 to 5 return HTTP status codes `201 Created` or validation result.
  - Call 6 returns `response.StatusCode.Should().Be(HttpStatusCode.TooManyRequests);` (HTTP 429)
  - `response.Headers.Should().ContainKey("Retry-After");`
- **Database State Verification:** Exactly 5 records inserted into SQLite; 6th request rejected before pipeline execution.

---

### IT-08: 409 Conflict Returned on Duplicate Email via SQLite Unique Constraint
- **Test ID & Name:** `IT-08_PostStudent_DuplicateEmail_Returns409Conflict`
- **Preconditions & Mock Configuration:**
  - SQLite database initialized with unique index on `Students(Email)`.
  - Existing student with email `"exists@university.edu"` pre-seeded in SQLite.
- **Input Payload / Test Data:**
  ```json
  {
    "fullName": "Duplicate User",
    "email": "exists@university.edu",
    "age": 22,
    "department": "Biology",
    "enrollmentDate": "2026-09-01T00:00:00Z"
  }
  ```
- **Execution Steps:**
  1. Send `POST /api/students` with duplicate email payload.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.Conflict);` (HTTP 409)
  - Problem Details response body contains: `detail: "A student record with email 'exists@university.edu' already exists."`
- **Database State Verification:** Querying SQLite confirms count of records with `Email = 'exists@university.edu'` remains exactly 1.

---

### IT-09: RFC 9457 Problem Details Format Verified on Validation Errors
- **Test ID & Name:** `IT-09_ValidationFailure_ReturnsRfc9457ProblemDetails`
- **Preconditions & Mock Configuration:**
  - Standard test API server setup.
- **Input Payload / Test Data:**
  - Invalid DTO: `{"fullName": "", "email": "invalid-email", "age": 5}`
- **Execution Steps:**
  1. Send `POST /api/students` with invalid payload.
  2. Parse HTTP response payload as JSON.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.BadRequest);`
  - `response.Content.Headers.ContentType.MediaType.Should().Be("application/problem+json");`
  - JSON response structure contains:
    ```json
    {
      "type": "https://tools.ietf.org/html/rfc9110#section-15.5.1",
      "title": "One or more validation errors occurred.",
      "status": 400,
      "errors": {
        "FullName": ["'Full Name' must not be empty."],
        "Email": ["'Email' is not a valid email address."],
        "Age": ["Age must be between 16 and 100."]
      },
      "traceId": "0HMV123456789:00000001"
    }
    ```
- **Database State Verification:** Database unaffected.

---

### IT-10: SQLite Database Persistence Verification
- **Test ID & Name:** `IT-10_PostStudent_PersistsRecordToSqliteDatabase`
- **Preconditions & Mock Configuration:**
  - `IntegrationTestWebApplicationFactory` running against real file-backed or persistent in-memory SQLite database.
- **Input Payload / Test Data:**
  ```json
  {
    "fullName": "Database Persistence Test",
    "email": "db.test@university.edu",
    "age": 24,
    "department": "Physics",
    "enrollmentDate": "2026-09-01T00:00:00Z"
  }
  ```
- **Execution Steps:**
  1. Execute `POST /api/students`.
  2. Extract created `id` (Guid) from HTTP response body.
  3. Resolve `AppDbContext` directly from `factory.Services.CreateScope()`.
  4. Query SQLite via EF Core: `await dbContext.Students.FindAsync(id)`.
- **Expected Result & Exact Assertions:**
  - `dbRecord.Should().NotBeNull();`
  - `dbRecord.FullName.Should().Be("Database Persistence Test");`
  - `dbRecord.Email.Should().Be("db.test@university.edu");`
  - `dbRecord.Age.Should().Be(24);`
  - `dbRecord.Department.Should().Be("Physics");`
  - `dbRecord.CreatedAtUtc.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));`
- **Database State Verification:** Explicit database query confirms physical record persistence.

---

### IT-11: Atomicity Verification - Transaction Rollback on Failure
- **Test ID & Name:** `IT-11_AtomicityVerification_RollsBackTransactionOnFailure`
- **Preconditions & Mock Configuration:**
  - Intercept database pipeline or simulate severe DB constraint failure during multi-entity operation.
- **Input Payload / Test Data:**
  - Batch registration payload containing 2 entities: Entity 1 is valid; Entity 2 triggers a database constraint failure.
- **Execution Steps:**
  1. Send request to multi-record endpoint or trigger failure after initial entity attachment.
- **Expected Result & Exact Assertions:**
  - API returns HTTP 500 / HTTP 409 depending on transaction exception.
  - Querying SQLite for Entity 1 confirms it was **NOT** committed.
- **Database State Verification:** SQLite database state contains 0 partial entries; transaction atomicity guaranteed.

---

### IT-12: Audit Identity Verification - CreatedBy Matches JWT Sub Claim
- **Test ID & Name:** `IT-12_AuditIdentityVerification_MatchesJwtSubClaim`
- **Preconditions & Mock Configuration:**
  - Client configured with JWT containing `sub = "user_auth_sec_9901"`.
- **Input Payload / Test Data:**
  - Standard valid registration JSON payload.
- **Execution Steps:**
  1. Send `POST /api/students` with Bearer header carrying the `user_auth_sec_9901` JWT token.
  2. Query SQLite database directly for inserted record.
- **Expected Result & Exact Assertions:**
  - `persistedEntity.CreatedBy.Should().Be("user_auth_sec_9901");`
- **Database State Verification:** Field `CreatedBy` in SQLite table `Students` stores exact `sub` claim value from token.

---

### IT-13: Concurrent Duplicate Registrations - SQLite Race Condition Prevention
- **Test ID & Name:** `IT-13_ConcurrentDuplicateRegistrations_PreventsRaceConditions`
- **Preconditions & Mock Configuration:**
  - Parallel execution harness (`Task.WhenAll`).
  - Single target payload with distinct email `"race.condition@university.edu"`.
- **Input Payload / Test Data:**
  - Identical registration DTO payload.
- **Execution Steps:**
  1. Spawn 10 simultaneous asynchronous HTTP POST requests pointing to `/api/students` using `Task.WhenAll`.
  2. Collect all 10 response status codes.
- **Expected Result & Exact Assertions:**
  - Exactly 1 request returns `HTTP 201 Created`.
  - Exactly 9 requests return `HTTP 409 Conflict`.
- **Database State Verification:** Querying SQLite confirms `SELECT COUNT(*) FROM Students WHERE Email = 'race.condition@university.edu'` equals `1`.

---

### IT-14: GET /health Returns 200 OK & Healthy Status
- **Test ID & Name:** `IT-14_GetHealth_Returns200OkAndHealthyStatus`
- **Preconditions & Mock Configuration:**
  - ASP.NET Core Health Checks configured with `SqliteHealthCheck`.
  - SQLite database online and responsive.
- **Input Payload / Test Data:**
  - None (`GET /health`).
- **Execution Steps:**
  1. Execute `GET /health`.
  2. Read status code and response body.
- **Expected Result & Exact Assertions:**
  - `response.StatusCode.Should().Be(HttpStatusCode.OK);`
  - JSON response contains:
    ```json
    {
      "status": "Healthy",
      "totalDuration": "00:00:00.0123456",
      "entries": {
        "sqlite": {
          "data": {},
          "duration": "00:00:00.0054321",
          "status": "Healthy",
          "tags": ["db", "sqlite"]
        }
      }
    }
    ```
- **Database State Verification:** Health check successfully executed `SELECT 1;` against live SQLite connection.

---

## 5. Test Execution Evidence & Reporting Requirements

### 5.1 Command Execution Guidelines
All tests must be executed strictly via command line interface using Release build configurations to ensure production-level code optimization and compliance:

```bash
dotnet test --configuration Release --logger "console;verbosity=detailed" --logger "html;logfilename=test-results.html"
```

### 5.2 Mandatory Evidence Artifacts
Upon test completion, the following mandatory test execution log files must be generated and archived:
1. **Console Execution Output (`test-execution.log`):** Full verbose log of xUnit test execution.
2. **HTML Results Report (`test-results.html`):** Visual pass/fail summary detailing execution duration per test case.
3. **Database Integrity Verification Log:** Validation log proving real SQLite files were created, queried, and cleanly unmounted/deleted during execution.

### 5.3 Acceptance Criteria Threshold
- **Total Test Cases:** 26 (12 Unit Tests, 14 Integration Tests)
- **Required Pass Rate:** 100% (Zero failures, zero skipped tests)
- **EF Core InMemory Provider Usage:** Exactly 0 occurrences (Enforced by code review). All integration tests utilize SQLite (`Microsoft.Data.Sqlite`).