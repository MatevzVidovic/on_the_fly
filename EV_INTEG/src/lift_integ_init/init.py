#!/usr/bin/env python3
"""Set one LIFT integration high-water mark from its staging table."""

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
SRC = HERE.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from integrations.catalog import catalog_entry


SCHEMA = "public"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a plain PostgreSQL identifier")
    return value.lower()


def relation(table: str) -> str:
    return f'"{SCHEMA}"."{table}"'


def resolve_table_spec(table: str):
    """Resolve the canonical declaration before opening either database."""
    return catalog_entry(identifier(table, "table")).spec


def load_environment() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("install requirements into .venv before running this script") from error
    # Canonical configuration wins. The legacy location is read only as a
    # non-overriding migration fallback, so existing operators are not broken.
    load_dotenv(HERE / ".env", override=False)
    load_dotenv(HERE.parent / "adapt_last_changed_datetime" / ".env", override=False)


def pg_settings(database: str) -> dict[str, str | int]:
    required = ("STAG_USER", "STAG_PASSWORD", "STAG_HOST", "STAG_PORT")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing staging PostgreSQL environment variables: {', '.join(missing)}")
    return {
        "user": os.environ["STAG_USER"], "password": os.environ["STAG_PASSWORD"],
        "host": os.environ["STAG_HOST"], "port": int(os.environ["STAG_PORT"]), "dbname": database,
    }


def columns(connection: Any, table: str) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
            (SCHEMA, table),
        )
        return {str(row[0]).lower() for row in cursor.fetchall()}


def table_name_column(connection: Any) -> str:
    available = columns(connection, "attribute_tables")
    for candidate in ("table_name", "name"):
        if candidate in available:
            return candidate
    raise RuntimeError("cannot find a table-name column in public.attribute_tables; available columns: " + ", ".join(sorted(available)))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="catalogued staging table name in public schema")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="show the proposed metadata update (default)")
    mode.add_argument("--apply", action="store_true", help="apply the metadata update")
    parser.add_argument("--last-sync-start-year", type=int, metavar="YEAR", help="also set last_sync_start to 1 January of YEAR")
    args = parser.parse_args(argv)
    if args.last_sync_start_year is not None and not 1 <= args.last_sync_start_year <= 9999:
        parser.error("--last-sync-start-year must be between 1 and 9999")
    return args


def apply_metadata_update(
    cursor: Any, integration_id: Any, maximum: Any, previous: Any,
    proposed_start: datetime | None, previous_start: Any | None,
) -> None:
    """Update only if the metadata row still equals the reviewed preview."""
    assignments, values = ["last_changed_datetime = %s"], [maximum]
    predicate = "id = %s AND last_changed_datetime IS NOT DISTINCT FROM %s"
    if proposed_start is not None:
        assignments.append("last_sync_start = %s")
        values.append(proposed_start)
        predicate += " AND last_sync_start IS NOT DISTINCT FROM %s"
    values.extend((integration_id, previous))
    if proposed_start is not None:
        values.append(previous_start)
    cursor.execute(
        f'UPDATE {relation("attribute_table_integrations")} SET {", ".join(assignments)} WHERE {predicate}',
        values,
    )
    if cursor.rowcount != 1:
        raise RuntimeError("integration metadata changed after the dry-run preview; no update was applied")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        spec = resolve_table_spec(args.table)
        if spec.date_change is None:
            raise RuntimeError(f"TableSpec for public.{spec.target_table} has no date_change field")
        load_environment()
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("install requirements into .venv before running this script") from error

        with psycopg.connect(**pg_settings(os.environ.get("STAG_DATABASE", "fmp_data_gurs"))) as data:
            if spec.date_change not in columns(data, spec.target_table):
                raise RuntimeError(f"staging table public.{spec.target_table} does not have a {spec.date_change} column")
            with data.cursor() as cursor:
                cursor.execute(f'SELECT MAX("{spec.date_change}") FROM {relation(spec.target_table)}')
                maximum = cursor.fetchone()[0]
        if maximum is None:
            raise RuntimeError(f"public.{spec.target_table} has no non-NULL {spec.date_change} value")

        with psycopg.connect(**pg_settings("fmp")) as metadata:
            integration_columns = columns(metadata, "attribute_table_integrations")
            required = {"id", "attribute_table_id", "last_changed_datetime"}
            if args.last_sync_start_year is not None:
                required.add("last_sync_start")
            if missing := required - integration_columns:
                raise RuntimeError("public.attribute_table_integrations is missing: " + ", ".join(sorted(missing)))
            name_column = table_name_column(metadata)
            with metadata.cursor() as cursor:
                cursor.execute(f'SELECT id, "{name_column}" FROM {relation("attribute_tables")} WHERE "{name_column}" = %s', (spec.target_table,))
                tables = cursor.fetchall()
                if len(tables) != 1:
                    raise RuntimeError(f"expected exactly one public.attribute_tables row for {spec.target_table!r}; found {len(tables)}")
                table_id, table_name = tables[0]
                fields = ["id", "attribute_table_id", "last_changed_datetime"] + (["last_sync_start"] if args.last_sync_start_year is not None else [])
                cursor.execute(f'SELECT {", ".join(fields)} FROM {relation("attribute_table_integrations")} WHERE attribute_table_id = %s', (table_id,))
                integrations = cursor.fetchall()
            if len(integrations) != 1:
                raise RuntimeError(f"expected exactly one integration for attribute_table_id={table_id!r}; found {len(integrations)}")
            integration_id, integration_table_id, previous, *previous_start = integrations[0]
            proposed_start = datetime(args.last_sync_start_year, 1, 1) if args.last_sync_start_year is not None else None
            preview = {
                "mode": "apply" if args.apply else "dry-run", "staging_table": f"{SCHEMA}.{spec.target_table}",
                "max_date_change": maximum,
                "attribute_table": {"id": table_id, name_column: table_name},
                "attribute_table_integration": {
                    "id": integration_id, "attribute_table_id": integration_table_id,
                    "current_last_changed_datetime": previous, "proposed_last_changed_datetime": maximum,
                    **({"current_last_sync_start": previous_start[0], "proposed_last_sync_start": proposed_start} if proposed_start is not None else {}),
                },
            }
            print(json.dumps(preview, default=str, ensure_ascii=False, indent=2))
            if not args.apply:
                return 0
            with metadata.transaction():
                with metadata.cursor() as cursor:
                    apply_metadata_update(
                        cursor, integration_id, maximum, previous, proposed_start,
                        previous_start[0] if previous_start else None,
                    )
            print("applied: " + ("last_changed_datetime and last_sync_start" if proposed_start is not None else "last_changed_datetime") + " updated")
            return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
