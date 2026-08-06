#!/usr/bin/env python3
"""Synchronise ID membership from a KN Oracle SELECT into a staging PG table.

The SQL file must contain one SELECT (or WITH ... SELECT) and must alias its
output columns to the destination PostgreSQL column names. The membership key
defaults to `id`, but can be selected with --id-field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import random
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
# These columns are owned by LIFT/PostgreSQL, not supplied by the KN SELECT.
LIFT_SYSTEM_COLUMNS = frozenset({"id", "created_at", "created_by", "updated_at", "updated_by"})


def valid_identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a plain PostgreSQL identifier")
    return value


def source_page_key(value: str) -> tuple[str, ...]:
    fields = tuple(valid_identifier(field.strip(), "source page key").lower() for field in value.split(",") if field.strip())
    if not fields or len(set(fields)) != len(fields):
        raise ValueError("--source-page-key must contain one or more distinct comma-separated columns")
    return fields


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("install requirements into .venv before running this script") from error
    load_dotenv(HERE / ".env", override=False)


def require_drivers() -> tuple[Any, Any]:
    try:
        import oracledb
        import psycopg
    except ImportError as error:
        raise RuntimeError("install requirements into .venv before running this script") from error
    return oracledb, psycopg


def enable_oracle_thick_mode(oracledb: Any) -> None:
    """Enable Thick mode when KN requires Oracle native network encryption."""
    configured = os.environ.get("KN_ORACLE_CLIENT_LIB_DIR")
    if not configured:
        return
    lib_dir = Path(configured).expanduser()
    if not lib_dir.is_dir():
        raise RuntimeError(f"KN_ORACLE_CLIENT_LIB_DIR does not exist or is not a directory: {lib_dir}")
    try:
        oracledb.init_oracle_client(lib_dir=str(lib_dir))
    except Exception as error:
        raise RuntimeError(f"could not initialise Oracle Thick mode from {lib_dir}: {error}") from error


def pg_settings() -> dict[str, str | int]:
    required = ("STAG_USER", "STAG_PASSWORD", "STAG_HOST", "STAG_PORT")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing staging PostgreSQL environment variables: {', '.join(missing)}")
    return {
        "user": os.environ["STAG_USER"], "password": os.environ["STAG_PASSWORD"],
        "host": os.environ["STAG_HOST"], "port": int(os.environ["STAG_PORT"]),
        "dbname": os.environ.get("STAG_DATABASE", "fmp_data_gurs"),
    }


def oracle_settings(oracledb: Any) -> dict[str, Any]:
    required = ("KN_USER", "KN_PASSWORD", "KN_HOST", "KN_PORT", "KN_SERVICE")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing KN Oracle environment variables: {', '.join(missing)}")
    return {
        "user": os.environ["KN_USER"],
        "password": os.environ["KN_PASSWORD"],
        "dsn": oracledb.makedsn(os.environ["KN_HOST"], int(os.environ["KN_PORT"]), service_name=os.environ["KN_SERVICE"]),
    }


def relation_sql(schema: str, table: str) -> str:
    return f'"{schema}"."{table}"'


def atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"checkpoint is unreadable: {path}; repair it or use --restart") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"checkpoint is invalid: {path}")
    return value


@contextmanager
def file_lock(path: Path) -> Iterable[None]:
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"another resumable sync holds {path}") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def is_transient(error: Exception) -> bool:
    text = str(error).lower()
    return any(marker in text for marker in ("connection", "network", "timeout", "temporar", "ora-12170", "ora-125", "could not connect", "dpy-6005"))


def retry(operation: Any, retries: int = 4) -> Any:
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception as error:
            if attempt >= retries or not is_transient(error):
                raise
            time.sleep(min(30.0, 0.5 * (2**attempt)) + random.uniform(0, 0.25))


def read_select(path: Path) -> str:
    try:
        query = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(f"cannot read integration SQL file: {path}") from error
    query = query.rstrip(";").strip()
    if not query or not re.match(r"^(SELECT|WITH)\b", query, re.IGNORECASE):
        raise ValueError("integration SQL must contain exactly one SELECT or WITH query")
    if ";" in query:
        raise ValueError("integration SQL must not contain multiple statements")
    return query


def target_columns(connection: Any, schema: str, table: str, id_field: str) -> tuple[list[str], list[str]]:
    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
          AND is_generated = 'NEVER'
          AND identity_generation IS DISTINCT FROM 'ALWAYS'
        ORDER BY ordinal_position
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (schema, table))
        destination_columns = [row[0] for row in cursor.fetchall()]
    if not destination_columns:
        raise RuntimeError(f"staging table {schema}.{table} was not found or has no insertable columns")
    if id_field not in destination_columns:
        raise RuntimeError(f"staging table {schema}.{table} must have the key column {id_field}")
    source_columns = [column for column in destination_columns if column not in LIFT_SYSTEM_COLUMNS]
    if id_field not in source_columns:
        raise RuntimeError(f"key column {id_field} cannot be a LIFT-managed system field")
    return source_columns, destination_columns


def require_unique_key(connection: Any, schema: str, table: str, id_field: str) -> None:
    query = """
        SELECT 1
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
        WHERE n.nspname = %s AND c.relname = %s
          AND i.indisunique AND array_length(i.indkey, 1) = 1 AND a.attname = %s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (schema, table, id_field))
        if cursor.fetchone() is None:
            raise RuntimeError(f"staging table {schema}.{table} needs a single-column unique key on {id_field}")


def insert_statement(schema: str, table: str, source_columns: list[str], destination_columns: list[str]) -> str:
    """Insert source data while explicitly filling LIFT-owned audit fields."""
    automatic_values = {
        "id": "uuid_generate_v4()",
        "created_at": "CURRENT_TIMESTAMP",
        "updated_at": "CURRENT_TIMESTAMP",
    }
    automatic_columns = [column for column in automatic_values if column in destination_columns]
    columns = [*automatic_columns, *source_columns]
    values = [*(automatic_values[column] for column in automatic_columns), *("%s" for _ in source_columns)]
    return f"INSERT INTO {relation_sql(schema, table)} ({', '.join(f'\"{column}\"' for column in columns)}) VALUES ({', '.join(values)})"


def scalar(value: Any) -> Any:
    """Materialise Oracle LOBs before their cursor and connection are closed."""
    read = getattr(value, "read", None)
    return read() if callable(read) else value


def source_rows(connection: Any, query: str, target_columns_: list[str], id_field: str) -> dict[Any, tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        source_columns = [description[0].lower() for description in cursor.description]
        if len(set(source_columns)) != len(source_columns):
            raise RuntimeError("integration SQL output contains duplicate column names")
        if set(source_columns) != set(target_columns_):
            missing = sorted(set(target_columns_) - set(source_columns))
            extra = sorted(set(source_columns) - set(target_columns_))
            raise RuntimeError(f"integration SQL columns do not match staging table; missing: {missing or '-'}; extra: {extra or '-'}")
        positions = [source_columns.index(column) for column in target_columns_]
        id_position = target_columns_.index(id_field)
        rows: dict[Any, tuple[Any, ...]] = {}
        while fetched := cursor.fetchmany(1_000):
            for raw_row in fetched:
                row = tuple(scalar(raw_row[position]) for position in positions)
                identifier = row[id_position]
                if identifier is None:
                    raise RuntimeError(f"integration SQL returned a NULL {id_field}")
                if identifier in rows:
                    raise RuntimeError(f"integration SQL returned duplicate {id_field}: {identifier!r}")
                rows[identifier] = row
        return rows


def staging_rows(connection: Any, schema: str, table: str, columns: list[str], id_field: str, identifiers: list[Any], batch_size: int) -> Iterable[tuple[Any, ...]]:
    projection = ", ".join(f'"{column}"' for column in columns)
    for start in range(0, len(identifiers), batch_size):
        batch = identifiers[start : start + batch_size]
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT {projection} FROM {relation_sql(schema, table)} WHERE "{id_field}" = ANY(%s) ORDER BY "{id_field}"', (batch,))
            yield from cursor.fetchall()


def staging_changes(connection: Any, schema: str, table: str, id_field: str, change_field: str | None) -> dict[Any, Any]:
    with connection.cursor() as cursor:
        if change_field:
            cursor.execute(f'SELECT "{id_field}", "{change_field}" FROM {relation_sql(schema, table)}')
        else:
            cursor.execute(f'SELECT "{id_field}" FROM {relation_sql(schema, table)}')
        result: dict[Any, Any] = {}
        for row in cursor.fetchall():
            identifier, changed_at = row if change_field else (row[0], None)
            if identifier is None:
                raise RuntimeError(f"staging table {schema}.{table} contains a NULL {id_field}")
            if identifier in result:
                raise RuntimeError(f"staging table {schema}.{table} contains a duplicate {id_field}: {identifier!r}")
            result[identifier] = changed_at
    return result


def ordered(values: Iterable[Any]) -> list[Any]:
    return sorted(values, key=lambda value: (type(value).__name__, repr(value)))


def comparable_change(value: Any) -> Any:
    """Accept ISO timestamp text when Oracle TSTZ values are selected as text."""
    if not isinstance(value, str):
        return value
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return value


def normalize_change_pair(kn_value: Any, staging_value: Any) -> tuple[Any, Any]:
    """Put mixed PostgreSQL timestamp representations on a common basis."""
    kn_change = comparable_change(kn_value)
    staging_change = comparable_change(staging_value)
    if isinstance(kn_change, datetime) and isinstance(staging_change, datetime) and (kn_change.tzinfo is None) != (staging_change.tzinfo is None):
        # A PostgreSQL `timestamp` value is naïve. KN's ISO value is local
        # Ljubljana wall-clock time, so compare the same local representation.
        return kn_change.replace(tzinfo=None), staging_change.replace(tzinfo=None)
    return kn_change, staging_change


def source_changes(connection: Any, query: str, id_field: str, change_field: str | None) -> dict[Any, Any]:
    projection = id_field if change_field is None else f"{id_field}, {change_field}"
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {projection} FROM ({query})")
        result: dict[Any, Any] = {}
        for row in cursor.fetchall():
            identifier, changed_at = row if change_field else (row[0], None)
            if identifier is None:
                raise RuntimeError(f"integration SQL returned a NULL {id_field}")
            if identifier in result:
                raise RuntimeError(f"integration SQL returned duplicate {id_field}: {identifier!r}")
            result[identifier] = scalar(changed_at)
        return result


def make_plan(kn_changes: dict[Any, Any], stag_changes: dict[Any, Any], change_field: str, ignore_change_field: bool) -> tuple[list[Any], list[Any], list[Any], list[Any], list[tuple[Any, Any, Any]]]:
    source_ids = set(kn_changes)
    stag_ids = set(stag_changes)
    delete_ids = ordered(stag_ids - source_ids)
    insert_ids = ordered(source_ids - stag_ids)
    unchanged_ids: list[Any] = []
    update_ids: list[Any] = []
    conflicts: list[tuple[Any, Any, Any]] = []
    for identifier in source_ids & stag_ids:
        if ignore_change_field:
            unchanged_ids.append(identifier)
            continue
        source_change, stag_change = normalize_change_pair(kn_changes[identifier], stag_changes[identifier])
        if source_change == stag_change:
            unchanged_ids.append(identifier)
        elif source_change is None or stag_change is None:
            conflicts.append((identifier, source_change, stag_change))
        else:
            try:
                if stag_change < source_change:
                    update_ids.append(identifier)
                else:
                    conflicts.append((identifier, source_change, stag_change))
            except TypeError as error:
                raise RuntimeError(
                    f"cannot compare {change_field} for key {identifier!r}: "
                    f"KN={source_change!r} ({type(source_change).__name__}), "
                    f"staging={stag_change!r} ({type(stag_change).__name__})"
                ) from error
    return delete_ids, insert_ids, ordered(unchanged_ids), ordered(update_ids), sorted(conflicts, key=lambda item: (type(item[0]).__name__, repr(item[0])))


def preview(label: str, rows: Iterable[tuple[Any, ...]], columns: list[str], limit: int) -> None:
    print(f"{label} rows (showing up to {limit}):")
    shown = 0
    for row in rows:
        if shown == limit:
            break
        print(json.dumps(dict(zip(columns, row, strict=True)), default=str, ensure_ascii=False))
        shown += 1
    if shown == 0:
        print("(none)")


def preview_conflicts(conflicts: list[tuple[Any, Any, Any]], id_field: str, change_field: str, limit: int) -> None:
    print(f"CONFLICT rows (staging {change_field} is newer or cannot be compared; showing up to {limit}):")
    for identifier, source_change, stag_change in conflicts[:limit]:
        print(json.dumps({id_field: identifier, f"kn_{change_field}": source_change, f"staging_{change_field}": stag_change}, default=str, ensure_ascii=False))


def resumable_paths(fingerprint: str) -> tuple[Path, Path, Path]:
    state_dir = HERE / ".state" / fingerprint
    return state_dir / "checkpoint.json", state_dir / "source_keys.sqlite3", state_dir / "loader.lock"


def sync_fingerprint(query: str, schema: str, table: str, id_field: str, change_field: str, ignore_change_field: bool, page_key: tuple[str, ...]) -> str:
    payload = json.dumps({"query": query, "schema": schema, "table": table, "id_field": id_field, "change_field": change_field, "ignore_change_field": ignore_change_field, "source_page_key": page_key}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def key_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE IF NOT EXISTS source_keys (key TEXT PRIMARY KEY)")
    return connection


def remember_keys(connection: sqlite3.Connection, identifiers: Iterable[Any]) -> None:
    connection.executemany("INSERT OR IGNORE INTO source_keys (key) VALUES (?)", ((str(identifier),) for identifier in identifiers))
    connection.commit()


def known_key(connection: sqlite3.Connection, identifier: Any) -> bool:
    return connection.execute("SELECT 1 FROM source_keys WHERE key = ?", (str(identifier),)).fetchone() is not None


def key_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT COUNT(*) FROM source_keys").fetchone()[0])


def composite_keyset_predicate(page_key: tuple[str, ...], has_cursor: bool) -> str:
    if not has_cursor:
        return ""
    branches = []
    for index, field in enumerate(page_key):
        equal_prefix = [f"{page_key[prefix]} = :last_key_{prefix}" for prefix in range(index)]
        branches.append(" AND ".join([*equal_prefix, f"{field} > :last_key_{index}"]))
    return " WHERE (" + " OR ".join(f"({branch})" for branch in branches) + ")"


def oracle_page(oracledb: Any, query: str, page_key: tuple[str, ...], projection: str, after_key: tuple[Any, ...] | None, page_size: int) -> tuple[list[str], list[tuple[Any, ...]]]:
    """Fetch a deterministic keyset page from the integration SELECT."""
    def operation() -> tuple[list[str], list[tuple[Any, ...]]]:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            suffix = composite_keyset_predicate(page_key, after_key is not None)
            paged = f"SELECT {projection} FROM ({query}) source_rows{suffix} ORDER BY {', '.join(page_key)} FETCH FIRST :page_size ROWS ONLY"
            binds: dict[str, Any] = {"page_size": page_size}
            if after_key is not None:
                binds.update({f"last_key_{index}": value for index, value in enumerate(after_key)})
            with connection.cursor() as cursor:
                cursor.execute(paged, binds)
                names = [description[0].lower() for description in cursor.description]
                return names, [tuple(scalar(value) for value in row) for row in cursor.fetchall()]
    return retry(operation)


def source_change_page(oracledb: Any, query: str, id_field: str, change_field: str | None, page_key: tuple[str, ...], after_key: tuple[Any, ...] | None, page_size: int) -> tuple[dict[Any, Any], tuple[Any, ...] | None]:
    selected = list(dict.fromkeys([id_field, *(() if change_field is None else (change_field,)), *page_key]))
    projection = ", ".join(selected)
    names, rows = oracle_page(oracledb, query, page_key, projection, after_key, page_size)
    expected = selected
    if names != expected:
        raise RuntimeError(f"integration SQL key projection did not match expected columns: {expected}; got {names}")
    positions = {name: index for index, name in enumerate(names)}
    result: dict[Any, Any] = {}
    previous_cursor: tuple[Any, ...] | None = None
    for row in rows:
        identifier = row[positions[id_field]]
        changed_at = row[positions[change_field]] if change_field else None
        page_cursor = tuple(row[positions[field]] for field in page_key)
        if any(value is None for value in page_cursor) or (previous_cursor is not None and page_cursor <= previous_cursor):
            raise RuntimeError(f"integration SQL must return unique, non-NULL source page keys: {', '.join(page_key)}")
        if identifier is None or identifier in result:
            raise RuntimeError(f"integration SQL must return unique, non-NULL {id_field} values")
        result[identifier] = changed_at
        previous_cursor = page_cursor
    return result, previous_cursor


def require_unique_source_keys(oracledb: Any, query: str, id_field: str) -> None:
    def operation() -> None:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT {id_field} FROM ({query}) source_rows GROUP BY {id_field} HAVING COUNT(*) > 1 FETCH FIRST 1 ROWS ONLY")
                duplicate = cursor.fetchone()
                if duplicate:
                    raise RuntimeError(f"integration SQL returned duplicate {id_field}: {duplicate[0]!r}")
    retry(operation)


def source_full_page(oracledb: Any, query: str, id_field: str, source_columns: list[str], page_key: tuple[str, ...], after_key: tuple[Any, ...] | None, page_size: int) -> tuple[dict[Any, tuple[Any, ...]], tuple[Any, ...] | None]:
    names, rows = oracle_page(oracledb, query, page_key, "source_rows.*", after_key, page_size)
    if len(set(names)) != len(names) or set(names) != set(source_columns):
        missing = sorted(set(source_columns) - set(names))
        extra = sorted(set(names) - set(source_columns))
        raise RuntimeError(f"integration SQL columns do not match staging table; missing: {missing or '-'}; extra: {extra or '-'}")
    positions = [names.index(column) for column in source_columns]
    page_positions = [names.index(field) for field in page_key]
    key_position = source_columns.index(id_field)
    result: dict[Any, tuple[Any, ...]] = {}
    previous_cursor: tuple[Any, ...] | None = None
    for raw_row in rows:
        row = tuple(raw_row[position] for position in positions)
        identifier = row[key_position]
        page_cursor = tuple(raw_row[position] for position in page_positions)
        if any(value is None for value in page_cursor) or (previous_cursor is not None and page_cursor <= previous_cursor):
            raise RuntimeError(f"integration SQL must return unique, non-NULL source page keys: {', '.join(page_key)}")
        if identifier is None or identifier in result:
            raise RuntimeError(f"integration SQL must return unique, non-NULL {id_field} values")
        result[identifier] = row
        previous_cursor = page_cursor
    return result, previous_cursor


def staging_changes_for_keys(connection: Any, schema: str, table: str, id_field: str, change_field: str | None, identifiers: list[Any]) -> dict[Any, Any]:
    if not identifiers:
        return {}
    projection = f'"{id_field}"' if change_field is None else f'"{id_field}", "{change_field}"'
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {projection} FROM {relation_sql(schema, table)} WHERE \"{id_field}\" = ANY(%s) FOR UPDATE", (identifiers,))
        result: dict[Any, Any] = {}
        for row in cursor.fetchall():
            if row[0] in result:
                raise RuntimeError(f"staging table {schema}.{table} contains a duplicate {id_field}: {row[0]!r}")
            result[row[0]] = row[1] if change_field else None
        return result


def staging_key_page(connection: Any, schema: str, table: str, id_field: str, after_key: str | None, page_size: int) -> list[Any]:
    suffix = "" if after_key is None else f' WHERE "{id_field}" > %s'
    parameters: tuple[Any, ...] = (page_size,) if after_key is None else (after_key, page_size)
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT "{id_field}" FROM {relation_sql(schema, table)}{suffix} ORDER BY "{id_field}" LIMIT %s', parameters)
        return [row[0] for row in cursor.fetchall()]


def save_state(path: Path, state: dict[str, Any], *, phase: str, cursor: Any, page_count: int, rows: int) -> None:
    persisted_cursor = list(cursor) if isinstance(cursor, tuple) else (None if cursor is None else str(cursor))
    state.update(phase=phase, cursor=persisted_cursor, pages=page_count, rows=rows)
    atomic_json_write(path, state)


def run_resumable(args: argparse.Namespace, query: str, schema: str, table: str, id_field: str, change_field: str, page_key: tuple[str, ...], oracledb: Any, psycopg: Any) -> int:
    fingerprint = sync_fingerprint(query, schema, table, id_field, change_field, args.ignore_change_field, page_key)
    checkpoint, key_path, lock_path = resumable_paths(fingerprint)
    if not args.apply:
        raise RuntimeError("--resumable is only available with --apply; dry-run is already read-only")
    with file_lock(lock_path):
        state = read_checkpoint(checkpoint)
        if state and state.get("fingerprint") != fingerprint:
            raise RuntimeError("checkpoint belongs to a different table, SQL, or sync options; use --restart after review")
        if state and state.get("phase") == "complete":
            print("resumable sync already complete; use --restart only to deliberately replay it")
            return 0
        with psycopg.connect(**pg_settings()) as connection:
            source_columns, destination_columns = target_columns(connection, schema, table, id_field)
            require_unique_key(connection, schema, table, id_field)
        missing_page_columns = set(page_key) - set(source_columns)
        if missing_page_columns:
            raise RuntimeError(f"--source-page-key columns must be selected by the integration and exist in staging: {', '.join(sorted(missing_page_columns))}")
        if not args.ignore_change_field and change_field not in source_columns:
            raise RuntimeError(f"integration/staging table must contain {change_field}, or use --ignore-change-field")
        if not state:
            require_unique_source_keys(oracledb, query, id_field)
            state = {"fingerprint": fingerprint, "schema": schema, "table": table, "id_field": id_field, "change_field": change_field, "source_page_key": page_key, "ignore_change_field": args.ignore_change_field, "phase": "preflight", "cursor": None, "pages": 0, "rows": 0, "status": "running"}
            atomic_json_write(checkpoint, state)
        keys = key_database(key_path)
        try:
            page_count = int(state["pages"])
            invocation_start_pages = page_count
            rows = int(state["rows"])
            phase = state["phase"]
            cursor = tuple(state["cursor"]) if phase in {"preflight", "apply"} and state.get("cursor") is not None else state.get("cursor")
            if phase in {"apply", "delete", "complete"}:
                if not state.get("key_index_complete") or key_count(keys) != state.get("source_key_count"):
                    raise RuntimeError("resumable source-key index is missing or incomplete; use --restart")
            while True:
                if args.max_pages and page_count - invocation_start_pages >= args.max_pages:
                    print("stopped at --max-pages; rerun with --resumable --apply to continue")
                    return 0
                if phase == "preflight":
                    kn_changes, next_cursor = source_change_page(oracledb, query, id_field, None if args.ignore_change_field else change_field, page_key, cursor, args.page_size)
                    if not kn_changes:
                        phase, cursor = "apply", None
                        state.update(key_index_complete=True, source_key_count=key_count(keys))
                        save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                        continue
                    with psycopg.connect(**pg_settings()) as connection:
                        stag_changes = staging_changes_for_keys(connection, schema, table, id_field, None if args.ignore_change_field else change_field, list(kn_changes))
                    _delete, _insert, _unchanged, _updates, conflicts = make_plan(kn_changes, stag_changes, change_field, args.ignore_change_field)
                    if conflicts:
                        state["phase"] = "conflict"
                        state["conflicts"] = len(conflicts)
                        atomic_json_write(checkpoint, state)
                        raise RuntimeError(f"found {len(conflicts)} staging-newer conflicts during preflight; no writes were made; correct them and use --restart")
                    remember_keys(keys, kn_changes)
                    cursor = next_cursor
                    page_count += 1
                    rows += len(kn_changes)
                    save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                    print(f"preflight committed page {page_count} ({len(kn_changes)} keys; total {rows})")
                    continue
                if phase == "apply":
                    source, next_cursor = source_full_page(oracledb, query, id_field, source_columns, page_key, cursor, args.page_size)
                    if not source:
                        phase, cursor = "delete", None
                        save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                        continue
                    if any(not known_key(keys, identifier) for identifier in source):
                        raise RuntimeError("KN result changed during resumable sync; use --restart to build a fresh key index")
                    with psycopg.connect(**pg_settings()) as connection:
                        with connection.transaction():
                            stag_changes = staging_changes_for_keys(connection, schema, table, id_field, None if args.ignore_change_field else change_field, list(source))
                            _delete, insert_ids, _unchanged, update_ids, conflicts = make_plan({identifier: row[source_columns.index(change_field)] if not args.ignore_change_field else None for identifier, row in source.items()}, stag_changes, change_field, args.ignore_change_field)
                            if conflicts:
                                raise RuntimeError("staging became newer during resumable sync; transaction rolled back")
                            insert_sql = insert_statement(schema, table, source_columns, destination_columns)
                            update_columns = [column for column in source_columns if column != id_field]
                            updated_at_clause = ', "updated_at" = CURRENT_TIMESTAMP' if "updated_at" in destination_columns else ""
                            update_sql = f'UPDATE {relation_sql(schema, table)} SET {", ".join(f"\"{column}\" = %s" for column in update_columns)}{updated_at_clause} WHERE "{id_field}" = %s'
                            with connection.cursor() as db_cursor:
                                db_cursor.executemany(insert_sql, (source[identifier] for identifier in insert_ids))
                                values = ((*[source[identifier][source_columns.index(column)] for column in update_columns], identifier) for identifier in update_ids)
                                db_cursor.executemany(update_sql, values)
                    cursor = next_cursor
                    page_count += 1
                    rows += len(source)
                    save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                    print(f"apply committed page {page_count} ({len(source)} rows; total {rows})")
                    continue
                if phase == "delete":
                    with psycopg.connect(**pg_settings()) as connection:
                        identifiers = staging_key_page(connection, schema, table, id_field, cursor, args.page_size)
                        if not identifiers:
                            state.update(phase="complete", status="complete", completed_at=datetime.now().astimezone().isoformat())
                            atomic_json_write(checkpoint, state)
                            print(f"complete: {state['rows']} scanned rows in {state['pages']} pages")
                            return 0
                        delete_ids = [identifier for identifier in identifiers if not known_key(keys, identifier)]
                        with connection.transaction():
                            if delete_ids:
                                with connection.cursor() as db_cursor:
                                    db_cursor.execute(f'DELETE FROM {relation_sql(schema, table)} WHERE "{id_field}" = ANY(%s)', (delete_ids,))
                    cursor = identifiers[-1]
                    page_count += 1
                    rows += len(identifiers)
                    save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                    print(f"delete committed page {page_count} ({len(delete_ids)} deleted; scanned {len(identifiers)})")
                    continue
                raise RuntimeError(f"unknown resumable checkpoint phase: {phase}")
        finally:
            keys.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="staging table name, without schema")
    parser.add_argument("--integration-sql", required=True, type=Path, help="path to the KN SELECT statement")
    parser.add_argument("--id-field", default="id", help="unique membership key in both systems (default: id)")
    parser.add_argument("--schema", default=None, help="defaults to STAG_SCHEMA or public")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only (the default)")
    mode.add_argument("--apply", action="store_true", help="perform deletes, inserts, and KN-newer updates")
    parser.add_argument("--change-field", default="date_change", help="field used to compare matching keys (default: DATE_CHANGE)")
    parser.add_argument("--ignore-change-field", action="store_true", help="use only key membership: delete absent staging keys and insert absent KN keys, but do not update or compare matching keys")
    parser.add_argument("--resumable", action="store_true", help="use local checkpointing and page-by-page commits (requires --apply)")
    parser.add_argument("--source-page-key", help="comma-separated native KN columns, in index order; required with --resumable")
    parser.add_argument("--status", action="store_true", help="show the resumable checkpoint and exit")
    parser.add_argument("--restart", action="store_true", help="remove only this integration's resumable checkpoint and key index")
    parser.add_argument("--preview-limit", type=int, default=5, help="maximum example rows shown for each action (default: 5)")
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--page-size", type=int, default=1_000, help="rows per resumable page (default: 1000)")
    parser.add_argument("--max-pages", type=int, help="stop cleanly after this many resumable pages")
    args = parser.parse_args()
    if args.preview_limit < 0 or args.batch_size <= 0 or args.page_size <= 0:
        parser.error("--preview-limit must be non-negative and --batch-size/--page-size must be positive")
    if (args.status or args.restart) and not args.resumable:
        parser.error("--status and --restart require --resumable")
    if args.resumable and not args.source_page_key:
        parser.error("--resumable requires --source-page-key")
    return args


def main() -> int:
    args = parse_args()
    try:
        table = valid_identifier(args.table, "table")
        id_field = valid_identifier(args.id_field, "id field").lower()
        change_field = valid_identifier(args.change_field, "change field").lower()
        page_key = source_page_key(args.source_page_key) if args.resumable else ()
        load_environment()
        schema = valid_identifier(args.schema or os.environ.get("STAG_SCHEMA", "public"), "schema")
        query = read_select(args.integration_sql)
        if args.resumable and (args.status or args.restart):
            fingerprint = sync_fingerprint(query, schema, table, id_field, change_field, args.ignore_change_field, page_key)
            checkpoint, key_path, lock_path = resumable_paths(fingerprint)
            if args.status:
                print(json.dumps(read_checkpoint(checkpoint) or {"status": "not started"}, indent=2, default=str))
                return 0
            with file_lock(lock_path):
                for path in (checkpoint, key_path):
                    if path.exists():
                        path.unlink()
            print("removed this integration's resumable checkpoint and source-key index")
            return 0
        oracledb, psycopg = require_drivers()
        enable_oracle_thick_mode(oracledb)
        if args.resumable:
            return run_resumable(args, query, schema, table, id_field, change_field, page_key, oracledb, psycopg)
        with oracledb.connect(**oracle_settings(oracledb)) as kn, psycopg.connect(**pg_settings()) as stag:
            source_columns, destination_columns = target_columns(stag, schema, table, id_field)
            if not args.ignore_change_field and change_field not in source_columns:
                raise RuntimeError(f"integration/staging table must contain {change_field}, or use --ignore-change-field")
            # Dry-runs deliberately fetch only the key and change field from KN.
            kn_changes = source_changes(kn, query, id_field, None if args.ignore_change_field else change_field)
            relation = relation_sql(schema, table)
            insert_sql = insert_statement(schema, table, source_columns, destination_columns)

            def report_and_preview(stag_changes: dict[Any, Any]) -> tuple[list[Any], list[Any], list[Any], list[Any], list[tuple[Any, Any, Any]]]:
                plan = make_plan(kn_changes, stag_changes, change_field, args.ignore_change_field)
                delete_ids, insert_ids, unchanged_ids, update_ids, conflicts = plan
                print(json.dumps({"mode": "apply" if args.apply else "dry-run", "schema": schema, "table": table, "id_field": id_field, "change_field": change_field, "ignore_change_field": args.ignore_change_field, "kn_keys": len(kn_changes), "staging_keys": len(stag_changes), "unchanged": len(unchanged_ids), "delete_from_staging": len(delete_ids), "insert_into_staging": len(insert_ids), "update_in_staging": len(update_ids), "staging_newer_conflicts": len(conflicts)}))
                if args.preview_limit:
                    preview_columns = [id_field] if args.ignore_change_field else [id_field, change_field]
                    if args.ignore_change_field:
                        preview("DELETE", ((identifier,) for identifier in delete_ids), preview_columns, args.preview_limit)
                        preview("INSERT", ((identifier,) for identifier in insert_ids), preview_columns, args.preview_limit)
                        preview("UPDATE", (), preview_columns, args.preview_limit)
                    else:
                        preview("DELETE", ((identifier, stag_changes[identifier]) for identifier in delete_ids), preview_columns, args.preview_limit)
                        preview("INSERT", ((identifier, kn_changes[identifier]) for identifier in insert_ids), preview_columns, args.preview_limit)
                        preview("UPDATE", ((identifier, kn_changes[identifier]) for identifier in update_ids), preview_columns, args.preview_limit)
                    if conflicts:
                        preview_conflicts(conflicts, id_field, change_field, args.preview_limit)
                return plan

            if not args.apply:
                plan = report_and_preview(staging_changes(stag, schema, table, id_field, None if args.ignore_change_field else change_field))
                if plan[-1]:
                    raise RuntimeError("staging has rows with a newer change field; no changes were made")
                return 0

            update_columns = [column for column in source_columns if column != id_field]
            updated_at_clause = ', "updated_at" = CURRENT_TIMESTAMP' if "updated_at" in destination_columns else ""
            update_sql = f'UPDATE {relation} SET {", ".join(f"\"{column}\" = %s" for column in update_columns)}{updated_at_clause} WHERE "{id_field}" = %s'
            with stag.transaction():
                with stag.cursor() as cursor:
                    cursor.execute(f"LOCK TABLE {relation} IN SHARE ROW EXCLUSIVE MODE")
                delete_ids, insert_ids, _unchanged_ids, update_ids, conflicts = report_and_preview(staging_changes(stag, schema, table, id_field, None if args.ignore_change_field else change_field))
                if conflicts:
                    raise RuntimeError("staging has rows with a newer change field; transaction rolled back without changes")
                # Fetch full KN rows only after the apply preflight has proved
                # that data must be inserted or updated.
                source: dict[Any, tuple[Any, ...]] = {}
                if insert_ids or update_ids:
                    source = source_rows(kn, query, source_columns, id_field)
                    if set(source) != set(kn_changes):
                        raise RuntimeError("KN result changed during this run; transaction rolled back without changes")
                with stag.cursor() as cursor:
                    for start in range(0, len(delete_ids), args.batch_size):
                        cursor.execute(f'DELETE FROM {relation} WHERE "{id_field}" = ANY(%s)', (delete_ids[start : start + args.batch_size],))
                    for start in range(0, len(insert_ids), args.batch_size):
                        cursor.executemany(insert_sql, (source[identifier] for identifier in insert_ids[start : start + args.batch_size]))
                    for start in range(0, len(update_ids), args.batch_size):
                        values = ((*[source[identifier][source_columns.index(column)] for column in update_columns], identifier) for identifier in update_ids[start : start + args.batch_size])
                        cursor.executemany(update_sql, values)
            print(f"applied: deleted {len(delete_ids)} rows; inserted {len(insert_ids)} rows; updated {len(update_ids)} rows")
            return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
