# XUnit Test Specifications: BCFC Mini SME Back-Office Banking Portal (.NET 8 / C#)

## 1. Test Suite Architecture
- **Framework**: XUnit with FluentAssertions, Moq, and Microsoft.AspNetCore.Mvc.Testing.
- **Test Categories**: Unit Tests (Services, SLA Engine), Integration Tests (Controllers, EF Core SQLite Repositories).

## 2. Test Cases

### TC-01: SLA Engine TAT Calculation (Happy Path & Thresholds)
- **Description**: Verify `SlaEngine` correctly evaluates 24.0-hour SLA benchmarks.
- **Input / Setup**: 
  - Remaining time ≥ 6h.
  - Remaining time < 6h.
  - Elapsed time > 24h.
- **Expected Assertions**: 
  - Returns status `ON_TRACK` with Green badge indicator.
  - Returns status `WARNING` with Amber badge indicator.
  - Returns status `BREACHED` with Red alert badge indicator.

### TC-02: Banksmart Proxy Envelope Formatting & Casing
- **Description**: Verify request headers and envelope casing rules are strictly applied.
- **Input / Setup**: 
  - Standard API call (Facility Overview) and Outward Payment API call.
- **Expected Assertions**: 
  - Headers include `User-Agent: PostmanRuntime/7.39.0`, `Accept: */*`, and Basic Auth.
  - `SignOnRq` uses PascalCase for standard APIs and `signOnRq` uses camelCase for Outward Payment.
  - `LogId` is a valid dynamic UUID v4 and `DateTime` format excludes trailing 'Z'.

### TC-03: Case 1 Overdue Pre-Maturity Data Ingestion
- **Description**: Query CIF 50000248 (Sample Customer A) with 141 DPD.
- **Input / Setup**: `POST /api/banksmart/loans` for CIF `50000248`.
- **Expected Assertions**: 
  - HTTP 200 OK.
  - Returns sub-loan `500002480026` with correct `oustandingBalance`, `oustandingProfit`, and DPD status.

### TC-04: Case 2 Overdue Post-Maturity Data Ingestion
- **Description**: Query CIF 50000231 (Sample Customer B) with 65 DPD bullet repayment default.
- **Input / Setup**: `POST /api/banksmart/loans` for CIF `50000231`.
- **Expected Assertions**: 
  - HTTP 200 OK.
  - Returns matured loan account `500002310050` with bullet repayment structure.

### TC-05: Case 3 Multi-Loan Facility Handling
- **Description**: Query CIF 50000248 facility with two running sub-loans.
- **Input / Setup**: `POST /api/banksmart/schedule` for multi-loan facility.
- **Expected Assertions**: 
  - HTTP 200 OK.
  - Correctly parses 3-month and 4-month tenors and payment schedules without spelling correction errors (`scheduler` property).

### TC-06: Case 4 Active Origination Wizard Flow
- **Description**: Execute 4-gate Murabaha origination wizard for CIF 50000231.
- **Input / Setup**: 
  - Gate 1: Limit verification (`/api/banksmart/facilities`).
  - Gate 2: Inventory booking (`/api/banksmart/inventory`) with `invoiceDate: "2031-08-01T00:00:00+08:00"`.
  - Gate 3: Disbursement (`/api/banksmart/disburse`).
  - Gate 4: Payout (`/api/banksmart/payout`).
- **Expected Assertions**: 
  - Each step returns `status.code == "MSG-000000"`.
  - Generates correct loan account `500002480028` and deal ref `LN-2026-001`.