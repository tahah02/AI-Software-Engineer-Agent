# Technical Design Document: Employment & Recruitment Management Portal (DOTNET_CSHARP)

## 1. Architecture Overview
The Employment & Recruitment Management Portal is built using an ASP.NET Core Web API backend, an Entity Framework Core data layer utilizing SQLite persistence, and a Next.js (TypeScript) App Router frontend. It integrates with a standalone Mock Vendor API service for identity verification, email notifications, and SMS alerts.

### System Topology
- **Frontend**: Next.js App Router SPA running on dynamic port (default `3000`), communicating via REST clients.
- **Backend API**: ASP.NET Core Web API (`.NET 8`) adhering to Controllers, Services, and DTO patterns, running on dynamic port (default `5100`).
- **Database**: SQLite file database (`recruitment.db`) managed via EF Core Code-First migrations.
- **Mock Vendor API**: Separate service handling external integrations (`/vendor/identity/verify`, `/vendor/email/send`, `/vendor/sms/send`) running on dynamic port (default `5200`).

---

## 2. Module Boundaries & Project Structure
```text
EmploymentPortal/
├── src/
│   ├── EmploymentPortal.Api/
│   │   ├── Controllers/
│   │   ├── Models/
│   │   ├── DTOs/
│   │   ├── Services/
│   │   ├── Data/
│   │   └── Program.cs
│   ├── EmploymentPortal.Frontend/
│   │   ├── app/
│   │   ├── components/
│   │   └── lib/
│   └── MockVendorApi/
│       ├── Controllers/
│       └── Program.cs
└── tests/
    └── EmploymentPortal.Tests/
        ├── Controllers/
        └── Services/
```

---

## 3. Database Schema (SQLite & EF Core)

### Entities
1. **Candidate**
   - `Id` (Guid, PK)
   - `FullName` (string, required)
   - `Email` (string, required, unique)
   - `PhoneNumber` (string, required)
   - `Qualification` (string)
   - `Experience` (int)
   - `VerificationStatus` (string: PENDING, VERIFIED, FAILED)
   - `CreatedAt` (DateTime)
   - `UpdatedAt` (DateTime)

2. **Job**
   - `Id` (Guid, PK)
   - `Title` (string, required)
   - `Description` (string, required)
   - `Requirements` (string)
   - `SalaryRange` (string)
   - `Status` (string: DRAFT, ACTIVE, CLOSED)
   - `CreatedAt` (DateTime)
   - `UpdatedAt` (DateTime)

3. **Application**
   - `Id` (Guid, PK)
   - `CandidateId` (Guid, FK -> Candidates.Id)
   - `JobId` (Guid, FK -> Jobs.Id)
   - `Status` (string: APPLIED, SHORTLISTED, REJECTED, HIRED)
   - `CreatedAt` (DateTime)
   - `UpdatedAt` (DateTime)

4. **Interview**
   - `Id` (Guid, PK)
   - `ApplicationId` (Guid, FK -> Applications.Id)
   - `ScheduledAt` (DateTime, required)
   - `LocationOrLink` (string)
   - `Notes` (string)
   - `Status` (string: SCHEDULED, RESCHEDULED, CANCELLED)
   - `CreatedAt` (DateTime)
   - `UpdatedAt` (DateTime)

5. **VendorCallLog**
   - `Id` (Guid, PK)
   - `VendorType` (string: IDENTITY, EMAIL, SMS)
   - `Endpoint` (string)
   - `Payload` (string)
   - `ResponseStatus` (int)
   - `ResponseBody` (string)
   - `CreatedAt` (DateTime)

---

## 4. API Endpoints Specification

### Candidates (`/api/candidates`)
- `POST /api/candidates`: Create candidate. Validates unique email.
- `GET /api/candidates`: List all candidates with optional filtering.
- `GET /api/candidates/{id}`: Get candidate details.
- `PUT /api/candidates/{id}`: Update candidate.
- `DELETE /api/candidates/{id}`: Delete candidate.

### Jobs (`/api/jobs`)
- `POST /api/jobs`: Create job posting.
- `GET /api/jobs`: List jobs.
- `GET /api/jobs/{id}`: Job details.
- `PUT /api/jobs/{id}`: Update job.
- `DELETE /api/jobs/{id}`: Delete job.

### Applications (`/api/applications`)
- `POST /api/applications`: Submit application against active job. Prevents duplicates.
- `GET /api/applications`: List applications.
- `GET /api/applications/{id}`: Application details.
- `PATCH /api/applications/{id}/status`: Update application status (APPLIED, SHORTLISTED, REJECTED, HIRED).

### Interviews (`/api/interviews`)
- `POST /api/interviews`: Schedule interview.
- `GET /api/interviews`: List interviews.
- `PUT /api/interviews/{id}`: Reschedule interview.
- `DELETE /api/interviews/{id}`: Cancel interview.

### Mock Vendor Endpoints (`/vendor/*`)
- `POST /vendor/identity/verify`: Verify candidate identity.
- `POST /vendor/email/send`: Send email notification.
- `POST /vendor/sms/send`: Send SMS alert.
