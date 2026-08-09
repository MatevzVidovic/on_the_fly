#!/usr/bin/env python3
"""Report unique-key coverage for KN ORACLE / GURS ORCL LIFT tables."""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCHEMA = "public"
SOURCE_CONNECTIONS = ("KN ORACLE", "GURS ORCL")


@dataclass(frozen=True)
class Integration:
    table: str
    connection: str
    integration_id: str


@dataclass(frozen=True)
class UniqueKey:
    index: str
    constraint: str | None
    columns: tuple[str, ...]
    valid: bool
    partial: bool


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("install requirements into .venv") from error
    # Reuse the established checker credentials when this small report has not
    # been given its own .env yet. A local .env wins, so it can safely target a
    # different environment without changing the other checker.
    load_dotenv(ROOT / ".env", override=False)
    load_dotenv(HERE.parent / "check_all" / ".env", override=False)
    load_dotenv(HERE / ".env", override=True)


def pg_settings(environment: str, *, metadata: bool = False) -> dict[str, Any]:
    prefix = "STAG" if environment == "staging" else "PROD"
    # The repository's original tools used PG_* for the one staging database.
    # Accept that established spelling for staging, without ever changing the
    # caller's process environment or conflating it with production.
    if environment == "staging":
        for field in ("USER", "PASSWORD", "HOST", "PORT"):
            os.environ.setdefault(f"STAG_{field}", os.getenv(f"PG_{field}", ""))
    required = [f"{prefix}_{field}" for field in ("USER", "PASSWORD", "HOST", "PORT")]
    missing = [field for field in required if not os.getenv(field)]
    if missing:
        raise RuntimeError("missing PostgreSQL environment variables: " + ", ".join(missing))
    database_field = f"{prefix}_{'METADATA_DATABASE' if metadata else 'DATABASE'}"
    return {
        "user": os.environ[f"{prefix}_USER"],
        "password": os.environ[f"{prefix}_PASSWORD"],
        "host": os.environ[f"{prefix}_HOST"],
        "port": int(os.environ[f"{prefix}_PORT"]),
        "dbname": os.getenv(database_field, "fmp" if metadata else "fmp_data_gurs"),
    }


def integrations(connection: Any) -> list[Integration]:
    query = """
        SELECT a.name, c.name, i.id::text
        FROM public.attribute_tables AS a
        JOIN public.attribute_table_integrations AS i ON i.attribute_table_id = a.id
        JOIN public.attribute_table_sql_connections AS c ON c.id = i.attribute_table_sql_connection_id
        WHERE upper(c.name) = ANY(%s)
        ORDER BY a.name, c.name, i.id
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (list(SOURCE_CONNECTIONS),))
        return [Integration(str(table), str(source), str(integration_id))
                for table, source, integration_id in cursor.fetchall()]


def pk_columns(connection: Any, table: str) -> list[str] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema=%s
              AND table_name=%s
              AND column_name LIKE %s ESCAPE '\\'
            ORDER BY ordinal_position
            """,
            (SCHEMA, table, r"%\_pk"),
        )
        rows = [str(row[0]) for row in cursor.fetchall()]
        cursor.execute("SELECT to_regclass(%s)", (f"{SCHEMA}.{table}",))
        exists = cursor.fetchone()[0] is not None
    return rows if exists else None


def unique_keys(connection: Any, table: str) -> list[UniqueKey]:
    query = """
        SELECT index_rel.relname AS index_name,
               constraint_rel.conname AS constraint_name,
               array_agg(attribute.attname ORDER BY key_column.ordinality) AS columns,
               index_meta.indisvalid,
               index_meta.indpred IS NOT NULL AS partial
        FROM pg_index AS index_meta
        JOIN pg_class AS table_rel ON table_rel.oid = index_meta.indrelid
        JOIN pg_namespace AS namespace ON namespace.oid = table_rel.relnamespace
        JOIN pg_class AS index_rel ON index_rel.oid = index_meta.indexrelid
        LEFT JOIN pg_constraint AS constraint_rel ON constraint_rel.conindid = index_meta.indexrelid
        JOIN LATERAL unnest(index_meta.indkey::smallint[]) WITH ORDINALITY
             AS key_column(attribute_num, ordinality) ON key_column.ordinality <= index_meta.indnkeyatts
        JOIN pg_attribute AS attribute
             ON attribute.attrelid = table_rel.oid AND attribute.attnum = key_column.attribute_num
        WHERE namespace.nspname=%s
          AND table_rel.relname=%s
          AND index_meta.indisunique
        GROUP BY index_rel.relname, constraint_rel.conname, index_meta.indisvalid, index_meta.indpred
        ORDER BY index_rel.relname
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (SCHEMA, table))
        return [UniqueKey(str(index_name), str(constraint) if constraint else None,
                          tuple(str(column) for column in columns), bool(valid), bool(partial))
                for index_name, constraint, columns, valid, partial in cursor.fetchall()]


def key_result(column: str, keys: list[UniqueKey]) -> tuple[bool, str]:
    matches = [key for key in keys if key.columns == (column,) and key.valid and not key.partial]
    if not matches:
        return False, "missing"
    labels = []
    for key in matches:
        label = f"`{key.index}`"
        if key.constraint:
            label += f" (constraint `{key.constraint}`)"
        labels.append(label)
    return True, "; ".join(labels)


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_report(environment: str, items: list[tuple[str, list[Integration], list[str] | None, list[UniqueKey]]]) -> tuple[str, bool]:
    lines = [
        "# KN ORACLE / GURS ORCL `_pk` unique-key report",
        "",
        f"Environment: `{environment}`. Metadata database: `fmp`; data database: `fmp_data_gurs`; schema: `{SCHEMA}`.",
        "",
        "A pass requires a valid, non-partial, single-column unique index for every field ending in `_pk`. "
        "A named PostgreSQL `UNIQUE` constraint is shown when it owns that index.",
        "",
        "| Attribute table | SQL connection(s) | Integration id(s) | `_pk` field(s) | Unique-key coverage |",
        "| --- | --- | --- | --- | --- |",
    ]
    failures = False
    checked_fields = 0
    covered_fields = 0
    for table, table_integrations, columns, keys in items:
        sources = ", ".join(sorted({item.connection for item in table_integrations}))
        ids = ", ".join(f"`{item.integration_id}`" for item in table_integrations)
        if columns is None:
            outcome = "❌ table not found in `public`"
            fields = "—"
            failures = True
        elif not columns:
            outcome = "— no field ending in `_pk` (not applicable)"
            fields = "—"
        else:
            fields = ", ".join(f"`{column}`" for column in columns)
            results = []
            for column in columns:
                checked_fields += 1
                passed, detail = key_result(column, keys)
                results.append(f"{'✅' if passed else '❌'} `{column}`: {detail}")
                covered_fields += int(passed)
                failures = failures or not passed
            outcome = "<br>".join(results)
        lines.append("| " + " | ".join([
            f"`{markdown_escape(table)}`", markdown_escape(sources), ids, fields, outcome,
        ]) + " |")
    lines.extend([
        "",
        f"Summary: {len(items)} discovered table(s); {checked_fields} `_pk` field(s) checked; "
        f"{covered_fields} covered; {checked_fields - covered_fields} missing.",
    ])
    lines.append(f"Result: {'**FAIL**' if failures else '**PASS**'} for tables that have `_pk` fields.")
    return "\n".join(lines), failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=("staging", "prod"), default="staging")
    parser.add_argument("--report", type=Path, default=HERE / "kn_tables_uk_report.md")
    parser.add_argument("--fail-on-missing", action="store_true",
                        help="exit non-zero if any discovered table lacks qualifying _pk unique-key coverage")
    args = parser.parse_args(argv)

    load_env()
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("install requirements into .venv") from error

    try:
        with psycopg.connect(**pg_settings(args.environment, metadata=True)) as meta, \
             psycopg.connect(**pg_settings(args.environment)) as data:
            discovered = integrations(meta)
            grouped: dict[str, list[Integration]] = {}
            for item in discovered:
                grouped.setdefault(item.table, []).append(item)
            items = [(table, table_integrations, pk_columns(data, table), unique_keys(data, table))
                     for table, table_integrations in sorted(grouped.items())]
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    report, failures = render_report(args.environment, items)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report + "\n", encoding="utf-8")
    print(f"wrote {args.report} ({len(items)} discovered table(s); {'failures found' if failures else 'all pass'})")
    return 1 if failures and args.fail_on_missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
