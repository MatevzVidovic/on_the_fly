"""Resumable PostgreSQL staging → production table copy.

The source is read in UUID ``id`` order.  Every committed page is an
idempotent production upsert, so a crash between commit and checkpoint is a
safe replay.  This adapter deliberately never deletes production rows.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
import re
from dataclasses import dataclass
from typing import Any

from .managed import DEFAULT_MANAGED_FIELDS
from .errors import is_size_related_error
from .page_size import PageSizer
from .runner import Page, PageRunner
from .state import Checkpoint, RunIdentity


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def identifier(value: str, label: str = "identifier") -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a plain PostgreSQL identifier: {value!r}")
    return value.lower()


def relation(schema: str, table: str) -> str:
    return f'"{identifier(schema, "schema")}"."{identifier(table, "table")}"'


def table_columns(connection: Any, schema: str, table: str) -> tuple[str, ...]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s "
            "AND is_generated = 'NEVER' AND identity_generation IS DISTINCT FROM 'ALWAYS' "
            "ORDER BY ordinal_position",
            (schema, table),
        )
        return tuple(identifier(row[0], "column") for row in cursor.fetchall())


def column_types(connection: Any, schema: str, table: str) -> dict[str, str]:
    """Canonical PostgreSQL types, including typmods, domains, and arrays."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod) "
            "FROM pg_attribute a JOIN pg_class t ON t.oid = a.attrelid "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "WHERE n.nspname = %s AND t.relname = %s AND a.attnum > 0 AND NOT a.attisdropped",
            (schema, table),
        )
        return {identifier(name, "column"): str(type_name) for name, type_name in cursor.fetchall()}


def copyable_columns(staging: Any, production: Any, schema: str, table: str) -> tuple[str, ...]:
    source, target = table_columns(staging, schema, table), table_columns(production, schema, table)
    if not source or not target:
        raise RuntimeError(f"{schema}.{table} was not found or has no copyable columns")
    if set(source) != set(target):
        raise RuntimeError(
            f"table columns differ for {schema}.{table}; only in staging: {sorted(set(source) - set(target)) or '-'}; "
            f"only in production: {sorted(set(target) - set(source)) or '-'}"
        )
    source_types, target_types = column_types(staging, schema, table), column_types(production, schema, table)
    mismatched = sorted(column for column in source if source_types.get(column) != target_types.get(column))
    if mismatched:
        raise RuntimeError(f"table column types differ for {schema}.{table}: {', '.join(mismatched)}")
    if "id" not in source:
        raise RuntimeError(f"{schema}.{table} requires copyable UUID id")
    return source


def usable_id_index(connection: Any, schema: str, table: str) -> bool:
    """A ready, valid, non-partial unique btree index exactly on ``id``."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_index i JOIN pg_class t ON t.oid = i.indrelid "
            "JOIN pg_namespace n ON n.oid = t.relnamespace JOIN pg_class idx ON idx.oid = i.indexrelid "
            "JOIN LATERAL unnest(i.indkey) WITH ORDINALITY x(attnum, ord) ON true "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum "
            "WHERE n.nspname = %s AND t.relname = %s AND i.indisunique AND i.indisvalid AND i.indisready "
            "AND i.indpred IS NULL AND idx.relam = (SELECT oid FROM pg_am WHERE amname = 'btree') "
            "AND x.ord <= i.indnkeyatts GROUP BY i.indexrelid, i.indnkeyatts "
            "HAVING i.indnkeyatts = 1 AND min(a.attname) = 'id'",
            (schema, table),
        )
        return cursor.fetchone() is not None


def ensure_non_null_id(connection: Any, schema: str, table: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT 1 FROM {relation(schema, table)} WHERE \"id\" IS NULL LIMIT 1")
        if cursor.fetchone() is not None:
            raise RuntimeError(f"{schema}.{table} contains NULL id values; UUID keyset paging is unsafe")


def ensure_uuid_id(connection: Any, schema: str, table: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_type, udt_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s AND column_name = 'id'",
            (schema, table),
        )
        row = cursor.fetchone()
    if row is None or str(row[0]).lower() != "uuid" or str(row[1]).lower() != "uuid":
        raise RuntimeError(f"{schema}.{table}.id must be PostgreSQL uuid")


def ensure_id_not_null(connection: Any, schema: str, table: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s AND column_name = 'id'",
            (schema, table),
        )
        row = cursor.fetchone()
    if row is None or str(row[0]).upper() != "NO":
        raise RuntimeError(f"{schema}.{table}.id must be declared NOT NULL")


def upsert_sql(schema: str, table: str, columns: tuple[str, ...]) -> str:
    if "id" not in columns:
        raise RuntimeError("copy columns must include id")
    quoted = ", ".join(f'"{column}"' for column in columns)
    values = ", ".join(f"%({column})s" for column in columns)
    immutable = DEFAULT_MANAGED_FIELDS.creation_fields
    updates = [column for column in columns if column not in immutable]
    conflict = "DO NOTHING" if not updates else "DO UPDATE SET " + ", ".join(f'"{column}" = EXCLUDED."{column}"' for column in updates)
    return f"INSERT INTO {relation(schema, table)} ({quoted}) VALUES ({values}) ON CONFLICT (\"id\") {conflict}"


@dataclass(slots=True)
class StagingProductionRun:
    schema: str
    table: str
    staging_connection: Any
    production_connection: Any
    columns: tuple[str, ...]
    page_size: int
    checkpoint_path: Any
    identity: RunIdentity
    run_context: Callable[[], Any]
    interrupts: Any | None = None
    reconnect: Callable[[], None] | None = None
    is_reconnectable: Callable[[Exception], bool] | None = None
    page_sizer: PageSizer | None = None

    def _shrink_page_for(self, error: Exception) -> bool:
        if self.page_sizer is None or not self.page_sizer.adaptive or not is_size_related_error(error):
            return False
        self.page_sizer.failed_for_size()
        return True

    def run(self, *, fresh: bool = False, truncate: bool = False) -> Any:
        statement = upsert_sql(self.schema, self.table, self.columns)

        def fetch(after: tuple[Any, ...] | None) -> Page[Mapping[str, Any]] | None:
            size = self.page_sizer.current if self.page_sizer is not None else self.page_size
            where, binds = "", [size]
            if after is not None:
                where, binds = "WHERE \"id\" > %s", [after[0], size]
            projection = ", ".join(f'"{column}"' for column in self.columns)
            with self.staging_connection.cursor() as cursor:
                cursor.execute(f"SELECT {projection} FROM {relation(self.schema, self.table)} {where} ORDER BY \"id\" LIMIT %s", binds)
                rows = tuple(dict(zip(self.columns, row, strict=True)) for row in cursor.fetchall())
            return None if not rows else Page(rows, (rows[-1]["id"],))

        def write(rows: tuple[Mapping[str, Any], ...]) -> None:
            with self.production_connection.cursor() as cursor:
                cursor.executemany(statement, rows)

        @contextmanager
        def transaction() -> Iterable[Any]:
            with self.production_connection.transaction():
                yield self.production_connection

        runner = PageRunner(
            self.checkpoint_path, self.identity, fetch, write, transaction, self.run_context,
            reconnect=self.reconnect, is_reconnectable=self.is_reconnectable, interrupts=self.interrupts,
            on_page_committed=(lambda _page: self.page_sizer.succeeded()) if self.page_sizer is not None else None,
            on_page_size_error=self._shrink_page_for,
        )
        # Read/reset/truncate/copy deliberately share exactly one writer
        # context.  A completed ordinary copy starts a new idempotent epoch;
        # a partial one resumes from its checkpoint.
        with self.run_context() as context:
            from .state import read_checkpoint
            # --truncate supersedes checkpoint identity: it is the explicit
            # destructive reset requested by the operator.
            reset = fresh or truncate
            if not reset:
                reset = read_checkpoint(self.checkpoint_path, self.identity).completed
            if truncate:
                # If the process dies after TRUNCATE but before checkpoint
                # reset, rerunning --truncate repeats the intentional reset.
                context.ensure_held()
                handoff_started = False
                try:
                    with self.production_connection.transaction():
                        context.begin_page_mutation(self.production_connection)
                        handoff_started = True
                        with self.production_connection.cursor() as cursor:
                            cursor.execute(f"TRUNCATE TABLE {relation(self.schema, self.table)}")
                finally:
                    if handoff_started:
                        context.end_page_mutation()
                reset = True
            return runner.run(fresh=reset, context=context)
