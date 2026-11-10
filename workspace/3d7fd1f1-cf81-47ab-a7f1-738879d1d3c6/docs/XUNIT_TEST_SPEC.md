# xUnit Test Specification: AAISE 2+2+1 Calculation API

**Project:** AAISE Calculator Workflow POC  
**Version:** 1.1 (Revised)  
**Status:** Final Specification  
**Author:** Principal Lead QA Architect  
**Test Framework:** xUnit, Moq, FluentAssertions, Microsoft.AspNetCore.Mvc.Testing

---

## 1. Introduction
This document defines the exhaustive test suite for the AAISE 2+2+1 Calculation API. It ensures strict adherence to the SRS v1.0 and the Technical Design Document. The suite covers unit-level logic, boundary conditions, and end-to-end integration scenarios including infrastructure failure modes.

## 2. Test Execution Environment
Tests are executed using the .NET CLI. The environment must have the .NET 8 SDK installed.

**Execution Command:**
```bash
dotnet test --configuration Release --verbosity normal
```

---

## 3. Unit Test Suite (Calculator.Tests.Unit)

### UT-01: Standard Calculation Logic
- **Requirement Traced:** FR-06 (Summation Logic)
- **Preconditions:** `ICalculationRepository` returns a record (1, 1). `IMockVendorClient` returns 1.
- **Input Payload:** Record ID: 1
- **Execution Steps:**
    1. Call `CalculationService.CalculateSumAsync(1)`.
- **Expected Result:** 
    - Total sum is 3 (1 + 1 + 1).
    - `ICalculationRepository.GetByIdAsync` was called exactly once.

### UT-02: Alternate Positive Values
- **Requirement Traced:** SRS Section 9 (Verification Scenarios)
- **Preconditions:** Repository returns (2, 3). Mock Vendor returns 1.
- **Input Payload:** Record ID: 2
- **Execution Steps:**
    1. Call `CalculationService.CalculateSumAsync(2)`.
- **Expected Result:** 
    - Total sum is 6 (2 + 3 + 1).

### UT-03: Zero Boundary Values
- **Requirement Traced:** SRS Section 9 (Verification Scenarios)
- **Preconditions:** Repository returns (0, 0). Mock Vendor returns 1.
- **Input Payload:** Record ID: 3
- **Execution Steps:**
    1. Call `CalculationService.CalculateSumAsync(3)`.
- **Expected Result:** 
    - Total sum is 1 (0 + 0 + 1).

### UT-04: Negative Inputs
- **Requirement Traced:** SRS Section 9 (Verification Scenarios)
- **Preconditions:** Repository returns (-2, 5). Mock Vendor returns 1.
- **Input Payload:** Record ID: 4
- **Execution Steps:**
    1. Call `CalculationService.CalculateSumAsync(4)`.
- **Expected Result:** 
    - Total sum is 4 (-2 + 5 + 1).

### UT-05: Repository Read Failure Handling
- **Requirement Traced:** FR-03 (Persistence Read)
- **Preconditions:** `ICalculationRepository.GetByIdAsync` is configured to return `null`.
- **Input Payload:** Record ID: 999
- **Execution Steps:**
    1. Call `CalculationService.CalculateSumAsync(999)`.
- **Expected Result:** 
    - Service throws `KeyNotFoundException`.
    - `IMockVendorClient` is never called.

### UT-06: Mock Vendor Client Failure Handling
- **Requirement Traced:** FR-05 (External Call)
- **Preconditions:** Repository returns valid record. `IMockVendorClient` throws `HttpRequestException`.
- **Input Payload:** Record ID: 1
- **Execution Steps:**
    1. Call `CalculationService.CalculateSumAsync(1)`.
- **Expected Result:** 
    - Service propagates the exception to be handled by the middleware.

### UT-07: Integer Overflow (Boundary Test)
- **Requirement Traced:** FR-06, SRS Section 9
- **Preconditions:** Repository returns (`int.MaxValue`, 1). Mock Vendor returns 1.
- **Input Payload:** Record ID: 5
- **Execution Steps:**
    1. Call `CalculationService.CalculateSumAsync(5)` inside a `checked` context.
- **Expected Result:** 
    - Service throws `OverflowException`.
    - Controller catches this and returns `422 Unprocessable Entity`.

---

## 4. Integration Test Suite (Calculator.Tests.Integration)

### IT-01: Successful POST (Record Creation)
- **Requirement Traced:** FR-01, FR-02
- **Preconditions:** SQLite database is initialized and empty.
- **Input Payload:** `POST /api/calculations` with `{"number1": 10, "number2": 20}`
- **Execution Steps:**
    1. Send POST request.
    2. Capture response.
- **Expected Result:** 
    - Status Code: `201 Created`.
    - Header `Location` contains `/api/calculations/{id}/sum`.
    - Body contains `id`, `number1: 10`, `number2: 20`.

### IT-02: Successful GET /sum
- **Requirement Traced:** FR-03, FR-04, FR-05, FR-06
- **Preconditions:** Record with ID 1 exists in SQLite (1, 1). Mock Vendor API is reachable and returns 1.
- **Input Payload:** `GET /api/calculations/1/sum`
- **Execution Steps:**
    1. Send GET request.
- **Expected Result:** 
    - Status Code: `200 OK`.
    - JSON Body: `{"recordId": 1, "number1": 1, "number2": 1, "mockValue": 1, "total": 3}`.

### IT-03: Persistence Verification (End-to-End)
- **Requirement Traced:** NFR-01 (Persistence)
- **Preconditions:** Clean SQLite DB.
- **Execution Steps:**
    1. POST `{"number1": 5, "number2": 5}`.
    2. Extract `id` from response.
    3. Restart/Re-instantiate `WebApplicationFactory` (simulating app restart).
    4. GET `/api/calculations/{id}/sum`.
- **Expected Result:** 
    - GET returns `200 OK`.
    - Data matches the POSTed values, proving persistence in SQLite.

### IT-04: 404 Not Found (Invalid ID)
- **Requirement Traced:** SRS Section 6.2
- **Preconditions:** Database does not contain ID 9999.
- **Input Payload:** `GET /api/calculations/9999/sum`
- **Execution Steps:**
    1. Send GET request.
- **Expected Result:** 
    - Status Code: `404 Not Found`.

### IT-05: 400 Bad Request (Malformed JSON)
- **Requirement Traced:** SRS Section 6.2
- **Preconditions:** API is running.
- **Input Payload:** `POST /api/calculations` with `{"number1": "invalid"}`
- **Execution Steps:**
    1. Send POST request.
- **Expected Result:** 
    - Status Code: `400 Bad Request`.

### IT-06: 415 Unsupported Media Type
- **Requirement Traced:** SRS Section 6.2
- **Preconditions:** API is running.
- **Input Payload:** `POST /api/calculations` with `Content-Type: text/plain`.
- **Execution Steps:**
    1. Send POST request.
- **Expected Result:** 
    - Status Code: `415 Unsupported Media Type`.

### IT-07: 422 Unprocessable Entity (Overflow)
- **Requirement Traced:** FR-06, SRS Section 9
- **Preconditions:** Record exists with `int.MaxValue`. Mock Vendor returns 1.
- **Input Payload:** `GET /api/calculations/{id}/sum`
- **Execution Steps:**
    1. Send GET request.
- **Expected Result:** 
    - Status Code: `422 Unprocessable Entity`.
    - Body contains error message regarding integer overflow.

### IT-08: 502 Bad Gateway (Mock Service Down)
- **Requirement Traced:** SRS Section 6.4, IT-07/IT-08 Alignment
- **Preconditions:** `MockVendorClient` receives a `SocketException` or `503` from the vendor.
- **Execution Steps:**
    1. Mock the `HttpClient` to simulate connection failure to MockVendor.Api.
    2. GET `/api/calculations/1/sum`.
- **Expected Result:** 
    - Status Code: `502 Bad Gateway`.

### IT-09: 503 Service Unavailable (SQLite DB Unavailable)
- **Requirement Traced:** SRS Section 9 (IT-09)
- **Preconditions:** Simulate SQLite file lock or connection string failure.
- **Execution Steps:**
    1. Configure `AppDbContext` with an invalid file path or simulate a `SqliteException`.
    2. GET `/api/calculations/1/sum`.
- **Expected Result:** 
    - Status Code: `503 Service Unavailable`.

### IT-10: 504 Gateway Timeout (Mock Timeout)
- **Requirement Traced:** SRS Section 9 (IT-10)
- **Preconditions:** Mock Vendor API takes > 10 seconds to respond (exceeding configured timeout).
- **Execution Steps:**
    1. Mock the `HttpClient` to delay response by 15 seconds.
    2. GET `/api/calculations/1/sum`.
- **Expected Result:** 
    - Status Code: `504 Gateway Timeout`.

### IT-11: 502 Bad Gateway (Malformed Vendor JSON)
- **Requirement Traced:** SRS Section 9 (IT-11)
- **Preconditions:** Mock Vendor returns invalid JSON (e.g., `{"value": "not-an-int"}` or plain text).
- **Execution Steps:**
    1. Mock Vendor response with malformed content.
    2. GET `/api/calculations/1/sum`.
- **Expected Result:** 
    - Status Code: `502 Bad Gateway`.

### IT-12: Swagger & Health Check Verification
- **Requirement Traced:** SRS Section 9 (IT-12)
- **Preconditions:** Application is running in Development/Staging.
- **Execution Steps:**
    1. GET `/swagger/v1/swagger.json`.
    2. GET `/health`.
- **Expected Result:** 
    - `/swagger/v1/swagger.json` returns `200 OK` with valid OpenAPI spec.
    - `/health` returns `200 OK` with status `Healthy`.

---

## 5. Database State Verification Logic
For all Integration Tests (IT-01 through IT-11), the following state verification is performed:
1. **Isolation:** Each test class uses a unique SQLite filename `test_{Guid}.db`.
2. **Cleanup:** The database file is deleted in the `Dispose()` method of the test class.
3. **Integrity:** Tests querying the database directly via a separate `AppDbContext` instance to verify that the API actually persisted the data to the physical file and did not just return the object from memory.