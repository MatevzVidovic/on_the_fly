"""Oracle KN to PostgreSQL staging adapter.

This is intentionally the only database-specific transfer adapter.  Table
wrappers provide a :class:`TableSpec`; this module owns query construction,
source validation, and idempotent staging upserts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import re
from time import monotonic
from typing import Any

from .managed import InsertPolicy
from .errors import is_size_related_error
from .page_size import PageSizer
from .runner import Page, PageRunner
from .run_store import RunStore
from .specs import TableSpec
from .state import Checkpoint, RunIdentity


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return value.lower()


def read_select(path: Any) -> str:
    """Read one Oracle SELECT, accepting a trailing SQL-client semicolon."""
    query = path.read_text(encoding="utf-8").strip()
    if query.endswith(";"):
        query = query[:-1].rstrip()
    if not re.match(r"^(?:select|with)\b", query, flags=re.IGNORECASE):
        raise ValueError("integration SQL must contain one SELECT or WITH query")
    # Semicolons are not legal inside the one statement sent by python-oracledb.
    if ";" in query:
        raise ValueError("integration SQL must contain exactly one SELECT or WITH query")
    return query


def lexicographic_predicate(fields: tuple[str, ...], operator: str, prefix: str) -> str:
    """Expand a portable Oracle lexicographic tuple comparison."""
    if operator not in {">", "<=", ">=", "<"}:
        raise ValueError("unsupported tuple operator")
    parts: list[str] = []
    strict = {">": ">", "<": "<", ">=": ">", "<=": "<"}[operator]
    for index, field in enumerate(fields):
        equal = " AND ".join(f"{fields[before]} = :{prefix}_{before}" for before in range(index))
        comparison = operator if index == len(fields) - 1 else strict
        parts.append(f"{equal + ' AND ' if equal else ''}{field} {comparison} :{prefix}_{index}")
    return "(" + " OR ".join(parts) + ")"


def keyset_query(source_sql: str, page_keys: tuple[str, ...], after: tuple[Any, ...] | None) -> tuple[str, dict[str, Any]]:
    """Return a lower-exclusive source page query and its binds.

    The selected aliases are deliberately used directly: wrappers never add
    loader-only columns to an integration SQL statement.
    """
    fields = tuple(_identifier(field) for field in page_keys)
    binds: dict[str, Any] = {}
    where = ""
    if after is not None:
        if len(after) != len(fields):
            raise ValueError("page cursor does not match source page key")
        binds = {f"after_{index}": value for index, value in enumerate(after)}
        where = " WHERE " + lexicographic_predicate(fields, ">", "after")
    return f"SELECT * FROM ({source_sql}) source_rows{where} ORDER BY {', '.join(fields)} FETCH NEXT :page_size ROWS ONLY", binds


def keyset_projection_query(source_sql: str, projection: tuple[str, ...], page_keys: tuple[str, ...], after: tuple[Any, ...] | None) -> tuple[str, dict[str, Any]]:
    """A keyset page containing only aliases already selected by the SQL."""
    query, binds = keyset_query(source_sql, page_keys, after)
    aliases = ", ".join(_identifier(field) for field in projection)
    return query.replace("SELECT *", f"SELECT {aliases}", 1), binds


def upper_watermark_query(source_sql: str, change_field: str, page_keys: tuple[str, ...]) -> str:
    fields = (_identifier(change_field), *( _identifier(field) for field in page_keys))
    return f"SELECT {', '.join(fields)} FROM ({source_sql}) source_rows ORDER BY {', '.join(field + ' DESC NULLS LAST' for field in fields)} FETCH FIRST 1 ROW ONLY"


def delta_materialization_query(
    source_sql: str, change_field: str,
    lower: tuple[Any, ...] | None, upper: tuple[Any, ...],
    page_keys: tuple[str, ...],
) -> tuple[str, dict[str, Any]]:
    """One ordered, payload-bearing query for a frozen timestamp window.

    The lower timestamp is inclusive so a resumed materialization can see and
    validate the exact boundary tuple again.  Composite lower/upper filtering
    happens in Python while rows stream into the durable local generation.
    """
    change = _identifier(change_field)
    fields = (change, *(_identifier(field) for field in page_keys))
    binds: dict[str, Any] = {"upper_change": upper[0]}
    clauses = [f"{change} <= :upper_change"]
    if lower is not None:
        clauses.append(f"{change} >= :lower_change")
        binds["lower_change"] = lower[0]
    return (
        f"SELECT * FROM ({source_sql}) source_rows WHERE {' AND '.join(clauses)} "
        f"ORDER BY {', '.join(field + ' ASC NULLS FIRST' for field in fields)}",
        binds,
    )


def source_columns(connection: Any, source_sql: str) -> tuple[str, ...]:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM ({source_sql}) source_rows WHERE 1 = 0")
        columns = tuple(_identifier(column[0]) for column in cursor.description)
    duplicates = sorted({column for column in columns if columns.count(column) > 1})
    if duplicates:
        raise RuntimeError(f"integration SQL has duplicate selected aliases: {', '.join(duplicates)}")
    return columns


def validate_selected_columns(columns: tuple[str, ...], spec: TableSpec, *, require_change: bool) -> None:
    """Validate one already-described source result against its paging facts."""
    selected = set(columns)
    required = {spec.membership_key, *spec.source_page_keys}
    if require_change and spec.date_change:
        required.add(spec.date_change)
    missing = sorted(required - selected)
    if missing:
        raise RuntimeError(f"integration SQL is missing required selected aliases: {', '.join(missing)}")


def validate_source_shape(connection: Any, source_sql: str, spec: TableSpec, *, require_change: bool) -> None:
    """Cheap structural validation for command previews and preflight."""
    validate_selected_columns(source_columns(connection, source_sql), spec, require_change=require_change)


def prove_source_membership(
    connection: Any, source_sql: str, spec: TableSpec, *,
    include_change: bool,
) -> None:
    """Globally prove identities used by full-sync paging and preflight."""
    page_fields = tuple(dict.fromkeys(spec.source_page_keys))
    fields = tuple(dict.fromkeys((spec.membership_key, *page_fields, *((spec.date_change,) if include_change and spec.date_change else ()))))
    null_checks = [
        f"SUM(CASE WHEN {spec.membership_key} IS NULL THEN 1 ELSE 0 END) AS null_membership",
        f"SUM(CASE WHEN {' OR '.join(f'{field} IS NULL' for field in page_fields)} THEN 1 ELSE 0 END) AS null_page",
    ]
    if include_change and spec.date_change:
        null_checks.append(f"SUM(CASE WHEN {spec.date_change} IS NULL THEN 1 ELSE 0 END) AS null_change")
    query = (
        f"SELECT COUNT(*) AS total, {', '.join(null_checks)}, "
        f"COUNT(DISTINCT {spec.membership_key}) AS distinct_membership "
        f"FROM ({source_sql}) source_rows"
    )
    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()
    total, null_membership, null_page, *tail = row
    null_change = tail.pop(0) if include_change and spec.date_change else 0
    distinct_membership = tail.pop(0)
    if null_membership:
        raise RuntimeError("KN integration result has null membership keys")
    if null_page:
        raise RuntimeError("KN integration result has null native page-key tuples")
    if null_change:
        raise RuntimeError(f"KN integration result has null {spec.date_change} values")
    if total != distinct_membership:
        raise RuntimeError("KN integration result has duplicate membership keys")
    # Full paging is *always* ordered by the native page tuple.  Prove that
    # tuple independently of date_change: two rows with the same native tuple
    # but different change timestamps would otherwise pass a composite proof
    # and make full keyset paging silently skip one of them.
    tuple_query = (
        f"SELECT COUNT(*) FROM (SELECT {', '.join(spec.source_page_keys)} "
        f"FROM ({source_sql}) source_rows GROUP BY {', '.join(spec.source_page_keys)})"
    )
    with connection.cursor() as cursor:
        cursor.execute(tuple_query)
        distinct_page = cursor.fetchone()[0]
    if total != distinct_page:
        raise RuntimeError("KN integration result has duplicate native page-key tuples")


def validate_oracle_index(connection: Any, owner: str, index_name: str | None, page_keys: tuple[str, ...]) -> None:
    """Validate declared native index order when a table wrapper supplies it.

    Aliases derived from expressions cannot be matched to dictionary metadata;
    those wrappers deliberately leave ``index_name`` unset and still receive
    result-shape uniqueness validation above.
    """
    if index_name is None:
        return
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT i.uniqueness, i.status, i.visibility, i.index_type, c.column_name "
            "FROM all_indexes i JOIN all_ind_columns c ON c.index_owner = i.owner AND c.index_name = i.index_name "
            "WHERE i.owner = :owner AND i.index_name = :index_name ORDER BY c.column_position",
            {"owner": owner.upper(), "index_name": index_name.upper()},
        )
        rows = cursor.fetchall()
    if not rows:
        raise RuntimeError(f"Oracle index {owner}.{index_name} was not found")
    uniqueness, status, visibility, index_type = (str(rows[0][index]).upper() for index in range(4))
    if uniqueness != "UNIQUE" or status != "VALID" or visibility != "VISIBLE" or index_type != "NORMAL":
        raise RuntimeError(f"Oracle index {owner}.{index_name} must be a visible valid UNIQUE NORMAL index")
    actual = tuple(str(row[4]).lower() for row in rows)
    expected = tuple(key.lower() for key in page_keys)
    if actual[: len(expected)] != expected:
        raise RuntimeError(f"Oracle index {owner}.{index_name} does not start with declared source page keys {', '.join(expected)}")


def _quoted(schema: str, table: str) -> str:
    return f'"{_identifier(schema)}"."{_identifier(table)}"'


def target_columns(connection: Any, spec: TableSpec) -> tuple[str, ...]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s AND is_generated = 'NEVER' ORDER BY ordinal_position",
            (spec.target_schema, spec.target_table),
        )
        columns = tuple(_identifier(row[0]) for row in cursor.fetchall())
    if spec.membership_key not in columns:
        raise RuntimeError(f"staging table {spec.target_relation} has no membership column {spec.membership_key}")
    return columns


def validate_target_membership_index(connection: Any, spec: TableSpec) -> None:
    """Require the index that makes conflict upserts and replay semantics safe."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_index i JOIN pg_class t ON t.oid = i.indrelid "
            "JOIN pg_namespace n ON n.oid = t.relnamespace "
            "JOIN LATERAL unnest(i.indkey) WITH ORDINALITY x(attnum, ord) ON true "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.attnum "
            "WHERE n.nspname = %s AND t.relname = %s AND i.indisunique AND i.indisvalid AND i.indisready AND i.indpred IS NULL AND x.ord <= i.indnkeyatts "
            "GROUP BY i.indexrelid, i.indnkeyatts HAVING i.indnkeyatts = 1 AND min(a.attname) = %s",
            (spec.target_schema, spec.target_table, spec.membership_key),
        )
        if cursor.fetchone() is None:
            raise RuntimeError(f"staging table {spec.target_relation} requires a non-partial single-column UNIQUE index on {spec.membership_key}")


def target_changes(connection: Any, spec: TableSpec, identifiers: list[Any]) -> dict[Any, Any]:
    if not identifiers or spec.date_change is None:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT \"{spec.membership_key}\", \"{spec.date_change}\" FROM {_quoted(spec.target_schema, spec.target_table)} WHERE \"{spec.membership_key}\" = ANY(%s)",
            (identifiers,),
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


def materialize_source_membership(
    connection: Any, source_sql: str, spec: TableSpec, page_size: int,
    store: RunStore, *, fresh: bool, interrupts: Any | None = None,
    include_change: bool = False, prove: bool = True,
    page_sizer: PageSizer | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Any, bool]:
    """Build/reuse one durable source generation for full preflight/purge."""
    database = store.open(fresh=fresh)
    handed_to_caller = False
    try:
        # Re-prove on every invocation, including a durable-generation or
        # payload resume. The SQLite cursor records data, not an enduring fact
        # about a live Oracle result, and older state may predate this proof.
        if prove:
            prove_source_membership(connection, source_sql, spec, include_change=include_change)
        if store.complete(database):
            handed_to_caller = True
            return database, False
        projection = tuple(dict.fromkeys((spec.membership_key, *((spec.date_change,) if include_change and spec.date_change else ()), *spec.source_page_keys)))
        after = store.cursor(database)
        if after is None:
            store.begin(database)
        started = monotonic()
        pages = 0
        rows_done = 0
        while True:
            query, binds = keyset_projection_query(source_sql, projection, spec.source_page_keys, after)
            binds["page_size"] = page_sizer.current if page_sizer is not None else page_size
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query, binds)
                    names = tuple(_identifier(column[0]) for column in cursor.description)
                    rows = cursor.fetchall()
            except BaseException as error:
                # A second Ctrl-C must remain an immediate abort.  The durable
                # cursor already reflects only previously committed SQLite pages.
                if isinstance(error, KeyboardInterrupt):
                    raise
                if interrupts is not None and interrupts.stop_requested:
                    handed_to_caller = True
                    return database, True
                if page_sizer is not None and page_sizer.adaptive and is_size_related_error(error):
                    page_sizer.failed_for_size()
                    continue
                raise
            if not rows:
                store.mark_complete(database)
                handed_to_caller = True
                return database, False
            generation_rows = []
            for row in rows:
                values = dict(zip(names, row, strict=True))
                generation_rows.append((values[spec.membership_key], values[spec.date_change] if include_change and spec.date_change else None))
            last = dict(zip(names, rows[-1], strict=True))
            store.append_page(database, generation_rows, tuple(last[key] for key in spec.source_page_keys))
            if page_sizer is not None:
                page_sizer.succeeded()
            pages += 1
            rows_done += len(rows)
            if progress is not None:
                elapsed = max(monotonic() - started, 1e-9)
                progress({
                    "phase": "preflight", "page": pages,
                    "page_rows": len(rows), "rows": rows_done,
                    "elapsed_seconds": elapsed, "rate": rows_done / elapsed,
                    "eta_seconds": None,
                })
            if interrupts is not None and interrupts.stop_requested:
                handed_to_caller = True
                return database, True
            after = tuple(last[key] for key in spec.source_page_keys)
    finally:
        if not handed_to_caller:
            database.close()


def assert_target_not_newer(connection: Any, spec: TableSpec, generation: Any, *, batch_size: int = 1_000, interrupts: Any | None = None) -> bool:
    """Abort a full run before payload writes if any target version wins."""
    if spec.date_change is None:
        return False
    for batch in RunStore.batches(generation, batch_size):
        source_changes = dict(batch)
        for identifier, target_change in target_changes(connection, spec, list(source_changes)).items():
            if target_change is not None and source_changes[identifier] < target_change:
                raise RuntimeError(f"staging has newer {spec.date_change} for source key {identifier!r}; no payload pages were written")
        if interrupts is not None and interrupts.stop_requested:
            return True
    return False


def materialize_delta_payload(
    connection: Any, source_sql: str, spec: TableSpec, store: RunStore,
    lower: tuple[Any, ...] | None, upper: tuple[Any, ...], page_size: int,
    *, interrupts: Any | None = None, page_sizer: PageSizer | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Any, bool]:
    """Freeze the exact only-new payload locally before any target write.

    Validation is proportional to the delta window: ordered rows prove a
    strict composite cursor as they are read, and SQLite's UNIQUE keys prove
    membership uniqueness.  No full-result aggregate or global NULL scan is
    needed for each incremental run.
    """
    if spec.date_change is None:
        raise RuntimeError("only-new needs a date_change column")
    database = store.open()
    handed_to_caller = False
    try:
        bounds = store.delta_bounds(database)
        if bounds != (lower, upper):
            store.begin_delta(database, lower, upper)
        elif store.delta_complete(database):
            handed_to_caller = True
            return database, False

        started = monotonic()
        pages = rows_done = 0
        while True:
            persisted_after = store.delta_cursor(database)
            query_lower = persisted_after if persisted_after is not None else lower
            query, binds = delta_materialization_query(
                source_sql, spec.date_change, query_lower, upper, spec.source_page_keys,
            )
            size = page_sizer.current if page_sizer is not None else page_size
            saw_persisted_boundary = persisted_after is None
            try:
                with connection.cursor() as cursor:
                    cursor.arraysize = size
                    cursor.execute(query, binds)
                    names = tuple(_identifier(column[0]) for column in cursor.description)
                    while True:
                        raw_rows = cursor.fetchmany(size)
                        if not raw_rows:
                            break
                        batch: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []
                        for raw in raw_rows:
                            row = dict(zip(names, raw, strict=True))
                            composite = (row[spec.date_change], *(row[key] for key in spec.source_page_keys))
                            if any(value is None for value in composite):
                                raise RuntimeError("only-new source has a NULL cursor component")
                            if persisted_after is not None and composite == persisted_after:
                                if saw_persisted_boundary:
                                    raise RuntimeError("only-new source cursor is duplicate or not strictly ordered")
                                saw_persisted_boundary = True
                                continue
                            if query_lower is not None and composite <= query_lower:
                                continue
                            if composite > upper:
                                continue
                            batch.append((row[spec.membership_key], composite, row))
                        store.append_delta_page(database, batch)
                        if page_sizer is not None:
                            page_sizer.succeeded()
                            size = page_sizer.current
                            cursor.arraysize = size
                        pages += 1
                        rows_done += len(batch)
                        if progress is not None:
                            elapsed = max(monotonic() - started, 1e-9)
                            progress({
                                "phase": "only-new-materialize", "page": pages,
                                "page_rows": len(batch), "rows": rows_done,
                                "elapsed_seconds": elapsed, "rate": rows_done / elapsed,
                                "eta_seconds": None,
                            })
                        if interrupts is not None and interrupts.stop_requested:
                            handed_to_caller = True
                            return database, True
                # The boundary row may be deleted after its payload was
                # durably stored. Its absence does not invalidate later rows;
                # filtering remains lower-exclusive from that stored cursor.
                store.mark_delta_complete(database)
                handed_to_caller = True
                return database, False
            except BaseException as error:
                if isinstance(error, KeyboardInterrupt):
                    raise
                if interrupts is not None and interrupts.stop_requested:
                    handed_to_caller = True
                    return database, True
                if page_sizer is not None and page_sizer.adaptive and is_size_related_error(error):
                    page_sizer.failed_for_size()
                    continue
                raise
    finally:
        if not handed_to_caller:
            database.close()


def upsert_sql(spec: TableSpec, source: tuple[str, ...], destination: tuple[str, ...], policy: InsertPolicy = InsertPolicy()) -> str:
    source_set, destination_set = set(source), set(destination)
    duplicates = sorted({column for column in source if source.count(column) > 1})
    if duplicates:
        raise RuntimeError(f"integration SQL has duplicate selected aliases: {', '.join(duplicates)}")
    expected_source = destination_set if policy.copy_managed_fields else destination_set - policy.managed.all_fields
    # Native Oracle paging keys may be selected for cursor traversal without
    # being stored in a legacy LIFT target (for example JN_REV_NUM).
    # Only declared paging keys can be omitted; other schema drift still fails.
    paging_only = (set(spec.source_page_keys) - destination_set
                   - {spec.membership_key, spec.date_change} - policy.managed.all_fields)
    missing = sorted(expected_source - source_set)
    extra = sorted(source_set - expected_source - paging_only)
    if missing or extra:
        raise RuntimeError(
            f"integration SQL columns do not match {spec.target_relation}; "
            f"missing: {missing or '-'}; extra: {extra or '-'}"
        )
    if spec.membership_key not in source_set:
        raise RuntimeError("integration SQL membership key is not insertable into staging")
    insertable = policy.insert_columns(tuple(column for column in source if column not in paging_only))
    generated = {key: value for key, value in policy.generated_insert_values().items() if key in destination}
    columns = (*generated, *insertable)
    values = (*generated.values(), *(f"%({column})s" for column in insertable))
    updates = [f'"{column}" = EXCLUDED."{column}"' for column in policy.update_columns(insertable) if column != spec.membership_key]
    if "updated_at" in destination and not policy.copy_managed_fields:
        updates.append('"updated_at" = CURRENT_TIMESTAMP')
    if not updates:
        conflict = "DO NOTHING"
    else:
        conflict = "DO UPDATE SET " + ", ".join(updates)
        # The Python preflight/comparison gives useful diagnostics and avoids
        # unnecessary writes, but it cannot prevent a concurrent non-loader
        # writer from advancing the row between SELECT and INSERT.  Keep the
        # source-newer rule in the atomic conflict statement as the final
        # safety boundary so a page can never regress target data.
        if spec.date_change is not None and spec.date_change in insertable and spec.date_change in destination:
            target = f'"{spec.target_table}"."{spec.date_change}"'
            conflict += f' WHERE {target} IS NULL OR EXCLUDED."{spec.date_change}" > {target}'
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    return f"INSERT INTO {_quoted(spec.target_schema, spec.target_table)} ({quoted_columns}) VALUES ({', '.join(values)}) ON CONFLICT (\"{spec.membership_key}\") {conflict}"


def checked_upsert(cursor: Any, statement: str, rows: tuple[Mapping[str, Any], ...]) -> None:
    """Write a page, rejecting an atomic conditional-upsert no-op.

    The date-change predicate in ``ON CONFLICT`` is the final concurrent
    writer guard.  PostgreSQL reports rows skipped by that predicate through
    ``rowcount``; treating that as success would checkpoint a page whose
    source version was not applied.
    """
    if not rows:
        return
    cursor.executemany(statement, rows)
    if cursor.rowcount != len(rows):
        raise RuntimeError(
            "staging changed concurrently during conditional date_change upsert; "
            "page rolled back and was not checkpointed"
        )


def _write_source_rows(
    connection: Any, spec: TableSpec, statement: str,
    rows: tuple[Mapping[str, Any], ...], *, newer_error: str,
) -> None:
    """Select versions once, reject target-newer rows, then upsert changes."""
    rows_to_write = rows
    if spec.date_change is not None:
        existing = target_changes(
            connection, spec, [row[spec.membership_key] for row in rows],
        )
        newer = [
            row[spec.membership_key]
            for row in rows
            if row[spec.membership_key] in existing
            and existing[row[spec.membership_key]] is not None
            and row[spec.date_change] < existing[row[spec.membership_key]]
        ]
        if newer:
            raise RuntimeError(newer_error.format(change=spec.date_change, key=newer[0]))
        rows_to_write = tuple(
            row for row in rows
            if row[spec.membership_key] not in existing
            or existing[row[spec.membership_key]] is None
            or row[spec.date_change] > existing[row[spec.membership_key]]
        )
    with connection.cursor() as cursor:
        checked_upsert(cursor, statement, rows_to_write)


@dataclass(slots=True)
class KnStagingRun:
    """Small composition layer around :class:`PageRunner` for one table."""

    spec: TableSpec
    source_connection: Any
    destination_connection: Any
    source_sql: str
    page_size: int
    checkpoint_path: Any
    identity: RunIdentity
    run_context: Callable[[], Any]
    policy: InsertPolicy = InsertPolicy()
    interrupts: Any | None = None
    reconnect: Callable[[], None] | None = None
    is_reconnectable: Callable[[Exception], bool] | None = None
    page_sizer: PageSizer | None = None
    progress: Callable[[dict[str, Any]], None] | None = None

    def _shrink_page_for(self, error: Exception) -> bool:
        if self.page_sizer is None or not self.page_sizer.adaptive or not is_size_related_error(error):
            return False
        self.page_sizer.failed_for_size()
        return True

    def _source_page(self, after: tuple[Any, ...] | None, query_builder: Callable[[int], tuple[str, dict[str, Any]]], cursor_keys: tuple[str, ...]) -> Page[Mapping[str, Any]] | None:
        """Fetch one unchanged cursor with optional core size adaptation."""
        size = self.page_sizer.current if self.page_sizer is not None else self.page_size
        query, binds = query_builder(size)
        with self.source_connection.cursor() as cursor:
            cursor.execute(query, binds)
            names = tuple(_identifier(column[0]) for column in cursor.description)
            rows = tuple(dict(zip(names, row, strict=True)) for row in cursor.fetchall())
        if not rows:
            return None
        return Page(rows, tuple(rows[-1][key] for key in cursor_keys))

    def _generation_store(self, identity: RunIdentity) -> RunStore:
        return RunStore(self.checkpoint_path.with_suffix(".generation.sqlite3"), identity.fingerprint)

    def run_full(self, *, fresh: bool = False, context: Any | None = None) -> Any:
        statement: str | None = None
        payload_started = monotonic()
        payload_pages = 0
        payload_rows = 0

        def page_committed(page: Page[Mapping[str, Any]]) -> None:
            nonlocal payload_pages, payload_rows
            if self.page_sizer is not None:
                self.page_sizer.succeeded()
            payload_pages += 1
            payload_rows += len(page.rows)
            if self.progress is not None:
                elapsed = max(monotonic() - payload_started, 1e-9)
                self.progress({
                    "phase": "payload", "page": payload_pages,
                    "page_rows": len(page.rows), "rows": payload_rows,
                    "elapsed_seconds": elapsed, "rate": payload_rows / elapsed,
                    "eta_seconds": None,
                })

        def fetch(after: tuple[Any, ...] | None) -> Page[Mapping[str, Any]] | None:
            def query_builder(size: int) -> tuple[str, dict[str, Any]]:
                query, binds = keyset_query(self.source_sql, self.spec.source_page_keys, after)
                binds["page_size"] = size
                return query, binds
            return self._source_page(after, query_builder, self.spec.source_page_keys)

        def write(rows: tuple[Mapping[str, Any], ...]) -> None:
            assert statement is not None
            _write_source_rows(
                self.destination_connection, self.spec, statement, rows,
                newer_error="staging has newer {change} for source key {key!r}; full sync refuses to overwrite it",
            )

        @contextmanager
        def transaction() -> Iterable[Any]:
            with self.destination_connection.transaction():
                yield self.destination_connection

        store = self._generation_store(self.identity)

        def prepare(checkpoint: Checkpoint) -> Checkpoint:
            nonlocal statement
            source = source_columns(self.source_connection, self.source_sql)
            validate_selected_columns(
                source, self.spec, require_change=self.spec.date_change is not None,
            )
            destination = target_columns(self.destination_connection, self.spec)
            validate_target_membership_index(self.destination_connection, self.spec)
            statement = upsert_sql(self.spec, source, destination, self.policy)
            generation, stopped = materialize_source_membership(
                self.source_connection, self.source_sql, self.spec, self.page_size, store,
                fresh=fresh or (checkpoint.completed and not store.has_active_incomplete_generation()),
                interrupts=self.interrupts, include_change=self.spec.date_change is not None,
                page_sizer=self.page_sizer, progress=self.progress,
            )
            if stopped:
                if generation is not None:
                    generation.close()
                return None
            try:
                if generation is not None and self.spec.date_change is not None:
                    stopped = assert_target_not_newer(self.destination_connection, self.spec, generation, interrupts=self.interrupts)
            finally:
                if generation is not None:
                    generation.close()
            if stopped:
                return None
            self.destination_connection.commit()
            if checkpoint.completed:
                return Checkpoint(self.identity)
            return checkpoint

        return PageRunner(self.checkpoint_path, self.identity, fetch, write, transaction, self.run_context, prepare_checkpoint=prepare, reconnect=self.reconnect, is_reconnectable=self.is_reconnectable, interrupts=self.interrupts, on_page_committed=page_committed, on_page_size_error=(lambda error: self._shrink_page_for(error))).run(fresh=fresh, context=context)

    def run_only_new(self, *, fresh: bool = False) -> Any:
        """Materialize one frozen delta window, then apply it locally."""
        if self.spec.date_change is None:
            raise RuntimeError("only-new needs a date_change column")
        if self.spec.date_change in self.spec.source_page_keys:
            raise RuntimeError("only-new date_change must not also be a source_page_key")
        statement: str | None = None
        payload_started = monotonic()
        payload_pages = 0
        payload_rows = 0

        def page_committed(page: Page[Mapping[str, Any]]) -> None:
            nonlocal payload_pages, payload_rows
            if self.page_sizer is not None:
                self.page_sizer.succeeded()
            payload_pages += 1
            payload_rows += len(page.rows)
            if self.progress is not None:
                elapsed = max(monotonic() - payload_started, 1e-9)
                self.progress({
                    "phase": "payload", "page": payload_pages,
                    "page_rows": len(page.rows), "rows": payload_rows,
                    "elapsed_seconds": elapsed, "rate": payload_rows / elapsed,
                    "eta_seconds": None,
                })

        window: dict[str, tuple[Any, ...] | None] = {"lower": None, "upper": None}
        generation: dict[str, Any] = {"database": None}
        store = self._generation_store(self.identity)

        def prewrite(operation: Callable[[], Any]) -> Any:
            """Run only-new setup with an explicit safe failure boundary.

            PageRunner reconnects/retries actual pages.  Setup is intentionally
            not retried: it has no destination-page mutation and a rerun
            repeats its immutable source proof before publishing a new frozen
            watermark.  Retrying an unknown Oracle query here would obscure
            which preflight query was expensive or failed.
            """
            try:
                return operation()
            except Exception as error:
                if self.is_reconnectable is not None and self.is_reconnectable(error):
                    raise RuntimeError(
                        "only-new pre-write setup lost a connection; no staging page or new frozen watermark "
                        "was committed by this invocation, so rerun the command safely"
                    ) from error
                raise

        def prepare(checkpoint: Checkpoint) -> Checkpoint:
            nonlocal statement
            source = prewrite(lambda: source_columns(self.source_connection, self.source_sql))
            destination = prewrite(lambda: target_columns(self.destination_connection, self.spec))
            validate_selected_columns(source, self.spec, require_change=True)
            prewrite(lambda: validate_target_membership_index(self.destination_connection, self.spec))
            statement = upsert_sql(self.spec, source, destination, self.policy)
            self.destination_connection.commit()
            metadata = dict(checkpoint.metadata or {})
            stored = metadata.get("window_upper")
            lower: tuple[Any, ...] | None
            upper: tuple[Any, ...] | None
            freeze_new_upper = False
            if not checkpoint.completed and metadata:
                if not isinstance(stored, tuple) or len(stored) != len(self.identity.source_page_keys):
                    raise RuntimeError("only-new checkpoint has an invalid frozen upper watermark")
                upper = stored
                if "window_lower" in metadata:
                    declared_lower = metadata["window_lower"]
                    if declared_lower is not None and (
                        not isinstance(declared_lower, tuple)
                        or len(declared_lower) != len(self.identity.source_page_keys)
                    ):
                        raise RuntimeError("only-new checkpoint has an invalid frozen lower watermark")
                    lower = declared_lower
                elif metadata.get("initialized_only_new_bootstrap") is True and checkpoint.cursor is None:
                    lower = None
                else:
                    raise RuntimeError("only-new checkpoint is missing its frozen lower watermark")
            else:
                if not checkpoint.completed and checkpoint.cursor is not None:
                    raise RuntimeError("only-new checkpoint is missing its frozen window metadata")
                if checkpoint.cursor is None:
                    raise RuntimeError(
                        "--only-new needs a completed composite watermark; this version cannot safely bootstrap one "
                        "from legacy full-sync state. Run a full sync, then initialise a reviewed "
                        "(date_change, source page-key) watermark before using --only-new."
                    )
                lower = checkpoint.cursor
                # A crash may have persisted part of a newly frozen generation
                # before PageRunner published its window metadata. Reuse those
                # durable bounds instead of silently opening a different window.
                probe = store.open()
                try:
                    bounds = store.delta_bounds(probe)
                finally:
                    probe.close()
                if bounds is not None and bounds[0] == lower and not checkpoint.metadata:
                    upper = bounds[1]
                else:
                    upper = None
                    freeze_new_upper = True
            if freeze_new_upper:
                upper = prewrite(lambda: freeze_upper_watermark(
                    self.source_connection, self.source_sql, self.spec,
                ))
            if upper is None:
                window["upper"] = None
                return Checkpoint(self.identity, checkpoint.cursor, checkpoint.pages, checkpoint.rows, True, None)
            if lower is not None and upper <= lower:
                window["upper"] = upper
                return Checkpoint(self.identity, checkpoint.cursor, checkpoint.pages, checkpoint.rows, True, None)
            database, stopped = prewrite(lambda: materialize_delta_payload(
                self.source_connection, self.source_sql, self.spec, store,
                lower, upper, self.page_size, interrupts=self.interrupts,
                page_sizer=self.page_sizer, progress=self.progress,
            ))
            generation["database"] = database
            if stopped:
                database.close()
                generation["database"] = None
                return None
            window["lower"], window["upper"] = lower, upper
            apply_cursor = checkpoint.cursor if not checkpoint.completed else lower
            return Checkpoint(
                self.identity, apply_cursor,
                0 if checkpoint.completed else checkpoint.pages,
                0 if checkpoint.completed else checkpoint.rows,
                False, {"window_lower": lower, "window_upper": upper},
            )

        def fetch(after: tuple[Any, ...] | None) -> Page[Mapping[str, Any]] | None:
            database = generation["database"]
            if database is None:
                return None
            size = self.page_sizer.current if self.page_sizer is not None else self.page_size
            rows, next_cursor = RunStore.delta_page(database, after, size)
            return None if not rows else Page(rows, next_cursor or ())

        def write(rows: tuple[Mapping[str, Any], ...]) -> None:
            assert statement is not None
            _write_source_rows(
                self.destination_connection, self.spec, statement, rows,
                newer_error="staging has newer {change} for source key {key!r}; only-new refuses to overwrite it",
            )

        @contextmanager
        def transaction() -> Iterable[Any]:
            with self.destination_connection.transaction():
                yield self.destination_connection

        def complete(checkpoint: Checkpoint) -> Checkpoint:
            # Oracle is live: rows at the frozen upper bound can disappear
            # after page fetches. Completion still advances to that bound, so
            # a later window cannot skip unseen keys between the last fetched
            # row and the persisted upper cursor.
            upper = window["upper"]
            if upper is None:
                return checkpoint
            return Checkpoint(self.identity, upper, checkpoint.pages, checkpoint.rows, True, None)

        try:
            return PageRunner(self.checkpoint_path, self.identity, fetch, write, transaction, self.run_context, prepare_checkpoint=prepare, reconnect=self.reconnect, is_reconnectable=self.is_reconnectable, interrupts=self.interrupts, on_page_committed=page_committed, on_page_size_error=(lambda error: self._shrink_page_for(error)), complete_checkpoint=complete).run(fresh=fresh)
        finally:
            database = generation["database"]
            if database is not None:
                database.close()


def freeze_upper_watermark(connection: Any, source_sql: str, spec: TableSpec) -> tuple[Any, ...] | None:
    if spec.date_change is None:
        raise RuntimeError("--only-new requires TableSpec.date_change")
    with connection.cursor() as cursor:
        cursor.execute(upper_watermark_query(source_sql, spec.date_change, spec.source_page_keys))
        row = cursor.fetchone()
    if row is None:
        return None
    fields = (spec.date_change, *spec.source_page_keys)
    missing = ", ".join(field for field, value in zip(fields, row, strict=True) if value is None)
    if missing:
        raise RuntimeError(f"only-new source has NULL cursor component(s): {missing}")
    return tuple(row)
