"""Small durable SQLite store for a complete KN source key/change generation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator
from uuid import UUID


def _encode(value: Any) -> str:
    if isinstance(value, datetime):
        value = {"type": "datetime", "value": value.isoformat()}
    elif isinstance(value, date):
        value = {"type": "date", "value": value.isoformat()}
    elif isinstance(value, Decimal):
        value = {"type": "decimal", "value": str(value)}
    elif isinstance(value, UUID):
        value = {"type": "uuid", "value": str(value)}
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
    if decoded["type"] == "uuid":
        return UUID(decoded["value"])
    raise RuntimeError("source generation contains unsupported typed value")


class RunStore:
    """One fingerprinted source generation, valid only after complete EOF."""

    def __init__(self, path: Path, fingerprint: str) -> None:
        self.path, self.fingerprint = path, fingerprint

    def open(self, *, fresh: bool = False, reset_on_mismatch: bool = True) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS source_generation (membership_json TEXT PRIMARY KEY, change_json TEXT NOT NULL)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS delta_payload ("
                "sequence INTEGER PRIMARY KEY AUTOINCREMENT, membership_json TEXT NOT NULL UNIQUE, "
                "cursor_json TEXT NOT NULL UNIQUE, payload_json TEXT NOT NULL)"
            )
            row = connection.execute("SELECT value FROM metadata WHERE key = 'fingerprint'").fetchone()
            if row is not None and row[0] != self.fingerprint and not reset_on_mismatch:
                raise RuntimeError("source generation fingerprint does not match this run")
            if fresh or row is None or row[0] != self.fingerprint:
                connection.execute("DELETE FROM source_generation")
                connection.execute("DELETE FROM delta_payload")
                connection.execute("DELETE FROM metadata")
                connection.execute("INSERT INTO metadata(key, value) VALUES ('fingerprint', ?)", (self.fingerprint,))
                connection.commit()
            return connection
        except BaseException:
            connection.close()
            raise

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

    @staticmethod
    def _tuple_json(values: tuple[Any, ...]) -> str:
        return json.dumps([json.loads(_encode(value)) for value in values], separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _payload_json(row: dict[str, Any]) -> str:
        return json.dumps(
            {key: json.loads(_encode(value)) for key, value in row.items()},
            separators=(",", ":"), sort_keys=True,
        )

    @staticmethod
    def _payload(value: str) -> dict[str, Any]:
        decoded = json.loads(value)
        if not isinstance(decoded, dict):
            raise RuntimeError("delta payload row is invalid")
        return {key: _decode(json.dumps(item, separators=(",", ":"), sort_keys=True)) for key, item in decoded.items()}

    @staticmethod
    def begin_delta(connection: sqlite3.Connection, lower: tuple[Any, ...] | None, upper: tuple[Any, ...]) -> None:
        """Start a durable frozen delta generation before reading its payload."""
        connection.execute("DELETE FROM delta_payload")
        connection.execute("DELETE FROM metadata WHERE key LIKE 'delta_%'")
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("delta_lower", RunStore._tuple_json(lower) if lower is not None else "null"),
                ("delta_upper", RunStore._tuple_json(upper)),
            ],
        )
        connection.commit()

    @staticmethod
    def delta_bounds(connection: sqlite3.Connection) -> tuple[tuple[Any, ...] | None, tuple[Any, ...]] | None:
        values = dict(connection.execute(
            "SELECT key, value FROM metadata WHERE key IN ('delta_lower', 'delta_upper')"
        ).fetchall())
        if not values:
            return None
        if set(values) != {"delta_lower", "delta_upper"}:
            raise RuntimeError("delta generation bounds are incomplete")

        def decode_tuple(raw: str) -> tuple[Any, ...] | None:
            decoded = json.loads(raw)
            if decoded is None:
                return None
            if not isinstance(decoded, list):
                raise RuntimeError("delta generation bound is invalid")
            return tuple(_decode(json.dumps(item, separators=(",", ":"), sort_keys=True)) for item in decoded)

        lower, upper = decode_tuple(values["delta_lower"]), decode_tuple(values["delta_upper"])
        if upper is None:
            raise RuntimeError("delta generation upper bound is invalid")
        return lower, upper

    @staticmethod
    def delta_complete(connection: sqlite3.Connection) -> bool:
        return connection.execute("SELECT value FROM metadata WHERE key = 'delta_complete'").fetchone() == ("1",)

    @staticmethod
    def delta_cursor(connection: sqlite3.Connection) -> tuple[Any, ...] | None:
        row = connection.execute("SELECT value FROM metadata WHERE key = 'delta_cursor'").fetchone()
        if row is None:
            return None
        decoded = json.loads(row[0])
        if not isinstance(decoded, list):
            raise RuntimeError("delta generation cursor is invalid")
        return tuple(_decode(json.dumps(item, separators=(",", ":"), sort_keys=True)) for item in decoded)

    @staticmethod
    def append_delta_page(
        connection: sqlite3.Connection,
        rows: list[tuple[Any, tuple[Any, ...], dict[str, Any]]],
    ) -> None:
        """Atomically persist one ordered payload batch and its cursor."""
        if not rows:
            return
        previous = RunStore.delta_cursor(connection)
        for membership, cursor, _payload in rows:
            if membership is None:
                raise RuntimeError("only-new source has a null membership key")
            if any(value is None for value in cursor):
                raise RuntimeError("only-new source has a NULL cursor component")
            if previous is not None and cursor <= previous:
                raise RuntimeError("only-new source cursor is duplicate or not strictly ordered")
            previous = cursor
        try:
            connection.executemany(
                "INSERT INTO delta_payload(membership_json, cursor_json, payload_json) VALUES (?, ?, ?)",
                [(_encode(membership), RunStore._tuple_json(cursor), RunStore._payload_json(payload)) for membership, cursor, payload in rows],
            )
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES ('delta_cursor', ?)",
                (RunStore._tuple_json(rows[-1][1]),),
            )
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise RuntimeError("only-new source has duplicate membership or cursor values") from error

    @staticmethod
    def mark_delta_complete(connection: sqlite3.Connection) -> None:
        connection.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES ('delta_complete', '1')")
        connection.commit()

    @staticmethod
    def delta_page(
        connection: sqlite3.Connection, after: tuple[Any, ...] | None, size: int,
    ) -> tuple[tuple[dict[str, Any], ...], tuple[Any, ...] | None]:
        """Read the next local page after an exact durable composite cursor."""
        if after is None:
            sequence = 0
        else:
            row = connection.execute(
                "SELECT sequence FROM delta_payload WHERE cursor_json = ?",
                (RunStore._tuple_json(after),),
            ).fetchone()
            if row is None:
                bounds = RunStore.delta_bounds(connection)
                if bounds is None or bounds[0] != after:
                    raise RuntimeError("only-new apply cursor is absent from its durable delta generation")
                sequence = 0
            else:
                sequence = row[0]
        rows = connection.execute(
            "SELECT cursor_json, payload_json FROM delta_payload WHERE sequence > ? ORDER BY sequence LIMIT ?",
            (sequence, size),
        ).fetchall()
        if not rows:
            return (), None
        payloads = tuple(RunStore._payload(payload) for _cursor, payload in rows)
        cursor_values = json.loads(rows[-1][0])
        next_cursor = tuple(_decode(json.dumps(item, separators=(",", ":"), sort_keys=True)) for item in cursor_values)
        return payloads, next_cursor
