# Technical Design Document: BankSmart Core Platform Financing Flow API Integration

## 1. Architecture Overview
This document defines the technical specifications for implementing the BankSmart Core Platform Financing Flow APIs using **ASP.NET Core Web API (.NET C#)** with **Entity Framework (EF) Core** and **SQLite** persistence.

The system implements six core endpoints supporting Murabaha (MURFIN) financing flows:
1. `POST /api/Corporate/FacilityOverview`
2. `POST /api/Loan/BookInventoryMurahaba`
3. `POST /api/Loan/MurahabaDisbursement`
4. `POST /api/Loan/OutWardPaymentAfterDisbursement`
5. `POST /api/Corporate/LoanDetails`
6. `POST /api/Corporate/LoanSchedule`

### 1.1 Module Boundaries
- **Controllers**: Handle HTTP routing, basic authentication validation, and request parsing.
- **Services**: Contain business logic, validation rules, identifier mapping, and state management.
- **Models / EF Core DbContext**: Entity models mapped to SQLite database tables.
- **DTOs**: Strict representation of external request and response contracts, preserving exact field names and irregular property spellings (`oustandingBalance`, `oustandingProfit`, `defferAccount`, `scheduler`, `Productid`, etc.).

---

## 2. Database Schema & Models

### 2.1 Entities
- **Facility**: Represents approved credit limits for a Customer Information File (CIF).
- **InventoryBooking**: Represents booked inventory for disbursements.
- **FinancingDeal**: Represents a disbursed loan/deal, accounts, status, and terms.
- **PaymentScheduleItem**: Represents individual repayment installments.
- **OutwardPayment**: Records disbursement payouts to beneficiaries.

### 2.2 Entity Framework Core Context (`BankSmartDbContext`)
```csharp
using Microsoft.EntityFrameworkCore;

public class BankSmartDbContext : DbContext
{
    public DbSet<Facility> Facilities { get; set; }
    public DbSet<InventoryBooking> InventoryBookings { get; set; }
    public DbSet<FinancingDeal> FinancingDeals { get; set; }
    public DbSet<PaymentScheduleItem> PaymentScheduleItems { get; set; }
    public DbSet<OutwardPaymentRecord> OutwardPaymentRecords { get; set; }

    public BankSmartDbContext(DbContextOptions<BankSmartDbContext> options) : base(options) { }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Facility>().HasKey(f => f.FacilityID);
        modelBuilder.Entity<InventoryBooking>().HasKey(i => i.ReferenceNo);
        modelBuilder.Entity<FinancingDeal>().HasKey(d => d.DealRefNo);
        modelBuilder.Entity<PaymentScheduleItem>().HasKey(p => p.Id);
        modelBuilder.Entity<OutwardPaymentRecord>().HasKey(o => o.ChannelRefID);
    }
}
```

---

## 3. Request / Response Contracts & DTOs

### 3.1 Common Envelope Structure
```csharp
public class ResponseEnvelope<T>
{
    public string RequestDateTime { get; set; }
    public string LogId { get; set; }
    public StatusObject Status { get; set; }
    public T Content { get; set; }
}

public class StatusObject
{
    public string Code { get; set; }
    public string Severity { get; set; }
    public string StatusMessage { get; set; }
}

public class SignOnRq
{
    public string LogId { get; set; }
    public string DateTime { get; set; }
    public string ChannelId { get; set; }
    public string OurBranchId { get; set; }
}

public class SignOnRqCamel
{
    public string logId { get; set; }
    public string dateTime { get; set; }
    public string channelId { get; set; }
    public string ourBranchId { get; set; }
}
```

### 3.2 Specific API DTOs

#### Facility Overview
- Request: `SignOnRq` (PascalCase), `clientID` (string)
- Response Content: Array of facilities (`facilityID`, `referenceID`, `status`, `reviewDate`, `expiryDate`, `securedType`, `limitType`, `approvedLimit`, `utilizedLimit`, `availableLimit`, `currencyID`, `productID`, `securityAccount`, `advanceAccount`).

#### Book Inventory
- Request: `SignOnRq` (PascalCase), `InvoiceNo`, `ReferenceNo`, `ProductID` (default `MURFIN`), `Amount`, `SuppAccountID` (default `500000040001`), `Description`, `AdvanceMurReferenceNo`, `InvoiceDate`, `ProductType` (default `MUR`).
- Response Content: `scrollNo`, `channelRefID`, `referenceNo`.

#### Murabaha Disbursement
- Request: `SignOnRq` (PascalCase), `InventoryReferenceNo` (`string[]`), `Amount`, `MoratoriumPeriod` (default `0`), `Productid` (default `MURFIN`), `FacilityID`, `Tenure`, `Method` (default `MUR`), `type`, `RePaymentMode`, `RateType` (default `F`), `ProfitRate`, `IsPortal` (default `true`), `clientID`, `AssetValue` (default `0`), `VirtualAccID` (default `""`), `ECertNo`, `PrincipalPeriod`, `sweepAccountID`, `GracePeriod` (default `7`), `FeeBaseRate` (default `1001`).
- Response Content: `referenceNo`, `channelRefID`, `scrollNo`, `loanAccount`, `receivableAccount`, `defferAccount`, `trxAccount`, `trxVAccount`, `securityAccount`, `securityVAccount`, `advanceAccount`, `advanceVAccount`, `schedule[]` (`installmentNo`, `installmentDueDate`, `daysInPeriod`, `principal`, `accruedProfit`, `profit`, `balance`, `installment`).

#### Outward Payment
- Request: `signOnRq` (camelCase), `refNo`, `beneficiaryList[]` (`typeCode`, `BeneficiaryBankName`, `BeneficiaryAccountNumber`, `BeneficiaryAccountName`, `Amount`), `internalAccountTypeCode`, `internalAccount[]`.
- Response Content: `channelRefID`.

#### Loan Details
- Request: `SignOnRq` (PascalCase), `clientID`, `facilityID`, `productID` (default `MURFIN`).
- Response Content: Array of financing accounts (`accountID`, `dealID`, `dealRefNo`, `currencyID`, `startDate`, `firstRepayDate`, `maturityDate`, `loanAmount`, `totalPaidAmount`, `oustandingBalance`, `oustandingProfit`, `trxAccountID`, `totalInstallments`, `paidInstallments`, `remainingInstallments`, `nextInstalmentDate`, `nextInstallmentAmount`, `monthlyPayment`, `interestRate`, `apr`).

#### Loan Schedule
- Request: `SignOnRq` (PascalCase), `dealId`.
- Response Content: `dealID`, `dealRefNo`, `status`, `clientID`, `accountID`, `productID`, `currencyID`, `description`, `amount`, `disbursementDate`, `maturityDate`, `settlementAccount`, `apr`, `interest`, `tenure`, `tenureType`, `scheduler[]` (`repaymentDate`, `principalAmount`, `toDateProfit`, `instAmount`, `isPaid`).

---

## 4. Error Handling & Validation Rules
- **HTTP Status Codes**: 200 OK on successful transport; 400 Bad Request on validation or business errors.
- **Response Status**: `status.code` must be `MSG-000000` for success. Any other code (e.g., `ERR-1000162`) indicates failure with `status.severity = "Error"`, populated `status.statusMessage`, and `content = null`.
- **Authentication**: HTTP Basic Authentication header check on every endpoint.