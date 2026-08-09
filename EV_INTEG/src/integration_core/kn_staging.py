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
from typing import Any

from .managed import InsertPolicy
from .errors import is_size_related_error
from .page_size import PageSizer
from .runner import Page, PageRunner
from .run_store import RunStore
from .specs import TableSpec
from .state import Checkpoint, RunIdentity, read_checkpoint


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


def delta_query(
    source_sql: str,
    change_field: str,
    page_keys: tuple[str, ...],
    lower: tuple[Any, ...] | None,
    upper: tuple[Any, ...],
) -> tuple[str, dict[str, Any]]:
    """Build lower-exclusive / upper-inclusive composite watermark paging."""
    fields = (_identifier(change_field), *( _identifier(field) for field in page_keys))
    if len(upper) != len(fields):
        raise ValueError("upper watermark does not match change/page keys")
    clauses = [lexicographic_predicate(fields, "<=", "upper")]
    binds = {f"upper_{index}": value for index, value in enumerate(upper)}
    if lower is not None:
        if len(lower) != len(fields):
            raise ValueError("lower watermark does not match change/page keys")
        clauses.append(lexicographic_predicate(fields, ">", "after"))
        binds.update({f"after_{index}": value for index, value in enumerate(lower)})
    return (
        f"SELECT * FROM ({source_sql}) source_rows WHERE {' AND '.join(clauses)} "
        f"ORDER BY {', '.join(fields)} FETCH NEXT :page_size ROWS ONLY",
        binds,
    )


def upper_watermark_query(source_sql: str, change_field: str, page_keys: tuple[str, ...]) -> str:
    fields = (_identifier(change_field), *( _identifier(field) for field in page_keys))
    return f"SELECT {', '.join(fields)} FROM ({source_sql}) source_rows ORDER BY {', '.join(field + ' DESC' for field in fields)} FETCH FIRST 1 ROW ONLY"


def source_columns(connection: Any, source_sql: str) -> tuple[str, ...]:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM ({source_sql}) source_rows WHERE 1 = 0")
        return tuple(_identifier(column[0]) for column in cursor.description)


def validate_source_shape(connection: Any, source_sql: str, spec: TableSpec, *, require_change: bool) -> None:
    """Cheap structural validation for normal transfer runs."""
    columns = set(source_columns(connection, source_sql))
    required = {spec.membership_key, *spec.source_page_keys}
    if require_change and spec.date_change:
        required.add(spec.date_change)
    missing = sorted(required - columns)
    if missing:
        raise RuntimeError(f"integration SQL is missing required selected aliases: {', '.join(missing)}")

def prove_source_membership(connection: Any, source_sql: str, spec: TableSpec, *, include_change: bool) -> None:
    """Prove that source identities can safely drive a resumable run.

    ``--only-new`` pages by ``(date_change, *source_page_keys)``.  A unique,
    non-null native page tuple is deliberately a stronger requirement: it
    makes that composite cursor deterministic as well as making ordinary full
    keyset paging safe.
    """
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


def materialize_source_membership(connection: Any, source_sql: str, spec: TableSpec, page_size: int, store: RunStore, *, fresh: bool, interrupts: Any | None = None, include_change: bool = False, prove: bool = True) -> tuple[Any, bool]:
    """Build/reuse one durable source generation for full preflight/purge."""
    database = store.open(fresh=fresh)
    handed_to_caller = False
    try:
        if store.complete(database):
            handed_to_caller = True
            return database, False
        projection = tuple(dict.fromkeys((spec.membership_key, *((spec.date_change,) if include_change and spec.date_change else ()), *spec.source_page_keys)))
        after = store.cursor(database)
        if after is None:
            if prove:
                prove_source_membership(connection, source_sql, spec, include_change=include_change)
            store.begin(database)
        while True:
            query, binds = keyset_projection_query(source_sql, projection, spec.source_page_keys, after)
            binds["page_size"] = page_size
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


def materialize_source_changes(*args: Any, **kwargs: Any) -> tuple[Any, bool]:
    """Compatibility helper for checker/research tests; no destructive proof."""
    kwargs["prove"] = False
    kwargs["include_change"] = True
    return materialize_source_membership(*args, **kwargs)


def upsert_sql(spec: TableSpec, source: tuple[str, ...], destination: tuple[str, ...], policy: InsertPolicy = InsertPolicy()) -> str:
    selected = tuple(column for column in source if column in destination)
    if spec.membership_key not in selected:
        raise RuntimeError("integration SQL membership key is not insertable into staging")
    insertable = policy.insert_columns(selected)
    generated = {key: value for key, value in policy.generated_insert_values().items() if key in destination}
    columns = (*generated, *insertable)
    values = (*generated.values(), *(f"%({column})s" for column in insertable))
    updates = [f'"{column}" = EXCLUDED."{column}"' for column in policy.update_columns(insertable) if column != spec.membership_key]
    if "updated_at" in destination and not policy.copy_managed_fields:
        updates.append('"updated_at" = CURRENT_TIMESTAMP')
    conflict = "DO NOTHING" if not updates else "DO UPDATE SET " + ", ".join(updates)
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    return f"INSERT INTO {_quoted(spec.target_schema, spec.target_table)} ({quoted_columns}) VALUES ({', '.join(values)}) ON CONFLICT (\"{spec.membership_key}\") {conflict}"


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

    def _purge_identity(self, generation_identity: RunIdentity, generation_id: str) -> RunIdentity:
        return RunIdentity(
            self.identity.environment, self.identity.database, self.spec.target_schema, self.spec.target_table,
            self.spec.version, self.identity.sql_content, "purge", (self.spec.membership_key,),
            {"generation_fingerprint": generation_identity.fingerprint, "generation_id": generation_id},
        )

    def _purge_path(self, generation_id: str) -> Any:
        return self.checkpoint_path.with_name(f"purge-{generation_id}.json")

    def run_full_and_purge(self, *, fresh: bool = False) -> tuple[Any, Any | None]:
        """Run source collection, full upsert, and purge under one writer lock.

        If the upsert completed but its matching purge was interrupted, only
        purge resumes; a later completed invocation starts a new generation.
        """
        with self.run_context() as context:
            store = self._generation_store(self.identity)
            # A normal run must never overwrite a generation belonging to a
            # different SQL/spec identity.  ``--fresh`` is the one explicit
            # operator request that is allowed to replace that stale state.
            current = store.open(fresh=fresh, reset_on_mismatch=fresh)
            try:
                complete = store.complete(current)
                generation_id = RunStore.generation_id(current) if complete else None
            finally:
                current.close()
            full_checkpoint = read_checkpoint(self.checkpoint_path, self.identity, fresh=fresh)
            if complete and generation_id is not None and full_checkpoint.completed and not fresh:
                purge_identity = self._purge_identity(self.identity, generation_id)
                purge_checkpoint = read_checkpoint(self._purge_path(generation_id), purge_identity)
                if not purge_checkpoint.completed:
                    return full_checkpoint, self.run_purge_non_existent(generation_identity=self.identity, context=context)
            full = self.run_full(fresh=fresh, context=context)
            if full.stopped_by_signal:
                return full, None
            return full, self.run_purge_non_existent(generation_identity=self.identity, fresh=fresh, context=context)

    def run_full(self, *, fresh: bool = False, context: Any | None = None) -> Any:
        statement: str | None = None

        def fetch(after: tuple[Any, ...] | None) -> Page[Mapping[str, Any]] | None:
            def query_builder(size: int) -> tuple[str, dict[str, Any]]:
                query, binds = keyset_query(self.source_sql, self.spec.source_page_keys, after)
                binds["page_size"] = size
                return query, binds
            return self._source_page(after, query_builder, self.spec.source_page_keys)

        def write(rows: tuple[Mapping[str, Any], ...]) -> None:
            rows_to_write = rows
            if self.spec.date_change is not None:
                existing = target_changes(self.destination_connection, self.spec, [row[self.spec.membership_key] for row in rows])
                newer = [row[self.spec.membership_key] for row in rows if row[self.spec.membership_key] in existing and existing[row[self.spec.membership_key]] is not None and row[self.spec.date_change] < existing[row[self.spec.membership_key]]]
                if newer:
                    raise RuntimeError(f"staging has newer {self.spec.date_change} for source key {newer[0]!r}; full sync refuses to overwrite it")
                rows_to_write = tuple(row for row in rows if row[self.spec.membership_key] not in existing or existing[row[self.spec.membership_key]] is None or row[self.spec.date_change] > existing[row[self.spec.membership_key]])
            with self.destination_connection.cursor() as cursor:
                assert statement is not None
                cursor.executemany(statement, rows_to_write)

        @contextmanager
        def transaction() -> Iterable[Any]:
            with self.destination_connection.transaction():
                yield self.destination_connection

        store = self._generation_store(self.identity)

        def prepare(checkpoint: Checkpoint) -> Checkpoint:
            nonlocal statement
            source = source_columns(self.source_connection, self.source_sql)
            destination = target_columns(self.destination_connection, self.spec)
            validate_target_membership_index(self.destination_connection, self.spec)
            statement = upsert_sql(self.spec, source, destination, self.policy)
            generation, stopped = materialize_source_membership(
                self.source_connection, self.source_sql, self.spec, self.page_size, store,
                fresh=fresh or (checkpoint.completed and not store.has_active_incomplete_generation()),
                interrupts=self.interrupts, include_change=self.spec.date_change is not None,
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

        return PageRunner(self.checkpoint_path, self.identity, fetch, write, transaction, self.run_context, prepare_checkpoint=prepare, reconnect=self.reconnect, is_reconnectable=self.is_reconnectable, interrupts=self.interrupts, on_page_committed=(lambda _page: self.page_sizer.succeeded()) if self.page_sizer is not None else None, on_page_size_error=(lambda error: self._shrink_page_for(error))).run(fresh=fresh, context=context)

    def run_only_new(self, *, fresh: bool = False) -> Any:
        """Apply one frozen composite-watermark window idempotently.

        A completed checkpoint's cursor is the completed composite watermark.
        An incomplete checkpoint contains a frozen ``window_upper`` metadata
        value.  This makes retries use exactly the same source window.
        """
        if self.spec.date_change is None:
            raise RuntimeError("only-new needs a date_change column")
        statement: str | None = None

        window: dict[str, tuple[Any, ...] | None] = {"upper": None}

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
            prewrite(lambda: validate_source_shape(self.source_connection, self.source_sql, self.spec, require_change=True))
            prewrite(lambda: validate_target_membership_index(self.destination_connection, self.spec))
            # This happens before looking up/persisting a new upper watermark.
            # NULLS LAST cannot make a nullable or duplicate cursor correct:
            # it would only hide rows from a later keyset page.
            prewrite(lambda: prove_source_membership(self.source_connection, self.source_sql, self.spec, include_change=True))
            statement = upsert_sql(self.spec, source, destination, self.policy)
            self.destination_connection.commit()
            metadata = dict(checkpoint.metadata or {})
            stored = metadata.get("window_upper")
            if not checkpoint.completed and stored is not None:
                if not isinstance(stored, tuple) or len(stored) != len(self.identity.source_page_keys):
                    raise RuntimeError("only-new checkpoint has an invalid frozen upper watermark")
                window["upper"] = stored
                return checkpoint
            upper = prewrite(lambda: freeze_upper_watermark(self.source_connection, self.source_sql, self.spec))
            if upper is None:
                window["upper"] = None
                return Checkpoint(self.identity, checkpoint.cursor, checkpoint.pages, checkpoint.rows, True, None)
            if checkpoint.cursor is not None and upper <= checkpoint.cursor:
                window["upper"] = upper
                return Checkpoint(self.identity, checkpoint.cursor, checkpoint.pages, checkpoint.rows, True, None)
            window["upper"] = upper
            # A first only-new run deliberately begins at no lower watermark.
            # It can replay existing staging rows, but cannot lose rows merely
            # because target timestamp serialization differs from Oracle's.
            lower = checkpoint.cursor if checkpoint.completed else checkpoint.cursor
            return Checkpoint(self.identity, lower, 0 if checkpoint.completed else checkpoint.pages, 0 if checkpoint.completed else checkpoint.rows, False, {"window_upper": upper})

        def fetch(after: tuple[Any, ...] | None) -> Page[Mapping[str, Any]] | None:
            upper = window["upper"]
            if upper is None:
                return None
            def query_builder(size: int) -> tuple[str, dict[str, Any]]:
                page_query, page_binds = delta_query(self.source_sql, self.spec.date_change or "", self.spec.source_page_keys, after, upper)
                page_binds["page_size"] = size
                return page_query, page_binds
            return self._source_page(after, query_builder, (self.spec.date_change, *self.spec.source_page_keys))

        def write(rows: tuple[Mapping[str, Any], ...]) -> None:
            existing = target_changes(self.destination_connection, self.spec, [row[self.spec.membership_key] for row in rows])
            newer = [row[self.spec.membership_key] for row in rows if row[self.spec.membership_key] in existing and existing[row[self.spec.membership_key]] is not None and row[self.spec.date_change] < existing[row[self.spec.membership_key]]]
            if newer:
                raise RuntimeError(f"staging has newer {self.spec.date_change} for source key {newer[0]!r}; only-new refuses to overwrite it")
            rows = tuple(row for row in rows if row[self.spec.membership_key] not in existing or existing[row[self.spec.membership_key]] is None or row[self.spec.date_change] > existing[row[self.spec.membership_key]])
            with self.destination_connection.cursor() as cursor:
                assert statement is not None
                cursor.executemany(statement, rows)

        @contextmanager
        def transaction() -> Iterable[Any]:
            with self.destination_connection.transaction():
                yield self.destination_connection

        return PageRunner(self.checkpoint_path, self.identity, fetch, write, transaction, self.run_context, prepare_checkpoint=prepare, reconnect=self.reconnect, is_reconnectable=self.is_reconnectable, interrupts=self.interrupts, on_page_committed=(lambda _page: self.page_sizer.succeeded()) if self.page_sizer is not None else None, on_page_size_error=(lambda error: self._shrink_page_for(error))).run(fresh=fresh)

    def run_purge_non_existent(self, *, generation_identity: RunIdentity, fresh: bool = False, context: Any | None = None) -> Any:
        """Delete staging-only non-null membership keys from a complete source generation.

        SQLite is never attached to PostgreSQL: each bounded staging key page
        is checked against the complete durable generation, then only missing
        keys are deleted inside the page transaction.  Null staging keys are
        deliberately outside the keyset and are never deleted by this mode.
        """
        generation_store = self._generation_store(generation_identity)
        source = generation_store.open(reset_on_mismatch=False)
        try:
            if not generation_store.complete(source):
                raise RuntimeError("--purge-non-existant requires a complete EOF-marked source generation")
            generation_id = RunStore.generation_id(source)
        finally:
            source.close()
        destination = target_columns(self.destination_connection, self.spec)
        validate_target_membership_index(self.destination_connection, self.spec)
        self.destination_connection.commit()
        purge_identity = self._purge_identity(generation_identity, generation_id)
        purge_path = self._purge_path(generation_id)

        def fetch(after: tuple[Any, ...] | None) -> Page[Any] | None:
            condition, binds = "", ()
            if after is not None:
                condition, binds = f' AND "{self.spec.membership_key}" > %s', (after[0],)
            with self.destination_connection.cursor() as cursor:
                cursor.execute(
                    f'SELECT "{self.spec.membership_key}" FROM {_quoted(self.spec.target_schema, self.spec.target_table)} '
                    f'WHERE "{self.spec.membership_key}" IS NOT NULL{condition} ORDER BY "{self.spec.membership_key}" LIMIT %s',
                    (*binds, self.page_size),
                )
                rows = tuple(row[0] for row in cursor.fetchall())
            if not rows:
                return None
            return Page(rows, (rows[-1],))

        def write(rows: tuple[Any, ...]) -> None:
            generation = generation_store.open(reset_on_mismatch=False)
            try:
                source_keys = RunStore.contains(generation, list(rows))
            finally:
                generation.close()
            missing = [key for key in rows if key not in source_keys]
            if not missing:
                return
            with self.destination_connection.cursor() as cursor:
                cursor.execute(
                    f'DELETE FROM {_quoted(self.spec.target_schema, self.spec.target_table)} WHERE "{self.spec.membership_key}" = ANY(%s)',
                    (missing,),
                )

        @contextmanager
        def transaction() -> Iterable[Any]:
            with self.destination_connection.transaction():
                yield self.destination_connection

        return PageRunner(purge_path, purge_identity, fetch, write, transaction, self.run_context, reconnect=self.reconnect, is_reconnectable=self.is_reconnectable, interrupts=self.interrupts).run(fresh=fresh, context=context)


def freeze_upper_watermark(connection: Any, source_sql: str, spec: TableSpec) -> tuple[Any, ...] | None:
    if spec.date_change is None:
        raise RuntimeError("--only-new requires TableSpec.date_change")
    with connection.cursor() as cursor:
        cursor.execute(upper_watermark_query(source_sql, spec.date_change, spec.source_page_keys))
        row = cursor.fetchone()
    return tuple(row) if row is not None else None
