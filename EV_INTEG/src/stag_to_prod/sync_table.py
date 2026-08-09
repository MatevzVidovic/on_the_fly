#!/usr/bin/env python3
"""Resumable, idempotent staging → production PostgreSQL copy."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SRC = HERE.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from integration_core import InterruptController, PageSizer, RunIdentity, StagingProductionRun, WriterRunContext, read_checkpoint
from integration_core.staging_production import copyable_columns, ensure_id_not_null, ensure_non_null_id, ensure_uuid_id, identifier, relation, usable_id_index


STATE_ROOT = HERE / ".state" / "core"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="production/staging table name without schema")
    parser.add_argument("--schema", default="public")
    parser.add_argument("--page-key", default="id", help="compatibility alias; only UUID id is supported")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="validate/count only (default)")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--status", action="store_true")
    parser.add_argument("--page-size", type=int, default=50_000)
    parser.add_argument("--auto-page-size", action="store_true")
    parser.add_argument("--initial-page-size", type=int)
    parser.add_argument("--max-page-size", type=int)
    parser.add_argument("--constant-page-size", type=int)
    parser.add_argument("--truncate", action="store_true", help="truncate production, reset checkpoint, then copy")
    parser.add_argument("--fresh", action="store_true", help="discard this completed/partial checkpoint and rescan staging")
    args = parser.parse_args(argv)
    if args.page_size <= 0:
        parser.error("--page-size must be positive")
    if args.initial_page_size is not None and args.initial_page_size <= 0: parser.error("--initial-page-size must be positive")
    if args.max_page_size is not None and args.max_page_size <= 0: parser.error("--max-page-size must be positive")
    if args.constant_page_size is not None and args.constant_page_size <= 0: parser.error("--constant-page-size must be positive")
    if args.constant_page_size is not None and (args.auto_page_size or args.initial_page_size is not None or args.max_page_size is not None): parser.error("--constant-page-size cannot be combined with adaptive-size options")
    if (args.initial_page_size is not None or args.max_page_size is not None) and not args.auto_page_size: parser.error("--initial-page-size/--max-page-size require --auto-page-size")
    if args.page_key.lower() != "id":
        parser.error("staging-to-production copy always pages on UUID id")
    if args.truncate and not args.apply:
        parser.error("--truncate requires --apply")
    if args.fresh and not args.apply:
        parser.error("--fresh requires --apply")
    return args


args_parse = parse_args  # compatibility for callers that imported the old CLI helper


def load_environment() -> None:
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env", override=False)


def settings(prefix: str) -> dict[str, Any]:
    required = [f"{prefix}_{field}" for field in ("USER", "PASSWORD", "HOST", "PORT")]
    missing = [field for field in required if not os.environ.get(field)]
    if missing:
        raise RuntimeError("missing PostgreSQL environment variables: " + ", ".join(missing))
    return {
        "user": os.environ[f"{prefix}_USER"], "password": os.environ[f"{prefix}_PASSWORD"],
        "host": os.environ[f"{prefix}_HOST"], "port": int(os.environ[f"{prefix}_PORT"]),
        "dbname": os.environ.get(f"{prefix}_DATABASE", "fmp_data_gurs"),
    }


def connection_name(prefix: str) -> str:
    config = settings(prefix)
    return f"{config['host']}:{config['port']}/{config['dbname']}"


def checkpoint_path(schema: str, table: str) -> Path:
    return STATE_ROOT / schema / table / "copy.json"


def count_rows(connection: Any, schema: str, table: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT count(*) FROM {relation(schema, table)}")
        return int(cursor.fetchone()[0])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_environment()
    import psycopg

    schema, table = identifier(args.schema, "schema"), identifier(args.table, "table")
    path = checkpoint_path(schema, table)
    with psycopg.connect(**settings("STAG")) as staging, psycopg.connect(**settings("PROD")) as production:
        columns = copyable_columns(staging, production, schema, table)
        if not usable_id_index(staging, schema, table) or not usable_id_index(production, schema, table):
            raise RuntimeError("both tables require a valid non-partial single-column UNIQUE btree index on id")
        ensure_uuid_id(staging, schema, table)
        ensure_uuid_id(production, schema, table)
        ensure_id_not_null(staging, schema, table)
        ensure_id_not_null(production, schema, table)
        ensure_non_null_id(staging, schema, table)
        identity = RunIdentity("prod", connection_name("PROD"), schema, table, 1, "staging-production-copy-v1", "upsert", ("id",), {"staging": connection_name("STAG"), "columns": columns})
        if args.status:
            print(read_checkpoint(path, identity).as_json() if path.exists() else {"status": "not started"})
            return 0
        staging_count, production_count = count_rows(staging, schema, table), count_rows(production, schema, table)
        print({"mode": "apply" if args.apply else "dry-run", "schema": schema, "table": table, "page_key": "id", "staging_rows": staging_count, "production_rows": production_count, "copyable_columns": len(columns), "page_size": args.page_size})
        if not args.apply:
            return 0
        staging.commit()
        production.commit()
        production.autocommit = True
        with InterruptController(lambda message: print(message, file=sys.stderr, flush=True)) as interrupts:
            maximum = args.max_page_size or max(args.page_size, args.constant_page_size or 0)
            page_sizer = PageSizer(max_page_size=maximum, initial_page_size=args.initial_page_size if args.auto_page_size else None, constant_page_size=args.constant_page_size) if args.auto_page_size or args.constant_page_size is not None else None
            run = StagingProductionRun(
                schema, table, staging, production, columns, args.page_size, path, identity,
                lambda: WriterRunContext(path.with_suffix(".lock"), lambda: psycopg.connect(**settings("PROD")), identity.database, schema, table),
                interrupts=interrupts, page_sizer=page_sizer,
            )

            # One invocation reads one stable staging snapshot.  We do not
            # transparently reconnect this source session: that would silently
            # replace its snapshot and could skip rows behind the checkpoint.
            with staging.transaction():
                with staging.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                result = run.run(fresh=args.fresh, truncate=args.truncate)
            print({"table": table, "pages": result.checkpoint.pages, "rows": result.checkpoint.rows, "completed": result.checkpoint.completed, "stopped": result.stopped_by_signal})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
