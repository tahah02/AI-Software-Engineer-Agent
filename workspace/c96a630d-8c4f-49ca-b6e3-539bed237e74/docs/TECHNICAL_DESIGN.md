# Technical Design Document: Recruitment Portal
Target Framework: DOTNET_CSHARP (ASP.NET Core 9.0)
## Architecture
Clean Architecture with Controllers, EF Core SQLite DbContext, Models, and DTOs.
## Entities
1. Job: Id (int), Title (string), Department (string), Status (string), CreatedAt (DateTime)
2. Candidate: Id (int), FullName (string), Email (string), Phone (string)
3. Application: Id (int), JobId (int), CandidateId (int), Status (string), AppliedAt (DateTime)
## Endpoints
- GET /api/jobs, POST /api/jobs, GET /api/jobs/{id}
- GET /api/candidates, POST /api/candidates, GET /api/candidates/{id}
- GET /api/applications, POST /api/applications
