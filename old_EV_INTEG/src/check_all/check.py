#!/usr/bin/env python3
"""Read-only state checks for EV historical KN-to-LIFT integrations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "tables.json"
CACHE_PATH = HERE / ".state" / "data_correct.json"
REPORTS_DIR = HERE / "reports"
CACHE_VERSION = 2
SCHEMA = "public"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
# Do not ask python-oracledb to describe or fetch a TIMESTAMP WITH TIME ZONE.
# The KN JDBC integrations expose the three temporal fields as TSTZ; on some
# client/server version combinations their type descriptor raises ORA-01805.
# LIFT stores wall-clock PostgreSQL timestamps, so an ISO wall-clock string is
# also the value we need for the checker comparison.
ORACLE_TIMESTAMP_FORMAT = "YYYY-MM-DD\"T\"HH24:MI:SS.FF6"
# This is the documented integration output format.  It is deliberately kept
# separate from ORACLE_TIMESTAMP_FORMAT: the former includes an offset, while
# the latter is the wall-clock value compared with LIFT's timestamp column.
DOCUMENTED_ISO_TZ_FORMAT = "YYYY-MM-DD\"T\"HH24:MI:SS.FF TZH:TZM"


def quote(name: str) -> str:
    if not IDENT.fullmatch(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return f'"{name}"'


def relation(name: str) -> str:
    return f'{quote(SCHEMA)}.{quote(name)}'


def norm_name(value: str) -> str:
    return value.lower()


def clean_sql(sql: str) -> str:
    sql = sql.strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    if not re.match(r"^(select|with)\b", sql, re.I):
        raise RuntimeError("integration SQL must be a SELECT or WITH query")
    # Semicolons permit a second statement even if surrounded by comments.
    if ";" in sql:
        raise RuntimeError("integration SQL must contain exactly one statement")
    return sql


def uncomment(sql: str) -> str:
    return re.sub(r"/\*.*?\*/|--[^\n]*", " ", sql, flags=re.S | re.M)


def target_table(spec: dict[str, Any], environment: str) -> str:
    return spec["staging_table" if environment == "staging" else "prod_table"]


def sql_hash(value: str) -> str:
    return hashlib.sha256(" ".join(value.split()).encode()).hexdigest()


def manifest_hash(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("install requirements into .venv") from error
    load_dotenv(HERE / ".env", override=False)


def drivers() -> tuple[Any, Any]:
    try:
        import oracledb
        import psycopg
    except ImportError as error:
        raise RuntimeError("install requirements into .venv") from error
    return oracledb, psycopg


def oracle_settings(driver: Any) -> dict[str, Any]:
    required = ["KN_USER", "KN_PASSWORD", "KN_HOST", "KN_PORT", "KN_SERVICE"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("missing KN variables: " + ", ".join(missing))
    client = os.getenv("KN_ORACLE_CLIENT_LIB_DIR")
    if client:
        path = Path(client).expanduser()
        if not path.is_dir():
            raise RuntimeError(f"KN_ORACLE_CLIENT_LIB_DIR is not a directory: {path}")
        try:
            driver.init_oracle_client(lib_dir=str(path))
        except Exception as error:
            # Calling init once is safe; a different requested client is not.
            if "already initialized" not in str(error).lower():
                raise RuntimeError(f"could not initialise Oracle Thick mode: {error}") from error
    return {"user": os.environ["KN_USER"], "password": os.environ["KN_PASSWORD"],
            "dsn": driver.makedsn(os.environ["KN_HOST"], int(os.environ["KN_PORT"]), service_name=os.environ["KN_SERVICE"])}


def pg_settings(environment: str, *, metadata: bool = False) -> dict[str, Any]:
    prefix = "STAG" if environment == "staging" else "PROD"
    required = [f"{prefix}_{key}" for key in ("USER", "PASSWORD", "HOST", "PORT")]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"missing {environment} variables: " + ", ".join(missing))
    database_variable = f"{prefix}_{'METADATA_DATABASE' if metadata else 'DATABASE'}"
    default_database = "fmp" if metadata else "fmp_data_gurs"
    return {"user": os.environ[f"{prefix}_USER"], "password": os.environ[f"{prefix}_PASSWORD"],
            "host": os.environ[f"{prefix}_HOST"], "port": int(os.environ[f"{prefix}_PORT"]),
            "dbname": os.getenv(database_variable, default_database)}


def initialise_sessions(oracle: Any, *pg_connections: Any) -> None:
    """Fix both sides to the KN/LIFT business timezone before any query."""
    try:
        with oracle.cursor() as cur:
            cur.execute("ALTER SESSION SET TIME_ZONE = 'Europe/Ljubljana'")
        for pg in pg_connections:
            with pg.cursor() as cur:
                cur.execute("SET TIME ZONE 'Europe/Ljubljana'")
    except Exception as error:
        raise RuntimeError(f"could not set Oracle/PostgreSQL session timezone to Europe/Ljubljana: {error}") from error


def column_names(connection: Any, table: str) -> set[str]:
    with connection.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s", (SCHEMA, table))
        return {str(row[0]).lower() for row in cur.fetchall()}


def pick(columns: set[str], candidates: Iterable[str], label: str) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    raise RuntimeError(f"cannot find {label}; available columns: {', '.join(sorted(columns))}")


def rows_as_dicts(cursor: Any) -> list[dict[str, Any]]:
    names = [str(item[0]).lower() for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def metadata(connection: Any, table: str) -> dict[str, Any]:
    # `information_schema.columns` can be empty for a role that can query a
    # LIFT metadata relation through a view/role grant but cannot inspect its
    # columns there.  The metadata contract used by this checker is explicit,
    # so use it as a fallback and let the subsequent real query report an
    # actual missing relation/column precisely.
    ats = column_names(connection, "attribute_tables") or {"id", "name"}
    ais = column_names(connection, "attribute_table_integrations") or {
        "id", "attribute_table_id", "last_changed_datetime", "last_sync_start", "url",
        "attribute_table_sql_connection_id", "is_full_sync", "use_changed_datetime_for_delta",
    }
    acs = column_names(connection, "attribute_table_sql_connections") or {"id", "name"}
    table_name = pick(ats, ("name", "table_name"), "attribute table name column")
    sql_col = pick(ais, ("url", "sql", "select_sql", "integration_sql", "query", "source_sql"), "integration SQL column")
    connection_fk = pick(ais, ("attribute_table_sql_connection_id", "sql_connection_id"), "SQL connection id column")
    connection_name = pick(acs, ("name",), "SQL connection name column")
    required = {"id", "attribute_table_id", "last_changed_datetime", "last_sync_start"}
    if missing := required - ais:
        raise RuntimeError("attribute_table_integrations missing: " + ", ".join(sorted(missing)))
    with connection.cursor() as cur:
        cur.execute(f"SELECT id FROM {relation('attribute_tables')} WHERE {quote(table_name)}=%s", (table,))
        attributes = cur.fetchall()
        if len(attributes) != 1:
            raise RuntimeError(f"expected exactly one attribute_tables row named {table!r}; found {len(attributes)}")
        attribute_id = attributes[0][0]
        # DB-API parameters must always be a sequence.  The original
        # ``(attribute_id)`` was just a UUID value, causing psycopg to call
        # ``len()`` on it while processing query parameters.
        attribute_id_parameter = (attribute_id,)
        config_missing = [name for name in ("is_full_sync", "use_changed_datetime_for_delta") if name not in ais]
        full_sync = f"i.{quote('is_full_sync')}" if "is_full_sync" in ais else "NULL AS is_full_sync"
        use_changed = (f"i.{quote('use_changed_datetime_for_delta')}"
                       if "use_changed_datetime_for_delta" in ais else "NULL AS use_changed_datetime_for_delta")
        cur.execute(
            f"SELECT i.id, i.last_changed_datetime, i.last_sync_start, {full_sync}, {use_changed}, "
            f"i.{quote(sql_col)}, c.{quote(connection_name)} "
            f"FROM {relation('attribute_table_integrations')} i "
            f"LEFT JOIN {relation('attribute_table_sql_connections')} c ON c.id=i.{quote(connection_fk)} "
            "WHERE i.attribute_table_id=%s", attribute_id_parameter)
        integrations = cur.fetchall()
        # There must be one integration, but its connection is a *reported
        # metadata defect*, not a reason to hide independently verifiable
        # target/KN data state.  We can still execute its saved SQL against
        # KN for those checks.
        if len(integrations) != 1:
            raise RuntimeError(
                f"expected exactly one integration total for {table!r}; found "
                f"{len(integrations)} (connections: {[r[6] for r in integrations]!r})"
            )
        integration_id, highwater, last_sync_start, is_full_sync, use_changed_datetime, source_sql, conn_name = integrations[0]
        translations: list[Any] = []
        try:
            trans = column_names(connection, "attribute_table_translations")
            title = pick(trans, ("title", "name"), "translation title column")
            cur.execute(f"SELECT {quote(title)} FROM {relation('attribute_table_translations')} WHERE attribute_table_id=%s", attribute_id_parameter)
            translations = [row[0] for row in cur.fetchall()]
        except RuntimeError:
            raise
    return {"attribute_id": attribute_id, "integration_id": integration_id, "highwater": highwater, "last_sync_start": last_sync_start,
            "is_full_sync": is_full_sync, "use_changed_datetime_for_delta": use_changed_datetime,
            "configuration_errors": config_missing, "sql": source_sql, "connection_name": conn_name, "titles": translations}


def oracle_timestamp_text(expression: str, alias: str) -> str:
    """Project an Oracle DATE/TIMESTAMP/TSTZ as a safe ISO wall-clock string."""
    return f"TO_CHAR(CAST({expression} AS TIMESTAMP), '{ORACLE_TIMESTAMP_FORMAT}') AS {quote(alias)}"


def documented_text_temporal_aliases(sql: str, aliases: Iterable[str]) -> set[str]:
    """Return documented ISO-TZ temporal aliases that are already VARCHAR2.

    Integrations may use the project-standard ``TO_CHAR(FROM_TZ(...),
    'YYYY-MM-DD\"T\"HH24:MI:SS.FF TZH:TZM') AS date_change`` form.  Applying
    ``CAST(alias AS TIMESTAMP)`` to that text relies on Oracle's NLS parsing
    settings, so keep it as text until Python normalises it.
    """
    source = uncomment(sql)
    matched: set[str] = set()
    format_pattern = re.escape(DOCUMENTED_ISO_TZ_FORMAT)
    for alias in aliases:
        # Non-greedy matching lets the expression contain nested calls such as
        # FROM_TZ(CAST(...), 'Europe/Ljubljana').  The exact format literal
        # keeps this limited to the documented ISO-TZ output contract.
        pattern = (
            rf"\bto_char\s*\(.*?,\s*'{format_pattern}'\s*\)\s*"
            rf"(?:as\s+)?\"?{re.escape(alias)}\"?(?![A-Za-z0-9_$])"
        )
        if re.search(pattern, source, flags=re.I | re.S):
            matched.add(alias.lower())
    return matched


def safe_validation_sql(sql: str, required: list[str], text_temporal_aliases: set[str] | None = None) -> str:
    """Describe required integration aliases without exposing TSTZ to the driver.

    Oracle resolves every quoted reference in this zero-row projection, so a
    missing required alias still produces the expected ORA-00904 validation
    error.  The temporal aliases are converted inside Oracle before the
    driver receives their metadata.
    """
    temporal = {"date_change", "valid_from", "valid_to"}
    text_temporal_aliases = text_temporal_aliases or set()
    projections = []
    # A single-column native page key is often the destination PK.  Project
    # it once; duplicate aliases in Oracle's derived table are ambiguous.
    for name in dict.fromkeys(required):
        source = f"q.{quote(name.upper())}"
        projections.append(
            oracle_timestamp_text(source, name.upper()) if name.lower() in temporal and name.lower() not in text_temporal_aliases
            else f"{source} AS {quote(name.upper())}"
        )
    return f"SELECT {', '.join(projections)} FROM ({sql}) q WHERE 1 = 0"


def describe_output_aliases(oracle: Any, sql: str, aliases: list[str], temporal_aliases: set[str]) -> tuple[dict[str, str], str | None]:
    """Safely prove that a specific set of integration output aliases exists."""
    try:
        with oracle.cursor() as cur:
            cur.execute(safe_validation_sql(sql, aliases, temporal_aliases))
            return ({str(column[0]).lower(): str(column[0]) for column in cur.description}, None)
    except Exception as error:
        return {}, str(error)


def data_output_aliases(oracle: Any, sql: str, spec: dict[str, Any], output: dict[str, str]) -> tuple[dict[str, str] | None, str | None]:
    """Return the aliases needed for comparison, independently of full spec checks."""
    required = list(dict.fromkeys([spec["pk"], "date_change", *spec["source_page_keys"]]))
    if all(name.lower() in output for name in required):
        return ({name.lower(): output[name.lower()] for name in required}, None)
    temporal = documented_text_temporal_aliases(sql, {"date_change"})
    verified, error = describe_output_aliases(oracle, sql, required, temporal)
    if error:
        return None, f"cannot validate data-critical output aliases: {error}"
    missing = [name for name in required if name.lower() not in verified]
    if missing:
        return None, "missing data-critical output alias(es): " + ", ".join(missing)
    return verified, None


def validate_sql(oracle: Any, sql: str, spec: dict[str, Any]) -> tuple[str, dict[str, str], list[str]]:
    sql = clean_sql(str(sql or ""))
    lower = uncomment(sql).lower()
    failures: list[str] = []
    if not re.search(rf"\b\"?ev\"?\s*\.\s*\"?{re.escape(spec['kn_table'].lower())}\"?\b", lower):
        failures.append(f"does not reference EV.{spec['kn_table']}")
    if spec.get("requires_jn_status") and not re.search(r"jn_status\"?\s*(?:!=|<>)\s*'x'", lower):
        failures.append("does not exclude JN_STATUS = 'X'")
    if spec.get("requires_jn_status") and not re.search(r"\b(revision|rev_num)\b", lower):
        failures.append("does not contain revision history join")
    if spec.get("from_2025") and not re.search(r"rf\s*\.\s*\"?created\"?\s*>=\s*timestamp\s*'2025-01-01\s+00:00:00'", lower):
        failures.append("does not contain required rf.created >= TIMESTAMP '2025-01-01 00:00:00' filter")
    if spec.get("forbid_podatki"):
        # Match an actual column token, not strings such as
        # DST_PRIPIS_PODATKI or dst_pripis_podatki_pk.  Only the two split
        # ENOTA integrations are required to omit this payload attribute.
        if re.search(r"(?:\.\s*|\b)(?:\"podatki\"|podatki)\b", lower):
            failures.append("references forbidden PODATKI column")
    required = [spec["pk"], "date_change", "valid_from", "valid_to", *spec["source_page_keys"]]
    if spec.get("requires_jn_status"):
        required.append("jn_status")
    text_temporal_aliases = documented_text_temporal_aliases(sql, {"date_change", "valid_from", "valid_to"})
    output, error = describe_output_aliases(oracle, sql, required, text_temporal_aliases)
    if error:
        failures.append(f"cannot validate required integration output aliases: {error}")
    for name in required:
        if name.lower() not in output:
            failures.append(f"missing output alias {name}")
    if spec.get("forbid_podatki") and "podatki" in output:
        failures.append("forbidden output alias podatki")
    return sql, output, failures


def normalize(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        # KN exposes Ljubljana wall-clock timestamps while LIFT uses PG
        # ``timestamp``.  This matches the existing synchroniser contract.
        if value.tzinfo:
            value = value.replace(tzinfo=None)
        return value.isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, str):
        candidate = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo:
                parsed = parsed.replace(tzinfo=None)
            return parsed.isoformat(timespec="microseconds")
        except ValueError:
            pass
    return str(value)


def optional_bool(value: Any) -> bool | None:
    """Return a PostgreSQL boolean, accepting drivers that return 0/1/text."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        parsed = value.strip().lower()
        if parsed in {"true", "t", "1"}:
            return True
        if parsed in {"false", "f", "0"}:
            return False
    return None


def integration_start_time() -> datetime:
    """Return the one Ljubljana wall-clock upper bound for this checker run.

    LIFT stores ``timestamp`` values and the KN queries are compared as
    Ljubljana wall-clock timestamps, so deliberately pass a naïve value to
    Oracle rather than an instant with an offset.
    """
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Europe/Ljubljana")).replace(tzinfo=None)


def cache_read() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"version": CACHE_VERSION, "entries": {}}
    try:
        result = json.loads(CACHE_PATH.read_text())
        if result.get("version") != CACHE_VERSION or not isinstance(result.get("entries"), dict):
            raise ValueError
        return result
    except (OSError, ValueError, json.JSONDecodeError):
        return {"version": CACHE_VERSION, "entries": {}}


def cache_write(value: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".data_correct.", dir=CACHE_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, CACHE_PATH)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def size_relevant_oracle_failure(error: Exception) -> bool:
    text = str(error).lower()
    # Transport failures do not indicate that a smaller result page helps.
    if any(token in text for token in ("connection", "network", "lost contact", "dpy-6005", "ora-125", "ssh")):
        return False
    return any(token in text for token in (
        "timeout", "timed out", "out of memory", "memory", "array", "buffer", "resource",
        "ora-04030", "ora-04031", "ora-01000",
    ))


def format_duration(seconds: float) -> str:
    return f"{int(seconds // 3600)}:{int(seconds % 3600 // 60):02d}:{int(seconds % 60):02d}"


def heartbeat(message: str) -> None:
    """Emit immediately so long KN checks remain visibly alive."""
    print(message, flush=True)


def oracle_count(oracle: Any, sql: str) -> int:
    with oracle.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM ({sql}) q")
        return int(cur.fetchone()[0])


def oracle_distinct_pk_count(oracle: Any, sql: str, source_pk: str) -> int:
    """Prove the KN result has one non-null destination PK per source row.

    Paged checks alone only see duplicate keys within one page.  This bounded
    aggregate makes equal source/target counts meaningful: once every source
    key is unique, successful page lookups prove exact PK membership too.
    """
    with oracle.cursor() as cur:
        cur.execute(f"SELECT COUNT(DISTINCT {quote(source_pk)}) FROM ({sql}) q")
        return int(cur.fetchone()[0])


def pg_count(pg: Any, table: str) -> int:
    with pg.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {relation(table)}")
        return int(cur.fetchone()[0])


def table_exists(pg: Any, table: str) -> bool:
    with pg.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"{SCHEMA}.{table}",))
        return cur.fetchone()[0] is not None


def has_unique_pk_index(pg: Any, table: str, key: str) -> bool:
    """Accept a valid single-column UNIQUE constraint or equivalent index."""
    sql = """
        SELECT 1
        FROM pg_index i
        JOIN pg_class table_rel ON table_rel.oid = i.indrelid
        JOIN pg_namespace namespace ON namespace.oid = table_rel.relnamespace
        JOIN pg_class index_rel ON index_rel.oid = i.indexrelid
        WHERE namespace.nspname = %s
          AND table_rel.relname = %s
          AND i.indisunique AND i.indisvalid AND i.indisready AND i.indpred IS NULL
          AND index_rel.relam = (SELECT oid FROM pg_am WHERE amname = 'btree')
          AND (
              SELECT array_agg(attribute.attname ORDER BY indexed.ordinality)
              FROM unnest(i.indkey) WITH ORDINALITY indexed(attnum, ordinality)
              JOIN pg_attribute attribute
                ON attribute.attrelid = table_rel.oid AND attribute.attnum = indexed.attnum
              WHERE indexed.ordinality <= i.indnkeyatts
          ) = ARRAY[%s]::name[]
        LIMIT 1
    """
    with pg.cursor() as cur:
        cur.execute(sql, (SCHEMA, table, key))
        return cur.fetchone() is not None


def keyset_predicate(keys: list[str]) -> str:
    parts = []
    for index, key in enumerate(keys):
        equal = " AND ".join(f"{quote(keys[before])} = :after_{before}" for before in range(index))
        condition = f"{quote(key)} > :after_{index}"
        parts.append(f"({equal} AND {condition})" if equal else f"({condition})")
    return " OR ".join(parts)


def page_sql(sql: str, source_pk: str, source_date: str, page_keys: list[str], after: tuple[Any, ...] | None, *, date_is_text: bool = False) -> str:
    date_column = quote(source_date) if date_is_text else oracle_timestamp_text(quote(source_date), "__CHECK_DATE_CHANGE")
    # A direct source ID is often both the destination membership PK and the
    # native page key.  Oracle rejects the resulting duplicate output name in
    # a derived SELECT, so page keys always receive private checker aliases.
    page_columns = [f'{quote(key)} AS {quote(f"__CHECK_PAGE_{index}")}' for index, key in enumerate(page_keys)]
    columns = ", ".join([quote(source_pk), date_column, *page_columns])
    where = "" if after is None else " WHERE " + keyset_predicate(page_keys)
    return f"SELECT {columns} FROM ({sql}) q{where} ORDER BY {', '.join(map(quote, page_keys))} FETCH NEXT :limit ROWS ONLY"


class PageSizer:
    """Find a safe page size without moving the source keyset cursor."""

    def __init__(self, initial: int, maximum: int, constant: int | None = None):
        self.maximum = maximum
        self.constant = constant
        self.current = constant if constant is not None else initial
        self.phase = "constant" if constant is not None else "growing"
        self.lower: int | None = None
        self.upper: int | None = None
        self.bisections = 0

    @property
    def adaptive(self) -> bool:
        return self.constant is None

    @property
    def stable(self) -> bool:
        return self.phase in {"constant", "stable"}

    def _begin_refinement(self) -> None:
        self.phase = "refining"
        self.bisections = 0
        self._next_bisection()

    def _next_bisection(self) -> None:
        assert self.lower is not None and self.upper is not None
        if self.bisections >= 3 or self.upper - self.lower <= 1:
            self.current = self.lower
            self.phase = "stable"
        else:
            self.current = (self.lower + self.upper) // 2

    def succeeded(self) -> bool:
        """Record a successful fetch; return whether its rows may be processed."""
        if self.phase in {"constant", "stable"}:
            return True
        if self.phase == "growing":
            self.lower = self.current
            if self.current >= self.maximum:
                self.phase = "stable"
            else:
                self.current = min(self.maximum, self.current * 2)
            return True
        if self.phase == "shrinking":
            self.lower = self.current
            self._begin_refinement()
            return False
        assert self.phase == "refining"
        self.lower = self.current
        self.bisections += 1
        self._next_bisection()
        return False

    def failed(self) -> None:
        """Record a size failure and select a smaller/reﬁnement probe."""
        if self.phase == "constant":
            raise RuntimeError(f"constant page size {self.current} failed")
        if self.phase == "stable":
            # A previously working size is no longer trustworthy.  Treat it
            # as failed and re-discover a safe lower bound below it.
            self.lower = None
            self.upper = self.current
            self.phase = "shrinking"
            self.current = max(1, self.current // 2)
            return
        if self.phase == "growing":
            self.upper = self.current
            if self.lower is None:
                self.phase = "shrinking"
                self.current = max(1, self.current // 2)
            else:
                self._begin_refinement()
            return
        if self.phase == "shrinking":
            # A lower failure invalidates all former larger successes.
            self.lower = None
            self.upper = self.current
            if self.current == 1:
                raise RuntimeError("page size 1 failed; no safe page size exists")
            self.current = max(1, self.current // 2)
            return
        assert self.phase == "refining"
        self.upper = self.current
        self.bisections += 1
        self._next_bisection()

    def description(self) -> str:
        bounds = ""
        if self.lower is not None or self.upper is not None:
            bounds = f"; working/failing bounds {self.lower}/{self.upper}"
        return f"{self.phase} page size {self.current}{bounds}"


def diff_data(oracle: Any, pg: Any, sql: str, spec: dict[str, Any], source_output: dict[str, str], initial_page_size: int, expected_count: int, max_page_size: int | None = None, constant_page_size: int | None = None) -> tuple[bool, str | None]:
    pk = spec["pk"].lower(); after: tuple[Any, ...] | None = None; seen = 0
    source_keys = [source_output[key.lower()] for key in spec["source_page_keys"]]
    date_is_text = "date_change" in documented_text_temporal_aliases(sql, {"date_change"})
    max_page_size = max_page_size or initial_page_size
    sizer = PageSizer(initial_page_size, max_page_size, constant_page_size)
    page = 0; started = time.monotonic(); full_page_seconds: list[float] = []
    while True:
        page += 1
        while True:
            current_size = sizer.current
            heartbeat(f"[{spec['table']}] heartbeat: fetching KN data-diff page {page} (checked {seen}/{expected_count} rows; {sizer.description()})")
            page_started = time.monotonic()
            try:
                with oracle.cursor() as cur:
                    params = {"limit": current_size}
                    if after is not None: params.update({f"after_{index}": value for index, value in enumerate(after)})
                    cur.execute(page_sql(sql, source_output[pk], source_output["date_change"], source_keys, after, date_is_text=date_is_text), params)
                    rows = cur.fetchall()
                page_seconds = time.monotonic() - page_started
            except Exception as error:
                if not sizer.adaptive or not size_relevant_oracle_failure(error):
                    raise
                sizer.failed()
                heartbeat(f"[{spec['table']}] KN page read failed at {current_size}: {error}; retrying the same cursor with {sizer.description()}")
                continue
            if sizer.succeeded():
                break
            heartbeat(f"[{spec['table']}] successful sizing probe at {current_size}; next probe uses {sizer.description()} on the same cursor")
        if not rows:
            heartbeat(f"[{spec['table']}] data-diff fetch complete ({seen}/{expected_count} rows)")
            return (seen == expected_count, None if seen == expected_count else f"KN scan count {seen} != COUNT(*) {expected_count}")
        keys = [row[0] for row in rows]
        tuples = [tuple(row[2:]) for row in rows]
        if any(key is None for key in keys) or len(set(map(str, keys))) != len(keys):
            return False, "KN query has null or duplicate PK in a page"
        if any(any(value is None for value in item) for item in tuples) or len(set(tuples)) != len(tuples):
            return False, "KN query has null or duplicate native page tuple"
        with pg.cursor() as cur:
            cur.execute(f"SELECT {quote(pk)}, {quote('date_change')} FROM {relation(spec['table'])} WHERE {quote(pk)} = ANY(%s)", (keys,))
            target_rows = cur.fetchall(); target: dict[str, str | None] = {}
            for row in target_rows:
                key = str(row[0])
                if key in target: return False, f"target has duplicate PK {key!r}"
                target[key] = normalize(row[1])
        for row in rows:
            key, changed = row[0], row[1]
            expected = normalize(changed)
            actual = target.get(str(key))
            if actual is None and str(key) not in target:
                return False, f"missing target PK {key!r}"
            if expected is None or actual is None:
                return False, f"null date_change for PK {key!r}"
            if expected != actual:
                return False, f"date_change mismatch for PK {key!r}: KN={expected}, target={actual}"
        seen += len(rows); after = tuples[-1]
        elapsed = time.monotonic() - started
        rate = len(rows) / page_seconds if page_seconds else 0
        remaining = max(0, expected_count - seen)
        eta = format_duration((remaining / rate) if rate else 0)
        heartbeat(f"[{spec['table']}] checked data-diff page {page} ({len(rows)} rows; total {seen}/{expected_count}; page size {current_size}; {rate:,.0f} rows/s; elapsed {format_duration(elapsed)}; ETA {eta})")
        if len(rows) == current_size:
            full_page_seconds.append(page_seconds / len(rows))
            if len(full_page_seconds) >= 6:
                baseline = sorted(full_page_seconds[:-3])[len(full_page_seconds[:-3]) // 2]
                if baseline > 0 and all(value >= baseline * 2 for value in full_page_seconds[-3:]):
                    return False, "stopped after three sustained 2x-per-row slowdowns; rerun after investigating"
        if len(rows) < current_size:
            return (
                seen == expected_count,
                None if seen == expected_count else f"KN scan count {seen} != COUNT(*) {expected_count}",
            )


def highwater_and_delta(
    pg: Any,
    oracle: Any,
    sql: str,
    spec: dict[str, Any],
    source_output: dict[str, str],
    highwater: Any,
    last_sync_start: Any,
    is_full_sync: bool | None,
    use_changed_datetime_for_delta: bool | None,
    check_started_at: datetime | None = None,
) -> tuple[bool, str, int | None, str, int | None, str]:
    """Check high-water equality, inclusive LIFT preview, and strict freshness."""
    check_started_at = check_started_at or integration_start_time()
    with pg.cursor() as cur:
        cur.execute(f"SELECT MAX({quote('date_change')}) FROM {relation(spec['table'])}")
        maximum = cur.fetchone()[0]
    highwater_ok = normalize(maximum) == normalize(highwater)
    highwater_detail = (
        "ok" if highwater_ok else
        f"target MAX(date_change)={normalize(maximum)} != integration last_changed_datetime={normalize(highwater)}"
    )
    if is_full_sync is None or use_changed_datetime_for_delta is None:
        detail = "cannot determine LIFT delta filter: integration configuration is unavailable"
        return highwater_ok, highwater_detail, None, detail, None, detail

    # LIFT ignores both dates for a first/full run.  Checking COUNT(*) rather
    # than only non-null date_change mirrors that behaviour exactly.
    if last_sync_start is None or is_full_sync:
        with oracle.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM ({sql}) q")
            candidates = int(cur.fetchone()[0])
        reason = "last_sync_start is NULL" if last_sync_start is None else "is_full_sync is true"
        detail = (
            f"ok ({reason}; source is empty)" if candidates == 0 else
            f"{candidates} KN rows would transfer because {reason}"
        )
        return highwater_ok, highwater_detail, candidates, detail, candidates, detail

    with oracle.cursor() as cur:
        # LIFT stores a naïve PostgreSQL timestamp; KN's FROM_TZ output is a
        # TSTZ. Cast to TIMESTAMP so this uses the same Ljubljana wall-clock
        # contract as normalize()/the data comparison.
        source_date = quote(source_output["date_change"])
        if "date_change" in documented_text_temporal_aliases(sql, {"date_change"}):
            source_date = f"CAST(TO_TIMESTAMP_TZ({source_date}, '{DOCUMENTED_ISO_TZ_FORMAT}') AS TIMESTAMP)"
        else:
            source_date = f"CAST({source_date} AS TIMESTAMP)"
        minimum = highwater if use_changed_datetime_for_delta and highwater is not None else last_sync_start
        bound_name = "last_changed_datetime" if use_changed_datetime_for_delta and highwater is not None else "last_sync_start"
        cur.execute(
            f"SELECT COUNT(*) FROM ({sql}) q WHERE {source_date} >= :minimum "
            f"AND {source_date} <= :integration_start",
            {"minimum": minimum, "integration_start": check_started_at},
        )
        current_candidates = int(cur.fetchone()[0])
        cur.execute(f"SELECT COUNT(*) FROM ({sql}) q WHERE {source_date} > :minimum", {"minimum": minimum})
        newer_candidates = int(cur.fetchone()[0])
    preview_detail = (
        f"0 rows match LIFT's inclusive {bound_name} predicate through {normalize(check_started_at)}"
        if current_candidates == 0 else
        f"{current_candidates} rows match LIFT's inclusive {bound_name} predicate through {normalize(check_started_at)} (boundary replay and/or newer data)"
    )
    newer_detail = (
        f"0 KN rows are strictly newer than {bound_name}"
        if newer_candidates == 0 else
        f"{newer_candidates} KN rows are strictly newer than {bound_name}"
    )
    return highwater_ok, highwater_detail, current_candidates, preview_detail, newer_candidates, newer_detail


def markdown(results: list[dict[str, Any]], environment: str) -> str:
    lines = [
        f"# EV integration state check ({environment})", "",
        "| Table | Table presence | Unique constraint | Integration SQL correctness | Integration metadata correctness | LIFT name correctness | Data | High-water | LIFT delta preview | Changes after high-water | Result |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in results:
        lines.append("| {table} | {table_presence} | {unique_constraint} | {integration_sql} | {integration_metadata} | {lift_name} | {data} | {highwater} | {lift_preview} | {changes_after_highwater} | **{result}** |".format(**item))
    lines += ["", "## Details", ""]
    for item in results:
        lines += [f"### {item['table']}", "", f"- {item['detail']}"]
    lines += [
        "", "## Column explanations", "",
        "| Column | Explanation |",
        "|---|---|",
        "| Table | Target EV table checked in the selected environment. |",
        "| Table presence | `PASS` when the expected `public` target table exists. |",
        "| Unique constraint | `PASS` when the manifest PK has a valid, ready, non-partial single-column unique btree index or constraint. |",
        "| Integration SQL correctness | Validates KN SQL structure, required output aliases, revision/date fields, required `JN_STATUS <> 'X'` filter, split-table date filter, and excluded `PODATKI` where applicable. |",
        "| Integration metadata correctness | Requires one integration using `KN ORACLE`, a non-null last sync start, `is_full_sync=false`, and `use_changed_datetime_for_delta=true`. |",
        "| LIFT name correctness | `PASS` when every LIFT translation title starts with `EV H`. |",
        "| Data | KN and target row count, PK membership, and `date_change` match. `CACHED` means the matching PK/date scan from the unchanged query/manifest was reused. |",
        "| High-water | Target `MAX(date_change)` equals LIFT `last_changed_datetime`. |",
        "| LIFT delta preview | Rows selected by LIFT's inclusive lower bound through the checker start. `INFO (N)` is expected boundary replay and does not fail the result. |",
        "| Changes after high-water | KN rows with `date_change > last_changed_datetime`; any such rows fail the result. |",
        "| Result | `PASS` only when every required check passes; the informational delta preview does not affect it. |",
        "",
    ]
    return "\n".join(lines)


def write_report(path: Path, results: list[dict[str, Any]], environment: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown(results, environment), encoding="utf-8")


def finalise_result(result: dict[str, Any]) -> dict[str, Any]:
    required = (
        "table_presence", "unique_constraint", "integration_sql", "integration_metadata",
        "lift_name", "data", "highwater", "changes_after_highwater",
    )
    result["result"] = "PASS" if all(result[name] in {"PASS", "CACHED"} for name in required) else "FAIL"
    return result


def check_one(target_pg: Any, metadata_pg: Any, oracle: Any, spec: dict[str, Any], environment: str, cache: dict[str, Any], refresh: bool, initial_page_size: int, mhash: str, check_started_at: datetime | None = None, *, max_page_size: int | None = None, constant_page_size: int | None = None) -> dict[str, Any]:
    table = target_table(spec, environment); local = {**spec, "table": table}
    check_started_at = check_started_at or integration_start_time()
    result = {
        "table": table, "table_presence": "FAIL", "unique_constraint": "NOT_CHECKED",
        "integration_sql": "NOT_CHECKED", "integration_metadata": "NOT_CHECKED",
        "lift_name": "NOT_CHECKED", "data": "NOT_CHECKED", "highwater": "NOT_CHECKED",
        "lift_preview": "NOT_CHECKED", "changes_after_highwater": "NOT_CHECKED",
        "result": "FAIL", "detail": "",
    }
    try:
        heartbeat(f"[{table}] heartbeat: checking target table presence and unique PK index")
        present = table_exists(target_pg, table)
        result["table_presence"] = "PASS" if present else "FAIL"
        detail_parts: list[str] = []
        if not present:
            detail_parts.append(f"target table {SCHEMA}.{table} does not exist")
        else:
            unique = has_unique_pk_index(target_pg, table, spec["pk"])
            result["unique_constraint"] = "PASS" if unique else "FAIL"
            if not unique:
                detail_parts.append(f"missing valid non-partial single-column unique index/constraint on {spec['pk']}")

        heartbeat(f"[{table}] heartbeat: resolving LIFT metadata and validating KN SQL")
        try:
            info = metadata(metadata_pg, table)
        except Exception as error:
            result["integration_metadata"] = "FAIL"
            detail_parts.append(str(error))
            result["detail"] = "; ".join(detail_parts)
            return finalise_result(result)

        sql, output, sql_failures = validate_sql(oracle, info["sql"], local)
        result["integration_sql"] = "PASS" if not sql_failures else "FAIL"
        detail_parts.extend(sql_failures)
        title_bad = not info["titles"] or any(not str(title or "").startswith("EV H") for title in info["titles"])
        result["lift_name"] = "FAIL" if title_bad else "PASS"
        if title_bad:
            detail_parts.append(f"titles must all start with EV H; got {info['titles']!r}")

        metadata_failures: list[str] = []
        if str(info["connection_name"] or "").upper() != "KN ORACLE": metadata_failures.append("integration connection is not KN ORACLE")
        config_errors = list(info.get("configuration_errors", []))
        full_sync = optional_bool(info.get("is_full_sync"))
        use_changed = optional_bool(info.get("use_changed_datetime_for_delta"))
        if config_errors:
            metadata_failures.append("integration configuration column(s) unavailable: " + ", ".join(config_errors))
        if full_sync is None:
            metadata_failures.append("is_full_sync must be a non-null boolean")
        elif full_sync:
            metadata_failures.append("is_full_sync must be false; this checker requires a delta integration")
        if use_changed is None:
            metadata_failures.append("use_changed_datetime_for_delta must be a non-null boolean")
        if info["last_sync_start"] is None:
            metadata_failures.append("last_sync_start is NULL; LIFT would run a full integration and ignore the delta high-water mark")
        result["integration_metadata"] = "PASS" if not metadata_failures else "FAIL"
        detail_parts.extend(metadata_failures)
        # Full validation includes presentation/spec fields such as JN_STATUS
        # and valid_from.  Comparison needs only PK/date/page tuple.  Retry a
        # minimal, zero-row projection when the full projection failed.
        data_output, data_output_error = data_output_aliases(oracle, sql, local, output)
        if data_output is None:
            result["integration_sql"] = "FAIL"
            detail_parts.append(data_output_error or "data aliases unavailable")
        if not present or data_output is None:
            result["detail"] = "; ".join(detail_parts)
            return finalise_result(result)
        identity = hashlib.sha256(json.dumps({
            "env": environment, "table": table, "integration": str(info["integration_id"]),
            "sql": sql_hash(sql), "manifest": mhash, "pk": spec["pk"],
            "date_change": "date_change", "source_page_keys": spec["source_page_keys"],
        }, sort_keys=True).encode()).hexdigest()
        entry = cache["entries"].get(identity, {})
        kn_count = entry.get("kn_count")
        if kn_count is None or refresh:
            heartbeat(f"[{table}] heartbeat: counting KN source rows")
            kn_count = oracle_count(oracle, sql); entry["kn_count"] = kn_count
            heartbeat(f"[{table}] KN count complete: {kn_count} rows")
        else:
            heartbeat(f"[{table}] checkpoint: reusing cached KN count {kn_count}")
        heartbeat(f"[{table}] heartbeat: counting target rows")
        target_count = pg_count(target_pg, table)
        heartbeat(f"[{table}] target count complete: {target_count} rows")
        data_ok = True
        if target_count != kn_count:
            result["data"] = "FAIL"; detail_parts.append(f"counts: KN={kn_count}, target={target_count}"); entry.pop("last_check_passed", None); data_ok = False
        if entry.get("last_check_passed") and not refresh:
            if data_ok: result["data"] = "CACHED"
        elif data_ok:
            heartbeat(f"[{table}] heartbeat: proving KN source PK uniqueness")
            distinct_pk_count = oracle_distinct_pk_count(oracle, sql, data_output[spec["pk"].lower()])
            if distinct_pk_count != kn_count:
                result["data"] = "FAIL"
                detail_parts.append(f"KN query has null or duplicate PK globally: COUNT(DISTINCT PK)={distinct_pk_count}, COUNT(*)={kn_count}")
                entry.pop("last_check_passed", None)
                data_ok = False
            else:
                same, reason = diff_data(
                    oracle, target_pg, sql, local, data_output, initial_page_size, kn_count,
                    max_page_size, constant_page_size,
                )
                if not same:
                    result["data"] = "FAIL"; detail_parts.append(reason or "PK/date diff failed"); entry.pop("last_check_passed", None); data_ok = False
                else:
                    entry["last_check_passed"] = True; result["data"] = "PASS"
        cache["entries"][identity] = entry
        heartbeat(f"[{table}] heartbeat: checking target high-water mark and KN strict-newer changes")
        highwater_ok, highwater_detail, preview_candidates, preview_detail, newer_candidates, newer_detail = highwater_and_delta(
            target_pg, oracle, sql, local, data_output, info["highwater"], info["last_sync_start"], full_sync, use_changed, check_started_at,
        )
        result["highwater"] = "PASS" if highwater_ok else "FAIL"
        result["lift_preview"] = "NOT_CHECKED" if preview_candidates is None else ("PASS" if preview_candidates == 0 else f"INFO ({preview_candidates})")
        result["changes_after_highwater"] = "NOT_CHECKED" if newer_candidates is None else ("PASS" if newer_candidates == 0 else "FAIL")
        detail_parts.append(
            f"integration={info['integration_id']}; connection={info['connection_name']!r}; "
            f"titles={info['titles']!r}; last_sync_start={normalize(info['last_sync_start'])}; "
            f"is_full_sync={full_sync}; use_changed_datetime_for_delta={use_changed}; "
            f"integration_start_time={normalize(check_started_at)}; counts KN/target={kn_count}/{target_count}; "
            f"{highwater_detail}; {preview_detail}; {newer_detail}"
        )
        result["detail"] = "; ".join(detail_parts)
        return finalise_result(result)
    except Exception as error:
        result["detail"] = "; ".join(part for part in (result["detail"], str(error)) if part)
        return finalise_result(result)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tables", nargs="*", help="manifest table key(s)")
    parser.add_argument("--environment", choices=("staging", "prod"), default="staging")
    parser.add_argument("--max-page-size", type=int, default=50_000, help="adaptive KN diff page-size ceiling (default: 50000)")
    parser.add_argument("--initial-page-size", type=int, help="adaptive KN diff page-size starting point (default: one quarter of maximum)")
    parser.add_argument("--constant-page-size", type=int, help="disable adaptation and use this KN diff page size")
    parser.add_argument("--refresh-data", action="store_true")
    parser.add_argument("--report", type=Path, help="custom report path (default: timestamped file in reports/)")
    args = parser.parse_args(argv)
    supplied = sys.argv[1:] if argv is None else argv
    explicit = lambda option: any(value == option or value.startswith(option + "=") for value in supplied)
    if args.constant_page_size is not None and (explicit("--initial-page-size") or explicit("--max-page-size")):
        parser.error("--constant-page-size cannot be combined with --initial-page-size or --max-page-size")
    return args


def default_report_path(environment: str, started_at: datetime) -> Path:
    label = "stag" if environment == "staging" else "prod"
    timestamp = started_at.strftime("%Y%m%d_%H%M%S")
    return REPORTS_DIR / f"state_report_{label}_{timestamp}.md"


def main() -> int:
    args = parse_args()
    if args.max_page_size < 1: raise SystemExit("error: --max-page-size must be positive")
    if args.constant_page_size is not None and args.constant_page_size < 1: raise SystemExit("error: --constant-page-size must be positive")
    initial_page_size = args.initial_page_size if args.initial_page_size is not None else max(1, args.max_page_size // 4)
    if initial_page_size < 1 or initial_page_size > args.max_page_size:
        raise SystemExit("error: --initial-page-size must be positive and no greater than --max-page-size")
    try:
        manifest = json.loads(MANIFEST_PATH.read_text()); specs = manifest["tables"]
        by_key = {item["key"]: item for item in specs}
        unknown = set(args.tables) - set(by_key)
        if unknown: raise RuntimeError("unknown table key(s): " + ", ".join(sorted(unknown)))
        selected = [by_key[key] for key in args.tables] if args.tables else specs
        load_env(); oracle_driver, psycopg = drivers(); cache = cache_read(); mhash = manifest_hash(manifest)
        report_path = args.report or default_report_path(args.environment, datetime.now())
        with (
            oracle_driver.connect(**oracle_settings(oracle_driver)) as oracle,
            psycopg.connect(**pg_settings(args.environment)) as target_pg,
            psycopg.connect(**pg_settings(args.environment, metadata=True)) as metadata_pg,
        ):
            initialise_sessions(oracle, target_pg, metadata_pg)
            check_started_at = integration_start_time()
            heartbeat(f"integration-start timestamp fixed at {normalize(check_started_at)} (Europe/Ljubljana wall clock)")
            results = []
            for index, spec in enumerate(selected, start=1):
                heartbeat(f"[{index}/{len(selected)}] starting {target_table(spec, args.environment)}")
                results.append(check_one(
                    target_pg, metadata_pg, oracle, spec, args.environment, cache,
                    args.refresh_data, initial_page_size, mhash, check_started_at,
                    max_page_size=args.max_page_size,
                    constant_page_size=args.constant_page_size,
                ))
                cache_write(cache)
                write_report(report_path, results, args.environment)
                heartbeat(f"[{index}/{len(selected)}] checkpoint saved: cache and partial report written")
        cache_write(cache)
        report = markdown(results, args.environment); write_report(report_path, results, args.environment)
        heartbeat(f"report written: {report_path}")
        print(report)
        return 0 if all(item["result"] == "PASS" for item in results) else 1
    except Exception as error:
        print(f"error: {error}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
