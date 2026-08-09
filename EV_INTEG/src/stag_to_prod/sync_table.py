#!/usr/bin/env python3
"""Resumable full copy from a staging PostgreSQL table to production."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
STATE_ROOT = HERE / ".state"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a plain PostgreSQL identifier")
    return value


def quote(value: str) -> str:
    return f'"{value}"'


def relation(schema: str, table: str) -> str:
    return f"{quote(schema)}.{quote(table)}"


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("install requirements into .venv before running this script") from error
    load_dotenv(HERE / ".env", override=False)


def settings(prefix: str) -> dict[str, str | int]:
    required = [f"{prefix}_{field}" for field in ("USER", "PASSWORD", "HOST", "PORT")]
    missing = [field for field in required if not os.environ.get(field)]
    if missing:
        raise RuntimeError(f"missing PostgreSQL environment variables: {', '.join(missing)}")
    return {
        "user": os.environ[f"{prefix}_USER"],
        "password": os.environ[f"{prefix}_PASSWORD"],
        "host": os.environ[f"{prefix}_HOST"],
        "port": int(os.environ[f"{prefix}_PORT"]),
        "dbname": os.environ.get(f"{prefix}_DATABASE", "fmp_data_gurs"),
    }


def connection_identity(prefix: str) -> str:
    config = settings(prefix)
    return f"{config['host']}:{config['port']}/{config['dbname']}"


def state_path(schema: str, table: str, page_key: str) -> Path:
    raw = json.dumps(["simple-copy-v1", connection_identity("STAG"), connection_identity("PROD"), schema, table, page_key])
    return STATE_ROOT / hashlib.sha256(raw.encode()).hexdigest() / "state.sqlite"


def open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = sqlite3.connect(path)
    state.execute("PRAGMA journal_mode=WAL")
    state.execute("PRAGMA synchronous=FULL")
    state.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    return state


def get_meta(state: sqlite3.Connection, key: str) -> str | None:
    row = state.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(state: sqlite3.Connection, key: str, value: str) -> None:
    state.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))
    state.commit()


def table_columns(connection: Any, schema: str, table: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
              AND is_generated = 'NEVER'
              AND identity_generation IS DISTINCT FROM 'ALWAYS'
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        return [row[0] for row in cursor.fetchall()]


def verify_columns(staging: Any, production: Any, schema: str, table: str, page_key: str) -> list[str]:
    staging_columns = table_columns(staging, schema, table)
    production_columns = table_columns(production, schema, table)
    if not staging_columns or not production_columns:
        raise RuntimeError(f"table {schema}.{table} was not found or has no copyable columns in both databases")
    if set(staging_columns) != set(production_columns):
        raise RuntimeError(
            f"table columns differ for {schema}.{table}; "
            f"only in staging: {sorted(set(staging_columns) - set(production_columns)) or '-'}; "
            f"only in production: {sorted(set(production_columns) - set(staging_columns)) or '-'}"
        )
    if page_key not in staging_columns:
        raise RuntimeError(f"both tables must contain page key {page_key}")
    return staging_columns


def has_unique_btree_index(connection: Any, schema: str, table: str, key: str) -> bool:
    sql = """
        SELECT 1
        FROM pg_index i
        JOIN pg_class table_rel ON table_rel.oid = i.indrelid
        JOIN pg_namespace namespace ON namespace.oid = table_rel.relnamespace
        JOIN pg_class index_rel ON index_rel.oid = i.indexrelid
        WHERE namespace.nspname = %s
          AND table_rel.relname = %s
          AND i.indisunique
          AND i.indisvalid
          AND i.indisready
          AND i.indpred IS NULL
          AND index_rel.relam = (SELECT oid FROM pg_am WHERE amname = 'btree')
          AND (
              SELECT array_agg(attribute.attname ORDER BY indexed.ord)
              FROM unnest(i.indkey) WITH ORDINALITY indexed(attnum, ord)
              JOIN pg_attribute attribute
                ON attribute.attrelid = table_rel.oid AND attribute.attnum = indexed.attnum
              WHERE indexed.ord <= i.indnkeyatts
          ) = ARRAY[%s]::name[]
        LIMIT 1
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, (schema, table, key))
        return cursor.fetchone() is not None


def ensure_non_null_key(connection: Any, schema: str, table: str, key: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT 1 FROM {relation(schema, table)} WHERE {quote(key)} IS NULL LIMIT 1")
        if cursor.fetchone():
            raise RuntimeError(f"{schema}.{table} contains NULL {key} values; resumable keyset paging is unsafe")


def count_rows(connection: Any, schema: str, table: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT count(*) FROM {relation(schema, table)}")
        return cursor.fetchone()[0]


def fetch_page(staging: Any, schema: str, table: str, columns: list[str], key: str, last_key: str | None, page_size: int) -> list[tuple[Any, ...]]:
    projection = ", ".join(quote(column) for column in columns)
    where = ""
    values: list[Any] = [page_size]
    if last_key is not None:
        where = f"WHERE {quote(key)} > %s"
        values = [last_key, page_size]
    with staging.cursor() as cursor:
        cursor.execute(
            f"SELECT {projection} FROM {relation(schema, table)} {where} ORDER BY {quote(key)} LIMIT %s",
            values,
        )
        return cursor.fetchall()


def copy_page(production: Any, schema: str, table: str, columns: list[str], key: str, rows: list[tuple[Any, ...]]) -> int:
    target = relation(schema, table)
    column_list = ", ".join(quote(column) for column in columns)
    temp = '"_stag_to_prod_page"'
    with production.transaction():
        with production.cursor() as cursor:
            cursor.execute(f"CREATE TEMP TABLE {temp} ON COMMIT DROP AS SELECT {column_list} FROM {target} WHERE false")
            with cursor.copy(f"COPY {temp} ({column_list}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row(row)
            cursor.execute(
                f"INSERT INTO {target} ({column_list}) "
                f"SELECT {column_list} FROM {temp} "
                f"ON CONFLICT ({quote(key)}) DO NOTHING"
            )
            return cursor.rowcount


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="table name without schema")
    parser.add_argument("--schema", help="defaults to SYNC_SCHEMA or public")
    parser.add_argument("--page-key", default="id", help="unique, non-null key used for paging (default: id)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="validate and print counts only (default)")
    mode.add_argument("--apply", action="store_true", help="truncate once and copy/resume pages")
    parser.add_argument("--page-size", type=int, default=50_000)
    parser.add_argument("--restart", action="store_true", help="discard copy state, truncate production, and restart")
    args = parser.parse_args()
    if args.page_size <= 0:
        parser.error("--page-size must be positive")
    if args.restart and not args.apply:
        parser.error("--restart requires --apply")
    return args


def main() -> int:
    args = parse_args()
    state: sqlite3.Connection | None = None
    try:
        load_environment()
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("install requirements into .venv before running this script") from error

        schema = identifier(args.schema or os.environ.get("SYNC_SCHEMA", "public"), "schema")
        table = identifier(args.table, "table")
        page_key = identifier(args.page_key, "page key")
        path = state_path(schema, table, page_key)

        with psycopg.connect(**settings("STAG")) as staging, psycopg.connect(**settings("PROD")) as production:
            columns = verify_columns(staging, production, schema, table, page_key)
            if not has_unique_btree_index(staging, schema, table, page_key) or not has_unique_btree_index(production, schema, table, page_key):
                raise RuntimeError(f"both tables require a valid non-partial single-column unique B-tree index on {page_key}")
            ensure_non_null_key(staging, schema, table, page_key)
            staging_count = count_rows(staging, schema, table)
            production_count = count_rows(production, schema, table)
            print(json.dumps({"mode": "apply" if args.apply else "dry-run", "schema": schema, "table": table, "page_key": page_key, "staging_rows": staging_count, "production_rows": production_count, "page_size": args.page_size}))
            if not args.apply:
                return 0

            staging.commit()
            production.commit()
            if args.restart and path.parent.exists():
                shutil.rmtree(path.parent)
            state = open_state(path)
            phase = get_meta(state, "phase")
            if phase == "completed":
                raise RuntimeError("copy already completed; use --restart to replace production again")
            if phase is None:
                # Commit the destructive reset before page commits. A crash here
                # is safe: a rerun with phase unset truncates again.
                with production.transaction():
                    with production.cursor() as cursor:
                        cursor.execute(f"TRUNCATE TABLE {relation(schema, table)}")
                set_meta(state, "phase", "copying")

            key_index = columns.index(page_key)
            last_key = get_meta(state, "last_key")
            copied = int(get_meta(state, "copied_rows") or "0")
            page = int(get_meta(state, "page") or "0")
            while True:
                rows = fetch_page(staging, schema, table, columns, page_key, last_key, args.page_size)
                if not rows:
                    set_meta(state, "phase", "completed")
                    print(f"applied: completed {copied} source rows in {page} pages")
                    return 0
                inserted = copy_page(production, schema, table, columns, page_key, rows)
                last_key = str(rows[-1][key_index])
                copied += len(rows)
                page += 1
                set_meta(state, "last_key", last_key)
                set_meta(state, "copied_rows", str(copied))
                set_meta(state, "page", str(page))
                print(f"committed page {page} ({len(rows)} source rows; {inserted} inserted; total {copied})", flush=True)
    except (RuntimeError, ValueError, KeyboardInterrupt) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    finally:
        if state is not None:
            state.close()


if __name__ == "__main__":
    raise SystemExit(main())
