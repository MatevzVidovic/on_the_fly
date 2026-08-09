"""Durable, inspectable JSON checkpoints for at-least-once page delivery."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID


STATE_VERSION = 1


class CheckpointMismatch(RuntimeError):
    """A state file belongs to a materially different run configuration."""


class CheckpointFormatError(RuntimeError):
    """A state file is malformed or cannot safely be resumed."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sql_hash(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RunIdentity:
    environment: str
    database: str
    schema: str
    table: str
    spec_version: int
    sql_content: str
    mode: str
    source_page_keys: tuple[str, ...]
    semantic_options: Mapping[str, Any]

    def __post_init__(self) -> None:
        text_fields = ("environment", "database", "schema", "table", "sql_content", "mode")
        if any(not isinstance(getattr(self, field), str) or not getattr(self, field) for field in text_fields):
            raise ValueError("run identity text fields must be non-empty strings")
        if not isinstance(self.spec_version, int) or isinstance(self.spec_version, bool) or self.spec_version < 1:
            raise ValueError("run identity spec_version must be a positive integer")
        if not self.source_page_keys or any(not isinstance(key, str) or not key for key in self.source_page_keys):
            raise ValueError("run identity source_page_keys must be non-empty strings")
        if len(set(self.source_page_keys)) != len(self.source_page_keys):
            raise ValueError("run identity source_page_keys must be distinct")
        if not isinstance(self.semantic_options, Mapping):
            raise ValueError("run identity semantic_options must be a mapping")
        try:
            _canonical(dict(self.semantic_options))
        except (TypeError, ValueError) as error:
            raise ValueError("run identity semantic_options must be strict JSON values") from error

    def payload(self) -> dict[str, Any]:
        return {
            "state_version": STATE_VERSION,
            "environment": self.environment,
            "database": self.database,
            "schema": self.schema,
            "table": self.table,
            "spec_version": self.spec_version,
            "sql_hash": sql_hash(self.sql_content),
            "mode": self.mode,
            "source_page_keys": list(self.source_page_keys),
            "semantic_options": dict(self.semantic_options),
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(self.payload()).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Checkpoint:
    identity: RunIdentity
    cursor: tuple[Any, ...] | None = None
    pages: int = 0
    rows: int = 0
    completed: bool = False
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, RunIdentity):
            raise TypeError("checkpoint identity must be a RunIdentity")
        if self.cursor is not None and not isinstance(self.cursor, tuple):
            raise TypeError("checkpoint cursor must be a tuple or None")
        if (not isinstance(self.pages, int) or isinstance(self.pages, bool) or self.pages < 0
                or not isinstance(self.rows, int) or isinstance(self.rows, bool) or self.rows < 0):
            raise ValueError("checkpoint counters must be non-negative integers")
        if not isinstance(self.completed, bool):
            raise TypeError("checkpoint completed must be bool")
        if self.metadata is not None and not isinstance(self.metadata, Mapping):
            raise TypeError("checkpoint metadata must be a mapping or None")

    def as_json(self) -> dict[str, Any]:
        return {
            "fingerprint": self.identity.fingerprint,
            "identity": self.identity.payload(),
            "cursor": [_encode_cursor_value(value) for value in self.cursor] if self.cursor is not None else None,
            "pages": self.pages,
            "rows": self.rows,
            "completed": self.completed,
            "metadata": _encode_metadata(dict(self.metadata or {})),
        }


def _encode_cursor_value(value: Any) -> Any:
    """Encode only explicit, lossless cursor scalar types.

    ``default=str`` is deliberately not used for cursor state: changing a
    native Oracle key's type during resume can change comparisons or binds.
    """
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CheckpointFormatError("cursor float values must be finite")
        return value
    if isinstance(value, Decimal):
        return {"$type": "decimal", "value": str(value)}
    if isinstance(value, UUID):
        return {"$type": "uuid", "value": str(value)}
    if isinstance(value, datetime):
        return {"$type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"$type": "date", "value": value.isoformat()}
    raise CheckpointFormatError(f"unsupported cursor value type: {type(value).__name__}")


def _decode_cursor_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CheckpointFormatError("checkpoint cursor contains a non-finite float")
        return value
    if not isinstance(value, dict) or set(value) != {"$type", "value"} or not isinstance(value["$type"], str) or not isinstance(value["value"], str):
        raise CheckpointFormatError("checkpoint cursor contains an invalid typed value")
    try:
        match value["$type"]:
            case "decimal":
                return Decimal(value["value"])
            case "uuid":
                return UUID(value["value"])
            case "datetime":
                return datetime.fromisoformat(value["value"])
            case "date":
                return date.fromisoformat(value["value"])
    except (ArithmeticError, ValueError) as error:
        raise CheckpointFormatError("checkpoint cursor contains an invalid typed value") from error
    raise CheckpointFormatError("checkpoint cursor contains an unsupported typed value")


def _encode_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CheckpointFormatError("checkpoint metadata keys must be strings")
        return {key: _encode_metadata(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_encode_metadata(item) for item in value]
    return _encode_cursor_value(value)


def _decode_metadata(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_decode_metadata(item) for item in value)
    if isinstance(value, dict):
        if set(value) == {"$type", "value"}:
            return _decode_cursor_value(value)
        if not all(isinstance(key, str) for key in value):
            raise CheckpointFormatError("checkpoint metadata keys must be strings")
        return {key: _decode_metadata(item) for key, item in value.items()}
    return _decode_cursor_value(value)


def _fresh_checkpoint(path: Path, identity: RunIdentity) -> Checkpoint:
    checkpoint = Checkpoint(identity=identity)
    # ``--fresh`` must replace stale state before source work begins.  If the
    # process dies before page one commits, a later ordinary invocation sees a
    # valid empty state rather than resuming the discarded run.
    save_checkpoint(path, checkpoint)
    return checkpoint


def atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    """Replace a checkpoint atomically and make both file and directory durable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, default=str, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_checkpoint(path: Path, identity: RunIdentity, *, fresh: bool = False) -> Checkpoint:
    if fresh:
        return _fresh_checkpoint(path, identity)
    if not path.exists():
        return Checkpoint(identity=identity)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"checkpoint is unreadable: {path}") from error
    expected_keys = {"fingerprint", "identity", "cursor", "pages", "rows", "completed", "metadata"}
    if not isinstance(raw, dict) or set(raw) != expected_keys:
        raise CheckpointFormatError(f"checkpoint has an invalid format: {path}")
    if raw.get("fingerprint") != identity.fingerprint or raw.get("identity") != identity.payload():
        raise CheckpointMismatch("checkpoint does not match this run; use --fresh to start over")
    cursor = raw.get("cursor")
    if cursor is not None:
        if not isinstance(cursor, list) or len(cursor) != len(identity.source_page_keys):
            raise CheckpointFormatError(f"checkpoint cursor is invalid for the declared source_page_keys: {path}")
        try:
            cursor = [_decode_cursor_value(value) for value in cursor]
        except CheckpointFormatError:
            raise
    pages, rows = raw.get("pages", 0), raw.get("rows", 0)
    completed = raw.get("completed")
    metadata = raw.get("metadata")
    if (not isinstance(pages, int) or isinstance(pages, bool) or not isinstance(rows, int) or isinstance(rows, bool)
            or pages < 0 or rows < 0 or not isinstance(completed, bool) or not isinstance(metadata, dict)):
        raise CheckpointFormatError(f"checkpoint counters are invalid: {path}")
    try:
        metadata = _decode_metadata(metadata)
        _canonical(_encode_metadata(metadata))
    except (CheckpointFormatError, TypeError, ValueError) as error:
        raise CheckpointFormatError(f"checkpoint metadata is invalid: {path}") from error
    return Checkpoint(identity, tuple(cursor) if cursor is not None else None, pages, rows, completed, metadata or None)


def save_checkpoint(path: Path, checkpoint: Checkpoint) -> None:
    if checkpoint.cursor is not None:
        if len(checkpoint.cursor) != len(checkpoint.identity.source_page_keys):
            raise CheckpointFormatError("checkpoint cursor does not match the declared source_page_keys")
        for value in checkpoint.cursor:
            _encode_cursor_value(value)
    atomic_json_write(path, checkpoint.as_json())
