# Technical Design Document: Employment & Recruitment Management Portal (DOTNET_CSHARP)

## 1. Architecture Overview
The Employment & Recruitment Management Portal is built using an ASP.NET Core Web API backend with Entity Framework Core and SQLite persistence, paired with a modern Next.js frontend application. It integrates with a separate Mock Vendor API service for Identity Verification, Email Gateway, and SMS Gateway notifications.

### Module Boundaries
- **Web API Controllers (`Controllers/`)**: Handle HTTP requests, input validation, and route mapping for Candidates, Jobs, Applications, Interviews, and Vendor Call Logs.
- **Entity Models (`Models/`)**: Domain models representing database tables in SQLite via EF Core (`Candidate`, `Job`, `Application`, `Interview`, `VendorCallLog`).
- **Data Transfer Objects (`DTOs/`)**: Request and response payloads decoupled from internal database entities.
- **Services (`Services/`)**: Business logic layer, including communication clients targeting the Mock Vendor API.
- **Database Context (`Data/ApplicationDbContext.cs`)**: Manages SQLite connection, entities, relationships, and migrations.

---

## 2. Database Schema & Entities

### Candidates
- `Id` (int, PK)
- `FullName` (string, required)
- `Email` (string, required, unique)
- `PhoneNumber` (string, required)
- `Qualification` (string)
- `Experience` (string)
- `VerificationStatus` (string, default: "PENDING")
- `CreatedAt` (datetime)
- `UpdatedAt` (datetime)

### Jobs
- `Id` (int, PK)
- `Title` (string, required)
- `Description` (string, required)
- `Requirements` (string)
- `SalaryRange` (string)
- `Status` (string, e.g., "OPEN", "CLOSED")
- `CreatedAt` (datetime)
- `UpdatedAt` (datetime)

### Applications
- `Id` (int, PK)
- `CandidateId` (int, FK -> Candidates.Id)
- `JobId` (int, FK -> Jobs.Id)
- `Status` (string, values: "APPLIED", "SHORTLISTED", "REJECTED", "HIRED")
- `CreatedAt` (datetime)
- `UpdatedAt` (datetime)

### Interviews
- `Id` (int, PK)
- `ApplicationId` (int, FK -> Applications.Id)
- `ScheduledAt` (datetime, required)
- `Mode` (string, e.g., "ONLINE", "IN_PERSON")
- `Notes` (string)
- `Status` (string, values: "SCHEDULED", "RESCHEDULED", "CANCELLED")
- `CreatedAt` (datetime)
- `UpdatedAt` (datetime)

### VendorCallLogs
- `Id` (int, PK)
- `VendorType` (string: "IDENTITY", "EMAIL", "SMS")
- `Endpoint` (string)
- `Payload` (string)
- `ResponseStatus` (int)
- `ResponseBody` (string)
- `CreatedAt` (datetime)

---

## 3. API Endpoints & Payloads

### Candidates (`/api/candidates`)
- `POST /api/candidates`
  - Request: `{ "fullName": "John Doe", "email": "john@example.com", "phoneNumber": "1234567890", "qualification": "BSc", "experience": "3 years" }`
  - Response: `201 Created` with Candidate object.
- `GET /api/candidates` -> `200 OK` (List of candidates)
- `GET /api/candidates/{id}` -> `200 OK` or `404 Not Found`
- `PUT /api/candidates/{id}` -> `200 OK` or `400/404`
- `DELETE /api/candidates/{id}` -> `204 No Content` or `404 Not Found`

### Jobs (`/api/jobs`)
- `POST /api/jobs`
  - Request: `{ "title": "Software Engineer", "description": "Build APIs", "requirements": "C# / .NET", "salaryRange": "$80k-$100k", "status": "OPEN" }`
  - Response: `201 Created`
- `GET /api/jobs` -> `200 OK`
- `GET /api/jobs/{id}` -> `200 OK`
- `PUT /api/jobs/{id}` -> `200 OK`
- `DELETE /api/jobs/{id}` -> `204 No Content`

### Applications (`/api/applications`)
- `POST /api/applications`
  - Request: `{ "candidateId": 1, "jobId": 1 }`
  - Response: `201 Created` (triggers mock email notification)
- `GET /api/applications` -> `200 OK`
- `GET /api/applications/{id}` -> `200 OK`
- `PATCH /api/applications/{id}/status`
  - Request: `{ "status": "SHORTLISTED" }`
  - Response: `200 OK`

### Interviews (`/api/interviews`)
- `POST /api/interviews`
  - Request: `{ "applicationId": 1, "scheduledAt": "2025-05-01T10:00:00Z", "mode": "ONLINE", "notes": "Technical round" }`
  - Response: `201 Created` (triggers mock email & SMS alerts)
- `GET /api/interviews` -> `200 OK`
- `PUT /api/interviews/{id}` -> `200 OK`
- `DELETE /api/interviews/{id}` -> `204 No Content`

---

## 4. Mock Vendor API Integration
Base URLs are configurable via `appsettings.json`. The backend calls:
- `POST /vendor/identity/verify`
- `POST /vendor/email/send`
- `POST /vendor/sms/send`
All responses are logged in `VendorCallLogs` for audit and review.
