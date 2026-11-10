# Technical Design Document (TDD)
## 2 + 2 + 1 Calculation API — AAISE End-to-End Agent Evaluation

**Document Version:** 1.1.0-REVISED  
**Date:** 06 November 2026  
**Status:** Pending Human Approval  
**Target Platform:** .NET 8.0 (C# 12) / ASP.NET Core Web API / Entity Framework Core 8.0 / SQLite  

---

## 1. Executive Summary & Document Control

### 1.1 Document Status & Approval State
This Technical Design Document (TDD) establishes the definitive system architecture, data models, API contracts, execution flows, and infrastructure specifications for the **2 + 2 + 1 Calculation API**.

> **CRITICAL STATUS NOTICE:**  
> This specification document is currently **Pending Human Approval**. Pursuant to directive **CR-05**, implementation work (Agent 3 - Coder) MUST NOT commence until the Human Reviewer explicitly signs off on this document and approves all architectural decision logs.

### 1.2 Outstanding Architecture Decisions & Human Approval Log

| Decision ID | Area | Proposed Architectural Design | Impact & Context | Approval Status |
|---|---|---|---|---|
| **DEC-001** | Audit Trail Fields | Inclusion of `CreatedAtUtc`, `CreatedBy`, `UpdatedAtUtc`, and `UpdatedBy` on SQLite entities. | Provides traceability for system actors and record creation timelines. Defaults to `'System'` / `'Anonymous'` if unauthenticated. | **Pending Approval** |
| **DEC-002** | Authentication / Claims | Inclusion of optional JWT Bearer authentication to extract `sub`/`NameIdentifier` for `CreatedBy`. | Allows identity binding when tokens are provided; falls back gracefully to `'Anonymous'` when authentication is disabled or absent. | **Pending Approval** |
| **DEC-003** | DTO Decoupling | Complete decoupling of `MockVendor.Api` and `Calculator.Api` data transfer objects. | Prevents project reference coupling; each microservice owns its internal object models and binary deployment boundaries. | **Pending Approval** |
| **DEC-004** | Error Mapping Domain | Mapping vendor failures to HTTP 502 (Bad Gateway) and timeouts to HTTP 504 (Gateway Timeout). | Maps third-party network layer failures to RFC 9457 Problem Details without leaking stack traces or internal IP addresses. | **Pending Approval** |

### 1.3 Core Architectural Principles
1. **Strict Stack Compliance:** Built strictly on ASP.NET Core Web API on .NET 8.0, EF Core 8.0 with SQLite file-backed database (`calculator.db`), xUnit test framework, and OpenAPI / Swagger. The use of EF Core `InMemory` provider for integration testing is **strictly prohibited**.
2. **Decoupled Service Boundary:** Strict separation of concerns via Controller $\rightarrow$ Service $\rightarrow$ Repository architectural pattern.
3. **Independent Executable Microservices:** `Calculator.Api` and `MockVendor.Api` maintain zero shared binary code references and compile independently.
4. **Deterministic Calculation Pipeline:** Execution of `GET /api/calculations/{id}/sum` follows a strict sequential flow:
   - Path parameter validation ($id > 0$).
   - Read persisted `CalculationRecord` from SQLite via `ICalculationRepository`.
   - Issue real out-of-process HTTP `GET` call to `MockVendor.Api` using a typed `HttpClient`.
   - Parse external vendor JSON payload (`{"value": 1}`).
   - Compute checked sum: $\text{Total} = \text{checked}(\text{Number1} + \text{Number2} + \text{MockValue})$.
   - Persist no new records during GET (idempotent evaluation).
   - Return composite HTTP 200 payload.
5. **Zero-Trust Error Boundary:** Standardized RFC 9457 Problem Details returned for all error scenarios with correlation trace IDs (`traceId`).

---

## 2. System Architecture & Project Layout

### 2.1 Complete Repository Directory Structure

```
aaise-calculator-poc/
├── .github/
│   └── workflows/
│       └── ci-cd.yml
├── docs/
│   ├── AAISE_2Plus2Plus1_Calculation_API_SRS_v1.0.pdf
│   └── TECHNICAL_DESIGN.md
├── src/
│   ├── Calculator.Api/
│   │   ├── Calculator.Api.csproj
│   │   ├── Program.cs
│   │   ├── appsettings.json
│   │   ├── appsettings.Development.json
│   │   ├── Controllers/
│   │   │   └── CalculationsController.cs
│   │   ├── Services/
│   │   │   ├── ICalculationService.cs
│   │   │   └── CalculationService.cs
│   │   ├── Repositories/
│   │   │   ├── ICalculationRepository.cs
│   │   │   └── CalculationRepository.cs
│   │   ├── Data/
│   │   │   ├── AppDbContext.cs
│   │   │   └── Migrations/
│   │   │       ├── 20261106000000_InitialCreate.cs
│   │   │       └── AppDbContextModelSnapshot.cs
│   │   ├── Models/
│   │   │   └── CalculationRecord.cs
│   │   ├── Dtos/
│   │   │   ├── CreateCalculationRequestDto.cs
│   │   │   ├── CalculationCreatedResponseDto.cs
│   │   │   ├── CalculationSumResponseDto.cs
│   │   │   └── MockVendorValueResponseDto.cs
│   │   ├── Clients/
│   │   │   ├── IMockVendorClient.cs
│   │   │   └── MockVendorClient.cs
│   │   ├── Middleware/
│   │   │   └── GlobalExceptionMiddleware.cs
│   │   └── Health/
│   │       └── SqliteHealthCheck.cs
│   └── MockVendor.Api/
│       ├── MockVendor.Api.csproj
│       ├── Program.cs
│       ├── appsettings.json
│       ├── appsettings.Development.json
│       ├── Controllers/
│       │   └── MockValueController.cs
│       └── Dtos/
│           └── MockVendorResponseDto.cs
├── tests/
│   └── Calculator.Tests/
│       ├── Calculator.Tests.csproj
│       ├── Unit/
│       │   ├── Services/
│       │   │   └── CalculationServiceTests.cs
│       │   ├── Clients/
│       │   │   └── MockVendorClientTests.cs
│       │   └── Controllers/
│       │       └── CalculationsControllerTests.cs
│       └── Integration/
│           ├── IntegrationTestWebApplicationFactory.cs
│           ├── CalculationsApiIntegrationTests.cs
│           └── MockVendorApiIntegrationTests.cs
├── Calculator.sln
└── README.md
```

### 2.2 Component Dependency & Invocation Sequence

```
+-----------------------------------------------------------------------------------------+
|                                    HTTP Client / Test Suite                             |
+-----------------------------------------------------------------------------------------+
       | (POST /api/calculations)                            | (GET /api/calculations/{id}/sum)
       v                                                     v
+-----------------------------------------------------------------------------------------+
|                                      Calculator.Api                                     |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  | CalculationsController                                                           |  |
|  +-----------------------------------------------------------------------------------+  |
|                                            |                                            |
|                                            v                                            |
|  +-----------------------------------------------------------------------------------+  |
|  | CalculationService                                                               |  |
|  +-----------------------------------------------------------------------------------+  |
|            |                                                    |                       |
|            v                                                    v                       |
|  +----------------------------------+         +--------------------------------------+  |
|  | CalculationRepository            |         | MockVendorClient (Typed HttpClient)  |  |
|  +----------------------------------+         +--------------------------------------+  |
|            |                                                    |                       |
+------------|----------------------------------------------------|-----------------------+
             |                                                    |
             v (EF Core 8.0 DbContext)                            v (HTTP GET /api/mock/value)
+----------------------------------+            +-----------------------------------------+
| SQLite Database File             |            | MockVendor.Api                          |
| (calculator.db / File-backed)    |            | (Host: localhost:5002 / Return: 1)      |
+----------------------------------+            +-----------------------------------------+
```

### 2.3 Dependency Injection (DI) & `HttpClientFactory` Configuration

The service container registration in `Calculator.Api/Program.cs` manages lifecycles strictly to prevent memory leaks and thread exhaustion:

```csharp
// Program.cs Configuration Fragment
var builder = WebApplication.CreateBuilder(args);

// 1. Database Context Setup (Scoped)
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(builder.Configuration.GetConnectionString("DefaultConnection") 
        ?? "Data Source=calculator.db"));

// 2. Repository Layer Registration (Scoped)
builder.Services.AddScoped<ICalculationRepository, CalculationRepository>();

// 3. Domain Service Layer Registration (Scoped)
builder.Services.AddScoped<ICalculationService, CalculationService>();

// 4. Typed HttpClient Registration for Vendor Api (Transient/Typed Scope Managed by IHttpClientFactory)
builder.Services.AddHttpClient<IMockVendorClient, MockVendorClient>(client =>
{
    var baseAddress = builder.Configuration["MockVendorApi:BaseUrl"] ?? "http://localhost:5002";
    client.BaseAddress = new Uri(baseAddress);
    client.Timeout = TimeSpan.FromSeconds(5); // Strict 5 second gateway timeout
    client.DefaultRequestHeaders.Add("Accept", "application/json");
});

// 5. Infrastructure: Health Checks, Controllers, Rate Limiting
builder.Services.AddHealthChecks()
    .AddCheck<SqliteHealthCheck>("sqlite_health_check");

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
```

---

## 3. Database Architecture & Domain Model

### 3.1 Domain Entity: `CalculationRecord`

The application persists user numeric inputs in a dedicated SQLite database table.

```csharp
namespace Calculator.Api.Models;

/// <summary>
/// Persisted domain entity representing two numeric integer operands.
/// </summary>
public class CalculationRecord
{
    /// <summary>
    /// Auto-incrementing primary key.
    /// </summary>
    public int Id { get; set; }

    /// <summary>
    /// Operand 1 (32-bit signed integer).
    /// </summary>
    public int Number1 { get; set; }

    /// <summary>
    /// Operand 2 (32-bit signed integer).
    /// </summary>
    public int Number2 { get; set; }

    /// <summary>
    /// Audit timestamp representing UTC creation time. Mandatory.
    /// </summary>
    public DateTime CreatedAtUtc { get; set; }

    /// <summary>
    /// Identity string of entity creator. Defaults to 'System' or token identity.
    /// </summary>
    public string CreatedBy { get; set; } = "System";

    /// <summary>
    /// Audit timestamp representing UTC update time. Nullable.
    /// </summary>
    public DateTime? UpdatedAtUtc { get; set; }

    /// <summary>
    /// Identity string of last updater. Nullable.
    /// </summary>
    public string? UpdatedBy { get; set; }
}
```

### 3.2 Database Schema Definition (SQLite DDL)

```sql
-- SQLite Database Schema Definition
CREATE TABLE "CalculationRecords" (
    "Id" INTEGER NOT NULL CONSTRAINT "PK_CalculationRecords" PRIMARY KEY AUTOINCREMENT,
    "Number1" INTEGER NOT NULL,
    "Number2" INTEGER NOT NULL,
    "CreatedAtUtc" TEXT NOT NULL,
    "CreatedBy" TEXT NOT NULL DEFAULT 'System',
    "UpdatedAtUtc" TEXT NULL,
    "UpdatedBy" TEXT NULL
);

-- Index for lookup and audit filtering optimization
CREATE INDEX "IX_CalculationRecords_CreatedAtUtc" ON "CalculationRecords" ("CreatedAtUtc");
```

### 3.3 Entity Framework Core Configuration & Atomic Persistence (`AppDbContext.cs`)

```csharp
using Calculator.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace Calculator.Api.Data;

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

            entity.Property(e => e.CreatedAtUtc)
                  .IsRequired()
                  .HasConversion(
                      v => v.ToString("o"),
                      v => DateTime.Parse(v, null, System.Globalization.DateTimeStyles.RoundtripKind));

            entity.Property(e => e.CreatedBy)
                  .IsRequired()
                  .HasMaxLength(256);

            entity.Property(e => e.UpdatedAtUtc)
                  .HasConversion(
                      v => v.HasValue ? v.Value.ToString("o") : null,
                      v => string.IsNullOrEmpty(v) ? null : DateTime.Parse(v, null, System.Globalization.DateTimeStyles.RoundtripKind));

            entity.Property(e => e.UpdatedBy)
                  .HasMaxLength(256);
        });
    }

    public override Task<int> SaveChangesAsync(CancellationToken cancellationToken = default)
    {
        var entries = ChangeTracker.Entries<CalculationRecord>();
        
        foreach (var entry in entries)
        {
            if (entry.State == EntityState.Added)
            {
                if (entry.Entity.CreatedAtUtc == default)
                {
                    entry.Entity.CreatedAtUtc = DateTime.UtcNow;
                }
                if (string.IsNullOrWhiteSpace(entry.Entity.CreatedBy))
                {
                    entry.Entity.CreatedBy = "System";
                }
            }
            else if (entry.State == EntityState.Modified)
            {
                entry.Entity.UpdatedAtUtc = DateTime.UtcNow;
            }
        }

        return base.SaveChangesAsync(cancellationToken);
    }
}
```

### 3.4 Migration Management Code

```csharp
// src/Calculator.Api/Data/Migrations/20261106000000_InitialCreate.cs
using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Calculator.Api.Data.Migrations
{
    public partial class InitialCreate : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "CalculationRecords",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    Number1 = table.Column<int>(type: "INTEGER", nullable: false),
                    Number2 = table.Column<int>(type: "INTEGER", nullable: false),
                    CreatedAtUtc = table.Column<string>(type: "TEXT", nullable: false),
                    CreatedBy = table.Column<string>(type: "TEXT", maxLength: 256, nullable: false, defaultValue: "System"),
                    UpdatedAtUtc = table.Column<string>(type: "TEXT", nullable: true),
                    UpdatedBy = table.Column<string>(type: "TEXT", maxLength: 256, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_CalculationRecords", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_CalculationRecords_CreatedAtUtc",
                table: "CalculationRecords",
                column: "CreatedAtUtc");
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "CalculationRecords");
        }
    }
}
```

---

## 4. Application Layer Specifications & Interfaces

### 4.1 Repository Layer (`ICalculationRepository.cs` & `CalculationRepository.cs`)

```csharp
using Calculator.Api.Data;
using Calculator.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace Calculator.Api.Repositories;

public interface ICalculationRepository
{
    Task<CalculationRecord> CreateAsync(CalculationRecord record, CancellationToken cancellationToken = default);
    Task<CalculationRecord?> GetByIdAsync(int id, CancellationToken cancellationToken = default);
}

public class CalculationRepository : ICalculationRepository
{
    private readonly AppDbContext _context;

    public CalculationRepository(AppDbContext context)
    {
        _context = context ?? throw new ArgumentNullException(nameof(context));
    }

    public async Task<CalculationRecord> CreateAsync(CalculationRecord record, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(record);

        await _context.CalculationRecords.AddAsync(record, cancellationToken);
        await _context.SaveChangesAsync(cancellationToken);
        return record;
    }

    public async Task<CalculationRecord?> GetByIdAsync(int id, CancellationToken cancellationToken = default)
    {
        return await _context.CalculationRecords
                             .AsNoTracking()
                             .FirstOrDefaultAsync(r => r.Id == id, cancellationToken);
    }
}
```

### 4.2 Decoupled Typed Mock Vendor Client (`IMockVendorClient.cs` & `MockVendorClient.cs`)

Pursuant to **CR-02**, `Calculator.Api` defines its own response model `MockVendorValueResponseDto` and does not import any types from `MockVendor.Api`.

```csharp
using System.Net;
using System.Net.Http.Json;
using Calculator.Api.Dtos;

namespace Calculator.Api.Clients;

public interface IMockVendorClient
{
    Task<int> GetMockValueAsync(CancellationToken cancellationToken = default);
}

public class MockVendorClient : IMockVendorClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<MockVendorClient> _logger;

    public MockVendorClient(HttpClient httpClient, ILogger<MockVendorClient> logger)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task<int> GetMockValueAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            _logger.LogInformation("Executing HTTP GET request to MockVendor API endpoint /api/mock/value");
            
            var response = await _httpClient.GetAsync("/api/mock/value", cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogError("MockVendor API returned non-success HTTP status code {StatusCode}", response.StatusCode);
                throw new HttpRequestException($"MockVendor service returned status {response.StatusCode}", null, response.StatusCode);
            }

            MockVendorValueResponseDto? payload;
            try
            {
                payload = await response.Content.ReadFromJsonAsync<MockVendorValueResponseDto>(cancellationToken);
            }
            catch (Exception ex) when (ex is System.Text.Json.JsonException || ex is FormatException)
            {
                _logger.LogError(ex, "Failed to parse JSON response payload from MockVendor API.");
                throw new BadHttpRequestException("Malformed JSON payload received from MockVendor API.", ex);
            }

            if (payload == null)
            {
                _logger.LogError("MockVendor API returned empty or null JSON payload.");
                throw new BadHttpRequestException("Null JSON payload returned from MockVendor API.");
            }

            _logger.LogInformation("Successfully retrieved mock value {Value} from vendor endpoint.", payload.Value);
            return payload.Value;
        }
        catch (TaskCanceledException ex) when (!cancellationToken.IsCancellationRequested)
        {
            _logger.LogError(ex, "HTTP Request to MockVendor API timed out after standard threshold.");
            throw new TimeoutException("MockVendor API request timed out.", ex);
        }
    }
}
```

### 4.3 Service Layer Implementation (`ICalculationService.cs` & `CalculationService.cs`)

```csharp
using Calculator.Api.Clients;
using Calculator.Api.Dtos;
using Calculator.Api.Models;
using Calculator.Api.Repositories;

namespace Calculator.Api.Services;

public interface ICalculationService
{
    Task<CalculationCreatedResponseDto> CreateCalculationAsync(CreateCalculationRequestDto request, string createdBy, CancellationToken cancellationToken = default);
    Task<CalculationSumResponseDto> CalculateSumAsync(int id, CancellationToken cancellationToken = default);
}

public class CalculationService : ICalculationService
{
    private readonly ICalculationRepository _repository;
    private readonly IMockVendorClient _mockVendorClient;
    private readonly ILogger<CalculationService> _logger;

    public CalculationService(
        ICalculationRepository repository,
        IMockVendorClient mockVendorClient,
        ILogger<CalculationService> logger)
    {
        _repository = repository ?? throw new ArgumentNullException(nameof(repository));
        _mockVendorClient = mockVendorClient ?? throw new ArgumentNullException(nameof(mockVendorClient));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task<CalculationCreatedResponseDto> CreateCalculationAsync(
        CreateCalculationRequestDto request, 
        string createdBy, 
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        if (!request.Number1.HasValue || !request.Number2.HasValue)
        {
            throw new ArgumentException("Both number1 and number2 must be non-null integer values.");
        }

        var entity = new CalculationRecord
        {
            Number1 = request.Number1.Value,
            Number2 = request.Number2.Value,
            CreatedAtUtc = DateTime.UtcNow,
            CreatedBy = string.IsNullOrWhiteSpace(createdBy) ? "System" : createdBy
        };

        var savedEntity = await _repository.CreateAsync(entity, cancellationToken);

        _logger.LogInformation("Successfully created CalculationRecord with Id {Id}, Number1: {N1}, Number2: {N2}", 
            savedEntity.Id, savedEntity.Number1, savedEntity.Number2);

        return new CalculationCreatedResponseDto
        {
            Id = savedEntity.Id,
            Number1 = savedEntity.Number1,
            Number2 = savedEntity.Number2
        };
    }

    public async Task<CalculationSumResponseDto> CalculateSumAsync(int id, CancellationToken cancellationToken = default)
    {
        if (id <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(id), "Calculation Record ID must be a positive integer.");
        }

        // Step 1: Read persisted inputs from SQLite database
        var record = await _repository.GetByIdAsync(id, cancellationToken);
        if (record == null)
        {
            _logger.LogWarning("Calculation Record with ID {RecordId} was not found in SQLite repository.", id);
            throw new KeyNotFoundException($"Calculation record with ID {id} does not exist.");
        }

        // Step 2: Make actual HTTP call to MockVendor API
        int mockValue = await _mockVendorClient.GetMockValueAsync(cancellationToken);

        // Step 3: Perform checked integer sum calculation
        int total;
        try
        {
            checked
            {
                total = record.Number1 + record.Number2 + mockValue;
            }
        }
        catch (OverflowException ex)
        {
            _logger.LogError(ex, "Integer arithmetic overflow encountered for RecordId {RecordId}: {N1} + {N2} + {Mock}", 
                id, record.Number1, record.Number2, mockValue);
            throw new OverflowException($"Integer arithmetic overflow: {record.Number1} + {record.Number2} + {mockValue} exceeds 32-bit integer boundaries.", ex);
        }

        _logger.LogInformation("Successfully computed sum for RecordId {RecordId}: {N1} + {N2} + {Mock} = {Total}", 
            id, record.Number1, record.Number2, mockValue, total);

        return new CalculationSumResponseDto
        {
            RecordId = record.Id,
            Number1 = record.Number1,
            Number2 = record.Number2,
            MockValue = mockValue,
            Total = total
        };
    }
}
```

---

## 5. API Contracts & Data Transfer Objects (DTOs)

### 5.1 Request and Response DTO Specifications (`Calculator.Api.Dtos`)

```csharp
using System.ComponentModel.DataAnnotations;
using System.Text.Json.Serialization;

namespace Calculator.Api.Dtos;

/// <summary>
/// Request payload for creating a new calculation record.
/// </summary>
public class CreateCalculationRequestDto
{
    [Required(ErrorMessage = "The number1 field is required.")]
    [JsonPropertyName("number1")]
    public int? Number1 { get; set; }

    [Required(ErrorMessage = "The number2 field is required.")]
    [JsonPropertyName("number2")]
    public int? Number2 { get; set; }
}

/// <summary>
/// Response payload issued upon creation of a calculation record.
/// </summary>
public class CalculationCreatedResponseDto
{
    [JsonPropertyName("id")]
    public int Id { get; set; }

    [JsonPropertyName("number1")]
    public int Number1 { get; set; }

    [JsonPropertyName("number2")]
    public int Number2 { get; set; }
}

/// <summary>
/// Composite response payload returned upon calculating total sum.
/// </summary>
public class CalculationSumResponseDto
{
    [JsonPropertyName("recordId")]
    public int RecordId { get; set; }

    [JsonPropertyName("number1")]
    public int Number1 { get; set; }

    [JsonPropertyName("number2")]
    public int Number2 { get; set; }

    [JsonPropertyName("mockValue")]
    public int MockValue { get; set; }

    [JsonPropertyName("total")]
    public int Total { get; set; }
}

/// <summary>
/// Internal DTO used by Calculator.Api to parse MockVendor responses.
/// </summary>
public class MockVendorValueResponseDto
{
    [JsonPropertyName("