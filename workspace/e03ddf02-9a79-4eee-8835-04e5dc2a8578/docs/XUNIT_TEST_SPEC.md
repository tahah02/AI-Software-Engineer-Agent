# Test Specifications (Jest / Supertest for Next.js)

## 1. Test Suite Overview
Tests validate the correctness of Next.js API routes for the Student LMS using Jest and Supertest against an SQLite test database.

## 2. Test Cases

### TC01: Create Student - Success
- **Endpoint**: POST `/api/students`
- **Payload**: `{"name": "Alice", "email": "alice@example.com", "age": 20, "grade": "A"}`
- **Expected Status**: `201 Created`
- **Assertions**: Returns object with generated `id`, correct properties.

### TC02: Create Student - Validation Error (Missing Email)
- **Endpoint**: POST `/api/students`
- **Payload**: `{"name": "Alice", "age": 20, "grade": "A"}`
- **Expected Status**: `400 Bad Request`
- **Assertions**: Error message regarding missing email.

### TC03: Get All Students
- **Endpoint**: GET `/api/students`
- **Expected Status**: `200 OK`
- **Assertions**: Returns an array containing created students.

### TC04: Get Student By ID - Success
- **Endpoint**: GET `/api/students/1`
- **Expected Status**: `200 OK`
- **Assertions**: Returns correct student object.

### TC05: Get Student By ID - Not Found
- **Endpoint**: GET `/api/students/9999`
- **Expected Status**: `404 Not Found`
- **Assertions**: Error message stating student not found.

### TC06: Update Student - Success
- **Endpoint**: PUT `/api/students/1`
- **Payload**: `{"name": "Alice Updated", "email": "alice@example.com", "age": 21, "grade": "A+"}`
- **Expected Status**: `200 OK`
- **Assertions**: Returns updated student data.

### TC07: Delete Student - Success
- **Endpoint**: DELETE `/api/students/1`
- **Expected Status**: `204 No Content`
- **Assertions**: Body is empty; subsequent GET returns 404.