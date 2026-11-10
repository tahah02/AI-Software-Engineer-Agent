# Technical Design Document: Student Registration System (SRS) v1.1

**Status:** Approved for Implementation  
**Version:** 1.1  
**Scope:** Student Registration API (DOTNET_CSHARP)

---

## 1. System Architecture and Component Design

The system utilizes a Clean Architecture pattern to ensure strict separation of concerns and testability.

*   **`StudentsController`**: The entry point. Responsible for HTTP request mapping, DTO validation via FluentValidation, and returning RFC 9457 compliant `ProblemDetails`.
*   **`IStudentService` / `StudentService`**: Orchestrates business logic. It performs data transformation, enforces audit field population, and invokes the repository.
*   **`IStudentRepository` / `StudentRepository`**: Encapsulates data access logic using asynchronous EF Core methods. It interacts directly with the `AppDbContext`.
*   **`AppDbContext`**: Inherits `DbContext`. Configures the SQLite provider, entity constraints, and unique indexes.
*   **Dependency Injection (DI)**: Registered in `Program.cs` via `IServiceCollection`:
    *   `AppDbContext`: Scoped.
    *   `IStudentRepository`: Scoped.
    *   `IStudentService`: Scoped.
*   **Execution Flow**: `Request` -> `Middleware (Auth/RateLimit/Exception)` -> `Controller` -> `Service` -> `Repository` -> `DbContext` -> `SQLite`.

---

## 2. Database Design and Domain Model

The `Student` entity is defined with the following schema:

| Field | Type | Constraints |
| :--- | :--- | :--- |
| `Id` | `Guid` | Primary Key, Database Generated |
| `FullName` | `string` | Required, MaxLength 200 |
| `Email` | `string` | Required, Unique Index, Normalized to Lowercase |
| `Age` | `int` | Required, Range 16-100 |
| `Department` | `string` | Required, MaxLength 100 |
| `EnrollmentDate` | `DateTime` | Required, UTC |
| `CreatedAt` | `DateTime` | Required, UTC |
| `CreatedBy` | `string` | Required, Auth Identity |
| `UpdatedAt` | `DateTime?` | Nullable |
| `UpdatedBy` | `string?` | Nullable |

*   **Migrations**: Managed via `dotnet ef migrations add InitialCreate`.
*   **Atomicity**: EF Core `SaveChangesAsync()` ensures that the creation of the student and the population of audit fields occur within a single database transaction.
*   **Concurrency**: The unique index on `Email` ensures that concurrent registration attempts for the same email result in a database-level constraint violation, which is caught and mapped to a 409 Conflict status.

---

## 3. API Specifications

*   **Endpoint**: `POST /api/students`
*   **Request DTO**: `FullName` (string), `Email` (string), `Age` (int), `Department` (string), `EnrollmentDate` (DateTime).
*   **Validation**: FluentValidation ensures trimming of whitespace and format validation. Client-supplied `Id`, `CreatedAt`, `CreatedBy`, `UpdatedAt`, or `UpdatedBy` fields are ignored or rejected.
*   **Constraints**: 16 KB request size limit enforced via `RequestSizeLimit` attribute.
*   **Status Codes**:
    *   201: Success.
    *   400: Validation failure (e.g., invalid email format, age out of range).
    *   401: Missing/Invalid JWT.
    *   403: Missing `student:create` claim.
    *   409: Duplicate email (Unique constraint violation).
    *   413: Payload too large (>16KB).
    *   415: Unsupported Media Type.
    *   429: Rate limit exceeded.
    *   500: Unhandled exception.
    *   503: Database unavailable.
*   **Error Handling**: Global Exception Middleware catches all exceptions and returns `RFC 9457` Problem Details.

---

## 4. Authentication and Authorization

*   **JWT Bearer**: Configured in `Program.cs` using `Microsoft.AspNetCore.Authentication.JwtBearer`.
*   **Permission**: `[Authorize(Policy = "student:create")]`.
*   **Identity**: The `CreatedBy` field is populated by extracting the `ClaimTypes.NameIdentifier` from the `ClaimsPrincipal`. If the identity is missing or invalid, the request is rejected with a 401 Unauthorized status.

---

## 5. Audit Field Lifecycle

*   **Logic**: `CreatedAt` and `EnrollmentDate` are set to `DateTime.UtcNow` within the `StudentService` layer.
*   **Immutability**: `CreatedBy` is populated from the authenticated user's identity at the time of creation.
*   **Nullability**: `UpdatedAt` and `UpdatedBy` are initialized as `null` upon record creation.
*   **Security**: The API layer explicitly ignores any client-supplied values for these fields to prevent tampering.

---

## 6. Production Readiness

*   **Rate Limiting**: `AspNetCoreRateLimit` configured for 20 requests per minute per IP.
*   **Logging**: Serilog with structured logging, including `TraceId` for correlation across the request pipeline.
*   **Health**: `/health` endpoint implemented via `Microsoft.Extensions.Diagnostics.HealthChecks`.
*   **Storage**: SQLite file path is configurable via `appsettings.Production.json`.
*   **Performance**: The system is designed to support p95 latency < 100ms under a load of 20 concurrent requests.

---

## 7. Git Workflow and Branching

*   **Branching**: `main` (protected, requires PR approval), `feature/student-registration`.
*   **CI/CD**: GitHub Actions workflow:
    1. `dotnet restore`
    2. `dotnet build --configuration Release`
    3. `dotnet test --configuration Release`
*   **Deployment**: Deployment requires successful CI pipeline completion.

---

## 8. Requirement Traceability Matrix

| Req ID | Description | TDD Section |
| :--- | :--- | :--- |
| FR-01 | Create Student | 3 |
| NFR-01 | SQLite Persistence | 2 |
| NFR-02 | Audit Fields | 5 |
| NFR-03 | JWT Auth | 4 |
| NFR-04 | Rate Limiting | 6 |
| NFR-05 | RFC 9457 Errors | 3 |

---

# XUnit Test Specification

## Test Infrastructure
*   **Fixture**: `DatabaseFixture` creates an isolated SQLite file per test class to ensure test independence.
*   **Execution**: `dotnet test --configuration Release`.

## Test Cases

### Unit Tests (UT-01 to UT-12)
*   **UT-01 to UT-05**: Service-level validation logic (Age range, Email format, Department length, Required fields).
*   **UT-06 to UT-09**: Audit field population logic (UTC timestamp verification, `CreatedBy` mapping).
*   **UT-10**: Mapping logic (DTO to Entity).
*   **UT-11**: Database exception handling (SQLite lock/connection failure).
*   **UT-12**: Whitespace trimming and email normalization logic.

### Integration Tests (IT-01 to IT-14)
*   **IT-01 (Success)**: Valid JWT, valid payload -> 201 Created.
*   **IT-02 (Auth)**: Missing JWT -> 401 Unauthorized.
*   **IT-03 (Auth)**: Missing `student:create` claim -> 403 Forbidden.
*   **IT-04 (Validation)**: Invalid Age -> 400 Bad Request.
*   **IT-05 (Validation)**: Invalid Email format -> 400 Bad Request.
*   **IT-06 (Conflict)**: Duplicate Email -> 409 Conflict.
*   **IT-07 (Size)**: Payload > 16KB -> 413 Payload Too Large.
*   **IT-08 (Media)**: Unsupported Content-Type -> 415 Unsupported Media Type.
*   **IT-09 (Rate)**: Exceeding 20 req/min -> 429 Too Many Requests.
*   **IT-10 (Database)**: DB unavailable -> 503 Service Unavailable.
*   **IT-11 (Audit)**: Verify `CreatedBy` matches JWT identity.
*   **IT-12 (Audit)**: Verify `CreatedAt` is UTC.
*   **IT-13 (Audit)**: Verify `UpdatedAt` is null on creation.
*   **IT-14 (Security)**: Verify client-supplied `Id` is ignored.