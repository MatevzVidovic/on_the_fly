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
import signal
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID


HERE = Path(__file__).resolve().parent
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
# These columns are owned by LIFT/PostgreSQL, not supplied by the KN SELECT.
LIFT_SYSTEM_COLUMNS = frozenset({"id", "created_at", "created_by", "updated_at", "updated_by"})
PAGE_ONLY_PREFIX = "kn_page_"
DELTA_ONLY_PREFIX = "kn_delta_"
STATE_FORMAT = 3  # Full-reconciliation checkpoint format: do not change.
ONLY_NEW_STATE_FORMAT = 1
_SIGINT_COUNT = 0
AUTO_PAGE_SIZE_DIR = HERE / ".auto_page_sizes"
AUTO_PAGE_SIZE_DIVISOR = 3
# Three consecutive full pages that each take at least twice the earlier
# median time per row are very unlikely to be normal end-of-result behaviour.
SLOW_PAGE_WINDOW = 3
SLOW_PAGE_FACTOR = 2.0


def install_sigint_handler() -> None:
    """First Ctrl-C stops after the current page; second aborts immediately."""
    def handle_sigint(_signum: int, _frame: Any) -> None:
        global _SIGINT_COUNT
        _SIGINT_COUNT += 1
        if _SIGINT_COUNT == 1:
            print("\nSIGINT received: finishing the current page, checkpointing it, then stopping. Press Ctrl-C again to abort immediately.", file=sys.stderr, flush=True)
            return
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_sigint)
    # Ask Python to restart interrupted system calls after the first graceful
    # SIGINT.  In particular this avoids needlessly breaking an Oracle fetch
    # when the operator only wants to stop after its page checkpoint.
    signal.siginterrupt(signal.SIGINT, False)


def valid_identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a plain PostgreSQL identifier")
    return value


def source_page_key(value: str) -> tuple[str, ...]:
    fields = tuple(valid_identifier(field.strip(), "source page key").lower() for field in value.split(",") if field.strip())
    if not fields or len(set(fields)) != len(fields):
        raise ValueError("--source-page-key must contain one or more distinct comma-separated columns")
    return fields


def source_watermark_field(value: str) -> str:
    """Return an integration-query alias used for Oracle delta ordering."""
    return valid_identifier(value, "source watermark field").lower()


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
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"JSON settings file is unreadable: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON settings file is invalid: {path}")
    return value


def auto_page_size_profile_key(query: str, schema: str, table: str, id_field: str, page_key: tuple[str, ...], category: str, ignore_change_field: bool) -> str:
    """Stable identity for the Oracle result shape whose page size is learned."""
    payload = json.dumps(
        {"query": query, "schema": schema, "table": table, "id_field": id_field, "source_page_key": page_key, "category": category, "ignore_change_field": ignore_change_field},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def auto_page_size_path(profile_key: str) -> Path:
    return AUTO_PAGE_SIZE_DIR / f"{profile_key}.json"


def learned_page_size(profile_key: str) -> int | None:
    try:
        value = read_json_object(auto_page_size_path(profile_key)).get("page_size")
    except RuntimeError as error:
        print(f"warning: ignoring unreadable auto page-size profile: {error}", file=sys.stderr, flush=True)
        return None
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def remember_page_size(profile_key: str, page_size: int, schema: str, table: str) -> None:
    try:
        atomic_json_write(auto_page_size_path(profile_key), {
            "page_size": page_size,
            "schema": schema,
            "table": table,
            "updated_at": datetime.now().astimezone().isoformat(),
        })
    except OSError as error:
        print(f"warning: could not save optional auto page-size profile: {error}", file=sys.stderr, flush=True)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = max(0, round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:d}:{seconds:02d}"


def record_page_timing(state: dict[str, Any], phase: str, page_rows: int, page_size: int, wall_elapsed: float, successful_elapsed: float) -> tuple[float, str | None, str | None]:
    """Store bounded timing history and return a conservative phase ETA."""
    metrics = state.setdefault("timing", {})
    phase_metrics = metrics.setdefault(phase, {"elapsed_seconds": 0.0, "rows": 0, "full_page_seconds_per_row": []})
    phase_metrics["elapsed_seconds"] = float(phase_metrics.get("elapsed_seconds", 0.0)) + wall_elapsed
    phase_metrics["rows"] = int(phase_metrics.get("rows", 0)) + page_rows
    history = list(phase_metrics.get("full_page_seconds_per_row", []))
    slow_reason: str | None = None
    if page_rows == page_size and page_rows:
        sample = successful_elapsed / page_rows
        history.append(sample)
        # Keep enough older measurements for a meaningful baseline without
        # making checkpoint files grow with a large integration.
        history = history[-12:]
        if len(history) >= SLOW_PAGE_WINDOW + 2:
            recent = history[-SLOW_PAGE_WINDOW:]
            baseline = sorted(history[:-SLOW_PAGE_WINDOW])[len(history[:-SLOW_PAGE_WINDOW]) // 2]
            if baseline > 0 and all(value >= baseline * SLOW_PAGE_FACTOR for value in recent):
                slow_reason = (
                    f"three full {phase} pages are at least {SLOW_PAGE_FACTOR:g}x slower per row "
                    f"than the earlier median"
                )
    phase_metrics["full_page_seconds_per_row"] = history
    total = state.get("source_key_count") if phase in {"apply", "verify", "delta"} else None
    if not isinstance(total, int) or total <= page_rows:
        aggregate_elapsed = float(phase_metrics["elapsed_seconds"])
        aggregate_rows = int(phase_metrics["rows"])
        return (aggregate_rows / aggregate_elapsed if aggregate_elapsed else float("inf")), None, slow_reason
    aggregate_elapsed = float(phase_metrics["elapsed_seconds"])
    aggregate_rows = int(phase_metrics["rows"])
    rate = aggregate_rows / aggregate_elapsed if aggregate_elapsed else float("inf")
    done = int(state.get({"apply": "applied_rows", "verify": "verified_rows", "delta": "delta_rows"}[phase], 0)) if phase in {"apply", "verify", "delta"} else 0
    eta = (total - done) / rate if rate else None
    return rate, (f"ETA {format_duration(eta)}" if eta is not None else None), slow_reason


def phase_page_number(state: dict[str, Any], phase: str) -> int:
    counts = state.setdefault("phase_pages", {})
    counts[phase] = int(counts.get(phase, 0)) + 1
    return counts[phase]


def is_size_relevant_failure(error: Exception) -> bool:
    """Failures for which fewer fetched rows can realistically help."""
    text = str(error).lower()
    return any(marker in text for marker in (
        "fetch timeout", "read timeout", "query timeout", "ora-04030", "ora-04031",
        "out of memory", "memory allocation", "dpi-1015", "array size", "fetch buffer",
    ))


def adaptive_source_page(args: argparse.Namespace, state: dict[str, Any], profile_key: str, schema: str, table: str, phase: str, category: str, operation: Any) -> tuple[Any, int, float, float]:
    """Read one Oracle page, with at most three 3x size reductions in auto mode."""
    sizes = state.setdefault("effective_page_sizes", {})
    page_size = int(sizes.get(category, args.page_size)) if args.auto_page_size else args.page_size
    reductions = 0
    logical_started = time.perf_counter()
    while True:
        started = time.perf_counter()
        try:
            # Auto sizing must observe the first candidate failure itself.
            return operation(page_size, not args.auto_page_size), page_size, time.perf_counter() - started, time.perf_counter() - logical_started
        except Exception as error:
            if not args.auto_page_size:
                raise
            if not is_size_relevant_failure(error):
                # Network/lost-contact failures are unrelated to row count;
                # retain ordinary transient retry rather than shrinking.
                try:
                    retried_started = time.perf_counter()
                    result = operation(page_size, True)
                    return result, page_size, time.perf_counter() - retried_started, time.perf_counter() - logical_started
                except Exception as retry_error:
                    error = retry_error
                    if not is_size_relevant_failure(error):
                        raise error
            if page_size <= 1 or reductions >= 3:
                raise
            smaller = max(1, page_size // AUTO_PAGE_SIZE_DIVISOR)
            if smaller == page_size:
                raise
            print(
                f"{phase} page read failed at page size {page_size}: {error}; "
                f"retrying the same cursor at {smaller}",
                file=sys.stderr,
                flush=True,
            )
            page_size = smaller
            sizes[category] = page_size
            reductions += 1


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


@contextmanager
def staging_advisory_lock(psycopg: Any, schema: str, table: str) -> Iterable[Any]:
    """Keep a cooperative per-table PG lock while individual pages commit."""
    connection = psycopg.connect(**pg_settings())
    # Session advisory locks outlive transactions.  This dedicated connection
    # must not remain idle in an open transaction for a long backfill run.
    connection.autocommit = True
    name = f"kn_to_stag_delta:{schema}.{table}"

    def heartbeat() -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

    try:
        with connection.cursor() as cursor:
            # This is a dedicated, intentionally idle session while Oracle
            # pages are fetched.  Disable the server's idle-session timeout
            # for it; the process still sends heartbeats between pages.
            cursor.execute("SET idle_session_timeout = 0")
            cursor.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (name,))
            if not cursor.fetchone()[0]:
                raise RuntimeError(f"another resumable sync holds the staging advisory lock for {schema}.{table}")
        yield heartbeat
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", (name,))
        finally:
            connection.close()


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


def require_unique_key(connection: Any, schema: str, table: str, id_field: str, trust_unique_non_null: bool = False, require_not_null: bool = True) -> None:
    if trust_unique_non_null:
        return
    query = """
        SELECT 1
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = i.indkey[0]
        WHERE n.nspname = %s AND c.relname = %s
          AND i.indisunique AND i.indisvalid AND i.indpred IS NULL
          AND i.indnkeyatts = 1 AND a.attname = %s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (schema, table, id_field))
        if cursor.fetchone() is None:
            raise RuntimeError(f"staging table {schema}.{table} needs a non-partial single-column unique key on {id_field}")
        if not require_not_null:
            return
        cursor.execute(
            "SELECT is_nullable FROM information_schema.columns WHERE table_schema = %s AND table_name = %s AND column_name = %s",
            (schema, table, id_field),
        )
        nullable = cursor.fetchone()
        if nullable is None or nullable[0] != "NO":
            raise RuntimeError(f"staging table {schema}.{table} requires {id_field} to be NOT NULL for resumable sync")


def insert_statement(schema: str, table: str, source_columns: list[str], destination_columns: list[str]) -> str:
    """Insert source data while explicitly filling LIFT-owned audit fields."""
    automatic_values = {
        "id": "uuid_generate_v4()",
        "created_by": "'00000000-0000-0000-0000-000000000000'::uuid",
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


def encode_value(value: Any) -> dict[str, str]:
    """Losslessly persist the Oracle values permitted in resumable keys."""
    if isinstance(value, bool) or value is None:
        raise RuntimeError("resumable key values must be non-NULL and cannot be boolean")
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, UUID):
        return {"type": "uuid", "value": str(value)}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    raise RuntimeError(
        "unsupported resumable key value type "
        f"{type(value).__name__}; supported types are str, int, Decimal, date, and datetime"
    )


def decode_value(value: Any) -> Any:
    if not isinstance(value, dict) or set(value) != {"type", "value"} or not isinstance(value["value"], str):
        raise RuntimeError("checkpoint contains an invalid typed value; use --restart")
    kind, text = value["type"], value["value"]
    if kind == "str":
        return text
    if kind == "int":
        return int(text)
    if kind == "decimal":
        return Decimal(text)
    if kind == "uuid":
        return UUID(text)
    if kind == "date":
        return date.fromisoformat(text)
    if kind == "datetime":
        return datetime.fromisoformat(text)
    raise RuntimeError("checkpoint contains an unsupported typed value; use --restart")


def encode_tuple(values: tuple[Any, ...]) -> list[dict[str, str]]:
    return [encode_value(value) for value in values]


def decode_tuple(values: Any) -> tuple[Any, ...] | None:
    if values is None:
        return None
    if not isinstance(values, list):
        raise RuntimeError("checkpoint cursor is invalid; use --restart")
    return tuple(decode_value(value) for value in values)


def encoded_key(value: Any) -> str:
    return json.dumps(encode_value(value), sort_keys=True, separators=(",", ":"))


def encoded_tuple(values: tuple[Any, ...]) -> str:
    return json.dumps(encode_tuple(values), sort_keys=True, separators=(",", ":"))


def allowed_extra_columns(columns: Iterable[str]) -> bool:
    return all(column.startswith((PAGE_ONLY_PREFIX, DELTA_ONLY_PREFIX)) for column in columns)


def validate_source_output(names: list[str], destination_columns: list[str], page_key: tuple[str, ...] = ()) -> None:
    if len(set(names)) != len(names):
        raise RuntimeError("integration SQL output contains duplicate column names")
    missing = sorted(set(destination_columns) - set(names))
    missing_page = sorted(set(page_key) - set(names))
    extras = sorted(set(names) - set(destination_columns))
    if missing or missing_page or not allowed_extra_columns(extras):
        extra_message = extras if not allowed_extra_columns(extras) else "-"
        raise RuntimeError(
            "integration SQL columns do not match staging table; "
            f"missing: {missing or '-'}; missing page keys: {missing_page or '-'}; extra: {extra_message}"
        )


def source_rows(connection: Any, query: str, target_columns_: list[str], id_field: str) -> dict[Any, tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        source_columns = [description[0].lower() for description in cursor.description]
        validate_source_output(source_columns, target_columns_)
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


def sync_fingerprint(query: str, schema: str, table: str, id_field: str, change_field: str, ignore_change_field: bool, page_key: tuple[str, ...], trust_unique_non_null: bool = False) -> str:
    payload = json.dumps({"format": STATE_FORMAT, "query": query, "schema": schema, "table": table, "id_field": id_field, "change_field": change_field, "ignore_change_field": ignore_change_field, "source_page_key": page_key, "trust_unique_non_null": trust_unique_non_null}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def key_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS source_keys (
            key TEXT PRIMARY KEY,
            page_key TEXT NOT NULL UNIQUE,
            change_value TEXT
        )
    """)
    return connection


def remember_keys(connection: sqlite3.Connection, records: Iterable[tuple[Any, tuple[Any, ...], Any]]) -> None:
    encoded_records = [
        (encoded_key(identifier), encoded_tuple(page_cursor), None if changed_at is None else encoded_key(changed_at))
        for identifier, page_cursor, changed_at in records
    ]
    # A crash after SQLite commits but before checkpoint.json is atomically
    # replaced replays this page.  Accept only an identical replay; a changed
    # ID/page tuple/change value is still an invariant failure.
    connection.executemany(
        "INSERT INTO source_keys (key, page_key, change_value) VALUES (?, ?, ?) "
        "ON CONFLICT DO NOTHING",
        encoded_records,
    )
    for key, page_key, change_value in encoded_records:
        found = connection.execute(
            "SELECT 1 FROM source_keys WHERE key = ? AND page_key = ? AND change_value IS ?",
            (key, page_key, change_value),
        ).fetchone()
        if found is None:
            raise RuntimeError("integration SQL returned duplicate source ID or source page tuple")
    connection.commit()


def known_record(connection: sqlite3.Connection, identifier: Any, page_cursor: tuple[Any, ...], changed_at: Any) -> bool:
    return connection.execute(
        "SELECT 1 FROM source_keys WHERE key = ? AND page_key = ? AND change_value IS ?",
        (encoded_key(identifier), encoded_tuple(page_cursor), None if changed_at is None else encoded_key(changed_at)),
    ).fetchone() is not None


def known_key(connection: sqlite3.Connection, identifier: Any) -> bool:
    return connection.execute("SELECT 1 FROM source_keys WHERE key = ?", (encoded_key(identifier),)).fetchone() is not None


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


def oracle_page(oracledb: Any, query: str, page_key: tuple[str, ...], projection: str, after_key: tuple[Any, ...] | None, page_size: int, retry_transient: bool = True) -> tuple[list[str], list[tuple[Any, ...]]]:
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
    return retry(operation) if retry_transient else operation()


def tuple_predicate(fields: tuple[str, ...], operator: str, bind_prefix: str) -> str:
    """Lexicographic tuple predicate which also works on Oracle versions without row comparison syntax."""
    branches: list[str] = []
    if operator not in {">", "<="}:
        raise ValueError("tuple predicate supports only > and <=")
    for index, field in enumerate(fields):
        equal_prefix = [f"{fields[prefix]} = :{bind_prefix}_{prefix}" for prefix in range(index)]
        comparison = operator if operator == ">" or index == len(fields) - 1 else "<"
        branches.append(" AND ".join([*equal_prefix, f"{field} {comparison} :{bind_prefix}_{index}"]))
    return "(" + " OR ".join(f"({branch})" for branch in branches) + ")"


def oracle_delta_upper(oracledb: Any, query: str, watermark_field: str, page_key: tuple[str, ...], lower_watermark: Any | None) -> tuple[Any, ...] | None:
    """Freeze the greatest Oracle `(watermark, native key)` tuple for this window."""
    fields = (watermark_field, *page_key)

    def operation() -> tuple[Any, ...] | None:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            where = "" if lower_watermark is None else f" WHERE {watermark_field} >= :lower_watermark"
            sql = (
                f"SELECT {', '.join(fields)} FROM ({query}) source_rows{where} "
                f"ORDER BY {', '.join(f'{field} DESC' for field in fields)} FETCH FIRST 1 ROWS ONLY"
            )
            with connection.cursor() as cursor:
                cursor.execute(sql, {} if lower_watermark is None else {"lower_watermark": lower_watermark})
                row = cursor.fetchone()
                return None if row is None else tuple(scalar(value) for value in row)

    return retry(operation)


def oracle_delta_page(oracledb: Any, query: str, watermark_field: str, page_key: tuple[str, ...], projection: str, lower_watermark: Any | None, upper_cursor: tuple[Any, ...], after_cursor: tuple[Any, ...] | None, page_size: int, retry_transient: bool = True) -> tuple[list[str], list[tuple[Any, ...]]]:
    """Fetch one bounded incremental page ordered by watermark then native key."""
    fields = (watermark_field, *page_key)

    def operation() -> tuple[list[str], list[tuple[Any, ...]]]:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            condition, binds = delta_conditions(watermark_field, page_key, lower_watermark, upper_cursor, after_cursor)
            binds["page_size"] = page_size
            sql = (
                f"SELECT {projection} FROM ({query}) source_rows WHERE {condition} "
                f"ORDER BY {', '.join(fields)} FETCH FIRST :page_size ROWS ONLY"
            )
            with connection.cursor() as cursor:
                cursor.execute(sql, binds)
                names = [description[0].lower() for description in cursor.description]
                return names, [tuple(scalar(value) for value in row) for row in cursor.fetchall()]

    return retry(operation) if retry_transient else operation()


def oracle_delta_count(oracledb: Any, query: str, watermark_field: str, page_key: tuple[str, ...], lower_watermark: Any | None, upper_cursor: tuple[Any, ...], after_cursor: tuple[Any, ...] | None = None) -> int:
    """Count the frozen delta window for accurate progress/ETA output."""
    fields = (watermark_field, *page_key)

    def operation() -> int:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            condition, binds = delta_conditions(watermark_field, page_key, lower_watermark, upper_cursor, after_cursor)
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM ({query}) source_rows WHERE {condition}", binds)
                return int(cursor.fetchone()[0])

    return retry(operation)


def source_delta_full_page(oracledb: Any, query: str, id_field: str, source_columns: list[str], watermark_field: str, page_key: tuple[str, ...], lower_watermark: Any | None, upper_cursor: tuple[Any, ...], after_cursor: tuple[Any, ...] | None, page_size: int, retry_transient: bool = True) -> tuple[dict[Any, tuple[Any, ...]], dict[Any, tuple[Any, ...]], tuple[Any, ...] | None]:
    names, rows = oracle_delta_page(oracledb, query, watermark_field, page_key, "source_rows.*", lower_watermark, upper_cursor, after_cursor, page_size, retry_transient)
    validate_source_output(names, source_columns, (*page_key, watermark_field))
    positions = [names.index(column) for column in source_columns]
    key_position = source_columns.index(id_field)
    cursor_positions = [names.index(field) for field in (watermark_field, *page_key)]
    result: dict[Any, tuple[Any, ...]] = {}
    cursors: dict[Any, tuple[Any, ...]] = {}
    for raw_row in rows:
        row = tuple(raw_row[position] for position in positions)
        identifier = row[key_position]
        page_cursor = tuple(raw_row[position] for position in cursor_positions)
        if identifier is None or identifier in result:
            raise RuntimeError(f"integration SQL must return unique, non-NULL {id_field} values in the incremental window")
        if any(value is None for value in page_cursor):
            raise RuntimeError(f"integration SQL must return non-NULL {watermark_field} and source page keys in the incremental window")
        result[identifier] = row
        cursors[identifier] = page_cursor
    return result, cursors, cursors[next(reversed(cursors))] if cursors else None


def source_delta_change_page(oracledb: Any, query: str, id_field: str, change_field: str, watermark_field: str, page_key: tuple[str, ...], lower_watermark: Any | None, upper_cursor: tuple[Any, ...], after_cursor: tuple[Any, ...] | None, page_size: int, retry_transient: bool = True) -> tuple[dict[Any, Any], tuple[Any, ...] | None]:
    selected = list(dict.fromkeys([id_field, change_field, watermark_field, *page_key]))
    names, rows = oracle_delta_page(oracledb, query, watermark_field, page_key, ", ".join(selected), lower_watermark, upper_cursor, after_cursor, page_size, retry_transient)
    if names != selected:
        raise RuntimeError(f"integration SQL incremental key projection did not match expected columns: {selected}; got {names}")
    positions = {name: index for index, name in enumerate(names)}
    changes: dict[Any, Any] = {}
    last_cursor: tuple[Any, ...] | None = None
    for row in rows:
        identifier = row[positions[id_field]]
        last_cursor = tuple(row[positions[field]] for field in (watermark_field, *page_key))
        if identifier is None or identifier in changes:
            raise RuntimeError(f"integration SQL must return unique, non-NULL {id_field} values in the incremental window")
        if any(value is None for value in last_cursor):
            raise RuntimeError(f"integration SQL must return non-NULL {watermark_field} and source page keys in the incremental window")
        changes[identifier] = row[positions[change_field]]
    return changes, last_cursor


def source_change_page(oracledb: Any, query: str, id_field: str, change_field: str | None, page_key: tuple[str, ...], after_key: tuple[Any, ...] | None, page_size: int, retry_transient: bool = True) -> tuple[dict[Any, Any], dict[Any, tuple[Any, ...]], tuple[Any, ...] | None]:
    selected = list(dict.fromkeys([id_field, *(() if change_field is None else (change_field,)), *page_key]))
    projection = ", ".join(selected)
    names, rows = oracle_page(oracledb, query, page_key, projection, after_key, page_size, retry_transient)
    expected = selected
    if names != expected:
        raise RuntimeError(f"integration SQL key projection did not match expected columns: {expected}; got {names}")
    positions = {name: index for index, name in enumerate(names)}
    result: dict[Any, Any] = {}
    page_cursors: dict[Any, tuple[Any, ...]] = {}
    for row in rows:
        identifier = row[positions[id_field]]
        changed_at = row[positions[change_field]] if change_field else None
        page_cursor = tuple(row[positions[field]] for field in page_key)
        if any(value is None for value in page_cursor):
            raise RuntimeError(f"integration SQL must return unique, non-NULL source page keys: {', '.join(page_key)}")
        if identifier is None or identifier in result:
            raise RuntimeError(f"integration SQL must return unique, non-NULL {id_field} values")
        result[identifier] = changed_at
        page_cursors[identifier] = page_cursor
    return result, page_cursors, page_cursors[next(reversed(page_cursors))] if page_cursors else None


def oracle_columns(oracledb: Any, query: str) -> list[str]:
    def operation() -> list[str]:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT * FROM ({query}) source_rows WHERE 1 = 0")
                return [description[0].lower() for description in cursor.description]
    return retry(operation)


def oracle_column_metadata(oracledb: Any, query: str) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT * FROM ({query}) source_rows WHERE 1 = 0")
                return {description[0].lower(): description[1] for description in cursor.description}
    return retry(operation)


def require_only_new_source_shape(oracledb: Any, query: str, source_columns: list[str], page_key: tuple[str, ...], watermark_field: str) -> None:
    metadata = oracle_column_metadata(oracledb, query)
    validate_source_output(list(metadata), source_columns, (*page_key, watermark_field))
    oracle_type = metadata[watermark_field]
    type_name = str(oracle_type).upper()
    if "DATE" not in type_name and "TIMESTAMP" not in type_name:
        raise RuntimeError(
            f"--source-watermark-field {watermark_field} must be an Oracle DATE or TIMESTAMP alias, "
            f"not {oracle_type!s}; expose a native CAST(... AS TIMESTAMP) field"
        )


def delta_conditions(watermark_field: str, page_key: tuple[str, ...], lower_watermark: Any | None, upper_cursor: tuple[Any, ...], after_cursor: tuple[Any, ...] | None = None) -> tuple[str, dict[str, Any]]:
    fields = (watermark_field, *page_key)
    conditions = [tuple_predicate(fields, "<=", "upper")]
    binds: dict[str, Any] = {f"upper_{index}": value for index, value in enumerate(upper_cursor)}
    if lower_watermark is not None:
        conditions.append(f"{watermark_field} >= :lower_watermark")
        binds["lower_watermark"] = lower_watermark
    if after_cursor is not None:
        conditions.append(tuple_predicate(fields, ">", "after"))
        binds.update({f"after_{index}": value for index, value in enumerate(after_cursor)})
    return " AND ".join(conditions), binds


def require_delta_invariants(oracledb: Any, query: str, id_field: str, watermark_field: str, page_key: tuple[str, ...], lower_watermark: Any | None, upper_cursor: tuple[Any, ...]) -> None:
    """Validate identity/cursor uniqueness only in the frozen incremental window."""
    conditions, binds = delta_conditions(watermark_field, page_key, lower_watermark, upper_cursor)

    def operation() -> None:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT {id_field} FROM ({query}) source_rows WHERE {conditions} GROUP BY {id_field} HAVING {id_field} IS NULL OR COUNT(*) > 1 FETCH FIRST 1 ROWS ONLY", binds)
                invalid = cursor.fetchone()
                if invalid:
                    raise RuntimeError(f"incremental window returned NULL or duplicate {id_field}: {invalid[0]!r}")
                fields = (watermark_field, *page_key)
                nulls = " OR ".join(f"{field} IS NULL" for field in fields)
                cursor.execute(f"SELECT 1 FROM ({query}) source_rows WHERE {conditions} GROUP BY {', '.join(fields)} HAVING ({nulls}) OR COUNT(*) > 1 FETCH FIRST 1 ROWS ONLY", binds)
                if cursor.fetchone():
                    raise RuntimeError(f"incremental window returned NULL or duplicate watermark/page tuple: {', '.join(fields)}")
    retry(operation)


def require_source_invariants(oracledb: Any, query: str, id_field: str, page_key: tuple[str, ...], source_columns: list[str], watermark_field: str | None = None) -> None:
    required_keys = (*page_key, *((watermark_field,) if watermark_field else ()))
    validate_source_output(oracle_columns(oracledb, query), source_columns, required_keys)

    def operation() -> None:
        with oracledb.connect(**oracle_settings(oracledb)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {id_field} FROM ({query}) source_rows GROUP BY {id_field} "
                    f"HAVING {id_field} IS NULL OR COUNT(*) > 1 FETCH FIRST 1 ROWS ONLY"
                )
                invalid_id = cursor.fetchone()
                if invalid_id:
                    if invalid_id[0] is None:
                        raise RuntimeError(f"integration SQL returned a NULL {id_field}")
                    raise RuntimeError(f"integration SQL returned duplicate {id_field}: {invalid_id[0]!r}")
                null_condition = " OR ".join(f"{field} IS NULL" for field in page_key)
                cursor.execute(
                    f"SELECT 1 FROM ({query}) source_rows GROUP BY {', '.join(page_key)} "
                    f"HAVING ({null_condition}) OR COUNT(*) > 1 FETCH FIRST 1 ROWS ONLY"
                )
                if cursor.fetchone():
                    raise RuntimeError(f"integration SQL returned NULL or duplicate source page tuple: {', '.join(page_key)}")
                if watermark_field:
                    cursor.execute(f"SELECT 1 FROM ({query}) source_rows WHERE {watermark_field} IS NULL FETCH FIRST 1 ROWS ONLY")
                    if cursor.fetchone():
                        raise RuntimeError(f"integration SQL returned a NULL {watermark_field}; incremental watermarking would skip it")
    retry(operation)


def source_full_page(oracledb: Any, query: str, id_field: str, source_columns: list[str], page_key: tuple[str, ...], after_key: tuple[Any, ...] | None, page_size: int, retry_transient: bool = True) -> tuple[dict[Any, tuple[Any, ...]], dict[Any, tuple[Any, ...]], tuple[Any, ...] | None]:
    names, rows = oracle_page(oracledb, query, page_key, "source_rows.*", after_key, page_size, retry_transient)
    validate_source_output(names, source_columns, page_key)
    positions = [names.index(column) for column in source_columns]
    page_positions = [names.index(field) for field in page_key]
    key_position = source_columns.index(id_field)
    result: dict[Any, tuple[Any, ...]] = {}
    page_cursors: dict[Any, tuple[Any, ...]] = {}
    for raw_row in rows:
        row = tuple(raw_row[position] for position in positions)
        identifier = row[key_position]
        page_cursor = tuple(raw_row[position] for position in page_positions)
        if any(value is None for value in page_cursor):
            raise RuntimeError(f"integration SQL must return unique, non-NULL source page keys: {', '.join(page_key)}")
        if identifier is None or identifier in result:
            raise RuntimeError(f"integration SQL must return unique, non-NULL {id_field} values")
        result[identifier] = row
        page_cursors[identifier] = page_cursor
    return result, page_cursors, tuple(rows[-1][page_positions[index]] for index in range(len(page_positions))) if rows else None


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


def staging_key_page(connection: Any, schema: str, table: str, id_field: str, after_key: Any | None, page_size: int) -> list[Any]:
    suffix = "" if after_key is None else f' WHERE "{id_field}" > %s'
    parameters: tuple[Any, ...] = (page_size,) if after_key is None else (after_key, page_size)
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT "{id_field}" FROM {relation_sql(schema, table)}{suffix} ORDER BY "{id_field}" LIMIT %s', parameters)
        return [row[0] for row in cursor.fetchall()]


def save_state(path: Path, state: dict[str, Any], *, phase: str, cursor: Any, page_count: int, rows: int) -> None:
    cursor_field = {"preflight": "source_cursor", "apply": "source_cursor", "verify": "verify_cursor", "delete": "delete_cursor"}.get(phase)
    if cursor_field:
        if phase == "delete":
            state[cursor_field] = None if cursor is None else encode_value(cursor)
        else:
            state[cursor_field] = None if cursor is None else encode_tuple(cursor)
    state.update(phase=phase, pages=page_count, rows=rows)
    atomic_json_write(path, state)


def staging_max_change(connection: Any, schema: str, table: str, change_field: str) -> Any:
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT MAX("{change_field}") FROM {relation_sql(schema, table)}')
        return cursor.fetchone()[0]


def delta_fingerprint_args(query: str, schema: str, table: str, id_field: str, change_field: str, page_key: tuple[str, ...], watermark_field: str, trust_unique_non_null: bool) -> str:
    payload = json.dumps({"format": ONLY_NEW_STATE_FORMAT, "mode": "only_new", "query": query, "schema": schema, "table": table, "id_field": id_field, "change_field": change_field, "source_page_key": page_key, "source_watermark_field": watermark_field, "trust_unique_non_null": trust_unique_non_null}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def only_new_auto_page_size_profile_key(query: str, schema: str, table: str, id_field: str, page_key: tuple[str, ...]) -> str:
    payload = json.dumps({"format": ONLY_NEW_STATE_FORMAT, "mode": "only_new", "query": query, "schema": schema, "table": table, "id_field": id_field, "source_page_key": page_key, "category": "data"}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def initialise_only_new_state(checkpoint: Path, query: str, schema: str, table: str, id_field: str, change_field: str, page_key: tuple[str, ...], watermark_field: str, fingerprint: str, trust_unique_non_null: bool, args: argparse.Namespace, completed_watermark: Any) -> dict[str, Any]:
    profile = only_new_auto_page_size_profile_key(query, schema, table, id_field, page_key)
    state: dict[str, Any] = {
        "format": ONLY_NEW_STATE_FORMAT, "fingerprint": fingerprint, "mode": "only_new",
        "schema": schema, "table": table, "id_field": id_field, "change_field": change_field,
        "source_page_key": list(page_key), "source_watermark_field": watermark_field,
        "trust_unique_non_null": trust_unique_non_null, "auto_page_size": args.auto_page_size,
        "phase": "complete", "status": "complete", "completed_watermark": None if completed_watermark is None else encode_value(completed_watermark),
        "window_upper": None, "delta_cursor": None, "pages": 0, "rows": 0, "delta_rows": 0,
        "inserted": 0, "updated": 0, "unchanged": 0, "phase_pages": {"delta": 0}, "timing": {},
    }
    if args.auto_page_size:
        state["effective_page_sizes"] = {"data": min(learned_page_size(profile) or args.page_size, args.page_size)}
    atomic_json_write(checkpoint, state)
    return state


def only_new_settings_match(state: dict[str, Any], schema: str, table: str, id_field: str, change_field: str, page_key: tuple[str, ...], watermark_field: str, trust_unique_non_null: bool) -> bool:
    return all(state.get(field) == value for field, value in {
        "mode": "only_new", "schema": schema, "table": table, "id_field": id_field,
        "change_field": change_field, "source_page_key": list(page_key),
        "source_watermark_field": watermark_field, "trust_unique_non_null": trust_unique_non_null,
    }.items())


def run_only_new(args: argparse.Namespace, query: str, schema: str, table: str, id_field: str, change_field: str, page_key: tuple[str, ...], watermark_field: str, oracledb: Any, psycopg: Any) -> int:
    """Resumable insert/update-only delta.  It intentionally has no delete phase."""
    fingerprint = delta_fingerprint_args(query, schema, table, id_field, change_field, page_key, watermark_field, args.trust_unique_non_null)
    data_profile = only_new_auto_page_size_profile_key(query, schema, table, id_field, page_key)
    checkpoint, _key_path, lock_path = resumable_paths(fingerprint)
    if not args.apply:
        # Dry run never writes state.  If an invocation is in progress, inspect
        # precisely its remaining frozen window rather than opening a new one.
        dry_state = read_checkpoint(checkpoint)
        if dry_state and (dry_state.get("format") != ONLY_NEW_STATE_FORMAT or dry_state.get("fingerprint") != fingerprint or not only_new_settings_match(dry_state, schema, table, id_field, change_field, page_key, watermark_field, args.trust_unique_non_null)):
            raise RuntimeError("checkpoint belongs to different incremental settings; use --restart after review")
        with psycopg.connect(**pg_settings()) as connection:
            source_columns, _destination_columns = target_columns(connection, schema, table, id_field)
            bootstrap_lower = staging_max_change(connection, schema, table, change_field)
        lower = bootstrap_lower if not dry_state or dry_state.get("completed_watermark") is None else decode_value(dry_state["completed_watermark"])
        require_only_new_source_shape(oracledb, query, source_columns, page_key, watermark_field)
        active = bool(dry_state and dry_state.get("phase") == "delta")
        upper = decode_tuple(dry_state.get("window_upper")) if active else oracle_delta_upper(oracledb, query, watermark_field, page_key, lower)
        cursor: tuple[Any, ...] | None = decode_tuple(dry_state.get("delta_cursor")) if active else None
        if upper is not None:
            require_delta_invariants(oracledb, query, id_field, watermark_field, page_key, lower, upper)
        total = 0 if upper is None else oracle_delta_count(oracledb, query, watermark_field, page_key, lower, upper, cursor)
        inserted = updated = unchanged = 0
        conflicts: list[tuple[Any, Any, Any]] = []
        insert_examples: list[tuple[Any, Any]] = []
        update_examples: list[tuple[Any, Any]] = []
        while upper is not None:
            changes, cursor = source_delta_change_page(oracledb, query, id_field, change_field, watermark_field, page_key, lower, upper, cursor, args.page_size)
            if not changes:
                break
            with psycopg.connect(**pg_settings()) as connection:
                staging = staging_changes_for_keys(connection, schema, table, id_field, change_field, list(changes))
            _delete, page_inserts, page_unchanged, page_updates, page_conflicts = make_plan(changes, staging, change_field, False)
            inserted += len(page_inserts)
            updated += len(page_updates)
            unchanged += len(page_unchanged)
            conflicts.extend(page_conflicts)
            insert_examples.extend((identifier, changes[identifier]) for identifier in page_inserts[: max(0, args.preview_limit - len(insert_examples))])
            update_examples.extend((identifier, changes[identifier]) for identifier in page_updates[: max(0, args.preview_limit - len(update_examples))])
        print(json.dumps({"mode": "dry-run", "only_new": True, "active_window": active, "schema": schema, "table": table, "completed_watermark": lower, "window_upper": upper, "source_rows": total, "insert_into_staging": inserted, "update_in_staging": updated, "unchanged": unchanged, "delete_from_staging": 0, "staging_newer_conflicts": len(conflicts)}, default=str))
        if args.preview_limit:
            preview("INSERT", insert_examples, [id_field, change_field], args.preview_limit)
            preview("UPDATE", update_examples, [id_field, change_field], args.preview_limit)
        if conflicts:
            preview_conflicts(conflicts, id_field, change_field, args.preview_limit)
            raise RuntimeError("staging has rows with a newer change field; no changes were made")
        return 0
    with file_lock(lock_path), staging_advisory_lock(psycopg, schema, table) as heartbeat:
        state = read_checkpoint(checkpoint)
        if state and (state.get("format") != ONLY_NEW_STATE_FORMAT or state.get("fingerprint") != fingerprint or not only_new_settings_match(state, schema, table, id_field, change_field, page_key, watermark_field, args.trust_unique_non_null)):
            raise RuntimeError("checkpoint belongs to different incremental settings; use --restart after review")
        if state and state.get("phase") == "conflict":
            raise RuntimeError("only-new sync is in terminal conflict state; resolve staging rows and use --restart (completed watermark is retained)")
        with psycopg.connect(**pg_settings()) as connection:
            source_columns, destination_columns = target_columns(connection, schema, table, id_field)
            require_unique_key(connection, schema, table, id_field, args.trust_unique_non_null, require_not_null=False)
            if change_field not in source_columns:
                raise RuntimeError(f"integration/staging table must contain {change_field}")
            staging_hwm = staging_max_change(connection, schema, table, change_field)
        require_only_new_source_shape(oracledb, query, source_columns, page_key, watermark_field)
        if not state:
            state = initialise_only_new_state(checkpoint, query, schema, table, id_field, change_field, page_key, watermark_field, fingerprint, args.trust_unique_non_null, args, staging_hwm)
        elif args.auto_page_size or state.get("auto_page_size"):
            args.auto_page_size = True
            state["auto_page_size"] = True
            sizes = state.setdefault("effective_page_sizes", {})
            sizes["data"] = min(int(sizes.get("data", learned_page_size(data_profile) or args.page_size)), args.page_size)
        if state.get("status") == "paused_performance_degraded":
            state["status"] = "running"
            for metrics in state.setdefault("timing", {}).values():
                if isinstance(metrics, dict):
                    metrics["full_page_seconds_per_row"] = []
            atomic_json_write(checkpoint, state)
        # A completed run is not terminal: freeze the next window while
        # retaining the last completed timestamp.  The lower bound is
        # deliberately inclusive so same-timestamp source rows are replayed.
        if state.get("phase") == "complete":
            lower = None if state.get("completed_watermark") is None else decode_value(state["completed_watermark"])
            upper = oracle_delta_upper(oracledb, query, watermark_field, page_key, lower)
            if upper is None:
                print(f"only-new complete: no source rows at or above watermark {lower!r}")
                return 0
            source_key_count = oracle_delta_count(oracledb, query, watermark_field, page_key, lower, upper)
            state.update(phase="delta", status="running", window_upper=encode_tuple(upper), delta_cursor=None,
                         delta_rows=0, inserted=0, updated=0, unchanged=0, pages=0, rows=0,
                         phase_pages={"delta": 0}, timing={}, source_key_count=source_key_count)
            atomic_json_write(checkpoint, state)
            print(f"only-new opened window through {upper[0]!r}; completed watermark remains {lower!r}")
        if state.get("phase") != "delta":
            raise RuntimeError(f"unknown incremental checkpoint phase: {state.get('phase')}")
        lower = None if state.get("completed_watermark") is None else decode_value(state["completed_watermark"])
        upper = decode_tuple(state.get("window_upper"))
        cursor = decode_tuple(state.get("delta_cursor"))
        if upper is None:
            raise RuntimeError("incremental checkpoint has no frozen upper watermark; use --restart")
        require_delta_invariants(oracledb, query, id_field, watermark_field, page_key, lower, upper)
        invocation_start_pages = int(state.get("pages", 0))
        while True:
            heartbeat()
            if _SIGINT_COUNT:
                print("stopped after the last committed incremental page; rerun the identical command to resume")
                return 130
            if args.max_pages and int(state["pages"]) - invocation_start_pages >= args.max_pages:
                print("stopped at --max-pages; rerun with --only-new --resumable --apply to continue")
                return 0
            (source, _cursors, next_cursor), used_size, fetch_elapsed, wall_fetch_elapsed = adaptive_source_page(
                args, state, data_profile, schema, table, "delta", "data",
                lambda size, retry_transient: source_delta_full_page(oracledb, query, id_field, source_columns, watermark_field, page_key, lower, upper, cursor, size, retry_transient),
            )
            started = time.perf_counter()
            if not source:
                # Only now is the high-water mark durable.  A restart while a
                # window is active discards its cursor, never this completed HWM.
                state.update(phase="complete", status="complete", completed_watermark=encode_value(upper[0]), delta_cursor=None, window_upper=None,
                             completed_at=datetime.now().astimezone().isoformat())
                atomic_json_write(checkpoint, state)
                print(f"only-new complete: inserted={state['inserted']}, updated={state['updated']}, unchanged={state['unchanged']}; watermark advanced to {upper[0]!r}")
                return 0
            changes = {identifier: source[identifier][source_columns.index(change_field)] for identifier in source}
            with psycopg.connect(**pg_settings()) as connection:
                with connection.transaction():
                    staging = staging_changes_for_keys(connection, schema, table, id_field, change_field, list(source))
                    _delete, inserts, unchanged, updates, conflicts = make_plan(changes, staging, change_field, False)
                    if conflicts:
                        state.update(phase="conflict", status="staging_newer_conflict", conflicts=len(conflicts), conflict_sample={id_field: conflicts[0][0], f"kn_{change_field}": str(conflicts[0][1]), f"staging_{change_field}": str(conflicts[0][2])})
                        atomic_json_write(checkpoint, state)
                        raise RuntimeError("staging became newer during only-new sync; transaction rolled back; use --restart after resolving it")
                    insert_sql = insert_statement(schema, table, source_columns, destination_columns)
                    update_columns = [column for column in source_columns if column != id_field]
                    updated_at_clause = ', "updated_at" = CURRENT_TIMESTAMP' if "updated_at" in destination_columns else ""
                    update_sql = f'UPDATE {relation_sql(schema, table)} SET {", ".join(f"\"{column}\" = %s" for column in update_columns)}{updated_at_clause} WHERE "{id_field}" = %s'
                    with connection.cursor() as db_cursor:
                        db_cursor.executemany(insert_sql, (source[identifier] for identifier in inserts))
                        values = ((*[source[identifier][source_columns.index(column)] for column in update_columns], identifier) for identifier in updates)
                        db_cursor.executemany(update_sql, values)
            cursor = next_cursor
            state["delta_cursor"] = encode_tuple(cursor) if cursor else None
            state["pages"] = int(state["pages"]) + 1
            state["rows"] = int(state["rows"]) + len(source)
            state["delta_rows"] = int(state.get("delta_rows", 0)) + len(source)
            state["inserted"] = int(state.get("inserted", 0)) + len(inserts)
            state["updated"] = int(state.get("updated", 0)) + len(updates)
            state["unchanged"] = int(state.get("unchanged", 0)) + len(unchanged)
            page = phase_page_number(state, "delta")
            processing = time.perf_counter() - started
            rate, eta, slow = record_page_timing(state, "delta", len(source), used_size, wall_fetch_elapsed + processing, fetch_elapsed + processing)
            atomic_json_write(checkpoint, state)
            if args.auto_page_size:
                remember_page_size(data_profile, used_size, schema, table)
            print(f"only-new committed page {page} ({len(source)} rows; total {state['delta_rows']}/{state['source_key_count']}; inserted {len(inserts)}, updated {len(updates)}, unchanged {len(unchanged)}; page size {used_size}; {rate:,.0f} rows/s; elapsed {format_duration(state['timing']['delta']['elapsed_seconds'])}{'; ' + eta if eta else ''})")
            if slow:
                state["status"] = "paused_performance_degraded"
                atomic_json_write(checkpoint, state)
                print(f"stopped safely after checkpoint: {slow}", file=sys.stderr)
                return 3


def run_resumable(args: argparse.Namespace, query: str, schema: str, table: str, id_field: str, change_field: str, page_key: tuple[str, ...], oracledb: Any, psycopg: Any) -> int:
    fingerprint = sync_fingerprint(query, schema, table, id_field, change_field, args.ignore_change_field, page_key, args.trust_unique_non_null)
    key_profile_key = auto_page_size_profile_key(query, schema, table, id_field, page_key, "keys", args.ignore_change_field)
    data_profile_key = auto_page_size_profile_key(query, schema, table, id_field, page_key, "data", args.ignore_change_field)
    checkpoint, key_path, lock_path = resumable_paths(fingerprint)
    if not args.apply:
        raise RuntimeError("--resumable is only available with --apply; dry-run is already read-only")
    with file_lock(lock_path), staging_advisory_lock(psycopg, schema, table) as heartbeat:
        state = read_checkpoint(checkpoint)
        if state and (state.get("fingerprint") != fingerprint or state.get("format") != STATE_FORMAT):
            raise RuntimeError("checkpoint belongs to a different table, SQL, or sync options; use --restart after review")
        if state:
            expected = {
                "schema": schema, "table": table, "id_field": id_field, "change_field": change_field,
                "ignore_change_field": args.ignore_change_field, "source_page_key": list(page_key),
                "trust_unique_non_null": args.trust_unique_non_null,
            }
            if any(state.get(name) != value for name, value in expected.items()):
                raise RuntimeError("checkpoint settings are inconsistent; use --restart")
        if state and state.get("phase") == "complete":
            print("resumable sync already complete; use --restart only to deliberately replay it")
            return 0
        if state and state.get("phase") in {"conflict", "verification_failed"}:
            raise RuntimeError(f"resumable sync is in terminal state {state.get('status', state['phase'])}; resolve the cause and use --restart")
        with psycopg.connect(**pg_settings()) as connection:
            source_columns, destination_columns = target_columns(connection, schema, table, id_field)
            require_unique_key(connection, schema, table, id_field, args.trust_unique_non_null)
        if not args.ignore_change_field and change_field not in source_columns:
            raise RuntimeError(f"integration/staging table must contain {change_field}, or use --ignore-change-field")
        if not state:
            require_source_invariants(oracledb, query, id_field, page_key, source_columns)
            learned_key_size = learned_page_size(key_profile_key) if args.auto_page_size else None
            learned_data_size = learned_page_size(data_profile_key) if args.auto_page_size else None
            state = {
                "format": STATE_FORMAT, "fingerprint": fingerprint, "schema": schema, "table": table,
                "id_field": id_field, "change_field": change_field, "source_page_key": list(page_key),
                "ignore_change_field": args.ignore_change_field, "trust_unique_non_null": args.trust_unique_non_null,
                "auto_page_size": args.auto_page_size,
                "phase": "preflight", "source_cursor": None,
                "verify_cursor": None, "delete_cursor": None, "pages": 0, "rows": 0, "status": "running",
                "preflight_rows": 0, "applied_rows": 0, "verified_rows": 0, "delete_scanned": 0, "deleted": 0,
                "phase_pages": {"preflight": 0, "apply": 0, "verify": 0, "delete": 0},
                "timing": {},
            }
            if args.auto_page_size:
                state["effective_page_sizes"] = {
                    "keys": min(learned_key_size or args.page_size, args.page_size),
                    "data": min(learned_data_size or args.page_size, args.page_size),
                }
            atomic_json_write(checkpoint, state)
            if learned_key_size or learned_data_size:
                print(f"auto page size: using learned key/data sizes {state['effective_page_sizes']['keys']}/{state['effective_page_sizes']['data']} for {schema}.{table}")
        elif args.auto_page_size or state.get("auto_page_size"):
            # A learned size is deliberately kept outside the restartable
            # checkpoint, then copied in once for a new logical run.
            args.auto_page_size = True
            state["auto_page_size"] = True
            old_size = state.pop("effective_page_size", None)
            sizes = state.setdefault("effective_page_sizes", {})
            sizes["keys"] = min(int(sizes.get("keys", old_size or learned_page_size(key_profile_key) or args.page_size)), args.page_size)
            sizes["data"] = min(int(sizes.get("data", old_size or learned_page_size(data_profile_key) or args.page_size)), args.page_size)
        state.setdefault("phase_pages", {"preflight": 0, "apply": 0, "verify": 0, "delete": 0})
        state.setdefault("timing", {})
        if state.get("status") == "paused_performance_degraded":
            # An explicit rerun acknowledges the warning.  Do not immediately
            # trip again on the same historical samples.
            state["status"] = "running"
            for phase_metrics in state["timing"].values():
                if isinstance(phase_metrics, dict):
                    phase_metrics["full_page_seconds_per_row"] = []
            atomic_json_write(checkpoint, state)
        keys = key_database(key_path)
        try:
            page_count = int(state["pages"])
            invocation_start_pages = page_count
            rows = int(state["rows"])
            phase = state["phase"]
            if phase in {"preflight", "apply"}:
                cursor = decode_tuple(state.get("source_cursor"))
            elif phase == "verify":
                cursor = decode_tuple(state.get("verify_cursor"))
            elif phase == "delete":
                cursor = None if state.get("delete_cursor") is None else decode_value(state["delete_cursor"])
            else:
                cursor = None
            if phase in {"apply", "verify", "delete", "complete"}:
                if not state.get("key_index_complete") or key_count(keys) != state.get("source_key_count"):
                    raise RuntimeError("resumable source-key index is missing or incomplete; use --restart")
            while True:
                heartbeat()
                if _SIGINT_COUNT:
                    print("stopped after the last committed page; rerun the identical command to resume")
                    return 130
                if args.max_pages and page_count - invocation_start_pages >= args.max_pages:
                    print("stopped at --max-pages; rerun with --resumable --apply to continue")
                    return 0
                if phase == "preflight":
                    (kn_changes, page_cursors, next_cursor), used_page_size, successful_fetch_elapsed, logical_fetch_elapsed = adaptive_source_page(
                        args, state, key_profile_key, schema, table, phase, "keys",
                        lambda size, retry_transient: source_change_page(oracledb, query, id_field, None if args.ignore_change_field else change_field, page_key, cursor, size, retry_transient),
                    )
                    page_started = time.perf_counter()
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
                    remember_keys(keys, ((identifier, page_cursors[identifier], None if args.ignore_change_field else comparable_change(kn_changes[identifier])) for identifier in kn_changes))
                    cursor = next_cursor
                    page_count += 1
                    rows += len(kn_changes)
                    state["preflight_rows"] = int(state.get("preflight_rows", 0)) + len(kn_changes)
                    phase_page = phase_page_number(state, phase)
                    processing_elapsed = time.perf_counter() - page_started
                    rate, eta, slow_reason = record_page_timing(state, phase, len(kn_changes), used_page_size, logical_fetch_elapsed + processing_elapsed, successful_fetch_elapsed + processing_elapsed)
                    save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                    if args.auto_page_size:
                        remember_page_size(key_profile_key, used_page_size, schema, table)
                    print(
                        f"preflight committed page {phase_page} ({len(kn_changes)} keys; total {state['preflight_rows']}; "
                        f"page size {used_page_size}; {rate:,.0f} keys/s; elapsed {format_duration(state['timing'][phase]['elapsed_seconds'])})"
                    )
                    if slow_reason:
                        state["status"] = "paused_performance_degraded"
                        atomic_json_write(checkpoint, state)
                        print(f"stopped safely after checkpoint: {slow_reason}", file=sys.stderr)
                        return 3
                    continue
                if phase == "apply":
                    (source, page_cursors, next_cursor), used_page_size, successful_fetch_elapsed, logical_fetch_elapsed = adaptive_source_page(
                        args, state, data_profile_key, schema, table, phase, "data",
                        lambda size, retry_transient: source_full_page(oracledb, query, id_field, source_columns, page_key, cursor, size, retry_transient),
                    )
                    page_started = time.perf_counter()
                    if not source:
                        phase, cursor = "verify", None
                        state["verified_rows"] = 0
                        save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                        continue
                    changes = {identifier: None if args.ignore_change_field else source[identifier][source_columns.index(change_field)] for identifier in source}
                    if any(not known_record(keys, identifier, page_cursors[identifier], None if args.ignore_change_field else comparable_change(changes[identifier])) for identifier in source):
                        state.update(phase="verification_failed", status="source_changed")
                        atomic_json_write(checkpoint, state)
                        raise RuntimeError("KN result changed during resumable sync; use --restart to build a fresh key index")
                    with psycopg.connect(**pg_settings()) as connection:
                        with connection.transaction():
                            stag_changes = staging_changes_for_keys(connection, schema, table, id_field, None if args.ignore_change_field else change_field, list(source))
                            _delete, insert_ids, _unchanged, update_ids, conflicts = make_plan(changes, stag_changes, change_field, args.ignore_change_field)
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
                    state["applied_rows"] = int(state.get("applied_rows", 0)) + len(source)
                    phase_page = phase_page_number(state, phase)
                    processing_elapsed = time.perf_counter() - page_started
                    rate, eta, slow_reason = record_page_timing(state, phase, len(source), used_page_size, logical_fetch_elapsed + processing_elapsed, successful_fetch_elapsed + processing_elapsed)
                    save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                    if args.auto_page_size:
                        remember_page_size(data_profile_key, used_page_size, schema, table)
                    print(
                        f"apply committed page {phase_page} ({len(source)} rows; total {state['applied_rows']}; "
                        f"page size {used_page_size}; {rate:,.0f} rows/s; elapsed {format_duration(state['timing'][phase]['elapsed_seconds'])}"
                        f"{'; ' + eta if eta else ''})"
                    )
                    if slow_reason:
                        state["status"] = "paused_performance_degraded"
                        atomic_json_write(checkpoint, state)
                        print(f"stopped safely after checkpoint: {slow_reason}", file=sys.stderr)
                        return 3
                    continue
                if phase == "verify":
                    (kn_changes, page_cursors, next_cursor), used_page_size, successful_fetch_elapsed, logical_fetch_elapsed = adaptive_source_page(
                        args, state, key_profile_key, schema, table, phase, "keys",
                        lambda size, retry_transient: source_change_page(oracledb, query, id_field, None if args.ignore_change_field else change_field, page_key, cursor, size, retry_transient),
                    )
                    page_started = time.perf_counter()
                    if not kn_changes:
                        if int(state.get("verified_rows", 0)) != key_count(keys):
                            state.update(phase="verification_failed", status="source_changed")
                            atomic_json_write(checkpoint, state)
                            raise RuntimeError("KN result changed during final verification; no deletes were made; use --restart")
                        phase, cursor = "delete", None
                        save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                        continue
                    if any(not known_record(keys, identifier, page_cursors[identifier], None if args.ignore_change_field else comparable_change(kn_changes[identifier])) for identifier in kn_changes):
                        state.update(phase="verification_failed", status="source_changed")
                        atomic_json_write(checkpoint, state)
                        raise RuntimeError("KN result changed during final verification; no deletes were made; use --restart")
                    cursor = next_cursor
                    page_count += 1
                    rows += len(kn_changes)
                    state["verified_rows"] = int(state.get("verified_rows", 0)) + len(kn_changes)
                    phase_page = phase_page_number(state, phase)
                    processing_elapsed = time.perf_counter() - page_started
                    rate, eta, slow_reason = record_page_timing(state, phase, len(kn_changes), used_page_size, logical_fetch_elapsed + processing_elapsed, successful_fetch_elapsed + processing_elapsed)
                    save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                    if args.auto_page_size:
                        remember_page_size(key_profile_key, used_page_size, schema, table)
                    print(
                        f"verify committed page {phase_page} ({len(kn_changes)} rows; total {state['verified_rows']}; "
                        f"page size {used_page_size}; {rate:,.0f} rows/s; elapsed {format_duration(state['timing'][phase]['elapsed_seconds'])}"
                        f"{'; ' + eta if eta else ''})"
                    )
                    if slow_reason:
                        state["status"] = "paused_performance_degraded"
                        atomic_json_write(checkpoint, state)
                        print(f"stopped safely after checkpoint: {slow_reason}", file=sys.stderr)
                        return 3
                    continue
                if phase == "delete":
                    page_started = time.perf_counter()
                    used_page_size = args.page_size
                    with psycopg.connect(**pg_settings()) as connection:
                        identifiers = staging_key_page(connection, schema, table, id_field, cursor, used_page_size)
                        if not identifiers:
                            state.update(phase="complete", status="complete", completed_at=datetime.now().astimezone().isoformat())
                            atomic_json_write(checkpoint, state)
                            print(
                                "complete: "
                                f"preflight={state.get('preflight_rows', 0)}, "
                                f"apply={state.get('applied_rows', 0)}, "
                                f"verify={state.get('verified_rows', 0)}, "
                                f"staging_scanned={state.get('delete_scanned', 0)}, "
                                f"deleted={state.get('deleted', 0)} rows in {state['pages']} pages"
                            )
                            return 0
                        delete_ids = [identifier for identifier in identifiers if not known_key(keys, identifier)]
                        with connection.transaction():
                            if delete_ids:
                                with connection.cursor() as db_cursor:
                                    db_cursor.execute(f'DELETE FROM {relation_sql(schema, table)} WHERE "{id_field}" = ANY(%s)', (delete_ids,))
                    cursor = identifiers[-1]
                    page_count += 1
                    rows += len(identifiers)
                    state["delete_scanned"] = int(state.get("delete_scanned", 0)) + len(identifiers)
                    state["deleted"] = int(state.get("deleted", 0)) + len(delete_ids)
                    phase_page = phase_page_number(state, phase)
                    elapsed = time.perf_counter() - page_started
                    rate, _eta, slow_reason = record_page_timing(state, phase, len(identifiers), used_page_size, elapsed, elapsed)
                    save_state(checkpoint, state, phase=phase, cursor=cursor, page_count=page_count, rows=rows)
                    print(
                        f"delete committed page {phase_page} ({len(delete_ids)} deleted; scanned {len(identifiers)}; "
                        f"page size {used_page_size}; {rate:,.0f} rows/s; elapsed {format_duration(state['timing'][phase]['elapsed_seconds'])})"
                    )
                    if slow_reason:
                        state["status"] = "paused_performance_degraded"
                        atomic_json_write(checkpoint, state)
                        print(f"stopped safely after checkpoint: {slow_reason}", file=sys.stderr)
                        return 3
                    continue
                raise RuntimeError(f"unknown resumable checkpoint phase: {phase}")
        finally:
            keys.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="staging table name, without schema")
    parser.add_argument("--integration-sql", required=True, type=Path, help="path to the KN SELECT statement")
    parser.add_argument("--id-field", required=True, help="unique source/staging membership key (LIFT system id is not valid)")
    parser.add_argument("--schema", default=None, help="defaults to STAG_SCHEMA or public")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only (the default)")
    mode.add_argument("--apply", action="store_true", help="perform deletes, inserts, and KN-newer updates")
    parser.add_argument("--change-field", default="date_change", help="field used to compare matching keys (default: DATE_CHANGE)")
    parser.add_argument("--ignore-change-field", action="store_true", help="use only key membership: delete absent staging keys and insert absent KN keys, but do not update or compare matching keys")
    parser.add_argument("--only-new", action="store_true", help="incremental insert/update-only mode, bounded by a persisted source change watermark; never deletes")
    parser.add_argument("--resumable", action="store_true", help="use local checkpointing and page-by-page commits (requires --apply)")
    parser.add_argument("--source-page-key", help="comma-separated native KN columns, in index order; required with --resumable")
    parser.add_argument("--source-watermark-field", help="native Oracle-comparable change timestamp alias; required with --only-new")
    parser.add_argument("--trust-unique-non-null", action="store_true", help="skip staging UNIQUE/NOT NULL metadata checks in resumable mode; use only when the data is known to satisfy both")
    parser.add_argument("--status", action="store_true", help="show the resumable checkpoint and exit")
    parser.add_argument("--restart", action="store_true", help="remove only this integration's resumable checkpoint and key index")
    parser.add_argument("--preview-limit", type=int, default=5, help="maximum example rows shown for each action (default: 5)")
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--page-size", type=int, default=50_000, help="initial rows per resumable page (default: 50000)")
    parser.add_argument("--page-size-cap", type=int, default=50_000, help="maximum rows per resumable page, including learned auto sizes (default: 50000)")
    parser.add_argument("--auto-page-size", action="store_true", help="on retryable Oracle page-read failure, reduce page size by 3x and persist the successful size for this integration")
    parser.add_argument("--max-pages", type=int, help="stop cleanly after this many resumable pages")
    args = parser.parse_args()
    if args.preview_limit < 0 or args.batch_size <= 0 or args.page_size <= 0 or args.page_size_cap <= 0:
        parser.error("--preview-limit must be non-negative and --batch-size/--page-size/--page-size-cap must be positive")
    # Store the effective value in one place so fixed-size delete pages and
    # learned auto sizes never exceed the operator's explicit cap.
    args.page_size = min(args.page_size, args.page_size_cap)
    if (args.status or args.restart) and not args.resumable:
        parser.error("--status and --restart require --resumable")
    if args.resumable and not args.source_page_key:
        parser.error("--resumable requires --source-page-key")
    if args.trust_unique_non_null and not args.resumable:
        parser.error("--trust-unique-non-null requires --resumable")
    if args.auto_page_size and not args.resumable:
        parser.error("--auto-page-size requires --resumable")
    if args.only_new and args.ignore_change_field:
        parser.error("--only-new cannot be combined with --ignore-change-field")
    if args.only_new and not args.source_page_key:
        parser.error("--only-new requires --source-page-key")
    if args.only_new and not args.source_watermark_field:
        parser.error("--only-new requires --source-watermark-field")
    if args.only_new and args.apply and not args.resumable:
        parser.error("--only-new --apply requires --resumable")
    if args.only_new and (args.status or args.restart) and not args.resumable:
        parser.error("--only-new --status/--restart require --resumable")
    return args


def main() -> int:
    args = parse_args()
    install_sigint_handler()
    try:
        table = valid_identifier(args.table, "table")
        id_field = valid_identifier(args.id_field, "id field").lower()
        change_field = valid_identifier(args.change_field, "change field").lower()
        page_key = source_page_key(args.source_page_key) if (args.resumable or args.only_new) else ()
        watermark_field = source_watermark_field(args.source_watermark_field) if args.only_new else None
        if watermark_field and watermark_field in page_key:
            raise ValueError("--source-watermark-field must not also appear in --source-page-key")
        load_environment()
        schema = valid_identifier(args.schema or os.environ.get("STAG_SCHEMA", "public"), "schema")
        query = read_select(args.integration_sql)
        if args.resumable and (args.status or args.restart):
            fingerprint = (delta_fingerprint_args(query, schema, table, id_field, change_field, page_key, watermark_field, args.trust_unique_non_null)
                           if args.only_new else sync_fingerprint(query, schema, table, id_field, change_field, args.ignore_change_field, page_key, args.trust_unique_non_null))
            checkpoint, key_path, lock_path = resumable_paths(fingerprint)
            if args.status:
                print(json.dumps(read_checkpoint(checkpoint) or {"status": "not started"}, indent=2, default=str))
                return 0
            with file_lock(lock_path):
                if args.only_new:
                    state = read_checkpoint(checkpoint)
                    if state and state.get("phase") != "complete":
                        state.update(phase="complete", status="complete", window_upper=None, delta_cursor=None,
                                     pages=0, rows=0, delta_rows=0, inserted=0, updated=0, unchanged=0,
                                     phase_pages={"delta": 0}, timing={})
                        atomic_json_write(checkpoint, state)
                    print("discarded the active only-new window; the completed watermark was kept")
                else:
                    for path in (checkpoint, key_path, Path(f"{key_path}-wal"), Path(f"{key_path}-shm")):
                        if path.exists():
                            path.unlink()
                    print("removed this integration's resumable checkpoint and source-key index")
            return 0
        oracledb, psycopg = require_drivers()
        enable_oracle_thick_mode(oracledb)
        if args.only_new:
            assert watermark_field is not None
            return run_only_new(args, query, schema, table, id_field, change_field, page_key, watermark_field, oracledb, psycopg)
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
    except KeyboardInterrupt:
        print("interrupted; committed pages are checkpointed and can be resumed", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
