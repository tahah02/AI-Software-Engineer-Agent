import pytest
from sqlalchemy import text

from src.infrastructure.db.session import engine, check_database_connection, SessionLocal


def test_sqlite_connection_check():
    connected = check_database_connection()
    assert connected is True


def test_sqlite_foreign_keys_pragma_enabled():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys;"))
        fk_status = result.scalar()
        assert fk_status == 1, "SQLite foreign_keys PRAGMA must be enabled (1)."


def test_session_scope():
    session = SessionLocal()
    try:
        result = session.execute(text("SELECT 1 + 1 AS sum_val"))
        assert result.scalar() == 2
    finally:
        session.close()
