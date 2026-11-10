# XUnit Test Specifications: BankSmart Core Platform Financing Flow API

## 1. Test Overview
This test suite validates the ASP.NET Core Web API implementation against all functional requirements, edge cases, error states, payload contracts, and irregular property spellings specified in the integration guide.

---

## 2. Test Cases

### 2.1 Facility Overview (`POST /api/Corporate/FacilityOverview`)
- **TC-FO-01 (Happy Path)**:
  - Input: Valid `SignOnRq` and `clientID` (`50000231`).
  - Assertions: HTTP 200, `status.code == "MSG-000000"`, content is a non-empty array containing facility `PK8xduPqjbt3gWLiphpWLcas4`, `status == "Active"`, approved limit `1500000.0000`, and `advanceAccount == "500002310049"`.
- **TC-FO-02 (Invalid Client ID / Not Found)**:
  - Input: Non-existent `clientID` (`99999999`).
  - Assertions: HTTP 400, `status.code != "MSG-000000"`, `status.severity == "Error"`, `content == null`.

### 2.2 Book Inventory (`POST /api/Loan/BookInventoryMurahaba`)
- **TC-BI-01 (Happy Path)**:
  - Input: Valid booking payload (`InvoiceNo: "INV-13042031-001"`, `ReferenceNo: "REF-13042031-001"`, `Amount: 15000.0000`).
  - Assertions: HTTP 200, `status.code == "MSG-000000"`, content returns echoed `referenceNo == "REF-13042031-001"`, valid `scrollNo` and `channelRefID` (GUID).
- **TC-BI-02 (Missing Mandatory Fields)**:
  - Input: Missing `Amount` or `InvoiceNo`.
  - Assertions: HTTP 400, `status.code` indicates payload validation error (`ERR-1000162`), `content == null`.

### 2.3 Murabaha Disbursement (`POST /api/Loan/MurahabaDisbursement`)
- **TC-MD-01 (Happy Path)**:
  - Input: Valid disbursement payload referencing booked inventory `REF-13042031-001`, facility `PK8xduPqjbt3gWLiphpWLcas4`, amount `15000`, tenure `"30 D"`, profit rate `11`.
  - Assertions: HTTP 200, `status.code == "MSG-000000"`, content returns `referenceNo` (Deal reference), `loanAccount` (`500002310062`), `trxAccount`, `defferAccount`, and `schedule` array with 1 installment (`installment: 15135.62`).
- **TC-MD-02 (Inactive Facility Error)**:
  - Input: Disbursement against an inactive facility (`referenceID: "20291204-50000231-0001"`).
  - Assertions: HTTP 400, `status.code` indicates error, `content == null`.

### 2.4 Outward Payment (`POST /api/Loan/OutWardPaymentAfterDisbursement`)
- **TC-OP-01 (Happy Path)**:
  - Input: `signOnRq` (camelCase), `refNo` (deal reference from disbursement), `beneficiaryList` with amount `15000.0`.
  - Assertions: HTTP 200, `status.code == "MSG-000000"`, content returns `channelRefID` confirming payout posting.
- **TC-OP-02 (Invalid Deal Reference)**:
  - Input: Non-existent or already paid `refNo`.
  - Assertions: HTTP 400, `status.code` indicates error, `content == null`.

### 2.5 Loan Details (`POST /api/Corporate/LoanDetails`)
- **TC-LD-01 (Happy Path & List Handling)**:
  - Input: `clientID: "50000231"`, `facilityID: "PK8xduPqjbt3gWLiphpWLcas4"`.
  - Assertions: HTTP 200, `status.code == "MSG-000000"`, content returns array of loan accounts containing exact irregular field names (`oustandingBalance`, `oustandingProfit`, `nextInstalmentDate`).
- **TC-LD-02 (Multiple Active Financings - Case 3)**:
  - Input: Customer A (`50000248`, facility `50jiNi89cs5cLRnFnyU9aZ3s5`).
  - Assertions: HTTP 200, returns multiple active financing accounts correctly mapped with respective balances and installment counts.

### 2.6 Loan Schedule (`POST /api/Corporate/LoanSchedule`)
- **TC-LS-01 (Happy Path)**:
  - Input: Valid `dealId` (Deal reference).
  - Assertions: HTTP 200, `status.code == "MSG-000000"`, content returns deal details and `scheduler` array with items (`repaymentDate`, `principalAmount`, `toDateProfit`, `instAmount`, `isPaid`).

### 2.7 Security & Authentication
- **TC-AUTH-01 (Unauthorized Access)**:
  - Input: Any API call without `Authorization: Basic` header.
  - Assertions: HTTP 401 Unauthorized.
