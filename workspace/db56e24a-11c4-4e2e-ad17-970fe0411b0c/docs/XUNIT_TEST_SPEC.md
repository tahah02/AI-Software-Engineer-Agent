# XUnit Test Specification: AAISE 2+2+1 Calculation API

**Version:** 1.0  
**Status:** Approved for Implementation  
**Target:** `Calculator.Tests`

---

## 1. Test Execution Strategy
All tests are executed using the .NET 8 SDK. The test suite is designed to be deterministic, isolated, and ephemeral.

**Execution Command:**
```bash
dotnet test --configuration Release
```

---

## 2. Unit Tests (`Calculator.Tests.Unit`)

### UT-01: Calculate_ValidInputs_ReturnsCorrectSum
*   **Preconditions:** `CalculationService` injected with mocked `ICalculationRepository` and `MockVendorClient`.
*   **Input:** `Number1: 1, Number2: 1`, Mock returns `1`.
*   **Steps:** Invoke `CalculationService.GetSumAsync(id)`.
*   **Assertions:** `Assert.Equal(3, result.Total)`.

### UT-02: Calculate_LargeInputs_ReturnsCorrectSum
*   **Preconditions:** Mock returns `1`.
*   **Input:** `Number1: 2, Number2: 3`.
*   **Steps:** Invoke service.
*   **Assertions:** `Assert.Equal(6, result.Total)`.

### UT-03: Calculate_ZeroInputs_ReturnsCorrectSum
*   **Preconditions:** Mock returns `1`.
*   **Input:** `Number1: 0, Number2: 0`.
*   **Steps:** Invoke service.
*   **Assertions:** `Assert.Equal(1, result.Total)`.

### UT-04: Calculate_NegativeInputs_ReturnsCorrectSum
*   **Preconditions:** Mock returns `1`.
*   **Input:** `Number1: -2, Number2: 5`.
*   **Steps:** Invoke service.
*   **Assertions:** `Assert.Equal(4, result.Total)`.

### UT-05: Post_InvalidModel_ReturnsBadRequest
*   **Preconditions:** None.
*   **Input:** `{"number1": "abc", "number2": 1}`.
*   **Steps:** Controller model validation.
*   **Assertions:** `Assert.IsType<BadRequestObjectResult>`.

### UT-06: MockClient_ParsesValidJson
*   **Preconditions:** `HttpClient` configured with `HttpMessageHandler` returning `{"value": 1}`.
*   **Input:** N/A.
*   **Steps:** `MockVendorClient.GetMockValueAsync()`.
*   **Assertions:** `Assert.Equal(1, value)`.

### UT-07: Calculate_Overflow_Returns422
*   **Preconditions:** Mock returns `1`.
*   **Input:** `Number1: Int32.MaxValue, Number2: 1`.
*   **Steps:** Service calculation.
*   **Assertions:** `Assert.Throws<OverflowException>` mapped to `422 Unprocessable Entity`.

### UT-08: CreatedBy_Identity_Mapping (Placeholder for future Auth)
*   **Preconditions:** Mock identity context.
*   **Assertions:** Verify identity propagation.

### UT-09: Nullable_Fields_Initialization
*   **Preconditions:** New `CalculationRecord`.
*   **Assertions:** Verify defaults are null/zero as per schema.

### UT-10: Duplicate_Email_Conflict (N/A for this scope)
*   **Status:** Skipped (Out of scope for Calculation API).

### UT-11: Database_Exception_Handling
*   **Preconditions:** Repository throws `DbUpdateException`.
*   **Assertions:** Verify `503 Service Unavailable`.

### UT-12: String_Sanitization (N/A for this scope)
*   **Status:** Skipped (Numeric only).

---

## 3. Integration Tests (`Calculator.Tests.Integration`)

### IT-01: POST_Calculations_Returns201
*   **Preconditions:** Clean SQLite file.
*   **Input:** `{"number1": 1, "number2": 1}`.
*   **Steps:** `POST /api/calculations`.
*   **Assertions:** `201 Created`, `Location` header present.

### IT-02: GET_Sum_Returns200_And_Total3
*   **Preconditions:** Record `1` exists in DB.
*   **Steps:** `GET /api/calculations/1/sum`.
*   **Assertions:** `200 OK`, `total: 3`.

### IT-03: GET_Sum_Persisted_2_3_Returns6
*   **Preconditions:** Record `2` exists with values `2, 3`.
*   **Steps:** `GET /api/calculations/2/sum`.
*   **Assertions:** `200 OK`, `total: 6`.

### IT-04: Mock_HTTP_Endpoint_Verification
*   **Preconditions:** Mock service running.
*   **Steps:** `GET /api/mock/value`.
*   **Assertions:** `200 OK`, `{"value": 1}`.

### IT-05: Unknown_ID_Returns404
*   **Steps:** `GET /api/calculations/999/sum`.
*   **Assertions:** `404 Not Found`.

### IT-06: Invalid_Create_Body_Returns400
*   **Input:** `{"number1": "invalid"}`.
*   **Assertions:** `400 Bad Request`.

### IT-07: Mock_Service_Unavailable_Returns502
*   **Preconditions:** Mock service port closed.
*   **Assertions:** `502 Bad Gateway`.

### IT-08: Mock_Timeout_Returns504
*   **Preconditions:** Mock service configured to delay response > 5s.
*   **Assertions:** `504 Gateway Timeout`.

### IT-09: SQLite_Unavailable_Returns503
*   **Preconditions:** DB file locked/inaccessible.
*   **Assertions:** `503 Service Unavailable`.

### IT-10: Repeated_GET_Same_ID
*   **Steps:** Call `GET` twice.
*   **Assertions:** Result remains identical; no mutation.

### IT-11: Malformed_Vendor_JSON_Returns502
*   **Preconditions:** Mock returns `{"value": "error"}`.
*   **Assertions:** `502 Bad Gateway`.

### IT-12: Swagger_And_Health_Check
*   **Steps:** `GET /health`.
*   **Assertions:** `200 OK`.

### IT-13: Atomicity_Verification
*   **Steps:** Force failure during transaction.
*   **Assertions:** DB count remains unchanged.

### IT-14: Database_Persistence_Verification
*   **Steps:** Query SQLite directly after `POST`.
*   **Assertions:** `SELECT count(*) FROM CalculationRecords` == 1.