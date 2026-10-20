---
name: database-migrations
description: Manages SQLAlchemy 2.x declarative models, Alembic migrations, and SQL Server schema evolution safely.
---

# Database Migrations Skill

## When to Use
Use this skill when designing or altering SQL Server tables, updating SQLAlchemy models, generating Alembic migrations, and applying schema changes to the `AI_SoftwareEngineer` database.

## Required Inputs
- Target entity schema and attributes.
- Relational dependencies, foreign keys, indexes, and constraints.
- Existing Alembic migration history.

## Execution Steps
1. **Model Definition**:
   - Update or create SQLAlchemy 2.x declarative models in `infrastructure/db/models/`.
   - Use `Mapped[T]` and `mapped_column()` syntax.
   - Define exact SQL Server types: `NVARCHAR(MAX)` or `NVARCHAR(n)`, `DATETIME2`, `BIT`, `BIGINT`, `UNIQUEIDENTIFIER`.
2. **Generate Migration Script**:
   - Run `alembic revision --autogenerate -m "<descriptive_message>"`.
   - Review the generated script in `alembic/versions/` to verify accuracy.
3. **Validate SQL Server Dialect**:
   - Verify compatibility with Microsoft SQL Server (T-SQL syntax, sequence/identity handling, index naming).
   - Ensure downgrade logic is present and reversible.
4. **Apply Migration**:
   - Apply migrations to the target database: `alembic upgrade head`.
   - Verify table creation or modification in SQL Server via CLI query or SSMS.

## Constraints
- Do not introduce PostgreSQL-specific or MySQL-specific constructs (`JSONB`, `SERIAL`, array columns).
- Ensure foreign keys have explicit cascade or restrict rules.
- Never drop production data tables without explicit human approval.

## Verification
- Query `INFORMATION_SCHEMA.TABLES` and `INFORMATION_SCHEMA.COLUMNS` to verify schema changes.
- Execute basic CRUD test with SQLAlchemy session to confirm model mapping.

## Expected Outputs
- Updated SQLAlchemy model classes.
- Validated Alembic migration version file.
- Successful migration execution log.
