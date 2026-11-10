# TECHNICAL DESIGN DOCUMENT: AAISE 2+2+1 CALCULATION ENGINE & API BASELINE

**Document Reference:** `docs/TECHNICAL_DESIGN.md`  
**System Scope:** AAISE 2+2+1 Calculation Engine & Downstream Mock Vendor Integration  
**Target Runtime:** .NET 8.0 SDK (ASP.NET Core Web API, C# 12, EF Core 8.0, SQLite)  
**Document Status:** Pending Human Approval (Revision 3.1.0 - Comprehensive Architectural Alignment & Baseline Isolation)  
**Revision:** 3.1.0  

---

## 1. System Architecture & Component Design

### 1.1 Architectural Overview
The AAISE 2+2+1 Calculation Engine is engineered as a high-reliability enterprise backend service adhering strictly to the **Controller-Service-Repository** pattern. The solution comprises two decoupled HTTP API services:
1. `Calculator.Api`: The core API service executing persistence, orchestration, checked sum arithmetic, and error handling.
2. `MockVendor.Api`: An independent downstream mock service returning a fixed integer payload (`{"value": 1}`).

The architecture emphasizes strict separation of concerns, explicit Dependency Injection (DI) lifetimes, non-blocking asynchronous I/O execution (`async`/`await`) across all persistence and HTTP network boundaries, and robust fault domain isolation. Per reviewer directives, all unapproved enterprise additions (such as request size limiting middleware and record audit fields) have been segregated into Section 7 (**Proposed Enhancements Pending Human Approval**) to guarantee that the core executable baseline matches the authoritative Functional Requirements (FR-01 through FR-10) and Non-Functional Requirements (NFR-01 through NFR-08).

```
                              +---------------------------------------+
                              |         Client / Consumer             |
                              +---------------------------------------+
                                        |                   |
                     HTTP POST /api/calculations    HTTP GET /api/calculations/{id}/sum
                                        |                   |
                                        v                   v
+---------------------------------------------------------------------------------------------------+
| Calculator.Api (ASP.NET Core Web API .NET 8.0)                                                    |
|                                                                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | Controllers Layer                                                                           |  |
|  |  - CalculationsController (POST /api/calculations, GET /api/calculations/{id}/sum)          |  |
|  +---------------------------------------------------------------------------------------------+  |
|                                               |                                                   |
|                                               v                                                   |
|  +---------------------------------------------------------------------------------------------+  |
|  | Business Logic Layer                                                                        |  |
|  |  - CalculationService (ICalculationService)                                                 |  |
|  +---------------------------------------------------------------------------------------------+  |
|                         |                                              |                          |
|                         v                                              v                          |
|  +------------------------------------------+       +------------------------------------------+  |
|  | Data Access Layer                        |       | HTTP Integration Client Layer            |  |
|  |  - CalculationRepository                 |       |  - MockVendorClient (IMockVendorClient)  |  |
|  |    (ICalculationRepository)              |       |    (Typed HttpClient via                 |  |
|  |  - AppDbContext (EF Core 8)              |       |     IHttpClientFactory)                  |  |
|  +------------------------------------------+       +------------------------------------------+  |
+------------------------------|-----------------------------------------|--------------------------+
                               |                                         |
                               v                                         v
                    +--------------------+                    +--------------------+
                    | SQLite File DB     |                    | MockVendor.Api     |
                    | (Data/calculator.db|                    | HTTP GET           |
                    | Persistent Storage |                    | /api/mock/value    |
                    +--------------------+                    +--------------------+
```

---

### 1.2 Component Topology & Class Responsibilities

#### 1. `CalculationsController` (`Calculator.Api/Controllers/CalculationsController.cs`)
* **Role**: Primary HTTP Interface Gateway.
* **Responsibilities**:
  * Exposes `POST /api/calculations` to persist 32-bit signed integer pairs (`Number1`, `Number2`). Returns HTTP 201 Created with a standard `Location` header pointing to `/api/calculations/{id}/sum`.
  * Exposes `GET /api/calculations/{id}/sum` to execute the complete sum aggregation workflow. Returns HTTP 200 OK containing record details and computed total.
  * Enforces model state validation and request header compliance (`Content-Type: application/json`).
  * Delegates business logic processing exclusively to `ICalculationService`.

#### 2. `CalculationService` (`Calculator.Api/Services/CalculationService.cs`)
* **Role**: Orchestration & Domain Calculation Engine.
* **Responsibilities**:
  * Validates path input identity (`id > 0`). Throws `CalculationNotFoundException` (mapped to HTTP 404) if `{id}` is absent from storage.
  * Queries `ICalculationRepository` asynchronously to fetch the stored record (`CalculationRecord`). Catches EF Core/SQLite infrastructure exceptions and rethrows them as `DatabaseUnavailableException` (mapped to HTTP 503).
  * Invokes `IMockVendorClient.GetMockValueAsync()` to retrieve the external integer value. Translates network failures, HTTP status errors, and response format anomalies into `MockVendorUnavailableException` (mapped to HTTP 502), and HTTP timeout events into `MockVendorTimeoutException` (mapped to HTTP 504).
  * Computes the grand total sum using C# checked arithmetic: `checked(record.Number1 + record.Number2 + mockValue)`. Throws `CalculationOverflowException` (mapped to HTTP 422) if the calculation breaches 32-bit signed integer boundaries (`int.MinValue` = -2,147,483,648 to `int.MaxValue` = 2,147,483,647).
  * Assembles `CalculationSumResponseDto` without modifying stored database entities (pure read operation).

#### 3. `CalculationRepository` (`Calculator.Api/Repositories/CalculationRepository.cs`)
* **Role**: Data Access Layer & Entity Persistence.
* **Responsibilities**:
  * Interacts with `AppDbContext` using Entity Framework Core 8 with the SQLite provider (`Microsoft.EntityFrameworkCore.Sqlite`).
  * Provides `CreateAsync(CalculationRecord entity)` to add and commit records (`SaveChangesAsync`).
  * Provides `GetByIdAsync(int id)` executing read-only (`AsNoTracking()`) queries for maximum performance.

#### 4. `MockVendorClient` (`Calculator.Api/Clients/MockVendorClient.cs`)
* **Role**: Outbound HTTP Integration Client.
* **Responsibilities**:
  * Typed HTTP client instantiated via `IHttpClientFactory`.
  * Executes asynchronous HTTP GET requests to `http://localhost:5005/api/mock/value`.
  * Configured with an explicit 5-second timeout (`TimeSpan.FromSeconds(5)`).
  * Handles standard cancellation tokens, detecting `TaskCanceledException` / `TimeoutException` to throw `MockVendorTimeoutException`.

#### 5. `GlobalExceptionHandlerMiddleware` (`Calculator.Api/Middleware/GlobalExceptionHandlerMiddleware.cs`)
* **Role**: Centralized Exception Pipeline Handler.
* **Responsibilities**:
  * Intercepts unhandled domain and infrastructure exceptions across the Web API pipeline.
  * Maps custom exception types to standardized RFC 9457 `application/problem+json` payloads.
  * Ensures trace correlation IDs (`HttpContext.TraceIdentifier`) are preserved in all standard error envelopes.

---

### 1.3 Service Registration & Dependency Injection Setup (`Program.cs`)

Below is the complete, executable `Program.cs` code for `Calculator.Api` establishing baseline service registration:

```csharp
namespace Calculator.Api;

using Calculator.Api.Clients;
using Calculator.Api.Data;
using Calculator.Api.Middleware;
using Calculator.Api.Repositories;
using Calculator.Api.Services;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System;
using System.IO;

public class Program
{
    public static void Main(string[] args)
    {
        var builder = WebApplication.CreateBuilder(args);

        // 1. Database Configuration (SQLite)
        var connectionString = builder.Configuration.GetConnectionString("DefaultConnection") 
            ?? "Data Source=Data/calculator.db";
        
        builder.Services.AddDbContext<AppDbContext>(options =>
        {
            options.UseSqlite(connectionString);
        });

        // 2. Core Business Services & Repository Registration
        builder.Services.AddScoped<ICalculationRepository, CalculationRepository>();
        builder.Services.AddScoped<ICalculationService, CalculationService>();
        builder.Services.AddHttpContextAccessor();

        // 3. Typed HttpClient Configuration for Mock Vendor Client (5-second Timeout)
        var mockVendorBaseUrl = builder.Configuration["MockVendor:BaseUrl"] ?? "http://localhost:5005";
        var timeoutSeconds = builder.Configuration.GetValue<int>("MockVendor:TimeoutSeconds", 5);

        builder.Services.AddHttpClient<IMockVendorClient, MockVendorClient>(client =>
        {
            client.BaseAddress = new Uri(mockVendorBaseUrl);
            client.Timeout = TimeSpan.FromSeconds(timeoutSeconds);
            client.DefaultRequestHeaders.Add("Accept", "application/json");
        });

        // 4. Controller Services & OpenAPI Configuration
        builder.Services.AddControllers();
        builder.Services.AddEndpointsApiExplorer();
        builder.Services.AddSwaggerGen();
        
        // 5. Health Checks Configuration (Database & Downstream Vendor Service)
        builder.Services.AddHealthChecks()
            .AddDbContextCheck<AppDbContext>("database_health_check")
            .AddUrlGroup(new Uri($"{mockVendorBaseUrl}/api/mock/value"), "mock_vendor_health_check");

        var app = builder.Build();

        // 6. Request Pipeline Configuration (Baseline Executable Pipeline)
        app.UseMiddleware<GlobalExceptionHandlerMiddleware>();

        if (app.Environment.IsDevelopment())
        {
            app.UseSwagger();
            app.UseSwaggerUI();
        }

        app.UseRouting();
        app.MapControllers();
        app.MapHealthChecks("/health");

        // 7. Directory Initialization & Database Auto-Migration
        using (var scope = app.Services.CreateScope())
        {
            var dbContext = scope.ServiceProvider.GetRequiredService<AppDbContext>();
            var rawPath = connectionString.Replace("Data Source=", "", StringComparison.OrdinalIgnoreCase).Trim();
            var dbDirectory = Path.GetDirectoryName(rawPath);
            if (!string.IsNullOrEmpty(dbDirectory) && !Directory.Exists(dbDirectory))
            {
                Directory.CreateDirectory(dbDirectory);
            }
            dbContext.Database.Migrate();
        }

        app.Run();
    }
}
```

---

### 1.4 Asynchronous Data Flow & Execution Sequence

The sequence diagram below details the step-by-step execution path for `GET /api/calculations/{id}/sum`:

```
Client / Consumer          CalculationsController      CalculationService       CalculationRepository      MockVendorClient        MockVendor.Api
       |                             |                         |                         |                        |                      |
       |--- GET /api/calc/1/sum ---->|                         |                         |                        |                      |
       |                             |-- GetSumAsync(1) ------>|                         |                        |                      |
       |                             |                         |-- GetByIdAsync(1) ----->|                        |                      |
       |                             |                         |<-- CalculationRecord ---|                        |                      |
       |                             |                         |                                                  |                      |
       |                             |                         |-- GetMockValueAsync() -------------------------->|                      |
       |                             |                         |                                                  |-- GET /api/mock/val->|
       |                             |                         |                                                  |<-- 200 OK {"val":1} -|
       |                             |                         |<-- return int (1) -------------------------------|                      |
       |                             |                         |                                                                         |
       |                             |                         |-- Compute: checked(Number1 + Number2 + MockValue)                                |
       |                             |                         |-- Assemble CalculationSumResponseDto                                    |
       |                             |<-- CalculationSumDto ---|                                                                         |
       |<-- 200 OK (JSON Payload) ---|                         |                                                                         |
```

---

## 2. Database Design & Domain Model (Baseline Core System)

### 2.1 Persistence Engine Specification
The baseline persistence engine utilizes **SQLite** version 3 with Entity Framework Core 8 (`Microsoft.EntityFrameworkCore.Sqlite`). Database records are persisted in a local file located at `Data/calculator.db`. SQLite ensures single-file database portability, ACID transactional compliance, and full auto-increment primary key capability.

---

### 2.2 Baseline Entity Schema (`CalculationRecords` Table)

The baseline schema is deliberately restricted to core calculation requirements (`Id`, `Number1`, `Number2`). All enterprise audit metadata fields are segregated into Section 7.

| Column Name | SQLite Data Type | C# Type | Nullable | Primary Key | Default / Constraint |
|---|---|---|---|---|---|
| `Id` | `INTEGER` | `int` | No | Yes | Primary Key, Auto Increment (`1, 2, 3...`) |
| `Number1` | `INTEGER` | `int` | No | No | `NOT NULL`, Valid 32-bit signed integer |
| `Number2` | `INTEGER` | `int` | No | No | `NOT NULL`, Valid 32-bit signed integer |

---

### 2.3 Baseline Data Model & DbContext Configuration

#### `CalculationRecord.cs` (`Calculator.Api/Models/CalculationRecord.cs`)
```csharp
namespace Calculator.Api.Models;

public class CalculationRecord
{
    public int Id { get; set; }
    public int Number1 { get; set; }
    public int Number2 { get; set; }
}
```

#### `AppDbContext.cs` (`Calculator.Api/Data/AppDbContext.cs`)
```csharp
namespace Calculator.Api.Data;

using Calculator.Api.Models;
using Microsoft.EntityFrameworkCore;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<CalculationRecord> CalculationRecords => Set<CalculationRecord>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        modelBuilder.Entity<CalculationRecord>(entity =>
        {
            entity.ToTable("CalculationRecords");
            
            entity.HasKey(e => e.Id);
            
            entity.Property(e => e.Id)
                .ValueGeneratedOnAdd();
                
            entity.Property(e => e.Number1)
                .IsRequired();
                
            entity.Property(e => e.Number2)
                .IsRequired();
        });
    }
}
```

#### `ICalculationRepository.cs` (`Calculator.Api/Repositories/ICalculationRepository.cs`)
```csharp
namespace Calculator.Api.Repositories;

using Calculator.Api.Models;
using System.Threading.Tasks;

public interface ICalculationRepository
{
    Task<CalculationRecord> CreateAsync(CalculationRecord record);
    Task<CalculationRecord?> GetByIdAsync(int id);
}
```

#### `CalculationRepository.cs` (`Calculator.Api/Repositories/CalculationRepository.cs`)
```csharp
namespace Calculator.Api.Repositories;

using Calculator.Api.Data;
using Calculator.Api.Models;
using Microsoft.EntityFrameworkCore;
using System.Threading.Tasks;

public class CalculationRepository : ICalculationRepository
{
    private readonly AppDbContext _context;

    public CalculationRepository(AppDbContext context)
    {
        _context = context;
    }

    public async Task<CalculationRecord> CreateAsync(CalculationRecord record)
    {
        _context.CalculationRecords.Add(record);
        await _context.SaveChangesAsync();
        return record;
    }

    public async Task<CalculationRecord?> GetByIdAsync(int id)
    {
        return await _context.CalculationRecords
            .AsNoTracking()
            .FirstOrDefaultAsync(r => r.Id == id);
    }
}
```

---

### 2.4 Database Migration & Initialization Strategy
Migrations are managed via Entity Framework Core tooling. The initialization process is automated during startup via `app.Services.CreateScope()` in `Program.cs`.

```bash
# Command to generate initial EF Core SQLite migration
dotnet ef migrations add InitialCreate --project Calculator.Api/Calculator.Api.csproj
```

The migration script creates the SQLite database structure dynamically:
```sql
CREATE TABLE "CalculationRecords" (
    "Id" INTEGER NOT NULL CONSTRAINT "PK_CalculationRecords" PRIMARY KEY AUTOINCREMENT,
    "Number1" INTEGER NOT NULL,
    "Number2" INTEGER NOT NULL
);
```

---

## 3. API Specifications & Data Transfer Contracts

### 3.1 Global Error Handling & Problem Details Schema (RFC 9457)
All error payloads returned by `Calculator.Api` strictly adhere to the RFC 9457 specification (`Content-Type: application/problem+json`).

```json
{
  "type": "https://tools.ietf.org/html/rfc9457",
  "title": "Bad Request",
  "status": 400,
  "detail": "The Number1 field is required.",
  "instance": "/api/calculations",
  "traceId": "0HMVN73P8A91B:00000001"
}
```

---

### 3.2 Endpoint: `POST /api/calculations`

Persists input numbers (`Number1`, `Number2`) into SQLite database storage.

* **HTTP Method**: `POST`
* **Path**: `/api/calculations`
* **Request Headers**:
  * `Content-Type: application/json`
  * `Accept: application/json`

#### Request DTO (`CreateCalculationRequestDto.cs`)
```csharp
namespace Calculator.Api.DTOs;

using System.ComponentModel.DataAnnotations;

public class CreateCalculationRequestDto
{
    [Required(ErrorMessage = "The Number1 field is required.")]
    public int? Number1 { get; set; }

    [Required(ErrorMessage = "The Number2 field is required.")]
    public int? Number2 { get; set; }
}
```

#### Response DTO (`CalculationRecordResponseDto.cs`)
```csharp
namespace Calculator.Api.DTOs;

public class CalculationRecordResponseDto
{
    public int Id { get; set; }
    public int Number1 { get; set; }
    public int Number2 { get; set; }
}
```

#### Detailed HTTP Response Scenarios

##### Scenario 3.2.1: 201 Created (Success)
* **Condition**: Valid payload containing 32-bit signed integers.
* **Headers**: `Location: /api/calculations/1/sum`, `Content-Type: application/json`
* **Body**:
```json
{
  "id": 1,
  "number1": 5,
  "number2": 10
}
```

##### Scenario 3.2.2: 400 Bad Request (Validation / Schema Error)
* **Condition**: Missing required fields, non-integer input types, or malformed JSON.
* **Headers**: `Content-Type: application/problem+json`
* **Body**:
```json
{
  "type": "https://tools.ietf.org/html/rfc9457",
  "title": "One or more validation errors occurred.",
  "status": 400,
  "detail": "The Number1 field is required.",
  "instance": "/api/calculations",
  "traceId": "0HMVN73P8A91B:00000002"
}
```

##### Scenario 3.2.3: 415 Unsupported Media Type
* **Condition**: `Content-Type` header is omitted or set to non-JSON media type (e.g., `text/plain`).
* **Headers**: `Content-Type: application/problem+json`
* **Body**:
```json
{
  "type": "https://tools.ietf.org/html/rfc9457",
  "title": "Unsupported Media Type",
  "status": 415,
  "detail": "Content-Type header must be application/json.",
  "instance": "/api/calculations",
  "traceId": "0HMVN73P8A91B:00000003"
}
```

##### Scenario 3.2.4: 500 Internal Server Error
* **Condition**: Unexpected unhandled system fault during database execution.
* **Headers**: `Content-Type: application/problem+json`
* **Body**:
```json
{
  "type": "https://tools.ietf.org/html/rfc9457",
  "title": "Internal Server Error",
  "status": 500,
  "detail": "An unexpected internal server error occurred.",
  "instance": "/api/calculations",
  "traceId": "0HMVN73P8A91B:00000004"
}
```

---

### 3.3 Endpoint: `GET /api/calculations/{id}/sum`

Retrieves record by ID from SQLite storage, fetches mock integer (`1`) from `MockVendor.Api`, computes total sum via checked arithmetic, and returns response without mutating stored records.

* **HTTP Method**: `GET`
* **Path**: `/api/calculations/{id}/sum`
* **Path Parameter**: `id` (32-bit signed integer, `id > 0`).

#### Response DTO (`CalculationSumResponseDto.cs`)
```csharp
namespace Calculator.Api.DTOs;

public class CalculationSumResponseDto
{
    public int RecordId { get; set; }
    public int Number1 { get; set; }
    public int Number2 { get; set; }
    public int MockValue { get; set; }
    public int Total { get; set; }
}
```

#### Detailed HTTP Response Scenarios

##### Scenario 3.3.1: 200 OK (Baseline Execution Success)
* **Condition**: Valid record ID, `MockVendor.Api` active and returning `1`, sum calculated successfully.
* **Headers**: `Content-Type: application/json`
* **Body**:
```json
{
  "recordId": 1,
  "number1": 1,
  "number2": 1,
  "mockValue": 1,
  "total": 3
}
```

##### Scenario 3.3.2: 400 Bad Request (Invalid Path Identity)
* **Condition**: Path parameter `{id}` is zero or negative (`id <= 0`).
* **Headers**: `Content-Type: application/problem+json`
* **Body**:
```json
{
  "type": "https://tools.ietf.org/html/rfc9457",
  "title": "Bad Request",
  "status": 400,
  "detail": "Calculation ID must be a positive integer greater than zero.",
  "instance": "/api/calculations/0/sum",
  "traceId": "0HMVN73P8A91B:00000005"
}
```

##### Scenario 3.3.3: 404 Not Found (Record Missing)
* **Condition**: `{id}` is a valid positive integer but does not exist in SQLite storage.
* **Headers**: `Content-Type: application/problem+json`
* **Body**:
```json
{
  "type": "https://tools.ietf.org/html/rfc9457",
  "title": "Not Found",
  "status": 404,
  "detail": "Calculation record with ID 999 was not found.",
  "instance": "/api/calculations/999/sum",
  "traceId": "0HMVN73P