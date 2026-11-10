# Technical Design Document

## 1. System Architecture
The system follows a layered architecture: Controller -> Service -> Repository. 
- **Controller**: Handles HTTP requests, model binding, and returns standardized responses.
- **Service**: Contains business logic, audit field population, and validation orchestration.
- **Repository**: Abstracts EF Core data access for SQLite.
- **Persistence**: SQLite via Entity Framework Core.

## 2. Domain Models & Schemas
### Student Entity
- `Id`: int (PK, Auto-increment)
- `FullName`: string (Required, 2-100 chars)
- `Email`: string (Required, Unique, Normalized)
- `Age`: int (Required, 1-120)
- `Department`: string (Required, 2-100 chars)
- `EnrollmentDate`: DateTime (UTC)
- `CreatedAt`: DateTime (UTC)
- `CreatedBy`: string
- `UpdatedAt`: DateTime? (Nullable)
- `UpdatedBy`: string? (Nullable)

## 3. API Route Specifications
- **POST /api/students**
  - **Request**: `CreateStudentRequest` (FullName, Email, Age, Department)
  - **Response**: `StudentResponse` (All fields including audit)
  - **Status Codes**: 201 (Created), 400 (Validation), 401 (Unauthorized), 403 (Forbidden), 409 (Conflict), 413 (Payload Too Large), 415 (Unsupported Media Type), 500 (Server Error)

## 4. Business Logic & Validation
- **Validation**: FluentValidation for request DTOs.
- **Audit**: Service layer injects `IHttpContextAccessor` to retrieve `User.Identity.Name` for `CreatedBy`.
- **Security**: JWT Bearer authentication with `[Authorize(Policy = "student:create")]`.