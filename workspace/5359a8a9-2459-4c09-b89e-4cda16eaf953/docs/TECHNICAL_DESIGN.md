# Technical Design Document: Student LMS API (Next.js TypeScript App Router)

## 1. System Overview
The Student Learning Management System (LMS) API is built using Next.js App Router and TypeScript, utilizing SQLite via Prisma ORM for data persistence. It provides a full set of CRUD operations for managing student records.

## 2. Module Boundaries & Architecture
- **Framework**: Next.js App Router (`app/api/students/...`)
- **Language**: TypeScript
- **ORM**: Prisma ORM
- **Database**: SQLite (`studentLMSdb.db`)
- **Validation**: Zod

## 3. Database Schema (Prisma)
```prisma
datasource db {
  provider = "sqlite"
  url      = "file:./studentLMSdb.db"
}

generator client {
  provider = "prisma-client-js"
}

model Student {
  id        Int      @id @default(autoincrement())
  name      String
  email     String   @unique
  age       Int
  grade     String
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}
```

## 4. API Endpoints & Payloads

### GET /api/students
- **Description**: Retrieve all students.
- **Response (200 OK)**:
```json
[
  {
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    "age": 20,
    "grade": "A",
    "createdAt": "2023-10-01T00:00:00.000Z",
    "updatedAt": "2023-10-01T00:00:00.000Z"
  }
]
```

### POST /api/students
- **Description**: Create a new student.
- **Request Body**:
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "age": 22,
  "grade": "B"
}
```
- **Response (201 Created)**: Returns the created student object.
- **Response (400 Bad Request)**: Validation error.

### GET /api/students/[id]
- **Description**: Get a student by ID.
- **Response (200 OK)**: Student object.
- **Response (404 Not Found)**: Student not found.

### PUT /api/students/[id]
- **Description**: Update student details.
- **Request Body**:
```json
{
  "name": "Jane Smith",
  "email": "janesmith@example.com",
  "age": 23,
  "grade": "A"
}
```
- **Response (200 OK)**: Updated student object.
- **Response (404 Not Found)**: Student not found.

### DELETE /api/students/[id]
- **Description**: Delete a student.
- **Response (204 No Content)**: Successfully deleted.
- **Response (404 Not Found)**: Student not found.