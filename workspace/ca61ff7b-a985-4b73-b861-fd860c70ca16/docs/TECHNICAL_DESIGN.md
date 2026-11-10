# Technical Design Document: BCFC Mini SME Back-Office Banking Portal (.NET C# Backend)

## 1. Architectural Overview
The BCFC Mini SME Back-Office Banking Portal is structured using an ASP.NET Core Web API backend implementing Clean Architecture principles (Controllers, Services, DTOs, EF Core, and SQLite persistence) combined with strict server-side gateway isolation to interface with the BankSmart Core Ledger Sandbox.

### Core Technology Stack
- **Backend Framework**: ASPNET Core 8.0 Web API (.NET C#)
- **Persistence**: Entity Framework Core with SQLite
- **HTTP Client**: Typed `HttpClient` configured with upstream BankSmart headers
- **Data Interchange**: JSON with PascalCase and specific legacy spellings (`oustandingBalance`, `oustandingProfit`, `nextInstalmentDate`, `defferAccount`)

---

## 2. Module Boundaries & Directory Structure

```text
src/
├── Controllers/
│   ├── BanksmartController.cs
│   └── OperationsController.cs
├── Models/
│   ├── Entities/
│   │   ├── TransactionEntity.cs
│   │   └── AuditLogEntity.cs
│   └── Dtos/
│       ├── SignOnRequestDto.cs
│       ├── FacilityOverviewDto.cs
│       ├── InventoryBookingDto.cs
│       ├── DisbursementDto.cs
│       ├── OutwardPaymentDto.cs
│       ├── LoanDetailsDto.cs
│       ├── LoanScheduleDto.cs
│       └── OperationsStateDto.cs
├── Services/
│   ├── IBankSmartGatewayService.cs
│   ├── BankSmartGatewayService.cs
│   ├── IOperationalStoreService.cs
│   └── OperationalStoreService.cs
├── Data/
│   └── BankingDbContext.cs
└── Program.cs
```

---

## 3. Database Schema (SQLite via EF Core)

### `Transactions` Table
- `Id` (TEXT, Primary Key, UUID v4)
- `ClientReference` (TEXT)
- `FacilityId` (TEXT)
- `DealReference` (TEXT, Nullable)
- `LoanAccountNumber` (TEXT, Nullable)
- `CurrentStage` (TEXT) - Values: `FACILITY_APPROVED`, `INVENTORY_PENDING`, `MURABAHA_PENDING`, `PAYOUT_PENDING`, `SETTLED`
- `Amount` (REAL)
- `SubmittedAt` (TEXT, ISO 8601 without 'Z')
- `ActionLabel` (TEXT)

---

## 4. API Endpoints & Request/Response Payloads

### 4.1 BankSmart Proxy Endpoints

#### POST `/api/banksmart/facilities`
- **Payload**: `{ "clientID": "50000248" }`
- **Envelope**: `SignOnRq` with `LogId` (UUID v4), `DateTime` (ISO 8601 w/o 'Z'), `ChannelId: "0"`, `OurBranchId: "01"`
- **Response**: Facility limits, utilized headroom, expiry dates, sweep accounts.

#### POST `/api/banksmart/inventory`
- **Payload**: `{ "facilityID": "...", "amount": 150000.0, "invoiceDate": "2031-08-01T00:00:00+08:00", "brokerID": "BRK-001" }`
- **Note**: Mandatory `2031-08-01` date to bypass `ERR-1000308`.

#### POST `/api/banksmart/disburse`
- **Payload**: Murabaha sale parameters generating sub-loan `500002480028` and deal reference `LN-2026-001`.

#### POST `/api/banksmart/payout`
- **Payload**: Outward payment settlement. Requires lowercase `signOnRq` root envelope property.

#### POST `/api/banksmart/loans`
- **Payload**: `{ "clientID": "50000248" }`
- **Response**: Active sub-loans, principal balance, `oustandingProfit`, `nextInstalmentDate`, DPD.

#### POST `/api/banksmart/schedule`
- **Payload**: `{ "dealReference": "LN-2026-001" }`
- **Response**: Repayment schedule amortization with principal, profit allocation, clearance flags.

### 4.2 Operations & SLA State Engine

#### GET `/api/operations/state`
- **Response**: Returns `{ "metrics": { ... }, "transactions": [ ... ], "overdueWatchlist": [ ... ], "multiLoanFacilities": [ ... ] }`

#### POST `/api/operations/state`
- **Payload**: `{ "id": "uuid", "newStage": "INVENTORY_PENDING", "actionLabel": "Reserve Commodity" }`

---

## 5. Security & Upstream Gateway Protocols
- **Credentials**: Stored in `appsettings.json` or environment variables as `Vendor5:[REDACTED_PASSWORD]`.
- **Headers Injected**: `User-Agent: PostmanRuntime/7.39.0`, `Accept: */*`, `Authorization: Basic VmVuZG9yNTpQQHNzdzByZDU=`.
- **DateTime Formatting**: `DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fff")` (No trailing 'Z').