"""Small durable SQLite store for a complete KN source key/change generation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator


def _encode(value: Any) -> str:
    if isinstance(value, datetime):
        value = {"type": "datetime", "value": value.isoformat()}
    elif isinstance(value, date):
        value = {"type": "date", "value": value.isoformat()}
    elif isinstance(value, Decimal):
        value = {"type": "decimal", "value": str(value)}
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _decode(value: str) -> Any:
    decoded = json.loads(value)
    if not isinstance(decoded, dict) or set(decoded) != {"type", "value"}:
        return decoded
    if decoded["type"] == "datetime":
        return datetime.fromisoformat(decoded["value"])
    if decoded["type"] == "date":
        return date.fromisoformat(decoded["value"])
    if decoded["type"] == "decimal":
        return Decimal(decoded["value"])
    raise RuntimeError("source generation contains unsupported typed value")


class RunStore:
    """One fingerprinted source generation, valid only after complete EOF."""

    def __init__(self, path: Path, fingerprint: str) -> None:
        self.path, self.fingerprint = path, fingerprint

    def open(self, *, fresh: bool = False, reset_on_mismatch: bool = True) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS source_generation (membership_json TEXT PRIMARY KEY, change_json TEXT NOT NULL)")
        row = connection.execute("SELECT value FROM metadata WHERE key = 'fingerprint'").fetchone()
        if row is not None and row[0] != self.fingerprint and not reset_on_mismatch:
            connection.close()
            raise RuntimeError("source generation fingerprint does not match this run")
        if fresh or row is None or row[0] != self.fingerprint:
            connection.execute("DELETE FROM source_generation")
            connection.execute("DELETE FROM metadata")
            connection.execute("INSERT INTO metadata(key, value) VALUES ('fingerprint', ?)", (self.fingerprint,))
            connection.commit()
        return connection

    @staticmethod
    def complete(connection: sqlite3.Connection) -> bool:
        row = connection.execute("SELECT value FROM metadata WHERE key = 'complete'").fetchone()
        return row == ("1",)

    def has_active_incomplete_generation(self) -> bool:
        """True only when this fingerprint has durable partial source work."""
        connection = self.open()
        try:
            if self.complete(connection):
                return False
            cursor = self.cursor(connection)
            if cursor is not None:
                return True
            return connection.execute("SELECT 1 FROM source_generation LIMIT 1").fetchone() is not None
        finally:
            connection.close()

    @staticmethod
    def begin(connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM source_generation")
        connection.execute("DELETE FROM metadata WHERE key IN ('complete', 'source_cursor')")
        connection.commit()

    @staticmethod
    def cursor(connection: sqlite3.Connection) -> tuple[Any, ...] | None:
        row = connection.execute("SELECT value FROM metadata WHERE key = 'source_cursor'").fetchone()
        if row is None:
            return None
        decoded = json.loads(row[0])
        if not isinstance(decoded, list):
            raise RuntimeError("source generation cursor is invalid")
        return tuple(_decode(json.dumps(item, separators=(",", ":"), sort_keys=True)) for item in decoded)

    @staticmethod
    def append_page(connection: sqlite3.Connection, rows: list[tuple[Any, Any]], next_cursor: tuple[Any, ...]) -> None:
        if any(identifier is None for identifier, _change in rows):
            raise RuntimeError("source generation has null membership values")
        try:
            connection.executemany(
                "INSERT INTO source_generation(membership_json, change_json) VALUES (?, ?)",
                [(_encode(identifier), _encode(change)) for identifier, change in rows],
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES ('source_cursor', ?)",
                (json.dumps([json.loads(_encode(value)) for value in next_cursor], separators=(",", ":"), sort_keys=True),),
            )
        except sqlite3.IntegrityError as error:
            raise RuntimeError("KN integration result has duplicate membership keys during full preflight") from error
        connection.commit()

    @staticmethod
    def append(connection: sqlite3.Connection, rows: list[tuple[Any, Any]]) -> None:
        """Test/support helper for a complete one-page generation."""
        if (not RunStore.complete(connection) and RunStore.cursor(connection) is None
                and connection.execute("SELECT 1 FROM source_generation LIMIT 1").fetchone() is None):
            RunStore.begin(connection)
        RunStore.append_page(connection, rows, ())

    @staticmethod
    def mark_complete(connection: sqlite3.Connection) -> None:
        connection.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES ('complete', '1')")
        connection.commit()

    @staticmethod
    def batches(connection: sqlite3.Connection, size: int) -> Iterator[list[tuple[Any, Any]]]:
        cursor = connection.execute("SELECT membership_json, change_json FROM source_generation ORDER BY membership_json")
        while rows := cursor.fetchmany(size):
            yield [(_decode(identifier), _decode(change)) for identifier, change in rows]
