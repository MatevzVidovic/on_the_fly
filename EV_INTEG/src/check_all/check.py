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
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "tables.json"
CACHE_PATH = HERE / ".state" / "data_correct.json"
CACHE_VERSION = 1
SCHEMA = "public"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


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
        "id", "attribute_table_id", "last_changed_datetime", "url",
        "attribute_table_sql_connection_id",
    }
    acs = column_names(connection, "attribute_table_sql_connections") or {"id", "name"}
    table_name = pick(ats, ("name", "table_name"), "attribute table name column")
    sql_col = pick(ais, ("url", "sql", "select_sql", "integration_sql", "query", "source_sql"), "integration SQL column")
    connection_fk = pick(ais, ("attribute_table_sql_connection_id", "sql_connection_id"), "SQL connection id column")
    connection_name = pick(acs, ("name",), "SQL connection name column")
    required = {"id", "attribute_table_id", "last_changed_datetime"}
    if missing := required - ais:
        raise RuntimeError("attribute_table_integrations missing: " + ", ".join(sorted(missing)))
    with connection.cursor() as cur:
        cur.execute(f"SELECT id FROM {relation('attribute_tables')} WHERE {quote(table_name)}=%s", (table,))
        attributes = cur.fetchall()
        if len(attributes) != 1:
            raise RuntimeError(f"expected exactly one attribute_tables row named {table!r}; found {len(attributes)}")
        attribute_id = attributes[0][0]
        cur.execute(
            f"SELECT i.id, i.last_changed_datetime, i.{quote(sql_col)}, c.{quote(connection_name)} "
            f"FROM {relation('attribute_table_integrations')} i "
            f"LEFT JOIN {relation('attribute_table_sql_connections')} c ON c.id=i.{quote(connection_fk)} "
            "WHERE i.attribute_table_id=%s", (attribute_id))
        integrations = cur.fetchall()
        kn = [row for row in integrations if str(row[3] or "").upper() == "KN ORACLE"]
        if len(integrations) != 1 or len(kn) != 1:
            raise RuntimeError(f"expected exactly one integration total and it must use KN ORACLE for {table!r}; found {len(integrations)} (connections: {[r[3] for r in integrations]!r})")
        integration_id, highwater, source_sql, conn_name = kn[0]
        translations: list[Any] = []
        try:
            trans = column_names(connection, "attribute_table_translations")
            title = pick(trans, ("title", "name"), "translation title column")
            cur.execute(f"SELECT {quote(title)} FROM {relation('attribute_table_translations')} WHERE attribute_table_id=%s", (attribute_id,))
            translations = [row[0] for row in cur.fetchall()]
        except RuntimeError:
            raise
    return {"attribute_id": attribute_id, "integration_id": integration_id, "highwater": highwater,
            "sql": source_sql, "connection_name": conn_name, "titles": translations}


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
    # Match an actual column token, not strings such as DST_PRIPIS_PODATKI
    # or dst_pripis_podatki_pk which are required identifiers in this domain.
    if re.search(r"(?:\.\s*|\b)(?:\"podatki\"|podatki)\b", lower):
        failures.append("references forbidden PODATKI column")
    with oracle.cursor() as cur:
        cur.execute(f"SELECT * FROM ({sql}) q WHERE 1 = 0")
        output = {str(column[0]).lower(): str(column[0]) for column in cur.description}
    required = [spec["pk"], "date_change", "valid_from", "valid_to", *spec["source_page_keys"]]
    if spec.get("requires_jn_status"):
        required.append("jn_status")
    for name in required:
        if name.lower() not in output:
            failures.append(f"missing output alias {name}")
    if "podatki" in output:
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


def oracle_count(oracle: Any, sql: str) -> int:
    with oracle.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM ({sql}) q")
        return int(cur.fetchone()[0])


def pg_count(pg: Any, table: str) -> int:
    with pg.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {relation(table)}")
        return int(cur.fetchone()[0])


def keyset_predicate(keys: list[str]) -> str:
    parts = []
    for index, key in enumerate(keys):
        equal = " AND ".join(f"{quote(keys[before])} = :after_{before}" for before in range(index))
        condition = f"{quote(key)} > :after_{index}"
        parts.append(f"({equal} AND {condition})" if equal else f"({condition})")
    return " OR ".join(parts)


def page_sql(sql: str, source_pk: str, source_date: str, page_keys: list[str], after: tuple[Any, ...] | None) -> str:
    columns = ", ".join([quote(source_pk), quote(source_date), *map(quote, page_keys)])
    where = "" if after is None else " WHERE " + keyset_predicate(page_keys)
    return f"SELECT {columns} FROM ({sql}) q{where} ORDER BY {', '.join(map(quote, page_keys))} FETCH NEXT :limit ROWS ONLY"


def diff_data(oracle: Any, pg: Any, sql: str, spec: dict[str, Any], source_output: dict[str, str], page_size: int, expected_count: int) -> tuple[bool, str | None]:
    pk = spec["pk"].lower(); after: tuple[Any, ...] | None = None; seen = 0
    source_keys = [source_output[key.lower()] for key in spec["source_page_keys"]]
    while True:
        with oracle.cursor() as cur:
            params = {"limit": page_size}
            if after is not None: params.update({f"after_{index}": value for index, value in enumerate(after)})
            cur.execute(page_sql(sql, source_output[pk], source_output["date_change"], source_keys, after), params)
            rows = cur.fetchall()
        if not rows: return (seen == expected_count, None if seen == expected_count else f"KN scan count {seen} != COUNT(*) {expected_count}")
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
        if len(rows) < page_size: return True, None


def highwater_and_delta(pg: Any, oracle: Any, sql: str, spec: dict[str, Any], source_output: dict[str, str], highwater: Any) -> tuple[bool, str, int]:
    with pg.cursor() as cur:
        cur.execute(f"SELECT MAX({quote('date_change')}) FROM {relation(spec['table'])}")
        maximum = cur.fetchone()[0]
    if normalize(maximum) != normalize(highwater):
        return False, f"target MAX(date_change)={normalize(maximum)} != integration last_changed_datetime={normalize(highwater)}", -1
    if highwater is None:
        with oracle.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM ({sql}) q WHERE {quote(source_output['date_change'])} IS NOT NULL")
            delta = int(cur.fetchone()[0])
            return delta == 0, ("ok (both target and KN are empty)" if delta == 0 else "empty high-water mark but KN has date_change values"), delta
    with oracle.cursor() as cur:
        # LIFT stores a naïve PostgreSQL timestamp; KN's FROM_TZ output is a
        # TSTZ. Cast to TIMESTAMP so this uses the same Ljubljana wall-clock
        # contract as normalize()/the data comparison.
        cur.execute(f"SELECT COUNT(*) FROM ({sql}) q WHERE CAST({quote(source_output['date_change'])} AS TIMESTAMP) > :highwater", {"highwater": highwater})
        delta = int(cur.fetchone()[0])
    return delta == 0, ("ok" if delta == 0 else f"{delta} KN rows are newer than high-water mark"), delta


def markdown(results: list[dict[str, Any]], environment: str) -> str:
    lines = [f"# EV integration state check ({environment})", "", "| Table | Metadata | Data | High-water | Zero newer rows | Result |", "|---|---|---|---|---|---|"]
    for item in results:
        lines.append("| {table} | {metadata} | {data} | {water} | {delta} | **{result}** |".format(
            table=item["table"], metadata=item["metadata"], data=item["data"], water=item["highwater"], delta=item["delta"], result=item["result"]))
    lines += ["", "## Details", ""]
    for item in results:
        lines += [f"### {item['table']}", "", f"- {item['detail']}"]
    lines += ["", "A passing `Zero newer rows` result is the precondition for manually running LIFT; that LIFT run should transfer zero records.", ""]
    return "\n".join(lines)


def check_one(target_pg: Any, metadata_pg: Any, oracle: Any, spec: dict[str, Any], environment: str, cache: dict[str, Any], refresh: bool, page_size: int, mhash: str) -> dict[str, Any]:
    table = target_table(spec, environment); local = {**spec, "table": table}
    result = {"table": table, "metadata": "FAIL", "data": "NOT_CHECKED", "highwater": "NOT_CHECKED", "delta": "NOT_CHECKED", "result": "FAIL", "detail": ""}
    try:
        info = metadata(metadata_pg, table)
        title_bad = not info["titles"] or any(not str(title or "").startswith("EV H") for title in info["titles"])
        sql, output, failures = validate_sql(oracle, info["sql"], local)
        if title_bad: failures.append(f"titles must all start with EV H; got {info['titles']!r}")
        if str(info["connection_name"] or "").upper() != "KN ORACLE": failures.append("integration connection is not KN ORACLE")
        if failures:
            result["detail"] = "; ".join(failures); return result
        result["metadata"] = "PASS"
        identity = hashlib.sha256(json.dumps({"env": environment, "table": table, "integration": str(info["integration_id"]), "sql": sql_hash(sql), "manifest": mhash, "pk": spec["pk"]}, sort_keys=True).encode()).hexdigest()
        entry = cache["entries"].get(identity, {})
        kn_count = entry.get("kn_count")
        if kn_count is None or refresh:
            kn_count = oracle_count(oracle, sql); entry["kn_count"] = kn_count
        target_count = pg_count(target_pg, table)
        data_ok = True
        if target_count != kn_count:
            result["data"] = "FAIL"; result["detail"] = f"counts: KN={kn_count}, target={target_count}"; entry.pop("last_check_passed", None); data_ok = False
        if entry.get("last_check_passed") and not refresh:
            if data_ok: result["data"] = "CACHED"
        elif data_ok:
            same, reason = diff_data(oracle, target_pg, sql, local, output, page_size, kn_count)
            if not same:
                result["data"] = "FAIL"; result["detail"] = reason or "PK/date diff failed"; entry.pop("last_check_passed", None); data_ok = False
            else:
                entry["last_check_passed"] = True; result["data"] = "PASS"
        cache["entries"][identity] = entry
        ok, detail, delta = highwater_and_delta(target_pg, oracle, sql, local, output, info["highwater"])
        result["highwater"] = "FAIL" if delta == -1 else "PASS"
        result["delta"] = "PASS" if ok else "FAIL"
        result["detail"] = ((result["detail"] + "; " if result["detail"] else "") + f"integration={info['integration_id']}; connection={info['connection_name']!r}; "
                            f"titles={info['titles']!r}; counts KN/target={kn_count}/{target_count}; {detail}")
        result["result"] = "PASS" if ok and data_ok else "FAIL"
        return result
    except Exception as error:
        result["detail"] = str(error); return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tables", nargs="*", help="manifest table key(s)")
    parser.add_argument("--environment", choices=("staging", "prod"), default="staging")
    parser.add_argument("--page-size", type=int, default=5000)
    parser.add_argument("--refresh-data", action="store_true")
    parser.add_argument("--report", type=Path, default=HERE / "state_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.page_size < 1: raise SystemExit("error: --page-size must be positive")
    try:
        manifest = json.loads(MANIFEST_PATH.read_text()); specs = manifest["tables"]
        by_key = {item["key"]: item for item in specs}
        unknown = set(args.tables) - set(by_key)
        if unknown: raise RuntimeError("unknown table key(s): " + ", ".join(sorted(unknown)))
        selected = [by_key[key] for key in args.tables] if args.tables else specs
        load_env(); oracle_driver, psycopg = drivers(); cache = cache_read(); mhash = manifest_hash(manifest)
        with (
            oracle_driver.connect(**oracle_settings(oracle_driver)) as oracle,
            psycopg.connect(**pg_settings(args.environment)) as target_pg,
            psycopg.connect(**pg_settings(args.environment, metadata=True)) as metadata_pg,
        ):
            initialise_sessions(oracle, target_pg, metadata_pg)
            results = [check_one(target_pg, metadata_pg, oracle, spec, args.environment, cache, args.refresh_data, args.page_size, mhash) for spec in selected]
        cache_write(cache)
        report = markdown(results, args.environment); args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(report, encoding="utf-8")
        print(report)
        return 0 if all(item["result"] == "PASS" for item in results) else 1
    except Exception as error:
        print(f"error: {error}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
