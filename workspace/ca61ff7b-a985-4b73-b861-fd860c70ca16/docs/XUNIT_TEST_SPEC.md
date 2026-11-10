# XUnit Test Specifications: BCFC Mini SME Back-Office Banking Portal (.NET C#)

## 1. Overview
This document specifies the complete test suite to be implemented using XUnit and Moq for the ASP.NET Core Web API backend. Tests validate security isolation, request envelope formatting, calendar synchronization, operational state transitions, and SLA calculations.

---

## 2. Test Suites & Test Cases

### Test Suite 1: BankSmart Gateway Proxy Tests (`BankSmartControllerTests.cs`)

#### Test Case 1.1: Facility Overview Success
- **Method**: `GetFacilityOverview_ReturnsSuccessAndPayload`
- **Description**: Verifies `POST /api/banksmart/facilities` successfully forwards requests with proper headers and parses `MSG-000000` response.
- **Assertions**: `HttpStatusCode.OK`, response status code equals `MSG-000000`.

#### Test Case 1.2: Inventory Booking Calendar Sync
- **Method**: `BookInventory_With2031Date_ReturnsSuccess`
- **Description**: Validates that passing `invoiceDate` set to `2031-08-01T00:00:00+08:00` avoids `ERR-1000308`.
- **Assertions**: `HttpStatusCode.OK`, no error code returned.

#### Test Case 1.3: Outward Payment Lowercase Envelope Casing
- **Method**: `OutwardPayment_UsesLowercaseSignOnRq`
- **Description**: Confirms API 4 serializes the root envelope strictly as lowercase `signOnRq`.
- **Assertions**: Serialized request JSON string contains `"signOnRq"` and lacks `"SignOnRq"`.

#### Test Case 1.4: Reverse Proxy Header Injection
- **Method**: `BankSmartClient_InjectsRequiredHeaders`
- **Description**: Asserts outbound `HttpClient` requests include `User-Agent: PostmanRuntime/7.39.0` and Basic Authorization header.
- **Assertions**: Request message headers contain expected `User-Agent` and `Authorization` values.

---

### Test Suite 2: DateTime & Model Binding Tests (`DateTimeBindingTests.cs`)

#### Test Case 2.1: ISO 8601 Without Trailing Z
- **Method**: `LogIdDateTime_FormatWithoutZ_SucceedsModelBinding`
- **Description**: Verifies `DateTime` strings generated for `SignOnRq` omit the 'Z' suffix to satisfy ASP.NET Core binder and avoid `ERR-1000162`.
- **Assertions**: String does not end with 'Z' and matches `yyyy-MM-ddTHH:mm:ss.fff` format.

---

### Test Suite 3: Operational State & SLA Engine Tests (`OperationsEngineTests.cs`)

#### Test Case 3.1: State Retrieval Hydration
- **Method**: `GetOperationsState_ReturnsHttp200AndValidMetrics`
- **Description**: Tests `GET /api/operations/state` returns complete hydrated payload including metrics, transactions, and overdue watchlists.
- **Assertions**: `HttpStatusCode.OK`, non-null metrics object.

#### Test Case 3.2: SLA TAT Calculation - On Track
- **Method**: `CalculateSlaStatus_RemainingGreaterThanOrEqual6h_ReturnsOnTrack`
- **Description**: Verifies SLA engine assigns `ON_TRACK` (Green badge) when remaining duration is $\ge$ 6 hours.
- **Assertions**: SLA badge status equals `ON_TRACK`.

#### Test Case 3.3: SLA TAT Calculation - Warning
- **Method**: `CalculateSlaStatus_RemainingLessThan6h_ReturnsWarning`
- **Description**: Verifies SLA engine assigns `WARNING` (Amber badge) when remaining duration is $<$ 6 hours.
- **Assertions**: SLA badge status equals `WARNING`.

#### Test Case 3.4: SLA TAT Calculation - Breached
- **Method**: `CalculateSlaStatus_ElapsedGreaterThan24h_ReturnsBreached`
- **Description**: Verifies SLA engine assigns `BREACHED` (Red badge) when elapsed duration exceeds 24 hours.
- **Assertions**: SLA badge status equals `BREACHED`.