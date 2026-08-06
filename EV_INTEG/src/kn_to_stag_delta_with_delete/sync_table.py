#!/usr/bin/env python3
"""Synchronise ID membership from a KN Oracle SELECT into a staging PG table.

The SQL file must contain one SELECT (or WITH ... SELECT) and must alias its
output columns to the destination PostgreSQL column names, including `id`.
Rows with an ID in both systems are intentionally not updated.
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
    if not query or not re.match(r"^(SELECT|WITH)\\b", query, re.IGNORECASE):
        raise ValueError("integration SQL must contain exactly one SELECT or WITH query")
    if ";" in query:
        raise ValueError("integration SQL must not contain multiple statements")
    return query


def target_columns(connection: Any, schema: str, table: str) -> list[str]:
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
        columns = [row[0] for row in cursor.fetchall()]
    if not columns:
        raise RuntimeError(f"staging table {schema}.{table} was not found or has no insertable columns")
    if "id" not in columns:
        raise RuntimeError(f"staging table {schema}.{table} must have an id column")
    return columns


def scalar(value: Any) -> Any:
    """Materialise Oracle LOBs before their cursor and connection are closed."""
    read = getattr(value, "read", None)
    return read() if callable(read) else value


def source_rows(connection: Any, query: str, target_columns_: list[str]) -> dict[Any, tuple[Any, ...]]:
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
        id_position = target_columns_.index("id")
        rows: dict[Any, tuple[Any, ...]] = {}
        while fetched := cursor.fetchmany(1_000):
            for raw_row in fetched:
                row = tuple(scalar(raw_row[position]) for position in positions)
                identifier = row[id_position]
                if identifier is None:
                    raise RuntimeError("integration SQL returned a NULL id")
                if identifier in rows:
                    raise RuntimeError(f"integration SQL returned duplicate id: {identifier!r}")
                rows[identifier] = row
        return rows


def staging_rows(connection: Any, schema: str, table: str, columns: list[str], identifiers: list[Any], batch_size: int) -> Iterable[tuple[Any, ...]]:
    projection = ", ".join(f'"{column}"' for column in columns)
    for start in range(0, len(identifiers), batch_size):
        batch = identifiers[start : start + batch_size]
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {projection} FROM {relation_sql(schema, table)} WHERE id = ANY(%s) ORDER BY id", (batch,))
            yield from cursor.fetchall()


def staging_ids(connection: Any, schema: str, table: str) -> set[Any]:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id FROM {relation_sql(schema, table)}")
        result = {row[0] for row in cursor.fetchall()}
    if None in result:
        raise RuntimeError(f"staging table {schema}.{table} contains a NULL id")
    return result


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="staging table name, without schema")
    parser.add_argument("--integration-sql", required=True, type=Path, help="path to the KN SELECT statement")
    parser.add_argument("--schema", default=None, help="defaults to STAG_SCHEMA or fmp_data_gurs")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only (the default)")
    mode.add_argument("--apply", action="store_true", help="perform the delete and insert changes")
    parser.add_argument("--preview-limit", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=1_000)
    args = parser.parse_args()
    if args.preview_limit < 0 or args.batch_size <= 0:
        parser.error("--preview-limit must be non-negative and --batch-size must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        table = valid_identifier(args.table, "table")
        load_environment()
        schema = valid_identifier(args.schema or os.environ.get("STAG_SCHEMA", "fmp_data_gurs"), "schema")
        query = read_select(args.integration_sql)
        oracledb, psycopg = require_drivers()
        with oracledb.connect(**oracle_settings(oracledb)) as kn, psycopg.connect(**pg_settings()) as stag:
            columns = target_columns(stag, schema, table)
            source = source_rows(kn, query, columns)
            source_ids = set(source)
            destination_ids = staging_ids(stag, schema, table)
            delete_ids = list(destination_ids - source_ids)
            insert_ids = list(source_ids - destination_ids)
            print(json.dumps({"mode": "apply" if args.apply else "dry-run", "schema": schema, "table": table, "kn_ids": len(source_ids), "staging_ids": len(destination_ids), "delete_from_staging": len(delete_ids), "insert_into_staging": len(insert_ids)}))
            if args.preview_limit:
                preview("DELETE", staging_rows(stag, schema, table, columns, delete_ids, args.batch_size), columns, args.preview_limit)
                preview("INSERT", (source[identifier] for identifier in insert_ids), columns, args.preview_limit)
            if not args.apply:
                return 0
            relation = relation_sql(schema, table)
            column_sql = ", ".join(f'"{column}"' for column in columns)
            insert_sql = f"INSERT INTO {relation} ({column_sql}) VALUES ({', '.join('%s' for _ in columns)})"
            with stag.transaction():
                with stag.cursor() as cursor:
                    for start in range(0, len(delete_ids), args.batch_size):
                        cursor.execute(f"DELETE FROM {relation} WHERE id = ANY(%s)", (delete_ids[start : start + args.batch_size],))
                    for start in range(0, len(insert_ids), args.batch_size):
                        cursor.executemany(insert_sql, (source[identifier] for identifier in insert_ids[start : start + args.batch_size]))
            print(f"applied: deleted {len(delete_ids)} rows; inserted {len(insert_ids)} rows")
            return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
