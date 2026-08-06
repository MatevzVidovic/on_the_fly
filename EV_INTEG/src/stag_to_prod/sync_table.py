#!/usr/bin/env python3
"""Copy missing IDs from staging to production and remove stale production IDs.

This intentionally never updates rows whose ID exists in both databases.
"""

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


def verify_tables(stag: Any, prod: Any, schema: str, table: str) -> list[str]:
    stag_columns = table_columns(stag, schema, table)
    prod_columns = table_columns(prod, schema, table)
    if not stag_columns:
        raise RuntimeError(f"staging table {schema}.{table} was not found or has no insertable columns")
    if not prod_columns:
        raise RuntimeError(f"production table {schema}.{table} was not found or has no insertable columns")
    if "id" not in stag_columns or "id" not in prod_columns:
        raise RuntimeError(f"both {schema}.{table} tables must have an id column")
    if stag_columns != prod_columns:
        only_stag = sorted(set(stag_columns) - set(prod_columns))
        only_prod = sorted(set(prod_columns) - set(stag_columns))
        raise RuntimeError(
            f"table columns differ for {schema}.{table}; only in staging: {only_stag or '-'}; "
            f"only in production: {only_prod or '-'}"
        )
    return prod_columns


def ids(connection: Any, schema: str, table: str) -> set[Any]:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id FROM {relation_sql(schema, table)}")
        return {row[0] for row in cursor.fetchall()}


def chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def rows_for_ids(connection: Any, schema: str, table: str, columns: list[str], wanted_ids: list[Any], batch_size: int) -> Iterable[tuple[Any, ...]]:
    projection = ", ".join(f'"{column}"' for column in columns)
    relation = relation_sql(schema, table)
    for batch in chunks(wanted_ids, batch_size):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {projection} FROM {relation} WHERE id = ANY(%s) ORDER BY id", (batch,))
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="table name, without schema")
    parser.add_argument("--schema", default=None, help="schema; defaults to SYNC_SCHEMA or public")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only (the default)")
    mode.add_argument("--apply", action="store_true", help="perform the deletes and inserts")
    parser.add_argument("--preview-limit", type=int, default=100, help="maximum rows shown for each action (default: 100)")
    parser.add_argument("--batch-size", type=int, default=1_000, help="IDs processed per SQL statement (default: 1000)")
    args = parser.parse_args()
    if args.preview_limit < 0 or args.batch_size <= 0:
        parser.error("--preview-limit must be non-negative and --batch-size must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        table = valid_identifier(args.table, "table")
        load_environment()
        schema = valid_identifier(args.schema or os.environ.get("SYNC_SCHEMA", "public"), "schema")
        psycopg = require_psycopg()
        with psycopg.connect(**connection_settings("STAG")) as stag, psycopg.connect(**connection_settings("PROD")) as prod:
            columns = verify_tables(stag, prod, schema, table)
            stag_ids = ids(stag, schema, table)
            prod_ids = ids(prod, schema, table)
            delete_ids = sorted(prod_ids - stag_ids)
            insert_ids = sorted(stag_ids - prod_ids)
            print(json.dumps({"mode": "apply" if args.apply else "dry-run", "schema": schema, "table": table, "staging_ids": len(stag_ids), "production_ids": len(prod_ids), "delete_from_production": len(delete_ids), "insert_into_production": len(insert_ids)}))
            if args.preview_limit:
                print_preview("DELETE", rows_for_ids(prod, schema, table, columns, delete_ids, args.batch_size), columns, args.preview_limit)
                print_preview("INSERT", rows_for_ids(stag, schema, table, columns, insert_ids, args.batch_size), columns, args.preview_limit)
            if not args.apply:
                return 0

            relation = relation_sql(schema, table)
            placeholders = ", ".join("%s" for _ in columns)
            column_sql = ", ".join(f'"{column}"' for column in columns)
            insert_sql = f"INSERT INTO {relation} ({column_sql}) VALUES ({placeholders})"
            # A transaction keeps production unchanged if any source row cannot be inserted.
            with prod.transaction():
                with prod.cursor() as cursor:
                    for batch in chunks(delete_ids, args.batch_size):
                        cursor.execute(f"DELETE FROM {relation} WHERE id = ANY(%s)", (batch,))
                    for batch in chunks(insert_ids, args.batch_size):
                        source_rows = list(rows_for_ids(stag, schema, table, columns, batch, args.batch_size))
                        cursor.executemany(insert_sql, source_rows)
            print(f"applied: deleted {len(delete_ids)} rows; inserted {len(insert_ids)} rows")
            return 0
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
