# XUnit Test Specifications: Employment Portal (DOTNET_CSHARP)

## 1. Overview
This document defines the suite of XUnit automated unit and integration tests required for the ASP.NET Core backend (`EmploymentPortal.Tests`). Tests cover happy paths, negative validation cases, boundary constraints, and integration with SQLite persistence.

---

## 2. Test Categories & Cases

### Candidate Controller & Service Tests
- **TC-CAN-01 (Happy Path)**: `CreateCandidate_ValidPayload_ReturnsCreated201`
  - *Payload*: Valid name, unique email, phone, qualification, experience.
  - *Assertion*: Status code 201 Created, returned DTO matches input, entity stored in SQLite.
- **TC-CAN-02 (Negative)**: `CreateCandidate_DuplicateEmail_ReturnsBadRequest400`
  - *Payload*: Candidate with an existing email.
  - *Assertion*: Status code 400 Bad Request, error message specifies duplicate email.
- **TC-CAN-03 (Edge Case)**: `GetCandidate_NonExistentId_ReturnsNotFound404`
  - *Parameter*: Random Guid.
  - *Assertion*: Status code 404 Not Found.

### Job Controller & Service Tests
- **TC-JOB-01 (Happy Path)**: `CreateJob_ValidPayload_ReturnsCreated201`
  - *Payload*: Title, description, requirements, salary range, status ACTIVE.
  - *Assertion*: Status code 201 Created.
- **TC-JOB-02 (Negative)**: `CreateJob_MissingTitle_ReturnsUnprocessable422`
  - *Payload*: Empty title.
  - *Assertion*: Status code 400/422 validation failure.

### Application Controller & Service Tests
- **TC-APP-01 (Happy Path)**: `SubmitApplication_ValidReferences_ReturnsCreated201`
  - *Payload*: Valid CandidateId and active JobId.
  - *Assertion*: Status code 201 Created, triggers mock email notification, application status is APPLIED.
- **TC-APP-02 (Negative)**: `SubmitApplication_DuplicateApplication_ReturnsBadRequest400`
  - *Payload*: Same candidate applying twice to the same job.
  - *Assertion*: Status code 400 Bad Request, prevents duplicate application.
- **TC-APP-03 (Happy Path)**: `UpdateApplicationStatus_ValidTransition_ReturnsOk200`
  - *Parameter*: Application ID, status SHORTLISTED.
  - *Assertion*: Status code 200 OK, updated status reflected in database.

### Interview Controller & Service Tests
- **TC-INT-01 (Happy Path)**: `ScheduleInterview_ValidPayload_ReturnsCreated201`
  - *Payload*: ApplicationId, future ScheduledAt datetime, location.
  - *Assertion*: Status code 201 Created, triggers mock SMS/Email notifications.
- **TC-INT-02 (Negative)**: `ScheduleInterview_PastDate_ReturnsBadRequest400`
  - *Payload*: ScheduledAt in the past.
  - *Assertion*: Status code 400 Bad Request.

### Mock Vendor Integration Tests
- **TC-VEN-01 (Happy Path)**: `VerifyIdentity_ValidToken_ReturnsSuccess`
  - *Assertion*: Returns success status and logs response in `VendorCallLogs`.
- **TC-VEN-02 (Error Handling)**: `SendEmail_TimeoutScenario_HandlesGracefully`
  - *Assertion*: Catches timeout exception from mock vendor and records failure log without crashing backend.
