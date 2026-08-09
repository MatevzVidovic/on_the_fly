#!/usr/bin/env python3
"""Set an attribute-table integration's last_changed_datetime from MAX(date_change)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
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


def pg_settings(database: str) -> dict[str, str | int]:
    required = ("STAG_USER", "STAG_PASSWORD", "STAG_HOST", "STAG_PORT")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing staging PostgreSQL environment variables: {', '.join(missing)}")
    return {
        "user": os.environ["STAG_USER"],
        "password": os.environ["STAG_PASSWORD"],
        "host": os.environ["STAG_HOST"],
        "port": int(os.environ["STAG_PORT"]),
        "dbname": database,
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
    parser.add_argument(
        "--last-sync-start-year",
        type=int,
        metavar="YEAR",
        help="also set last_sync_start to midnight on 1 January of YEAR",
    )
    args = parser.parse_args()
    if args.last_sync_start_year is not None and not 1 <= args.last_sync_start_year <= 9999:
        parser.error("--last-sync-start-year must be between 1 and 9999")
    return args


def main() -> int:
    args = parse_args()
    try:
        table = identifier(args.table, "table")
        load_environment()
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("install requirements into .venv before running this script") from error
        data_database = os.environ.get("STAG_DATABASE", "fmp_data_gurs")
        with psycopg.connect(**pg_settings(data_database)) as staging_connection:
            target_columns = columns(staging_connection, table)
            if "date_change" not in target_columns:
                raise RuntimeError(f"staging table public.{table} does not have a date_change column")
            with staging_connection.cursor() as cursor:
                cursor.execute(f'SELECT MAX("date_change") FROM {relation(table)}')
                max_date_change = cursor.fetchone()[0]
                if max_date_change is None:
                    raise RuntimeError(f"public.{table} has no non-NULL date_change value")

        with psycopg.connect(**pg_settings("fmp")) as metadata_connection:
            metadata_columns = columns(metadata_connection, "attribute_table_integrations")
            required_metadata = {"id", "attribute_table_id", "last_changed_datetime"}
            if args.last_sync_start_year is not None:
                required_metadata.add("last_sync_start")
            missing_metadata = required_metadata - metadata_columns
            if missing_metadata:
                raise RuntimeError(f"public.attribute_table_integrations is missing: {', '.join(sorted(missing_metadata))}")
            name_column = table_name_column(metadata_connection)

            with metadata_connection.cursor() as cursor:
                cursor.execute(f'SELECT id, "{name_column}" FROM {relation("attribute_tables")} WHERE "{name_column}" = %s', (table,))
                attribute_rows = cursor.fetchall()
                if len(attribute_rows) != 1:
                    raise RuntimeError(f"expected exactly one public.attribute_tables row for {table!r}; found {len(attribute_rows)}")
                attribute_table_id, attribute_table_name = attribute_rows[0]
                integration_fields = ["id", "attribute_table_id", "last_changed_datetime"]
                if args.last_sync_start_year is not None:
                    integration_fields.append("last_sync_start")
                cursor.execute(
                    f'SELECT {", ".join(integration_fields)} FROM {relation("attribute_table_integrations")} WHERE attribute_table_id = %s',
                    (attribute_table_id,),
                )
                integration_rows = cursor.fetchall()
                if len(integration_rows) != 1:
                    raise RuntimeError(f"expected exactly one integration for attribute_table_id={attribute_table_id!r}; found {len(integration_rows)}")
                integration_id, integration_attribute_table_id, current_last_changed, *optional_current_last_sync_start = integration_rows[0]

            proposed_last_sync_start = (
                datetime(args.last_sync_start_year, 1, 1)
                if args.last_sync_start_year is not None
                else None
            )

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
                    **(
                        {
                            "current_last_sync_start": optional_current_last_sync_start[0],
                            "proposed_last_sync_start": proposed_last_sync_start,
                        }
                        if args.last_sync_start_year is not None
                        else {}
                    ),
                },
            }
            print(json.dumps(preview, default=str, ensure_ascii=False, indent=2))
            if not args.apply:
                return 0
            with metadata_connection.transaction():
                with metadata_connection.cursor() as cursor:
                    assignments = ["last_changed_datetime = %s"]
                    values: list[Any] = [max_date_change]
                    if proposed_last_sync_start is not None:
                        assignments.append("last_sync_start = %s")
                        values.append(proposed_last_sync_start)
                    values.append(integration_id)
                    cursor.execute(
                        f'UPDATE {relation("attribute_table_integrations")} SET {", ".join(assignments)} WHERE id = %s',
                        values,
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError("integration row changed unexpectedly; transaction rolled back")
            changed = "last_changed_datetime and last_sync_start" if proposed_last_sync_start is not None else "last_changed_datetime"
            print(f"applied: {changed} updated")
            return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
