# XUnit Test Specifications (DOTNET_CSHARP)

## 1. Overview
This document defines the comprehensive XUnit test cases for validating the ASP.NET Core Web API application.

## 2. Test Suites

### 2.1. ItemsControllerTests (Integration / Controller Tests)
- **GetItems_ReturnsOk_WithListOfItems**
  - *Setup*: Seed SQLite in-memory database with test items.
  - *Action*: Invoke `GET /api/items`.
  - *Assertion*: Status code 200 OK, response body is a JSON array containing the seeded items.

- **GetItemById_ReturnsOk_WhenItemExists**
  - *Setup*: Seed item with ID 1.
  - *Action*: Invoke `GET /api/items/1`.
  - *Assertion*: Status code 200 OK, response body matches the item details.

- **GetItemById_ReturnsNotFound_WhenItemDoesNotExist**
  - *Action*: Invoke `GET /api/items/999`.
  - *Assertion*: Status code 404 Not Found.

- **CreateItem_ReturnsCreated_WhenPayloadIsValid**
  - *Setup*: Valid `CreateItemDto` payload.
  - *Action*: Invoke `POST /api/items`.
  - *Assertion*: Status code 201 Created, Location header present, response contains created item with generated ID.

- **CreateItem_ReturnsBadRequest_WhenPayloadIsInvalid**
  - *Setup*: Invalid `CreateItemDto` payload (e.g., missing Name, negative Price).
  - *Action*: Invoke `POST /api/items`.
  - *Assertion*: Status code 400 Bad Request with validation error details.

- **UpdateItem_ReturnsNoContent_WhenValid**
  - *Setup*: Seed item ID 1, valid `UpdateItemDto`.
  - *Action*: Invoke `PUT /api/items/1`.
  - *Assertion*: Status code 204 No Content, database reflects updated values.

- **UpdateItem_ReturnsNotFound_WhenItemDoesNotExist**
  - *Action*: Invoke `PUT /api/items/999` with valid payload.
  - *Assertion*: Status code 404 Not Found.

- **DeleteItem_ReturnsNoContent_WhenItemExists**
  - *Setup*: Seed item ID 1.
  - *Action*: Invoke `DELETE /api/items/1`.
  - *Assertion*: Status code 204 No Content, item is removed from database.

- **DeleteItem_ReturnsNotFound_WhenItemDoesNotExist**
  - *Action*: Invoke `DELETE /api/items/999`.
  - *Assertion*: Status code 404 Not Found.