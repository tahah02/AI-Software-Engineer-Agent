# XUnit Test Specifications

## 1. Contract Test Suite
- **POST /api/students**: 
  - Happy Path: Valid payload returns 201 and created object.
  - Validation: Missing required fields returns 400 Bad Request.
- **GET /api/students**: 
  - Returns 200 OK with list of students.
- **GET /api/students/{id}**: 
  - Valid ID: 200 OK.
  - Invalid ID: 404 Not Found.
- **PUT /api/students/{id}**: 
  - Valid Update: 200 OK.
  - Non-existent ID: 404 Not Found.
- **DELETE /api/students/{id}**: 
  - Valid Delete: 204 No Content.
  - Non-existent ID: 404 Not Found.

## 2. Validation & Edge Cases
- **Age Constraint**: Verify age < 1 returns 400.
- **Email Uniqueness**: Verify duplicate email returns 400/409.
- **Data Integrity**: Verify EnrollmentDate is set automatically.

## 3. End-to-End Test Scenarios
- Use `WebApplicationFactory<TEntryPoint>` to spin up in-memory SQLite database for integration testing of the full request pipeline.