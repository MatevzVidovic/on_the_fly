#!/usr/bin/env python3
"""Set an attribute-table integration's last_changed_datetime from MAX(date_change)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
SCHEMA = "public"


def identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a plain PostgreSQL identifier")
    return value


def relation(table: str) -> str:
    return f'"{SCHEMA}"."{table}"'


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("install requirements into .venv before running this script") from error
    load_dotenv(HERE / ".env", override=False)


def pg_settings() -> dict[str, str | int]:
    required = ("STAG_USER", "STAG_PASSWORD", "STAG_HOST", "STAG_PORT")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing staging PostgreSQL environment variables: {', '.join(missing)}")
    return {
        "user": os.environ["STAG_USER"],
        "password": os.environ["STAG_PASSWORD"],
        "host": os.environ["STAG_HOST"],
        "port": int(os.environ["STAG_PORT"]),
        "dbname": os.environ.get("STAG_DATABASE", "fmp_data_gurs"),
    }


def columns(connection: Any, table: str) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
            (SCHEMA, table),
        )
        return {row[0] for row in cursor.fetchall()}


def table_name_column(connection: Any) -> str:
    available = columns(connection, "attribute_tables")
    for candidate in ("table_name", "name"):
        if candidate in available:
            return candidate
    raise RuntimeError(
        "cannot find a table-name column in public.attribute_tables; "
        f"available columns: {', '.join(sorted(available)) or '(table missing)'}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="staging table name in the public schema")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="show the proposed metadata update (default)")
    mode.add_argument("--apply", action="store_true", help="apply the metadata update")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        table = identifier(args.table, "table")
        load_environment()
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("install requirements into .venv before running this script") from error
        with psycopg.connect(**pg_settings()) as connection:
            target_columns = columns(connection, table)
            if "date_change" not in target_columns:
                raise RuntimeError(f"staging table public.{table} does not have a date_change column")
            metadata_columns = columns(connection, "attribute_table_integrations")
            required_metadata = {"id", "attribute_table_id", "last_changed_datetime"}
            missing_metadata = required_metadata - metadata_columns
            if missing_metadata:
                raise RuntimeError(f"public.attribute_table_integrations is missing: {', '.join(sorted(missing_metadata))}")
            name_column = table_name_column(connection)

            with connection.cursor() as cursor:
                cursor.execute(f'SELECT MAX("date_change") FROM {relation(table)}')
                max_date_change = cursor.fetchone()[0]
                if max_date_change is None:
                    raise RuntimeError(f"public.{table} has no non-NULL date_change value")
                cursor.execute(f'SELECT id, "{name_column}" FROM {relation("attribute_tables")} WHERE "{name_column}" = %s', (table,))
                attribute_rows = cursor.fetchall()
                if len(attribute_rows) != 1:
                    raise RuntimeError(f"expected exactly one public.attribute_tables row for {table!r}; found {len(attribute_rows)}")
                attribute_table_id, attribute_table_name = attribute_rows[0]
                cursor.execute(
                    f'SELECT id, attribute_table_id, last_changed_datetime FROM {relation("attribute_table_integrations")} WHERE attribute_table_id = %s',
                    (attribute_table_id,),
                )
                integration_rows = cursor.fetchall()
                if len(integration_rows) != 1:
                    raise RuntimeError(f"expected exactly one integration for attribute_table_id={attribute_table_id!r}; found {len(integration_rows)}")
                integration_id, integration_attribute_table_id, current_last_changed = integration_rows[0]

            preview = {
                "mode": "apply" if args.apply else "dry-run",
                "staging_table": f"{SCHEMA}.{table}",
                "max_date_change": max_date_change,
                "attribute_table": {"id": attribute_table_id, name_column: attribute_table_name},
                "attribute_table_integration": {
                    "id": integration_id,
                    "attribute_table_id": integration_attribute_table_id,
                    "current_last_changed_datetime": current_last_changed,
                    "proposed_last_changed_datetime": max_date_change,
                },
            }
            print(json.dumps(preview, default=str, ensure_ascii=False, indent=2))
            if not args.apply:
                return 0
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f'UPDATE {relation("attribute_table_integrations")} SET last_changed_datetime = %s WHERE id = %s',
                        (max_date_change, integration_id),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError("integration row changed unexpectedly; transaction rolled back")
            print("applied: last_changed_datetime updated")
            return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
