# XUnit Test Specifications: Employment Portal Backend

## 1. Candidate Controller Tests (`CandidatesControllerTests.cs`)
- **TestCreateCandidate_Success**: Posts valid candidate payload, asserts `201 Created` and correct JSON properties.
- **TestCreateCandidate_DuplicateEmail**: Posts candidate with existing email, asserts `400 Bad Request`.
- **TestGetCandidates_ReturnsList**: Calls `GET /api/candidates`, asserts `200 OK` and non-empty list.
- **TestGetCandidateById_NotFound**: Requests non-existent ID, asserts `404 Not Found`.
- **TestUpdateCandidate_Success**: Updates candidate details, asserts `200 OK`.
- **TestDeleteCandidate_Success**: Deletes candidate, asserts `204 No Content`.

## 2. Job Controller Tests (`JobsControllerTests.cs`)
- **TestCreateJob_Success**: Posts valid job posting, asserts `201 Created`.
- **TestGetJobs_ReturnsList**: Calls `GET /api/jobs`, asserts `200 OK`.
- **TestUpdateJob_Success**: Updates job status/salary, asserts `200 OK`.
- **TestDeleteJob_Success**: Deletes job, asserts `204 No Content`.

## 3. Application Controller Tests (`ApplicationsControllerTests.cs`)
- **TestSubmitApplication_Success**: Submits valid application referencing existing candidate and job, asserts `201 Created` and verifies mock vendor email notification is triggered.
- **TestSubmitApplication_Duplicate**: Submits duplicate application for same candidate & job, asserts `400 Bad Request`.
- **TestUpdateApplicationStatus_Success**: Patches status to `SHORTLISTED`, asserts `200 OK`.

## 4. Interview Controller Tests (`InterviewsControllerTests.cs`)
- **TestScheduleInterview_Success**: Schedules interview with valid application ID, asserts `201 Created` and triggers mock SMS/Email notifications.
- **TestRescheduleInterview_Success**: Updates scheduled time, asserts `200 OK`.
- **TestCancelInterview_Success**: Deletes/cancels interview, asserts `204 No Content`.

## 5. Mock Vendor Integration & Resilience Tests (`VendorServiceTests.cs`)
- **TestVendorEmailGateway_Success**: Verifies backend successfully dispatches and logs email notifications.
- **TestVendorTimeout_Handling**: Simulates mock vendor timeout scenario, asserts graceful error handling and logging without crashing core application flow.
