"""Resumable, keyset-paginated Oracle-to-PostgreSQL historical loader."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class TableSpec:
    code: str
    oracle_table: str
    key_column: str
    columns: tuple[str, ...]

    @property
    def pk_column(self) -> str:
        return f"{self.code}_pk"

    @property
    def output_columns(self) -> tuple[str, ...]:
        return (self.pk_column, *[column.lower() for column in self.columns], "valid_from", "valid_to", "date_change")


IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def parse_relation(value: str) -> tuple[str, str]:
    parts = value.split(".")
    if len(parts) == 1 and IDENTIFIER.fullmatch(parts[0]):
        return "public", parts[0]
    if len(parts) == 2 and all(IDENTIFIER.fullmatch(part) for part in parts):
        return parts[0], parts[1]
    raise ValueError("target table must be a PostgreSQL identifier, e.g. ev_h_pe_parc or public.ev_h_pe_parc")


def quote_relation(value: str) -> str:
    schema, table = parse_relation(value)
    return f'"{schema}"."{table}"'


def keyset_predicate(key_column: str, has_cursor: bool) -> str:
    if not has_cursor:
        return ""
    return f' AND (j."{key_column}" > :last_key OR (j."{key_column}" = :last_key AND j."JN_REV_NUM" > :last_rev))'


def canonical_query(spec: TableSpec, has_cursor: bool) -> str:
    selected: list[str] = [f'TO_CHAR(j."{spec.key_column}") || \'-\' || TO_CHAR(j."JN_REV_NUM") AS {spec.pk_column}']
    for column in spec.columns:
        if column == "JN_STATUS":
            selected.append('CAST(TRIM(j."JN_STATUS") AS VARCHAR2(1)) AS jn_status')
        else:
            selected.append(f'j."{column}" AS {column.lower()}')
    selected.extend([
        "FROM_TZ(CAST(rf.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_from",
        "FROM_TZ(CAST(rt.CREATED AS TIMESTAMP), 'Europe/Ljubljana') AS valid_to",
        "FROM_TZ(CAST(COALESCE(rt.CREATED, rf.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AS date_change",
    ])
    projection = ",\n    ".join(selected)
    return f'''SELECT
    {projection}
FROM EV.{spec.oracle_table} j
JOIN EV.REVISION rf ON j."JN_REV_NUM" = rf.REV_NUM
LEFT JOIN EV.REVISION rt ON j."JN_REV_NUM_TO" = rt.REV_NUM
WHERE j."JN_STATUS" <> 'X'
  AND rf.CREATED < :fence{keyset_predicate(spec.key_column, has_cursor)}
ORDER BY j."{spec.key_column}", j."JN_REV_NUM"
FETCH FIRST :page_size ROWS ONLY'''


def config_fingerprint(spec: TableSpec, target: str) -> str:
    payload = json.dumps({"spec": asdict(spec), "target": target}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"checkpoint is unreadable: {path}; repair or use --restart") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"checkpoint is invalid: {path}")
    return value


@contextmanager
def file_lock(path: Path) -> Iterable[None]:
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"another loader holds {path}") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def is_transient(error: Exception) -> bool:
    message = str(error).lower()
    return any(indicator in message for indicator in ("connection", "network", "timeout", "temporar", "ora-12170", "ora-125", "could not connect"))


def retry(operation: Any, retries: int) -> Any:
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception as error:
            if attempt >= retries or not is_transient(error):
                raise
            time.sleep(min(30.0, 0.5 * (2**attempt)) + random.uniform(0, 0.25))


def require_drivers() -> tuple[Any, Any]:
    try:
        import oracledb
        import psycopg
    except ImportError as error:
        raise RuntimeError("install requirements into the shared .venv before running a loader") from error
    return oracledb, psycopg


def load_project_environment() -> None:
    """Load only this repository's .env; never print its values."""
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("install requirements into the shared .venv before running a loader") from error
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env", override=False)


def source_connection(oracledb: Any) -> Any:
    required = ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_HOST", "ORACLE_PORT", "ORACLE_SERVICE")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing Oracle environment variables: {', '.join(missing)}")
    dsn = oracledb.makedsn(
        os.environ["ORACLE_HOST"],
        int(os.environ["ORACLE_PORT"]),
        service_name=os.environ["ORACLE_SERVICE"],
    )
    return oracledb.connect(user=os.environ["ORACLE_USER"], password=os.environ["ORACLE_PASSWORD"], dsn=dsn)


def pg_connection(psycopg: Any) -> Any:
    required = ("PG_USER", "PG_PASSWORD", "PG_HOST", "PG_PORT")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"missing PostgreSQL environment variables: {', '.join(missing)}")
    return psycopg.connect(
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        host=os.environ["PG_HOST"],
        port=int(os.environ["PG_PORT"]),
        dbname=os.environ.get("PG_DATABASE", "fmp_data_gurs"),
    )


def get_fence(oracledb: Any) -> datetime:
    connection = source_connection(oracledb)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT CAST(SYSTIMESTAMP AT TIME ZONE 'Europe/Ljubljana' AS TIMESTAMP) FROM dual")
            return cursor.fetchone()[0]
    finally:
        connection.close()


def fetch_page(oracledb: Any, spec: TableSpec, fence: datetime, cursor_key: tuple[str, int] | None, page_size: int) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        connection = source_connection(oracledb)
        try:
            with connection.cursor() as cursor:
                binds: dict[str, Any] = {"fence": fence, "page_size": page_size}
                if cursor_key:
                    binds.update(last_key=cursor_key[0], last_rev=cursor_key[1])
                cursor.execute(canonical_query(spec, bool(cursor_key)), binds)
                names = [description[0].lower() for description in cursor.description]
                return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
        finally:
            connection.close()
    return retry(operation, retries=4)


def check_target(connection: Any, spec: TableSpec, target: str) -> None:
    schema, table = parse_relation(target)
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s", (schema, table))
        present = {row[0] for row in cursor.fetchall()}
        missing = set(spec.output_columns) - present
        if missing:
            raise RuntimeError(f"target {target} is missing LIFT output columns: {', '.join(sorted(missing))}")
        cursor.execute("""SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey) WHERE n.nspname = %s AND c.relname = %s AND i.indisunique AND array_length(i.indkey, 1) = 1 AND a.attname = %s""", (schema, table, spec.pk_column))
        if cursor.fetchone() is None:
            raise RuntimeError(f"target {target} needs a single-column unique key on {spec.pk_column}")


def write_page(psycopg: Any, spec: TableSpec, target: str, rows: list[dict[str, Any]]) -> None:
    columns = spec.output_columns
    assignments = ", ".join(f"{column} = EXCLUDED.{column}" for column in columns if column != spec.pk_column)
    placeholders = ", ".join("%s" for _ in columns)
    query = f"INSERT INTO {quote_relation(target)} ({', '.join(columns)}) VALUES ({placeholders}) ON CONFLICT ({spec.pk_column}) DO UPDATE SET {assignments} WHERE EXCLUDED.date_change >= date_change"
    values = [tuple(row[column] for column in columns) for row in rows]

    def operation() -> None:
        connection = pg_connection(psycopg)
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.executemany(query, values)
        finally:
            connection.close()
    retry(operation, retries=4)


def checkpoint_path(entrypoint: Path) -> Path:
    return entrypoint.parent / ".state" / "checkpoint.json"


def run_loader(spec: TableSpec, entrypoint: Path | str) -> None:
    parser = argparse.ArgumentParser(description=f"Resumable EV bootstrap loader for {spec.oracle_table}")
    parser.add_argument("--target-table", help="required LIFT destination; defaults to public schema when unqualified")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, help="stop cleanly after this many committed pages")
    parser.add_argument("--status", action="store_true", help="print local checkpoint and exit")
    parser.add_argument("--restart", action="store_true", help="remove only this loader's local checkpoint")
    args = parser.parse_args()
    state_path = checkpoint_path(Path(entrypoint).resolve())
    if args.status:
        print(json.dumps(read_checkpoint(state_path) or {"status": "not started"}, indent=2, default=str))
        return
    lock_path = state_path.with_name("loader.lock")
    if args.restart:
        with file_lock(lock_path):
            if state_path.exists():
                state_path.unlink()
                print(f"removed local checkpoint {state_path}")
        return
    load_project_environment()
    target = args.target_table or os.environ.get("PG_TARGET_TABLE")
    if not target:
        parser.error("--target-table or PG_TARGET_TABLE is required")
    if args.page_size <= 0:
        parser.error("--page-size must be positive")
    fingerprint = config_fingerprint(spec, target)
    with file_lock(lock_path):
        state = read_checkpoint(state_path)
        if state and state.get("fingerprint") != fingerprint:
            raise RuntimeError("checkpoint belongs to a different target or source contract; use --restart only after review")
        if state and state.get("status") == "complete":
            print("bootstrap already complete; use --restart only to deliberately replay it")
            return
        oracledb, psycopg = require_drivers()
        connection = pg_connection(psycopg)
        try:
            check_target(connection, spec, target)
        finally:
            connection.close()
        if not state:
            state = {"table": spec.oracle_table, "target": target, "fingerprint": fingerprint, "fence": get_fence(oracledb).isoformat(), "last_key": None, "last_rev": None, "pages": 0, "rows": 0, "status": "running"}
            atomic_json_write(state_path, state)
        fence = datetime.fromisoformat(state["fence"])
        while True:
            cursor_key = (state["last_key"], int(state["last_rev"])) if state["last_key"] is not None else None
            rows = fetch_page(oracledb, spec, fence, cursor_key, args.page_size)
            if not rows:
                state["status"] = "complete"
                state["completed_at"] = datetime.now().astimezone().isoformat()
                atomic_json_write(state_path, state)
                print(f"complete: {state['rows']} rows in {state['pages']} pages; fence={state['fence']}")
                return
            write_page(psycopg, spec, target, rows)
            last = rows[-1]
            state.update(last_key=str(last[spec.key_column.lower()]), last_rev=int(last["jn_rev_num"]), pages=state["pages"] + 1, rows=state["rows"] + len(rows))
            atomic_json_write(state_path, state)
            print(f"committed page {state['pages']} ({len(rows)} rows; total {state['rows']})")
            if args.max_pages and state["pages"] >= args.max_pages:
                print("stopped at --max-pages; rerun without it to resume")
                return
