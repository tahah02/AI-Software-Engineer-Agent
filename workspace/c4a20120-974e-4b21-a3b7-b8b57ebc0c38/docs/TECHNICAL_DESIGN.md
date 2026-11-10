# Technical Design Document: BCFC Mini SME Back-Office Banking Portal (.NET C# Backend Proxy & State Engine)

## 1. Architecture Overview
The BCFC Mini SME Back-Office Banking Portal is built on an ASP.NET Core Web API backend implementing a clean architectural separation: Controllers, DTOs, Services, Models, Entity Framework Core DbContext, and SQLite persistence. It integrates directly with the BankSmart Core Platform Sandbox (`http://api-apacsbx.dbgsonline.com:8003`) utilizing HTTP Basic Authentication (`Vendor5:P@ssw0rd5`) and acts as an enterprise middle-office store with an SLA computation engine.

### 1.1 Technology Stack
- **Framework:** ASP.NET Core 8.0 Web API
- **Language:** C# 12
- **Database/ORM:** Entity Framework Core with SQLite (`bcfc_operations.db`)
- **Authentication:** HTTP Basic Auth & Role-Based Access Control (Personas: OPS-4091, RM-1042, CR-8820 with PIN '654321')
- **Testing:** XUnit, FluentAssertions, Moq

---

## 2. Module Boundaries & Services

### 2.1 BankSmartProxyService
Responsible for proxying requests to the 6 BankSmart Core endpoints:
1. `POST /api/Corporate/FacilityOverview`
2. `POST /api/Loan/BookInventoryMurahaba`
3. `POST /api/Loan/MurahabaDisbursement`
4. `POST /api/Payment/OutwardPayment` (Requires lowercase `signOnRq` property casing)
5. `POST /api/Corporate/LoanDetails`
6. `POST /api/Corporate/LoanSchedule`

*Handling Nuances:* 
- Dynamic UUID v4 generation for `LogId` / `logId`.
- UTC/ISO 8601 formatting without 'Z' for `DateTime`.
- Calendar sync enforcing `invoiceDate: "2031-08-01T00:00:00+08:00"` for commodity bookings to avoid `ERR-1000308`.

### 2.2 OperationalStoreService & SLA Engine
- Manages pending maker-checker transactions, metrics, and overdue watchlists.
- Computes 24-hour SLA turnaround times (TAT):
  - `ON_TRACK`: $\ge 6$ hours remaining
  - `WARNING`: $< 6$ hours remaining
  - `BREACHED`: $> 24$ hours elapsed

---

## 3. Database Schema & Entities (EF Core SQLite)

### 3.1 Entities
- **TransactionQueueEntity**: Id, LogId, Cif, FacilityId, StepName, PayloadJson, Status, CreatedAt, UpdatedAt, SlaStatus
- **CustomerEntity**: Cif, CustomerName, RiskStage, RmId
- **FacilityEntity**: FacilityId, Cif, ReferenceId, Status, ApprovedLimit, UtilizedLimit, AvailableLimit, CurrencyId, ProductId, SecurityAccount, AdvanceAccount
- **LoanEntity**: AccountID, DealRefNo, Cif, FacilityId, LoanAmount, OutstandingBalance, OutstandingProfit, Status, Dpd

---

## 4. API Endpoints & Request/Response Contracts

### 4.1 Proxy Endpoints
- `POST /api/banksmart/facilities` -> Proxies to `/api/Corporate/FacilityOverview`
- `POST /api/banksmart/inventory` -> Proxies to `/api/Loan/BookInventoryMurahaba`
- `POST /api/banksmart/disburse` -> Proxies to `/api/Loan/MurahabaDisbursement`
- `POST /api/banksmart/payout` -> Proxies to `/api/Payment/OutwardPayment`
- `POST /api/banksmart/loans` -> Proxies to `/api/Corporate/LoanDetails`
- `POST /api/banksmart/schedule` -> Proxies to `/api/Corporate/LoanSchedule`

### 4.2 Operations & State Endpoints
- `GET /api/operations/state` -> Returns current queue, SLA metrics, and watchlists for the 4 official test cases.
- `POST /api/operations/state` -> Creates or advances a maker-checker transaction stage.
