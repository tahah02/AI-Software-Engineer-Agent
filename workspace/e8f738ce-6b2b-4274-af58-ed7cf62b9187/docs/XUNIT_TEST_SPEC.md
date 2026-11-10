# XUnit Test Specifications: Employment & Recruitment Management Portal

## 1. Overview
This document specifies the unit and integration tests to be implemented using xUnit, Moq, and Microsoft.AspNetCore.Mvc.Testing for the ASP.NET Core Web API backend.

## 2. Test Suites & Test Cases

### CandidateControllerTests
- `CreateCandidate_ValidPayload_Returns201Created`: Verifies candidate creation with valid details including GitRepositoryUrl (`https://github.com/tahah02/Test-Project-AAISE.git`).
- `CreateCandidate_InvalidEmail_Returns400BadRequest`: Verifies validation rules on candidate creation.
- `GetCandidateById_ExistingId_Returns200Ok`: Verifies retrieval of candidate by valid GUID.
- `GetCandidateById_NonExistingId_Returns404NotFound`: Verifies appropriate error status on missing candidate.
- `UpdateCandidate_ValidPayload_Returns200Ok`: Verifies successful update including Git repository link modifications.

### JobControllerTests
- `CreateJob_ValidPayload_Returns201Created`: Verifies job posting with valid attributes.
- `GetJobs_Returns200OkWithList`: Verifies fetching all jobs.
- `UpdateJob_ExistingId_Returns200Ok`: Verifies job update.

### ApplicationControllerTests
- `CreateApplication_ValidCandidateAndJob_Returns201Created`: Verifies application workflow creation.
- `UpdateApplicationStatus_ValidStatus_Returns200Ok`: Verifies status updates (e.g., to SHORTLISTED or HIRED).

### InterviewControllerTests
- `ScheduleInterview_ValidPayload_Returns201Created`: Verifies interview scheduling.
- `RescheduleInterview_ExistingId_Returns200Ok`: Verifies interview date/time update.

### VendorControllerTests
- `VerifyIdentity_ValidPayload_Returns200Ok`: Verifies external vendor identity verification logging and response.
- `SendEmail_ValidPayload_Returns200Ok`: Verifies mock email dispatch.

### HealthControllerTests
- `GetHealth_Returns200Ok`: Verifies health check endpoint returns active status.