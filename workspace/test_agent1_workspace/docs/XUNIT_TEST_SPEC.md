# XUnit Test Specifications: Employment & Recruitment Management Portal

## 1. Overview
This document details the xUnit test specifications for the Employment & Recruitment Management Portal API. Tests are designed to validate controllers, services, business rules, model validations, and integration flows using xUnit and `WebApplicationFactory` with SQLite In-Memory persistence.

## 2. Test Suites

### 2.1 JobsControllerTests
- **TC-JOB-01**: `GetJobs_ReturnsOk_WithListOfJobs`
  - Action: GET `/api/jobs`
  - Expected: 200 OK, returns list of jobs matching optional filters.
- **TC-JOB-02**: `GetJobById_ReturnsOk_WhenJobExists`
  - Action: GET `/api/jobs/{id}`
  - Expected: 200 OK, returns specific job.
- **TC-JOB-03**: `GetJobById_ReturnsNotFound_WhenJobDoesNotExist`
  - Action: GET `/api/jobs/9999`
  - Expected: 404 Not Found.
- **TC-JOB-04**: `CreateJob_ReturnsCreated_WhenValidDto`
  - Action: POST `/api/jobs` with valid `CreateJobDto`
  - Expected: 201 Created, returns created job with location header.
- **TC-JOB-05**: `CreateJob_ReturnsBadRequest_WhenMissingRequiredFields`
  - Action: POST `/api/jobs` with invalid/empty title
  - Expected: 400 Bad Request.
- **TC-JOB-06**: `UpdateJob_ReturnsNoContent_WhenValid`
  - Action: PUT `/api/jobs/{id}` with valid `UpdateJobDto`
  - Expected: 204 No Content.
- **TC-JOB-07**: `DeleteJob_ReturnsNoContent_WhenExists`
  - Action: DELETE `/api/jobs/{id}`
  - Expected: 204 No Content.

### 2.2 CandidatesControllerTests
- **TC-CAND-01**: `GetCandidates_ReturnsOk`
  - Action: GET `/api/candidates`
  - Expected: 200 OK.
- **TC-CAND-02**: `CreateCandidate_ReturnsCreated_WhenValid`
  - Action: POST `/api/candidates` with unique email
  - Expected: 201 Created.
- **TC-CAND-03**: `CreateCandidate_ReturnsBadRequest_WhenDuplicateEmail`
  - Action: POST `/api/candidates` with existing email
  - Expected: 400 Bad Request / 422 Unprocessable Entity (Conflict via ProblemDetails).
- **TC-CAND-04**: `GetCandidateById_ReturnsNotFound_WhenMissing`
  - Action: GET `/api/candidates/9999`
  - Expected: 404 Not Found.

### 2.3 ApplicationsControllerTests
- **TC-APP-01**: `CreateApplication_ReturnsCreated_WhenJobOpenAndNotDuplicate`
  - Action: POST `/api/applications` with valid `JobId` (Open) and `CandidateId`
  - Expected: 201 Created.
- **TC-APP-02**: `CreateApplication_ReturnsBadRequest_WhenJobClosed`
  - Action: POST `/api/applications` with `JobId` status Closed
  - Expected: 400 Bad Request (Business Rule Violation).
- **TC-APP-03**: `CreateApplication_ReturnsBadRequest_WhenDuplicateApplication`
  - Action: POST `/api/applications` twice for same `JobId` and `CandidateId`
  - Expected: 400 Bad Request.
- **TC-APP-04**: `UpdateApplicationStatus_ReturnsNoContent_WhenValid`
  - Action: PUT `/api/applications/{id}/status` with valid status and feedback
  - Expected: 204 No Content.

### 2.4 InterviewsControllerTests
- **TC-INT-01**: `GetInterviews_ReturnsOk`
  - Action: GET `/api/interviews` with optional filters
  - Expected: 200 OK, returns list of interviews.
- **TC-INT-02**: `GetInterviewById_ReturnsOk_WhenExists`
  - Action: GET `/api/interviews/{id}`
  - Expected: 200 OK.
- **TC-INT-03**: `GetInterviewById_ReturnsNotFound_WhenMissing`
  - Action: GET `/api/interviews/9999`
  - Expected: 404 Not Found.
- **TC-INT-04**: `CreateInterview_ReturnsCreated_WhenValid`
  - Action: POST `/api/interviews` with valid `ApplicationId` and future `ScheduledAt`
  - Expected: 201 Created, returns interview details.
- **TC-INT-05**: `CreateInterview_ReturnsBadRequest_WhenApplicationNotFound`
  - Action: POST `/api/interviews` with non-existent `ApplicationId`
  - Expected: 400 Bad Request / 404 Not Found.
- **TC-INT-06**: `CreateInterview_ReturnsBadRequest_WhenScheduledAtInPast`
  - Action: POST `/api/interviews` with past `ScheduledAt` datetime
  - Expected: 400 Bad Request (Validation Error).
- **TC-INT-07**: `UpdateInterview_ReturnsNoContent_WhenValid`
  - Action: PUT `/api/interviews/{id}` with valid update payload
  - Expected: 204 No Content.
- **TC-INT-08**: `DeleteInterview_ReturnsNoContent_WhenExists`
  - Action: DELETE `/api/interviews/{id}`
  - Expected: 204 No Content.

## 3. Error Handling and Edge Cases
- **TC-ERR-01**: Global exception handling middleware returns RFC 7807 `ProblemDetails` for unhandled exceptions.
- **TC-ERR-02**: Validation attributes on all DTOs properly trigger 400 Bad Request responses with model state validation dictionary.