"""PostgreSQL connection, schema and transaction helpers."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

import psycopg
from psycopg.pq import TransactionStatus

import config

SCHEMA_VERSION = 5


class Record(dict):
    """Mapping row that also supports positional access used by existing services."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _row_factory(cursor):
    columns = [column.name for column in cursor.description]
    return lambda values: Record(zip(columns, values))


class DatabaseConnection:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def execute(self, query: str, params: Optional[Sequence[Any]] = None):
        statement = query.strip()
        returns_id = statement[:11].upper() == "INSERT INTO" and "RETURNING" not in statement.upper()
        if returns_id:
            statement += " RETURNING id"
        cursor = self._connection.execute(statement.replace("?", "%s"), params)
        return DatabaseCursor(cursor, returns_id)

    @property
    def in_transaction(self) -> bool:
        return self._connection.info.transaction_status != TransactionStatus.IDLE

    def close(self) -> None:
        self._connection.close()


class DatabaseCursor:
    def __init__(self, cursor, returns_id: bool):
        self._cursor = cursor
        self._inserted_id = None
        if returns_id:
            row = cursor.fetchone()
            self._inserted_id = row["id"] if row else None

    @property
    def lastrowid(self):
        return self._inserted_id

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


def build_schema_sql() -> str:
    """Return the same idempotent schema file that can be applied with psql."""
    return (Path(__file__).resolve().parent.parent / "supabase" / "schema.sql").read_text(encoding="utf-8")


def get_connection(db_url: Optional[str] = None) -> DatabaseConnection:
    url = db_url or config.get_database_url()
    connection = psycopg.connect(
        url,
        row_factory=_row_factory,
        connect_timeout=10,
        autocommit=True,
        prepare_threshold=None,
    )
    return DatabaseConnection(connection)


@contextmanager
def connect(db_url: Optional[str] = None) -> Iterator[DatabaseConnection]:
    connection = get_connection(db_url)
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(db_url: Optional[str] = None) -> Iterator[DatabaseConnection]:
    connection = get_connection(db_url)
    try:
        connection.execute("BEGIN")
        yield connection
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def init_db(db_url: Optional[str] = None) -> None:
    """Create the current schema in PostgreSQL; safe to run repeatedly."""
    with transaction(db_url) as connection:
        connection._connection.execute(build_schema_sql(), prepare=False)