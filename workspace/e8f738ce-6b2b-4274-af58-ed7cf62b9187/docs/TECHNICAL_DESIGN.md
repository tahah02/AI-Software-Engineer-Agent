# Technical Design Document: Employment & Recruitment Management Portal (.NET 8)

## 1. System Architecture & Overview
The Employment & Recruitment Management Portal backend is implemented as an ASP.NET Core Web API targeting .NET 8, utilizing Entity Framework Core with SQLite for data persistence, following the Controller-Service pattern. It features comprehensive candidate and job management, application tracking, interview scheduling, external vendor integrations (identity verification, email, SMS), and explicit support for Git repository URL linking (such as `https://github.com/tahah02/Test-Project-AAISE.git`).

## 2. Module Boundaries & Components
- **Controllers**: Handle HTTP requests, model binding, and return appropriate status codes (`CandidatesController`, `JobsController`, `ApplicationsController`, `InterviewsController`, `VendorController`, `HealthController`).
- **Services**: Contain the core business logic (`CandidateService`, `JobService`, `ApplicationService`, `InterviewService`, `VendorIntegrationService`).
- **Data / EF Core**: `AppDbContext` managing database configurations, entities, and SQLite persistence.
- **DTOs**: Data transfer objects with validation attributes ensuring payload integrity.

## 3. Database Schema & Entities (SQLite via EF Core)

### Entities
1. **Candidate**
   - `Id` (Guid, PK)
   - `FullName` (string, required)
   - `Email` (string, required, unique)
   - `PhoneNumber` (string, required)
   - `Qualification` (string, required)
   - `Experience` (string, required)
   - `GitRepositoryUrl` (string, optional - e.g., for `https://github.com/tahah02/Test-Project-AAISE.git` integration and code push references)
   - `VerificationStatus` (string, default: "Pending")
   - `CreatedAt` (DateTime), `UpdatedAt` (DateTime)

2. **Job**
   - `Id` (Guid, PK)
   - `Title` (string, required)
   - `Description` (string, required)
   - `Requirements` (string, required)
   - `SalaryRange` (string, required)
   - `Status` (string, required: "Active" / "Closed")
   - `CreatedAt` (DateTime), `UpdatedAt` (DateTime)

3. **Application**
   - `Id` (Guid, PK)
   - `CandidateId` (Guid, FK)
   - `JobId` (Guid, FK)
   - `Status` (string, required: "APPLIED", "SHORTLISTED", "REJECTED", "HIRED")
   - `CreatedAt` (DateTime), `UpdatedAt` (DateTime)

4. **Interview**
   - `Id` (Guid, PK)
   - `ApplicationId` (Guid, FK)
   - `ScheduledAt` (DateTime, required)
   - `InterviewerName` (string, required)
   - `LocationOrLink` (string, required)
   - `Status` (string, required: "SCHEDULED", "RESCHEDULED", "CANCELED")
   - `CreatedAt` (DateTime), `UpdatedAt` (DateTime)

5. **VendorCallLog**
   - `Id` (Guid, PK)
   - `VendorType` (string)
   - `Endpoint` (string)
   - `RequestBody` (string)
   - `ResponseBody` (string)
   - `StatusCode` (int)
   - `IsSuccess` (bool)
   - `Timestamp` (DateTime)

## 4. API Endpoints Specification
- `POST /api/candidates` (Supports optional Git Repository URL such as `https://github.com/tahah02/Test-Project-AAISE.git`)
- `GET /api/candidates`, `GET /api/candidates/{id}`
- `PUT /api/candidates/{id}` (Supports updating Git Repository URL)
- `DELETE /api/candidates/{id}`
- `POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{id}`, `PUT /api/jobs/{id}`, `DELETE /api/jobs/{id}`
- `POST /api/applications`, `GET /api/applications`, `GET /api/applications/{id}`, `PATCH /api/applications/{id}/status`
- `POST /api/interviews`, `GET /api/interviews`, `PUT /api/interviews/{id}`, `DELETE /api/interviews/{id}`
- `POST /vendor/identity/verify`, `POST /vendor/email/send`, `POST /vendor/sms/send`
- `GET /health`

## 5. Error Handling & Validation
- Standard ASP.NET Core model validation returning `400 Bad Request` on invalid payloads.
- Entity not found scenarios return `404 Not Found`.
- Unhandled exceptions return `500 Internal Server Error` with formatted JSON error payload.