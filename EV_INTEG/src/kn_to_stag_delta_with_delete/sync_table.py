#!/usr/bin/env python3
"""Synchronise ID membership from a KN Oracle SELECT into a staging PG table.

The SQL file must contain one SELECT (or WITH ... SELECT) and must alias its
output columns to the destination PostgreSQL column names. The membership key
defaults to `id`, but can be selected with --id-field.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
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


def make_plan(source: dict[Any, tuple[Any, ...]], source_columns: list[str], stag_changes: dict[Any, Any], change_field: str, insert_only: bool) -> tuple[list[Any], list[Any], list[Any], list[Any], list[tuple[Any, Any, Any]]]:
    source_ids = set(source)
    stag_ids = set(stag_changes)
    delete_ids = [] if insert_only else ordered(stag_ids - source_ids)
    insert_ids = ordered(source_ids - stag_ids)
    unchanged_ids: list[Any] = []
    update_ids: list[Any] = []
    conflicts: list[tuple[Any, Any, Any]] = []
    change_position = source_columns.index(change_field) if not insert_only else None
    for identifier in source_ids & stag_ids:
        if insert_only:
            unchanged_ids.append(identifier)
            continue
        source_change = source[identifier][change_position]
        stag_change = stag_changes[identifier]
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
                raise RuntimeError(f"cannot compare {change_field} for key {identifier!r}") from error
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
    parser.add_argument("--insert-only", action="store_true", help="only insert absent keys; do not delete, update, or compare existing keys")
    parser.add_argument("--preview-limit", type=int, default=5, help="maximum example rows shown for each action (default: 5)")
    parser.add_argument("--batch-size", type=int, default=1_000)
    args = parser.parse_args()
    if args.preview_limit < 0 or args.batch_size <= 0:
        parser.error("--preview-limit must be non-negative and --batch-size must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        table = valid_identifier(args.table, "table")
        id_field = valid_identifier(args.id_field, "id field").lower()
        change_field = valid_identifier(args.change_field, "change field").lower()
        load_environment()
        schema = valid_identifier(args.schema or os.environ.get("STAG_SCHEMA", "public"), "schema")
        query = read_select(args.integration_sql)
        oracledb, psycopg = require_drivers()
        enable_oracle_thick_mode(oracledb)
        with oracledb.connect(**oracle_settings(oracledb)) as kn, psycopg.connect(**pg_settings()) as stag:
            source_columns, destination_columns = target_columns(stag, schema, table, id_field)
            if not args.insert_only and change_field not in source_columns:
                raise RuntimeError(f"integration/staging table must contain {change_field}, or use --insert-only")
            source = source_rows(kn, query, source_columns, id_field)
            relation = relation_sql(schema, table)
            column_sql = ", ".join(f'"{column}"' for column in source_columns)
            insert_sql = f"INSERT INTO {relation} ({column_sql}) VALUES ({', '.join('%s' for _ in source_columns)})"

            def report_and_preview(stag_changes: dict[Any, Any]) -> tuple[list[Any], list[Any], list[Any], list[Any], list[tuple[Any, Any, Any]]]:
                plan = make_plan(source, source_columns, stag_changes, change_field, args.insert_only)
                delete_ids, insert_ids, unchanged_ids, update_ids, conflicts = plan
                print(json.dumps({"mode": "apply" if args.apply else "dry-run", "schema": schema, "table": table, "id_field": id_field, "change_field": change_field, "insert_only": args.insert_only, "kn_keys": len(source), "staging_keys": len(stag_changes), "unchanged": len(unchanged_ids), "delete_from_staging": len(delete_ids), "insert_into_staging": len(insert_ids), "update_in_staging": len(update_ids), "staging_newer_conflicts": len(conflicts)}))
                if args.preview_limit:
                    preview("DELETE", staging_rows(stag, schema, table, destination_columns, id_field, delete_ids, args.batch_size), destination_columns, args.preview_limit)
                    preview("INSERT", (source[identifier] for identifier in insert_ids), source_columns, args.preview_limit)
                    preview("UPDATE", (source[identifier] for identifier in update_ids), source_columns, args.preview_limit)
                    if conflicts:
                        preview_conflicts(conflicts, id_field, change_field, args.preview_limit)
                return plan

            if not args.apply:
                plan = report_and_preview(staging_changes(stag, schema, table, id_field, None if args.insert_only else change_field))
                if plan[-1]:
                    raise RuntimeError("staging has rows with a newer change field; no changes were made")
                return 0

            update_columns = [column for column in source_columns if column != id_field]
            updated_at_clause = ', "updated_at" = CURRENT_TIMESTAMP' if "updated_at" in destination_columns else ""
            update_sql = f'UPDATE {relation} SET {", ".join(f"\"{column}\" = %s" for column in update_columns)}{updated_at_clause} WHERE "{id_field}" = %s'
            with stag.transaction():
                with stag.cursor() as cursor:
                    cursor.execute(f"LOCK TABLE {relation} IN SHARE ROW EXCLUSIVE MODE")
                delete_ids, insert_ids, _unchanged_ids, update_ids, conflicts = report_and_preview(staging_changes(stag, schema, table, id_field, None if args.insert_only else change_field))
                if conflicts:
                    raise RuntimeError("staging has rows with a newer change field; transaction rolled back without changes")
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
