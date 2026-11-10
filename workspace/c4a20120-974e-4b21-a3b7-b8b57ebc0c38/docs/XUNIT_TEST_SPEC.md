# XUnit Test Specifications: BCFC Mini SME Back-Office Banking Portal

## 1. Test Suite Overview
All tests are implemented using XUnit, FluentAssertions, and Moq targeting the ASP.NET Core Web API solution. Tests validate happy paths, edge cases, error states, payload formatting, and exact casing requirements for BankSmart integration.

---

## 2. Test Cases Specification

### 2.1 BankSmart Gateway Proxy Tests
- **Test_FacilityOverview_Success**: 
  - *Given* valid CIF `50000231` and PascalCase `SignOnRq`.
  - *When* `POST /api/banksmart/facilities` is invoked.
  - *Then* returns HTTP 200, status code `MSG-000000`, and maps facility `PK8xduPqjbt3gWLiphpWLcas4` with `Active` status and correct limits.

- **Test_OutwardPayment_LowercaseSignOnRq_Success**:
  - *Given* valid deal reference and camelCase `signOnRq` payload.
  - *When* `POST /api/banksmart/payout` is invoked.
  - *Then* successfully proxies to BankSmart core and returns channel reference ID without payload validation error `ERR-1000162`.

- **Test_BookInventory_CalendarSync_Success**:
  - *Given* commodity booking request with `invoiceDate: "2031-08-01T00:00:00+08:00"`.
  - *When* `POST /api/banksmart/inventory` is invoked.
  - *Then* bypasses `ERR-1000308` and returns generated `referenceNo`.

### 2.2 Operational Store & SLA Engine Tests
- **Test_SlaEngine_OnTrack**:
  - *Given* a transaction created 2 hours ago.
  - *When* SLA status is computed.
  - *Then* returns `ON_TRACK`.

- **Test_SlaEngine_Warning**:
  - *Given* a transaction created 20 hours ago.
  - *When* SLA status is computed.
  - *Then* returns `WARNING`.

- **Test_SlaEngine_Breached**:
  - *Given* a transaction created 26 hours ago.
  - *When* SLA status is computed.
  - *Then* returns `BREACHED`.

### 2.3 Ground Truth Persona & Scenario Tests
- **Test_Case1_PreMaturityOverdue_CustomerA**:
  - *Given* Customer A (CIF `50000248`), Facility `20301022-50000248-0001`, Loan `500002480026`.
  - *When* loan details and schedule are retrieved.
  - *Then* verifies 141 DPD overdue installments, Outstanding PKR 27,000, and Overdue Profit PKR 1,420.50 displayed in Credit Risk Stage 2/3 Watchlist.

- **Test_Case2_PostMaturityDefault_CustomerB**:
  - *Given* Customer B (CIF `50000231`), Facility `20301209-50000231-0003`, Loan `500002310050`.
  - *When* loan details are evaluated.
  - *Then* verifies 65 DPD bullet repayment default with Principal Due PKR 327,563.37.

- **Test_Case3_MultiLoanFacility_CustomerA**:
  - *Given* Customer A (CIF `50000248`), master facility `20301022-50000248-0001`.
  - *When* querying active sub-loans (`500002480026` and `500002480027`).
  - *Then* verifies concurrent running sub-loans in Customer 360 Explorer.

- **Test_Case4_LiveOriginationWizard**:
  - *Given* Customer B (CIF `50000231`), Facility `20301209-50000231-0003`, requested financing PKR 350,000.
  - *When* executing the 4-Gate Murabaha Origination (Gate 1 Limit Check -> Gate 2 Commodity Booking -> Gate 3 Deal Execution -> Gate 4 Outward Payout -> Gate 5 Completion Certificate).
  - *Then* verifies successful end-to-end posting with generated loan account and payout transaction reference.
