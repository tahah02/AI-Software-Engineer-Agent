# Technical Design Document: AAISE 2+2+1 Calculation API

**Project:** AAISE Calculator Workflow POC  
**Version:** 1.1 (Revised)  
**Status:** Final Design (Agent 1 Approved)  
**Technology Stack:** DOTNET_CSHARP (.NET 8), EF Core 8, SQLite

---

## 1. System Architecture & Component Design

The system is designed using a clean, layered architectural pattern to ensure strict separation of concerns, high testability, and adherence to the AAISE agentic delivery loop. All operations are asynchronous to maximize throughput and resource utilization.

### 1.1 Component Overview
The solution is composed of three distinct projects within a single repository:

1.  **Calculator.Api (The Orchestrator)**:
    *   **Controllers**: Entry points for HTTP requests. Responsible for model validation and returning appropriate HTTP status codes.
    *   **Services**: Contains the core business logic. Orchestrates the flow between the database and the external Mock Vendor.
    *   **Repositories**: Encapsulates all EF Core logic. Responsible for persisting and retrieving `CalculationRecord` entities from SQLite.
    *   **Clients**: A typed `HttpClient` implementation (`MockVendorClient`) that communicates with the external MockVendor.Api.
2.  **MockVendor.Api (External Dependency)**:
    *   A lightweight, standalone service that simulates a third-party vendor. It exposes a single endpoint returning a fixed integer value.
3.  **Calculator.Tests (Validation Suite)**:
    *   An xUnit project containing unit tests (mocking dependencies) and integration tests (using real SQLite files and real HTTP calls to the MockVendor.Api).

### 1.2 Dependency Injection (DI) & Service Lifecycle
The application utilizes the built-in .NET DI container with the following registrations:
*   **AppDbContext**: `AddDbContext<AppDbContext>` with a **Scoped** lifecycle. This ensures a single database connection per HTTP request, maintaining transaction integrity.
*   **ICalculationRepository / ICalculationService**: Registered as **Scoped**.
*   **IMockVendorClient**: Registered via `IHttpClientFactory` as **Transient**. This prevents socket exhaustion and ensures DNS changes are respected while providing a pre-configured client for the service layer.
*   **Logging**: `ILogger<T>` is injected into all layers for structured logging.

### 1.3 Execution Flow (GET /api/calculations/{id}/sum)
1.  **Request**: Client sends a GET request to `/api/calculations/{id}/sum`.
2.  **Validation**: The Controller validates that the `id` is a positive integer.
3.  **Persistence Read (FR-03)**: The Service calls the Repository. The Repository executes an `async` query against the SQLite database to retrieve the `CalculationRecord`. **Crucial**: The system must never use cached data from a previous POST; it must perform a fresh read.
4.  **External Call (FR-05)**: The Service uses the `MockVendorClient` to perform a real HTTP GET request to the `MockVendor.Api` endpoint.
5.  **Computation (FR-06)**: The Service performs the summation: `Number1 + Number2 + MockValue`. This is wrapped in a `checked` block to detect `Int32` overflows.
6.  **Response**: The Controller returns a JSON object containing the inputs, the mock value, and the total sum.

---

## 2. Database Design & Domain Model

The system uses SQLite for persistence, satisfying the requirement for a real, file-backed database that persists across application restarts.

### 2.1 Entity: CalculationRecord
This entity represents the data model for the calculation inputs.

| Property | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| **Id** | `int` | Primary Key, Identity (Auto-Increment) | Unique identifier. Tests must not hardcode this value but retrieve it from the POST response. |
| **Number1** | `int` | NOT NULL | The first numeric input (signed 32-bit integer). |
| **Number2** | `int` | NOT NULL | The second numeric input (signed 32-bit integer). |

### 2.2 Persistence Lifecycle & Migrations
*   **ORM**: Entity Framework Core 8 using the `Microsoft.EntityFrameworkCore.Sqlite` provider.
*   **Migrations**: EF Core Migrations are used to manage the schema. The `AppDbContext` will apply migrations at startup in the development environment to ensure the SQLite file is initialized correctly.
*   **Database Isolation (NFR-06)**: For integration testing, the `WebApplicationFactory` is configured to override the connection string. Each test run generates a unique filename (e.g., `test_db_{Guid}.sqlite`) to ensure deterministic results and prevent cross-test data contamination. These files are deleted during the test cleanup phase.
*   **Configuration**: The connection string is managed via `appsettings.json` using the key `ConnectionStrings:DefaultConnection`.

---

## 3. API Specifications

### 3.1 Calculator.Api Endpoints

#### 3.1.1 POST /api/calculations
Creates a new calculation record in the database.
*   **Request Body**:
    ```json
    {
      "number1": 1,
      "number2": 1
    }
    ```
*   **Success Response**: `201 Created`
*   **Header**: `Location: /api/calculations/{id}/sum` (where `{id}` is the auto-generated database ID).
*   **Response Body**:
    ```json
    {
      "id": 1,
      "number1": 1,
      "number2": 1
    }
    ```
*   **Error Responses**:
    *   `400 Bad Request`: Malformed JSON, missing fields, or non-integer values.
    *   `415 Unsupported Media Type`: `Content-Type` header is not `application/json`.

#### 3.1.2 GET /api/calculations/{id}/sum
Retrieves the record from SQLite, calls the Mock Vendor, and returns the aggregated sum.
*   **Success Response**: `200 OK`
*   **Response Body**:
    ```json
    {
      "recordId": 1,
      "number1": 1,
      "number2": 1,
      "mockValue": 1,
      "total": 3
    }
    ```
*   **Error Responses**:
    *   `404 Not Found`: The provided `id` does not exist in the SQLite database.
    *   `422 Unprocessable Entity`: The summation of `Number1 + Number2 + MockValue` exceeds the `Int32` range (Overflow).
    *   `500 Internal Server Error`: Unexpected server-side failure.
    *   `502 Bad Gateway`: The Mock Vendor API is unreachable or returned an invalid response (e.g., malformed JSON).
    *   `503 Service Unavailable`: The SQLite database is unreachable or locked.
    *   `504 Gateway Timeout`: The Mock Vendor API failed to respond within the 5-second timeout period.

### 3.2 MockVendor.Api Endpoints

#### 3.2.1 GET /api/mock/value
*   **Success Response**: `200 OK`
*   **Response Body**:
    ```json
    {
      "value": 1
    }
    ```

---

## 4. Security, Authentication & Authorization

### 4.1 Authentication & Authorization
*   **Scheme**: As per SRS Section 14, authentication is omitted for this POC. The APIs are designed for internal/localhost execution.
*   **Identity Context**: No user context is required.

### 4.2 Input Validation & Error Handling
*   **Strict Validation**: All inputs are validated against the `Int32` range. The API uses `DataAnnotations` on DTOs to enforce required fields.
*   **RFC 9457 Problem Details**: All error responses (4xx and 5xx) strictly follow the "Problem Details for HTTP APIs" standard.
    *   **traceId**: Every error response includes a `traceId` for log correlation.
    *   **Sanitization**: Production/Release logs and responses must not leak stack traces or internal file paths.
*   **No-Fallback Policy**: If the Mock Vendor is down, the API must return a `502 Bad Gateway`. It is strictly prohibited to fall back to a hardcoded value of `1` in the code (FR-05).

---

## 5. Audit & Validation Rules

### 5.1 Business Logic Constraints
1.  **Persistence Verification (FR-03)**: The GET request MUST perform a `SELECT` query against the SQLite database. Reusing the object from the POST request memory is prohibited.
2.  **Real HTTP Boundary (FR-05)**: The communication between `Calculator.Api` and `MockVendor.Api` must occur over a real TCP/IP socket (localhost). In-process mocking is only allowed in Unit Tests.
3.  **Immutability (FR-10)**: The GET request to the sum endpoint is a read-only operation. It must not modify any data in the `CalculationRecord` table.
4.  **No-Insert on GET**: The GET endpoint must never create a record if the ID is missing; it must return a 404.

### 5.2 Overflow Handling
*   The summation logic is encapsulated in a C# `checked` block:
    ```csharp
    try {
        int total = checked(record.Number1 + record.Number2 + mockValue);
    } catch (OverflowException) {
        // Map to 422 Unprocessable Entity
    }
    ```

---

## 6. Production Readiness

### 6.1 Structured Logging
*   **Provider**: `Microsoft.Extensions.Logging`.
*   **Format**: JSON structured logs.
*   **Key Events**:
    *   Database record creation (with ID).
    *   Outgoing HTTP request to Mock Vendor (URL, Method, Duration).
    *   Calculation success/failure (including overflow events).
    *   Correlation of `traceId` across log entries.

### 6.2 Health Checks
*   **Endpoint**: `/health`
*   **Checks**:
    *   **SQLite Check**: Verifies the database file exists and a simple `SELECT 1` can be executed.
    *   **MockVendor Check**: Verifies the configured `MockVendor:BaseUrl` is reachable.

### 6.3 Configuration Management
*   **MockVendor:BaseUrl**: Configurable via `appsettings.json` or Environment Variables.
*   **ConnectionStrings:DefaultConnection**: Configurable SQLite file path.
*   **HttpClient:Timeout**: Set to 5 seconds via `IHttpClientFactory` configuration.

---

## 7. Git Workflow & Branching Strategy

### 7.1 Branching Model
*   **main**: Protected branch. Only stable, reviewed code is merged here.
*   **feature/calculation-api**: The primary development branch for the POC implementation.

### 7.2 Commit Standards
*   Commits must be descriptive and reference the Requirement ID (e.g., "Add SQLite repository implementation [FR-02]").
*   Agent 4 (QA) is required to commit test execution logs as evidence of passing gates.

### 7.3 CI/CD Pipeline (Local Simulation)
1.  `dotnet restore`: Restore dependencies.
2.  `dotnet build --configuration Release`: Compile the solution.
3.  `dotnet test --configuration Release --no-build`: Execute the xUnit suite.

---

## 8. Requirement Traceability Matrix

| Req ID | Requirement Description | Design Component / Implementation Detail |
| :--- | :--- | :--- |
| **FR-01** | Accept two numeric inputs | `CalculationsController.Post` with `CalculationRequest` DTO. |
| **FR-02** | Persist to SQLite | `CalculationRepository.AddAsync` using EF Core 8. |
| **FR-03** | Read values from SQLite | `CalculationRepository.GetByIdAsync` (Fresh DB query). |
| **FR-04** | Mock HTTP API returning 1 | `MockVendor.Api` project, `MockController`. |
| **FR-05** | Real HTTP call to mock | `MockVendorClient` using `HttpClient` (No in-process fallback). |
| **FR-06** | Return sum (N1+N2+Mock) | `CalculationService.CalculateSumAsync` logic. |
| **FR-07** | Baseline 1+1+1=3 | Verified by Integration Test `IT-02`. |
| **FR-08** | Handle failures | RFC 9457 Problem Details Middleware. |
| **FR-09** | OpenAPI & Health | Swagger UI at `/swagger` and Health Checks at `/health`. |
| **FR-10** | No mutation on GET | Service layer logic ensures read-only DB access. |
| **NFR-01** | Async EF Core | Use of `ToListAsync`, `FirstOrDefaultAsync`, `SaveChangesAsync`. |
| **NFR-02** | HttpClient Timeout | 5-second timeout configured in `Program.cs`. |
| **NFR-03** | Structured Logging | `ILogger` implementation with JSON formatting. |
| **NFR-04** | Configurable Ports | Defined in `launchSettings.json` and `appsettings.json`. |
| **NFR-05** | Build/Test Logs | Captured during CI pipeline execution. |
| **NFR-06** | Deterministic Tests | Unique SQLite file per test case with auto-cleanup. |
| **NFR-07** | No Secrets in Repo | Use of environment variables and `.gitignore` for local settings. |
| **NFR-08** | Graceful Shutdown | Standard .NET Generic Host `IHostApplicationLifetime` support. |

---

## 9. xUnit Test Specification (v1.1)

This section defines the mandatory test suite required for implementation approval, aligned 1-to-1 with SRS Section 9.

### 9.1 Unit Tests (Calculator.Tests/Unit)
*   **UT-01 (Baseline Calculation)**: Input (1, 1) + Mock 1 $\rightarrow$ Total 3.
*   **UT-02 (Alternate Positive Values)**: Input (2, 3) + Mock 1 $\rightarrow$ Total 6.
*   **UT-03 (Zero Boundary Values)**: Input (0, 0) + Mock 1 $\rightarrow$ Total 1.
*   **UT-04 (Negative Inputs)**: Input (-2, 5) + Mock 1 $\rightarrow$ Total 4.
*   **UT-05 (Repository Mocking)**: Verify `GetByIdAsync` is called exactly once with the correct ID.
*   **UT-06 (Client Mocking)**: Verify `GetMockValueAsync` is called exactly once.
*   **UT-07 (Integer Overflow)**: Input (`Int32.MaxValue`, 1) + Mock 1 $\rightarrow$ Throws `OverflowException` (mapped to 422).

### 9.2 Integration Tests (Calculator.Tests/Integration)
*   **IT-01 (End-to-End Success)**: Full flow: POST (1,1) $\rightarrow$ 201; GET sum $\rightarrow$ 200 (Total 3).
*   **IT-02 (Persistence Verification)**: POST (1,1), restart/clear context, GET sum $\rightarrow$ Verify data is pulled from SQLite file.
*   **IT-03 (Invalid POST Body)**: POST malformed JSON $\rightarrow$ 400 Bad Request.
*   **IT-04 (Unsupported Media Type)**: POST with `text/plain` $\rightarrow$ 415 Unsupported Media Type.
*   **IT-05 (Record Not Found)**: GET `/api/calculations/9999/sum` $\rightarrow$ 404 Not Found.
*   **IT-06 (Negative ID Validation)**: GET `/api/calculations/-1/sum` $\rightarrow$ 400 Bad Request.
*   **IT-07 (Overflow Response)**: POST (`Int32.MaxValue`, 1), GET sum $\rightarrow$ 422 Unprocessable Entity.
*   **IT-08 (Mock Service Down)**: Mock Vendor process stopped, GET sum $\rightarrow$ 502 Bad Gateway.
*   **IT-09 (Mock Timeout)**: Mock Vendor delayed by 10s, GET sum $\rightarrow$ 504 Gateway Timeout (5s limit).
*   **IT-10 (SQLite DB Unavailable)**: Database file read-only or deleted during runtime, GET sum $\rightarrow$ 503 Service Unavailable.
*   **IT-11 (Malformed Vendor JSON)**: Mock Vendor returns invalid JSON string, GET sum $\rightarrow$ 502 Bad Gateway.
*   **IT-12 (Swagger & Health Check)**: 
    *   Verify GET `/swagger/v1/swagger.json` returns 200.
    *   Verify GET `/health` returns 200 and `{"status": "Healthy"}`.

---

## 10. Design Decisions & Approvals (Agent 1)

1.  **Stack Confirmation**: .NET 8 / C# / SQLite is the final approved stack.
2.  **Two-Step Process**: The separation of POST (storage) and GET (calculation) is mandatory to prove the persistence lifecycle.
3.  **Network Boundary**: The Mock Vendor MUST run as a separate process to validate real-world HTTP handling, including timeouts and connection failures.
4.  **Overflow Policy**: The system will not return incorrect results on overflow; it will return a `422 Unprocessable Entity` to maintain data integrity.
5.  **Test Isolation**: Manual verification is required to ensure that each test run uses a fresh SQLite database file to prevent ID collisions.
6.  **Location Header**: The `POST` response must include the `Location` header to facilitate automated discovery of the calculation endpoint.
7.  **Status Code Strictness**: Adherence to 502 (Bad Gateway) for vendor failures and 504 (Gateway Timeout) for vendor timeouts is non-negotiable.