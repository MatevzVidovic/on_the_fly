#!/usr/bin/env python3
"""Synchronise a staging PostgreSQL table to production using id and DATE_CHANGE."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
HERE = Path(__file__).resolve().parent


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


def require_psycopg() -> Any:
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("install requirements into .venv before running this script") from error
    return psycopg


def connection_settings(prefix: str) -> dict[str, str | int]:
    required = ("USER", "PASSWORD", "HOST", "PORT")
    missing = [f"{prefix}_{field}" for field in required if not os.environ.get(f"{prefix}_{field}")]
    if missing:
        raise RuntimeError(f"missing PostgreSQL environment variables: {', '.join(missing)}")
    return {
        "user": os.environ[f"{prefix}_USER"],
        "password": os.environ[f"{prefix}_PASSWORD"],
        "host": os.environ[f"{prefix}_HOST"],
        "port": int(os.environ[f"{prefix}_PORT"]),
        "dbname": os.environ.get(f"{prefix}_DATABASE", "fmp_data_gurs"),
    }


def relation_sql(schema: str, table: str) -> str:
    # Identifiers were checked above, then quoted so mixed-case names remain safe.
    return f'"{schema}"."{table}"'


def table_columns(connection: Any, schema: str, table: str) -> list[str]:
    """Return source columns that production accepts in INSERT statements."""
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
        return [row[0] for row in cursor.fetchall()]


def verify_tables(stag: Any, prod: Any, schema: str, table: str, id_field: str, change_field: str) -> list[str]:
    stag_columns = table_columns(stag, schema, table)
    prod_columns = table_columns(prod, schema, table)
    if not stag_columns:
        raise RuntimeError(f"staging table {schema}.{table} was not found or has no insertable columns")
    if not prod_columns:
        raise RuntimeError(f"production table {schema}.{table} was not found or has no insertable columns")
    if id_field not in stag_columns or id_field not in prod_columns:
        raise RuntimeError(f"both {schema}.{table} tables must have the key field {id_field}")
    if change_field not in stag_columns or change_field not in prod_columns:
        raise RuntimeError(f"both {schema}.{table} tables must have the change field {change_field}")
    # Staging and production can have the same fields in a different physical
    # order.  All copy statements name columns explicitly, so order is safe.
    if set(stag_columns) != set(prod_columns):
        only_stag = sorted(set(stag_columns) - set(prod_columns))
        only_prod = sorted(set(prod_columns) - set(stag_columns))
        raise RuntimeError(
            f"table columns differ for {schema}.{table}; only in staging: {only_stag or '-'}; "
            f"only in production: {only_prod or '-'}"
        )
    # Keep source reads in staging order; destination INSERT/UPDATE statements
    # explicitly name this same column sequence.
    return stag_columns


def id_changes(connection: Any, schema: str, table: str, id_field: str, change_field: str) -> dict[Any, Any]:
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT "{id_field}", "{change_field}" FROM {relation_sql(schema, table)}')
        result: dict[Any, Any] = {}
        for identifier, changed_at in cursor.fetchall():
            if identifier is None:
                raise RuntimeError(f"{schema}.{table} contains a NULL {id_field}")
            if identifier in result:
                raise RuntimeError(f"{schema}.{table} contains a duplicate {id_field}: {identifier!r}")
            result[identifier] = changed_at
        return result


def ordered(values: Iterable[Any]) -> list[Any]:
    """Stable display/order without assuming a particular PostgreSQL id type."""
    return sorted(values, key=lambda value: (type(value).__name__, repr(value)))


def make_plan(stag_changes: dict[Any, Any], prod_changes: dict[Any, Any]) -> tuple[list[Any], list[Any], list[Any], list[Any], list[tuple[Any, Any, Any]]]:
    delete_ids = ordered(prod_changes.keys() - stag_changes.keys())
    insert_ids = ordered(stag_changes.keys() - prod_changes.keys())
    unchanged_ids: list[Any] = []
    update_ids: list[Any] = []
    conflicts: list[tuple[Any, Any, Any]] = []
    for identifier in stag_changes.keys() & prod_changes.keys():
        stag_change = stag_changes[identifier]
        prod_change = prod_changes[identifier]
        if stag_change == prod_change:
            unchanged_ids.append(identifier)
        elif stag_change is None or prod_change is None:
            conflicts.append((identifier, stag_change, prod_change))
        else:
            try:
                if prod_change < stag_change:
                    update_ids.append(identifier)
                else:
                    conflicts.append((identifier, stag_change, prod_change))
            except TypeError as error:
                raise RuntimeError(
                    f"cannot compare change field for id {identifier!r}: "
                    f"staging={stag_change!r}, production={prod_change!r}"
                ) from error
    return delete_ids, insert_ids, ordered(unchanged_ids), ordered(update_ids), sorted(conflicts, key=lambda item: (type(item[0]).__name__, repr(item[0])))


def chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def rows_for_ids(connection: Any, schema: str, table: str, columns: list[str], id_field: str, wanted_ids: list[Any], batch_size: int) -> Iterable[tuple[Any, ...]]:
    projection = ", ".join(f'"{column}"' for column in columns)
    relation = relation_sql(schema, table)
    for batch in chunks(wanted_ids, batch_size):
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT {projection} FROM {relation} WHERE "{id_field}" = ANY(%s) ORDER BY "{id_field}"', (batch,))
            yield from cursor.fetchall()


def print_preview(label: str, rows: Iterable[tuple[Any, ...]], columns: list[str], limit: int) -> None:
    print(f"{label} rows (showing up to {limit}):")
    shown = 0
    for row in rows:
        if shown >= limit:
            break
        print(json.dumps(dict(zip(columns, row, strict=True)), default=str, ensure_ascii=False))
        shown += 1
    if shown == 0:
        print("(none)")


def print_conflicts(conflicts: list[tuple[Any, Any, Any]], change_field: str, limit: int) -> None:
    print(f"CONFLICT rows (production {change_field} is newer or cannot be compared; showing up to {limit}):")
    for identifier, stag_change, prod_change in conflicts[:limit]:
        print(json.dumps({"id": identifier, f"staging_{change_field}": stag_change, f"production_{change_field}": prod_change}, default=str, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="table name, without schema")
    parser.add_argument("--schema", default=None, help="schema; defaults to SYNC_SCHEMA or public")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only (the default)")
    mode.add_argument("--apply", action="store_true", help="perform the deletes, inserts, and staging-newer updates")
    parser.add_argument("--id-field", default="id", help="unique membership key in both systems (default: id)")
    parser.add_argument("--change-field", default="date_change", help="field used to compare matching IDs (default: DATE_CHANGE)")
    parser.add_argument("--preview-limit", type=int, default=5, help="maximum example rows shown for each action (default: 5)")
    parser.add_argument("--batch-size", type=int, default=1_000, help="IDs processed per SQL statement (default: 1000)")
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
        schema = valid_identifier(args.schema or os.environ.get("SYNC_SCHEMA", "public"), "schema")
        psycopg = require_psycopg()
        with psycopg.connect(**connection_settings("STAG")) as stag, psycopg.connect(**connection_settings("PROD")) as prod:
            columns = verify_tables(stag, prod, schema, table, id_field, change_field)
            stag_changes = id_changes(stag, schema, table, id_field, change_field)
            relation = relation_sql(schema, table)
            placeholders = ", ".join("%s" for _ in columns)
            column_sql = ", ".join(f'"{column}"' for column in columns)
            insert_sql = f"INSERT INTO {relation} ({column_sql}) VALUES ({placeholders})"
            update_columns = [column for column in columns if column != id_field]
            update_sql = f'UPDATE {relation} SET {", ".join(f"\"{column}\" = %s" for column in update_columns)} WHERE "{id_field}" = %s'

            def report_and_preview(prod_changes: dict[Any, Any]) -> tuple[list[Any], list[Any], list[Any], list[Any], list[tuple[Any, Any, Any]]]:
                plan = make_plan(stag_changes, prod_changes)
                delete_ids, insert_ids, unchanged_ids, update_ids, conflicts = plan
                print(json.dumps({"mode": "apply" if args.apply else "dry-run", "schema": schema, "table": table, "id_field": id_field, "change_field": change_field, "staging_ids": len(stag_changes), "production_ids": len(prod_changes), "unchanged": len(unchanged_ids), "delete_from_production": len(delete_ids), "insert_into_production": len(insert_ids), "update_in_production": len(update_ids), "production_newer_conflicts": len(conflicts)}))
                if args.preview_limit:
                    print_preview("DELETE", rows_for_ids(prod, schema, table, columns, id_field, delete_ids, args.batch_size), columns, args.preview_limit)
                    print_preview("INSERT", rows_for_ids(stag, schema, table, columns, id_field, insert_ids, args.batch_size), columns, args.preview_limit)
                    print_preview("UPDATE", rows_for_ids(stag, schema, table, columns, id_field, update_ids, args.batch_size), columns, args.preview_limit)
                    if conflicts:
                        print_conflicts(conflicts, change_field, args.preview_limit)
                return plan

            if not args.apply:
                plan = report_and_preview(id_changes(prod, schema, table, id_field, change_field))
                if plan[-1]:
                    raise RuntimeError("production has rows with a newer change field; no changes were made")
                return 0

            # The lock and second production read make the conflict check authoritative for this apply run.
            with prod.transaction():
                with prod.cursor() as cursor:
                    cursor.execute(f"LOCK TABLE {relation} IN SHARE ROW EXCLUSIVE MODE")
                delete_ids, insert_ids, _unchanged_ids, update_ids, conflicts = report_and_preview(id_changes(prod, schema, table, id_field, change_field))
                if conflicts:
                    raise RuntimeError("production has rows with a newer change field; transaction rolled back without changes")
                with prod.cursor() as cursor:
                    for batch in chunks(delete_ids, args.batch_size):
                        cursor.execute(f'DELETE FROM {relation} WHERE "{id_field}" = ANY(%s)', (batch,))
                    for batch in chunks(insert_ids, args.batch_size):
                        source_rows = list(rows_for_ids(stag, schema, table, columns, id_field, batch, args.batch_size))
                        cursor.executemany(insert_sql, source_rows)
                    for batch in chunks(update_ids, args.batch_size):
                        source_rows = rows_for_ids(stag, schema, table, columns, id_field, batch, args.batch_size)
                        values = ((*[row[columns.index(column)] for column in update_columns], row[columns.index(id_field)]) for row in source_rows)
                        cursor.executemany(update_sql, values)
            print(f"applied: deleted {len(delete_ids)} rows; inserted {len(insert_ids)} rows; updated {len(update_ids)} rows")
            return 0
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
