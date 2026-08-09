#!/usr/bin/env python3
"""Core KN→staging CLI, with ``ev_pe_parc_h`` as its compatibility default.

Thin sibling wrappers select their own fixed catalog table; this script may
also receive any non-pending catalogued target table as its positional value.
"""

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

from integration_core import Checkpoint, InterruptController, PageSizer, RunIdentity, WriterRunContext, read_checkpoint
from integration_core.kn_staging import KnStagingRun, freeze_upper_watermark, prove_source_membership, read_select, validate_oracle_index, validate_source_shape
from integration_core.state import save_checkpoint
from integrations.catalog import table_spec
from integrations.ev_pe_parc import SPEC


STATE_ROOT = HERE / ".state" / "core"


def parse_args(fixed_table: str | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", nargs="?", default=fixed_table or SPEC.target_table)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--initialize-only-new-watermark", action="store_true", help="write the reviewed initial only-new composite watermark; never transfers rows")
    parser.add_argument("--resumable", action="store_true")
    parser.add_argument("--only-new", action="store_true")
    parser.add_argument("--confirm-staging-already-current", action="store_true", help="required acknowledgement for --initialize-only-new-watermark")
    parser.add_argument("--purge-non-existant", action="store_true", help="reserved: unavailable until purge has a source-consistent Oracle snapshot")
    parser.add_argument("--page-size", type=int, default=50_000)
    parser.add_argument("--auto-page-size", action="store_true", help="adapt source payload pages within the configured maximum")
    parser.add_argument("--initial-page-size", type=int, help="adaptive starting size (default: one quarter of max)")
    parser.add_argument("--max-page-size", type=int, help="adaptive hard ceiling (default: --page-size)")
    parser.add_argument("--constant-page-size", type=int, help="fixed page size; disables adaptive sizing")
    parser.add_argument("--fresh", action="store_true", help="discard this pilot wrapper checkpoint")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if fixed_table and args.table.lower() != fixed_table.lower():
        parser.error(f"this wrapper is only for {fixed_table}")
    try:
        spec = table_spec(args.table)
    except (KeyError, RuntimeError) as error:
        parser.error(str(error))
    args.table = spec.target_table
    if args.page_size <= 0:
        parser.error("--page-size must be positive")
    if args.initial_page_size is not None and args.initial_page_size <= 0:
        parser.error("--initial-page-size must be positive")
    if args.max_page_size is not None and args.max_page_size <= 0:
        parser.error("--max-page-size must be positive")
    if args.constant_page_size is not None and args.constant_page_size <= 0:
        parser.error("--constant-page-size must be positive")
    if args.constant_page_size is not None and (args.auto_page_size or args.initial_page_size is not None or args.max_page_size is not None):
        parser.error("--constant-page-size cannot be combined with adaptive-size options")
    if (args.initial_page_size is not None or args.max_page_size is not None) and not args.auto_page_size:
        parser.error("--initial-page-size/--max-page-size require --auto-page-size")
    if args.only_new and not args.resumable:
        parser.error("--only-new requires --resumable")
    if args.only_new and args.fresh:
        parser.error("--only-new cannot use --fresh; initialise or preserve its reviewed composite watermark")
    if args.initialize_only_new_watermark:
        if args.only_new:
            parser.error("--initialize-only-new-watermark already operates on only-new state; omit --only-new")
        if not args.resumable:
            parser.error("--initialize-only-new-watermark requires --resumable")
        if not args.confirm_staging_already_current:
            parser.error("--initialize-only-new-watermark requires --confirm-staging-already-current")
        if args.fresh:
            parser.error("--initialize-only-new-watermark cannot use --fresh")
        if args.status:
            parser.error("--initialize-only-new-watermark cannot be combined with --status")
    elif args.confirm_staging_already_current:
        parser.error("--confirm-staging-already-current is only valid with --initialize-only-new-watermark")
    if args.purge_non_existant:
        parser.error("--purge-non-existant is unavailable until source membership and payload use one Oracle snapshot")
    if args.apply and not args.resumable:
        parser.error("the core pilot requires --resumable --apply")
    args.spec = spec
    return args


def load_environment() -> None:
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env", override=False)


def drivers() -> tuple[Any, Any]:
    import oracledb
    import psycopg
    return oracledb, psycopg


def enable_oracle_thick_mode(oracledb: Any) -> None:
    """Use the same optional Thick-mode contract as the legacy loader."""
    configured = os.environ.get("KN_ORACLE_CLIENT_LIB_DIR")
    if not configured:
        return
    directory = Path(configured).expanduser()
    if not directory.is_dir():
        raise RuntimeError(f"KN_ORACLE_CLIENT_LIB_DIR is not a directory: {directory}")
    oracledb.init_oracle_client(lib_dir=str(directory))


def reconnectable(error: Exception) -> bool:
    text = str(error).upper()
    return any(token in text for token in ("DPY-6005", "DPY-4011", "ORA-12152", "ORA-12547", "ORA-12541", "CONNECTION CLOSED", "LOST CONTACT"))


def replace_data_connections(run: Any, connect_oracle: Any, connect_staging: Any) -> None:
    """Reconnect both data sessions at the unchanged checkpoint cursor."""
    for previous in (run.source_connection, run.destination_connection):
        close = getattr(previous, "close", None)
        if callable(close):
            close()
    run.source_connection = connect_oracle()
    run.destination_connection = connect_staging()
    run.destination_connection.autocommit = True


def close_replaced_connections(run: Any, original_source: Any, original_destination: Any) -> None:
    """Close replacement sessions that outer ``with`` blocks do not own."""
    for connection, original in ((run.source_connection, original_source), (run.destination_connection, original_destination)):
        if connection is not original:
            close = getattr(connection, "close", None)
            if callable(close):
                close()


def oracle_settings(oracledb: Any) -> dict[str, Any]:
    required = ("KN_USER", "KN_PASSWORD", "KN_HOST", "KN_PORT", "KN_SERVICE")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError("missing KN Oracle environment variables: " + ", ".join(missing))
    return {"user": os.environ["KN_USER"], "password": os.environ["KN_PASSWORD"], "dsn": oracledb.makedsn(os.environ["KN_HOST"], int(os.environ["KN_PORT"]), service_name=os.environ["KN_SERVICE"])}


def pg_settings() -> dict[str, Any]:
    required = ("STAG_USER", "STAG_PASSWORD", "STAG_HOST", "STAG_PORT")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError("missing staging PostgreSQL environment variables: " + ", ".join(missing))
    return {"user": os.environ["STAG_USER"], "password": os.environ["STAG_PASSWORD"], "host": os.environ["STAG_HOST"], "port": int(os.environ["STAG_PORT"]), "dbname": os.environ.get("STAG_DATABASE", "fmp_data_gurs")}


def checkpoint_path(spec: Any, mode: str) -> Path:
    return STATE_ROOT / spec.name / f"{mode}.json"


def identity(spec: Any, query: str, mode: str, options: dict[str, Any]) -> RunIdentity:
    return RunIdentity("stag", os.environ.get("STAG_DATABASE", "fmp_data_gurs"), spec.target_schema, spec.target_table, spec.version, query, mode, spec.source_page_keys if mode == "full" else (spec.date_change or "date_change", *spec.source_page_keys), options)


def preview(kn: Any, query: str, spec: Any, only_new: bool) -> None:
    validate_source_shape(kn, query, spec, require_change=True)
    if only_new:
        upper = freeze_upper_watermark(kn, query, spec)
        print({"mode": "source-shape-preview", "table": spec.target_table, "only_new": True, "upper_watermark": upper})
    else:
        print({"mode": "source-shape-preview", "table": spec.target_table, "source_page_keys": spec.source_page_keys})


def initialize_only_new_watermark(
    kn: Any, query: str, spec: Any, path: Path, run_id: RunIdentity,
    context_factory: Any, interrupts: InterruptController,
) -> Checkpoint:
    """Freeze and persist a bootstrap window for later only-new completion.

    The acknowledgement belongs at the CLI boundary.  This function proves
    the source tuple, reads its native upper tuple under writer locks, and
    writes only an *incomplete* window checkpoint—never a staging payload
    row. The caller must transfer that frozen window before it can become a
    completed lower cursor.
    """
    with context_factory() as context:
        context.ensure_held()
        checkpoint = read_checkpoint(path, run_id)
        if checkpoint.completed:
            if checkpoint.metadata and checkpoint.metadata.get("initialized_only_new_bootstrap"):
                return checkpoint
            raise RuntimeError("only-new state already exists; refusing to replace its completed watermark")
        if checkpoint.metadata:
            if checkpoint.metadata.get("window_upper") is not None:
                return checkpoint
            raise RuntimeError("only-new checkpoint is incomplete; resume it or inspect/reset it before initialization")
        if checkpoint.cursor is not None or checkpoint.pages or checkpoint.rows:
            raise RuntimeError("only-new checkpoint is incomplete; resume it or inspect/reset it before initialization")
        validate_source_shape(kn, query, spec, require_change=True)
        if spec.oracle_owner is None or spec.oracle_index is None:
            raise RuntimeError(f"{spec.target_table} is not runnable until its verified Oracle index metadata is catalogued")
        validate_oracle_index(kn, spec.oracle_owner, spec.oracle_index, spec.oracle_index_columns or spec.source_page_keys)
        prove_source_membership(kn, query, spec, include_change=True)
        if interrupts.stop_requested:
            return checkpoint
        upper = freeze_upper_watermark(kn, query, spec)
        if interrupts.stop_requested:
            return checkpoint
        if upper is None:
            raise RuntimeError("cannot initialise --only-new from an empty source; no safe composite watermark exists")
        initialized = Checkpoint(run_id, None, 0, 0, False, {"window_upper": upper, "initialized_only_new_bootstrap": True})
        context.ensure_held()
        save_checkpoint(path, initialized)
        return initialized


def main(fixed_table: str | None = None) -> int:
    args = parse_args(fixed_table)
    spec = args.spec
    load_environment()
    oracledb, psycopg = drivers()
    enable_oracle_thick_mode(oracledb)
    query = read_select(spec.source_sql)
    only_new_state = args.only_new or args.initialize_only_new_watermark
    path = checkpoint_path(spec, "only_new" if only_new_state else "full")
    if args.status:
        print(read_checkpoint(path, identity(spec, query, "only-new" if only_new_state else "full", {"adapter": "kn-staging-v1"})).as_json() if path.exists() else {"status": "not started"})
        return 0
    with oracledb.connect(**oracle_settings(oracledb)) as kn:
        if args.dry_run or (not args.apply and not args.initialize_only_new_watermark):
            preview(kn, query, spec, args.only_new)
            return 0
        if not args.initialize_only_new_watermark:
            validate_source_shape(kn, query, spec, require_change=True)
        # A wrapper can later provide an actual Oracle index name.  The pilot
        # has expression-derived membership and validates the selected native
        # tuple instead, so no unsafe guessed dictionary lookup is made.
        if spec.oracle_owner is None or spec.oracle_index is None:
            raise RuntimeError(f"{spec.target_table} is not runnable until its verified Oracle index metadata is catalogued")
        if not args.initialize_only_new_watermark:
            validate_oracle_index(kn, spec.oracle_owner, spec.oracle_index, spec.oracle_index_columns or spec.source_page_keys)
        with psycopg.connect(**pg_settings()) as staging, InterruptController(lambda message: print(message, file=sys.stderr, flush=True)) as interrupts:
            # Keep long source/preflight reads outside an implicit PostgreSQL
            # transaction.  Each PageRunner transaction remains explicit.
            staging.autocommit = True
            # Page size changes are operational tuning, not a different data
            # contract, so a safe resumed window may use a new size.
            options = {"adapter": "kn-staging-v1"}
            run_id = identity(spec, query, "only-new" if only_new_state else "full", options)
            context = lambda: WriterRunContext(path.with_suffix(".lock"), lambda: psycopg.connect(**pg_settings()), run_id.database, spec.target_schema, spec.target_table)
            maximum = args.max_page_size or max(args.page_size, args.constant_page_size or 0)
            page_sizer = None
            if args.auto_page_size or args.constant_page_size is not None:
                page_sizer = PageSizer(
                    max_page_size=maximum,
                    initial_page_size=args.initial_page_size if args.auto_page_size else None,
                    constant_page_size=args.constant_page_size,
                )
            run = KnStagingRun(spec, kn, staging, query, args.page_size, path, run_id, context, interrupts=interrupts, page_sizer=page_sizer)

            def reconnect() -> None:
                # The runner cannot safely know whether a retryable exception
                # came from Oracle fetch or PostgreSQL page work.  Replace both
                # data sessions at the unchanged checkpoint cursor; the
                # advisory-lock session remains separate in WriterRunContext.
                replace_data_connections(run, lambda: oracledb.connect(**oracle_settings(oracledb)), lambda: psycopg.connect(**pg_settings()))

            run.reconnect = reconnect
            run.is_reconnectable = reconnectable
            try:
                if args.initialize_only_new_watermark:
                    checkpoint = initialize_only_new_watermark(kn, query, spec, path, run_id, context, interrupts)
                    if interrupts.stop_requested:
                        print({"table": spec.target_table, "mode": "only-new-bootstrap", "stopped": True})
                        return 0
                    print({"table": spec.target_table, "mode": "only-new-bootstrap", "frozen_upper": (checkpoint.metadata or {}).get("window_upper"), "next_step": "run --only-new --apply"})
                    return 0
                if not args.only_new:
                    result = run.run_full(fresh=args.fresh)
                    print({"table": spec.target_table, "mode": "full", "pages": result.checkpoint.pages, "rows": result.checkpoint.rows, "stopped": result.stopped_by_signal})
                    return 0
                result = run.run_only_new(fresh=args.fresh)
                print({"table": spec.target_table, "mode": "only-new", "pages": result.checkpoint.pages, "rows": result.checkpoint.rows, "stopped": result.stopped_by_signal})
                return 0
            finally:
                close_replaced_connections(run, kn, staging)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
