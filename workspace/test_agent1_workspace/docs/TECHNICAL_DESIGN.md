# Technical Design Document: Employment & Recruitment Management Portal

## 1. System Overview
The Employment & Recruitment Management Portal is an ASP.NET Core Web API designed to manage job postings, candidate profiles, job applications, and interview schedules. The backend utilizes Entity Framework Core (EF Core) with SQLite for data persistence, following clean architecture principles with Controllers, Services, DTOs, Data Context, and Entities.

## 2. Target Framework & Technology Stack
- **Framework**: .NET 8.0 / ASP.NET Core Web API
- **ORM**: Entity Framework Core 8.0
- **Database**: SQLite
- **Testing**: xUnit, Microsoft.AspNetCore.Mvc.Testing, EF Core SQLite In-Memory

## 3. Architecture & Project Structure
```
RecruitmentPortal/
├── Controllers/
│   ├── JobsController.cs
│   ├── CandidatesController.cs
│   ├── ApplicationsController.cs
│   └── InterviewsController.cs
├── Data/
│   ├── AppDbContext.cs
│   └── Migrations/
├── Models/
│   ├── Entities/
│   │   ├── Job.cs
│   │   ├── Candidate.cs
│   │   ├── Application.cs
│   │   └── Interview.cs
│   ├── DTOs/
│   │   ├── JobDtos.cs
│   │   ├── CandidateDtos.cs
│   │   ├── ApplicationDtos.cs
│   │   └── InterviewDtos.cs
│   └── Enums/
│       ├── JobType.cs
│       ├── JobStatus.cs
│       ├── ApplicationStatus.cs
│       └── InterviewStatus.cs
├── Services/
│   ├── Interfaces/
│   │   ├── IJobService.cs
│   │   ├── ICandidateService.cs
│   │   ├── IApplicationService.cs
│   │   └── IInterviewService.cs
│   └── Implementations/
│       ├── JobService.cs
│       ├── CandidateService.cs
│       ├── ApplicationService.cs
│       └── InterviewService.cs
├── Middleware/
│   └── ExceptionHandlingMiddleware.cs
└── Program.cs
```

## 4. Domain Models & Database Schema

### 4.1 Entities

#### Job
- `Id`: int (PK, Auto-Increment)
- `Title`: string (Required, Max 150)
- `Description`: string (Required)
- `Company`: string (Required, Max 100)
- `Location`: string (Required, Max 100)
- `JobType`: JobType Enum (FullTime, PartTime, Contract, Remote)
- `JobStatus`: JobStatus Enum (Draft, Open, Closed)
- `SalaryRange`: string (Optional, Max 50)
- `CreatedAt`: DateTime (UTC)
- `UpdatedAt`: DateTime (UTC)
- `Applications`: ICollection<Application>

#### Candidate
- `Id`: int (PK, Auto-Increment)
- `FirstName`: string (Required, Max 50)
- `LastName`: string (Required, Max 50)
- `Email`: string (Required, Max 100, Unique Index)
- `Phone`: string (Required, Max 20)
- `ResumeUrl`: string (Optional)
- `Skills`: string (Optional, Comma-separated tags)
- `ExperienceYears`: int (Min 0)
- `CreatedAt`: DateTime (UTC)
- `Applications`: ICollection<Application>

#### Application
- `Id`: int (PK, Auto-Increment)
- `JobId`: int (FK -> Jobs.Id, Cascade Delete)
- `CandidateId`: int (FK -> Candidates.Id, Cascade Delete)
- `CoverLetter`: string (Optional)
- `Status`: ApplicationStatus Enum (Submitted, UnderReview, InterviewScheduled, Offered, Rejected, Withdrawn)
- `AppliedDate`: DateTime (UTC)
- `Feedback`: string (Optional)
- `Interviews`: ICollection<Interview>

#### Interview
- `Id`: int (PK, Auto-Increment)
- `ApplicationId`: int (FK -> Applications.Id, Cascade Delete)
- `ScheduledAt`: DateTime (UTC)
- `Status`: InterviewStatus Enum (Scheduled, Completed, Cancelled, Rescheduled)
- `Notes`: string (Optional, Max 1000)
- `CreatedAt`: DateTime (UTC)

### 4.2 Enums
- `JobType`: `FullTime = 0`, `PartTime = 1`, `Contract = 2`, `Remote = 3`
- `JobStatus`: `Draft = 0`, `Open = 1`, `Closed = 2`
- `ApplicationStatus`: `Submitted = 0`, `UnderReview = 1`, `InterviewScheduled = 2`, `Offered = 3`, `Rejected = 4`, `Withdrawn = 5`
- `InterviewStatus`: `Scheduled = 0`, `Completed = 1`, `Cancelled = 2`, `Rescheduled = 3`

## 5. API Endpoints Specification

### 5.1 Jobs API (`/api/jobs`)
- `GET /api/jobs` - List jobs (Query Params: `status`, `search`, `jobType`)
- `GET /api/jobs/{id}` - Get job by ID
- `POST /api/jobs` - Create a new job
- `PUT /api/jobs/{id}` - Update job details
- `DELETE /api/jobs/{id}` - Delete job

### 5.2 Candidates API (`/api/candidates`)
- `GET /api/candidates` - List candidates (Query Params: `email`, `search`)
- `GET /api/candidates/{id}` - Get candidate details
- `POST /api/candidates` - Create candidate profile
- `PUT /api/candidates/{id}` - Update candidate profile
- `DELETE /api/candidates/{id}` - Delete candidate

### 5.3 Applications API (`/api/applications`)
- `GET /api/applications` - List applications (Query Params: `jobId`, `candidateId`, `status`)
- `GET /api/applications/{id}` - Get application by ID
- `POST /api/applications` - Submit new job application
- `PUT /api/applications/{id}/status` - Update application status & feedback
- `DELETE /api/applications/{id}` - Delete/Withdraw application

### 5.4 Interviews API (`/api/interviews`)
- `GET /api/interviews` - List interviews (Query Params: `applicationId`, `status`)
- `GET /api/interviews/{id}` - Get interview by ID
- `POST /api/interviews` - Schedule a new interview
- `PUT /api/interviews/{id}` - Update interview details (ScheduledAt, Status, Notes)
- `DELETE /api/interviews/{id}` - Delete/Cancel interview

## 6. DTO Definitions & Validation Rules

### Job DTOs
- `CreateJobDto`: `Title` [Required, Max 150], `Description` [Required], `Company` [Required, Max 100], `Location` [Required, Max 100], `JobType` [Enum], `SalaryRange` [Max 50]
- `UpdateJobDto`: Same as `CreateJobDto` plus `JobStatus` [Enum]
- `JobResponseDto`: Output representation including `Id`, `CreatedAt`, `UpdatedAt`

### Candidate DTOs
- `CreateCandidateDto`: `FirstName` [Required, Max 50], `LastName` [Required, Max 50], `Email` [Required, EmailAddress, Max 100], `Phone` [Required, Max 20], `ResumeUrl` [Url], `Skills` [Max 500], `ExperienceYears` [Range(0, 50)]
- `UpdateCandidateDto`: Same as `CreateCandidateDto`
- `CandidateResponseDto`: Output representation including `Id`, `CreatedAt`

### Application DTOs
- `CreateApplicationDto`: `JobId` [Required], `CandidateId` [Required], `CoverLetter` [Max 2000]
- `UpdateApplicationStatusDto`: `Status` [Required, Enum], `Feedback` [Max 1000]
- `ApplicationResponseDto`: Includes nested minimal Job (`JobResponseDto`) and Candidate (`CandidateResponseDto`) summary

### Interview DTOs
- `CreateInterviewDto`: `ApplicationId` [Required], `ScheduledAt` [Required, Future DateTime], `Notes` [Max 1000]
- `UpdateInterviewDto`: `ScheduledAt` [Required, Future DateTime], `Status` [Required, Enum], `Notes` [Max 1000]
- `InterviewResponseDto`: Output representation including `Id`, `ApplicationId`, `ScheduledAt`, `Status`, `Notes`, `CreatedAt`

## 7. Business Rules & Validation
1. Candidate Email must be unique across the system.
2. Candidates cannot apply for the same job more than once (`JobId` + `CandidateId` unique constraint check).
3. Applications can only be created for Jobs with status `Open` (`JobStatus == Open`).
4. Interviews can only be scheduled for existing Applications, and `ScheduledAt` must be a valid future timestamp.
5. If a Job, Candidate, or Application is deleted, associated child records are cascade deleted.
6. Standard error responses return ASP.NET Core `ProblemDetails` format (RFC 7807).