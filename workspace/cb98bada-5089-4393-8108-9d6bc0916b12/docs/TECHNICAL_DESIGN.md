# Technical Design Document: BCFC Mini SME Back-Office Banking Portal (C# / .NET 8 Web API)

## 1. Architectural Overview & Framework Alignment
- **Target Framework**: ASP.NET Core Web API (.NET 8) with C# 12, Entity Framework Core, and SQLite persistence.
- **Architecture Pattern**: Clean Architecture with Controllers, DTOs, Services, Repositories, Domain Models, and EF Core DbContext.
- **Design Enforcement**: Zero AI / LLM / Copilot components. Fully aligned with the BankSmart Core Platform Sandbox and Financing Flow API Integration Guide v1.0.

## 2. Module Boundaries & Components
- **Controllers (`Controllers/`)**: 
  - `BanksmartProxyController.cs`: Proxies requests to BankSmart core endpoints (`/api/Corporate/FacilityOverview`, `/api/Loan/BookInventoryMurahaba`, `/api/Loan/MurahabaDisbursement`, `/api/Loan/OutWardPaymentAfterDisbursement`, `/api/Corporate/LoanDetails`, `/api/Corporate/LoanSchedule`). Injects required headers (`User-Agent: PostmanRuntime/7.39.0`, `Accept: */*`, Basic Auth).
  - `OperationsStateController.cs`: Manages operational state store and maker-checker pipeline (`GET`/`POST`).
- **Services (`Services/`)**: 
  - `IBanksmartService.cs` / `BanksmartService.cs`: Implements envelope signing, dynamic UUID v4 `LogId`, ISO 8601 formatting without trailing 'Z', case-sensitive `signOnRq` handling for Outward Payment, and specific payload workarounds (e.g., `invoiceDate: "2031-08-01T00:00:00+08:00"`).
  - `ISlaEngine.cs` / `SlaEngine.cs`: 24-hour SLA TAT calculation engine (`ON_TRACK`, `WARNING`, `BREACHED`).
- **Models & DTOs (`Models/`, `DTOs/`)**: Entity definitions preserving exact backend spellings (`oustandingBalance`, `oustandingProfit`, `nextInstalmentDate`, `defferAccount`, `scheduler`, `Productid`, `BookInventoryMurahaba`).
- **Data Access (`Data/`)**: `BcfcDbContext.cs` configured for SQLite persistence.

## 3. Database Schema & Entities
- **FacilityEntity**: `FacilityId` (PK), `ClientId`, `ReferenceId`, `Status`, `ApprovedLimit`, `UtilizedLimit`, `AvailableLimit`, `CurrencyId`, `ProductID`, `SecurityAccount`, `AdvanceAccount` (sweep account).
- **LoanEntity**: `AccountId` (PK), `FacilityId`, `ClientId`, `DealId`, `DealRefNo`, `LoanAmount`, `OutstandingBalance`, `OutstandingProfit`, `TrxAccountId`, `TotalInstallments`, `PaidInstallments`, `RemainingInstallments`, `NextInstallmentDate`, `NextInstallmentAmount`, `MonthlyPayment`, `InterestRate`.
- **TransactionStateEntity**: `Id` (PK), `DealRefNo`, `ClientId`, `NewStage`, `ActionLabel`, `CreatedAt`, `SlaDeadline`.

## 4. API Specification & Payloads
- **POST /api/banksmart/facilities**: Client facility overview lookup.
- **POST /api/banksmart/inventory**: Commodity title booking (`BookInventoryMurahaba`) with `InvoiceDate` alignment.
- **POST /api/banksmart/disburse**: Murabaha financing contract execution (`MurabahaDisbursement`) fixing profit margin (11%).
- **POST /api/banksmart/payout**: Outward settlement (`OutWardPaymentAfterDisbursement`) requiring lowercase `signOnRq` envelope.
- **POST /api/banksmart/loans**: Active sub-loans lookup (`LoanDetails`).
- **POST /api/banksmart/schedule**: Installment amortization breakdown (`LoanSchedule`).