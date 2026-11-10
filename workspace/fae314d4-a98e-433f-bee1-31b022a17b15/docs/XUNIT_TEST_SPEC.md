# XUnit Test Specifications

## 1. Contract Test Suite
- **UT-01**: Verify successful creation returns 201 and correct object mapping.
- **UT-02/05**: Verify validation logic for missing/invalid fields (400).
- **UT-06**: Verify 409 Conflict when email exists in DB.

## 2. Validation & Edge Cases
- **UT-10**: Verify 400 if client attempts to inject `Id`, `CreatedAt`, or `CreatedBy` in request body.
- **UT-12**: Verify email normalization (case-insensitivity) and whitespace trimming.

## 3. End-to-End Test Scenarios
- **IT-01**: Full flow: Auth -> POST /api/students -> DB check -> 201 response.
- **IT-04/05**: Verify 401/403 responses for missing/invalid JWT tokens.
- **IT-06**: Concurrent request test to ensure database unique constraint handles race conditions (409).