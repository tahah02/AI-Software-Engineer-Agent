# Technical Design Document: AAISE 2+2+1 Calculation API

**Version:** 1.0  
**Status:** Proposed for Approval  
**Stack:** ASP.NET Core 8, C#, EF Core 8, SQLite, xUnit  

---

## 1. System Architecture & Component Design

The system follows a clean, layered architecture to ensure separation of concerns and testability.

### 1.1 Layered Structure
*   **API Layer (Controllers):** `CalculationsController` handles HTTP routing, request validation, and response mapping.
*   **Service Layer (`CalculationService`):** Orchestrates business logic, including database interaction via the repository and external communication via `MockVendorClient`.
*   **Repository Layer (`CalculationRepository`):** Encapsulates EF Core `DbContext` operations.
*   **Infrastructure Layer:** `MockVendorClient` uses `IHttpClientFactory` to perform the HTTP call to the mock service.

### 1.2 Dependency Injection (DI) Setup
Services are registered in `Program.cs` with appropriate lifetimes:
*   `AppDbContext`: Scoped.
*   `ICalculationRepository`: Scoped.
*   `ICalculationService`: Scoped.
*   `MockVendorClient`: Transient (via `HttpClientFactory`).

### 1.3 Async Flow
All I/O-bound operations (Database access and HTTP calls) are implemented using `async/await` patterns to ensure non-blocking execution.

---

## 2. Database Design & Domain Model

### 2.1 Entity: `CalculationRecord`
| Column | Type | Constraints |
| :--- | :--- | :--- |
| `Id` | `INTEGER` | PK, Auto-increment |
| `Number1` | `INTEGER` | NOT NULL |
| `Number2` | `INTEGER` | NOT NULL |

### 2.2 Persistence Strategy
*   **EF Core Migrations:** Used to manage the SQLite schema.
*   **Atomicity:** The `POST` operation uses `SaveChangesAsync()` to ensure the record is persisted before returning the `201 Created` response.
*   **Isolation:** Each integration test utilizes a unique, ephemeral SQLite file to ensure test independence.

---

## 3. API Specifications

### 3.1 POST /api/calculations
*   **Request:** `{"number1": int, "number2": int}`
*   **Response (201):** `{"id": int, "number1": int, "number2": int}`
*   **Headers:** `Location: /api/calculations/{id}/sum`

### 3.2 GET /api/calculations/{id}/sum
*   **Response (200):** `{"recordId": int, "number1": int, "number2": int, "mockValue": int, "total": int}`

### 3.3 Error Handling (RFC 9457)
All errors return a `ProblemDetails` object:
```json
{
  "status": 400,
  "title": "Validation Error",
  "detail": "Number1 is required.",
  "traceId": "00-af76..."
}
```
*   **400:** Validation failure.
*   **404:** Record not found.
*   **422:** Integer overflow.
*   **502:** Mock service failure.
*   **503:** Database unavailable.
*   **504:** Mock service timeout.

---

## 4. Production Readiness
*   **Logging:** Structured logging via `ILogger` with correlation IDs.
*   **Health Checks:** `/health` endpoint returning `200 OK` if DB and Mock service are reachable.
*   **Configuration:** `appsettings.json` defines `MockVendor:BaseUrl` and `ConnectionStrings:DefaultConnection`.

---

## 5. Requirement Traceability Matrix

| Requirement | Implementation | Verification |
| :--- | :--- | :--- |
| FR-01/02 | `CalculationsController.Post` | IT-01 |
| FR-03/06 | `CalculationService.GetSumAsync` | IT-02, IT-03 |
| FR-04/05 | `MockVendorClient` | IT-04 |
| NFR-01 | EF Core Async | Code Review |
| NFR-03 | `ILogger` + TraceID | Code Review |

---

## 6. xUnit Test Specification

### 6.1 Unit Tests (`Calculator.Tests.Unit`)
*   **UT-01:** `Calculate_ValidInputs_ReturnsCorrectSum` (1,1,1 -> 3)
*   **UT-02:** `Calculate_LargeInputs_ReturnsCorrectSum` (2,3,1 -> 6)
*   **UT-03:** `Calculate_ZeroInputs_ReturnsCorrectSum` (0,0,1 -> 1)
*   **UT-04:** `Calculate_NegativeInputs_ReturnsCorrectSum` (-2,5,1 -> 4)
*   **UT-05:** `Post_InvalidModel_ReturnsBadRequest`
*   **UT-06:** `MockClient_ParsesValidJson`
*   **UT-07:** `Calculate_Overflow_Returns422`

### 6.2 Integration Tests (`Calculator.Tests.Integration`)
*   **IT-01:** Verify POST persists to SQLite.
*   **IT-02:** Verify GET retrieves persisted record and calls mock.
*   **IT-07:** Verify 502 when Mock API is down.
*   **IT-08:** Verify 504 on Mock timeout.
*   **IT-09:** Verify 503 when SQLite is inaccessible.

---

## 7. Git Workflow
*   **Branching:** `main` (protected) -> `feature/calculation-api`.
*   **CI Pipeline:** 
    1. `dotnet restore`
    2. `dotnet build --configuration Release`
    3. `dotnet test --configuration Release`
*   **Evidence:** All logs and exit codes must be captured in the PR description.