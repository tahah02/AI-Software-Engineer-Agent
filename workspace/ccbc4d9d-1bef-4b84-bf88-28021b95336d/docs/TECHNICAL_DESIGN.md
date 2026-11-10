# Technical Design Document (DOTNET_CSHARP)

## 1. Overview
This document outlines the technical architecture and specifications for the ASP.NET Core Web API application using C#, Entity Framework Core, and SQLite persistence, aligned with the requirements.

## 2. Architecture & Module Boundaries
- **Controllers**: Handle HTTP requests, input validation via DataAnnotations or FluentValidation, and return appropriate ActionResults.
- **Services**: Contain the business logic, transaction management, and coordinate between repositories/DbContext and DTOs.
- **Models / Entities**: Domain models mapped to SQLite via EF Core.
- **DTOs**: Data Transfer Objects for request payloads and response serialization.
- **DbContext**: `AppDbContext` managing database connectivity and change tracking.

## 3. Database Schema (SQLite)
- **Table: `Items`**
  - `Id` (INTEGER, Primary Key, Auto-increment)
  - `Name` (TEXT, Required, Max Length 100)
  - `Description` (TEXT, Optional)
  - `Price` (REAL, Required)
  - `CreatedAt` (DATETIME, Required)

## 4. API Endpoints & Payloads
- **GET /api/items**
  - Response: 200 OK with List of ItemDto
- **GET /api/items/{id}**
  - Response: 200 OK with ItemDto or 404 Not Found
- **POST /api/items**
  - Request Body: `CreateItemDto` (`Name`, `Description`, `Price`)
  - Response: 201 Created with ItemDto or 400 Bad Request
- **PUT /api/items/{id}**
  - Request Body: `UpdateItemDto` (`Name`, `Description`, `Price`)
  - Response: 204 No Content, 400 Bad Request, or 404 Not Found
- **DELETE /api/items/{id}**
  - Response: 204 No Content or 404 Not Found