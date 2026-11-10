# Technical Design Document: Student Management System

## 1. System Architecture
This system follows a layered architecture using ASP.NET Core Web API (.NET 8).
- **Controller Layer**: Handles HTTP requests and maps to Service layer.
- **Service Layer**: Contains business logic and validation.
- **Repository Layer**: Abstracts EF Core data access.
- **Data Access Layer**: Entity Framework Core with SQLite provider.
- **Dependency Injection**: Built-in .NET DI container for service registration.

## 2. Domain Models & Schemas
### Student Entity
- `StudentId`: int (Primary Key, Identity)
- `FullName`: string (Required, MaxLength: 100)
- `Email`: string (Required, Unique)
- `Age`: int (Required, Range: 1-120)
- `Department`: string (Required)
- `EnrollmentDate`: DateTime (Default: DateTime.UtcNow)

## 3. API Route Specifications
| Method | Endpoint | Description | Request Body | Response |
| :--- | :--- | :--- | :--- | :--- |
| POST | /api/students | Create Student | {FullName, Email, Age, Department} | 201 Created |
| GET | /api/students | List All | N/A | 200 OK |
| GET | /api/students/{id} | Get by ID | N/A | 200 OK / 404 |
| PUT | /api/students/{id} | Update | {FullName, Email, Age, Department} | 200 OK / 404 |
| DELETE | /api/students/{id} | Delete | N/A | 204 No Content / 404 |

## 4. Business Logic & Validation
- **Validation**: DataAnnotations on DTOs and FluentValidation for complex rules.
- **Error Handling**: Global Exception Middleware returning ProblemDetails (RFC 7807).
- **Persistence**: SQLite database file managed via EF Core Migrations.