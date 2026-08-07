"""Read-only KN Oracle/FMP delta audit.

The database-facing pieces are deliberately small so comparison semantics can
be tested without credentials.  All identifiers originate in the reviewed
selection file and are quoted after strict validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from decimal import Decimal
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from zoneinfo import ZoneInfo

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")
SQL_START = re.compile(r"^\s*(?:with\b|select\b)", re.I | re.S)
LJ = ZoneInfo("Europe/Ljubljana")
SQL_FIELDS = ("url", "sql", "sql_query", "query", "select_sql", "source_sql", "integration_sql")
HIGHWATER_FIELDS = ("last_changed_datetime", "highwater", "high_water", "highwater_column", "date_changed_column")


class AuditError(Exception): pass


def qi(name: str) -> str:
    if not IDENT.fullmatch(name):
        raise AuditError(f"unsafe identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def validated_select(sql: str) -> str:
    """Allow precisely one read-only SELECT/WITH statement."""
    if not isinstance(sql, str):
        raise AuditError("integration SQL must start with SELECT or WITH")
    s = sql.strip()
    # Mask comments and quoted literals before checking syntax keywords; words such as
    # "delete" in a string/comment are harmless, but statement separators are not.
    masked = re.sub(r"/\*.*?\*/|--[^\n]*|'(?:''|[^'])*'", lambda m: " " * len(m.group(0)), s, flags=re.S)
    if not SQL_START.match(masked): raise AuditError("integration SQL must start with SELECT or WITH")
    if masked.rstrip().endswith(";"):
        i = s.rfind(";"); s = s[:i].rstrip(); masked = masked[:i].rstrip()
    if ";" in masked or re.search(r"\b(?:insert|update|delete|merge|alter|drop|create|grant|execute|lock)\b", masked, re.I):
        raise AuditError("integration SQL is not a single read-only statement")
    return s


def parse_cutoff(value: str) -> datetime:
    try: result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e: raise AuditError("--as-of must be ISO-8601") from e
    if result.tzinfo is None or result.utcoffset() is None:
        raise AuditError("--as-of must include a UTC offset")
    return result.astimezone(timezone.utc)


def norm_date(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())
    if not isinstance(value, datetime): raise AuditError(f"not a temporal value: {value!r}")
    # Oracle DATE has no timezone. Its documented connection/session timezone is Ljubljana.
    if value.tzinfo is None: value = value.replace(tzinfo=LJ)
    return value.astimezone(timezone.utc)


def jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)): return v.isoformat()
    if isinstance(v, bytes): return v.hex()
    if isinstance(v, Decimal): return str(v)
    if isinstance(v, uuid.UUID): return str(v)
    return v


@dataclass(frozen=True)
class KeyMap:
    source: str
    target: str

@dataclass(frozen=True)
class Selection:
    name: str
    integration_id: str
    target_table: str
    target_schema: str
    keys: tuple[KeyMap, ...]
    source_date: str
    target_date: str

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Selection":
        try:
            keys = tuple(KeyMap(x["source"], x["target"]) for x in row["keys"])
            out = cls(row.get("name", row["target_table"]), str(row["integration_id"]), row["target_table"],
                      row.get("target_schema", "public"), keys, row["source_date"], row["target_date"])
        except (KeyError, TypeError, ValueError) as e: raise AuditError(f"bad selection: {row!r}") from e
        if not out.keys: raise AuditError(f"{out.name}: at least one key is required")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", out.integration_id): raise AuditError("invalid integration id")
        if not re.fullmatch(r"[A-Za-z0-9_. -]{1,100}", out.name): raise AuditError("unsafe selection name")
        for value in (out.target_table, out.target_schema, out.source_date, out.target_date,
                      *(p for k in out.keys for p in (k.source, k.target))): qi(value)
        if len({x.source.lower() for x in out.keys}) != len(out.keys) or len({x.target.lower() for x in out.keys}) != len(out.keys):
            raise AuditError(f"{out.name}: duplicate key mapping")
        return out


def load_selection(path: Path) -> list[Selection]:
    raw = json.loads(path.read_text())
    rows = raw["tables"] if isinstance(raw, dict) else raw
    values = [Selection.from_dict(x) for x in rows]
    if not values: raise AuditError("selection has no tables")
    if len({x.integration_id for x in values}) != len(values): raise AuditError("selection repeats an integration id")
    return values


def load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal dotenv loader: never overwrites supplied environment values."""
    if not path.is_file(): return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k.strip()): os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def profile(env: str, require_kn: bool = False) -> dict[str, str]:
    p = env.upper()
    if p not in {"TEST", "STAG"}: raise AuditError("environment must be test or stag")
    need = ("USER", "PASSWORD", "HOST", "PORT", "DATABASE")
    missing = [p + "_" + x for x in need if not os.getenv(p + "_" + x)]
    kn_missing = ["KN_" + x for x in ("USER", "PASSWORD", "HOST", "PORT", "SERVICE") if not os.getenv("KN_" + x)] if require_kn else []
    if missing or kn_missing: raise AuditError("missing environment variables: " + ", ".join(missing + kn_missing))
    return {"name": p.lower(), "user": os.environ[p+"_USER"], "password": os.environ[p+"_PASSWORD"],
            "host": os.environ[p+"_HOST"], "port": os.environ[p+"_PORT"], "database": os.environ[p+"_DATABASE"],
            "metadata_database": os.getenv(p+"_METADATA_DATABASE", "fmp")}


def pg_connect(p: dict[str, str], metadata=False):
    import psycopg
    return psycopg.connect(host=p["host"], port=p["port"], user=p["user"], password=p["password"],
                           dbname=p["metadata_database"] if metadata else p["database"], autocommit=False)

def oracle_connect():
    import oracledb
    lib = os.getenv("KN_ORACLE_CLIENT_LIB_DIR")
    if lib: oracledb.init_oracle_client(lib_dir=lib)
    return oracledb.connect(user=os.environ["KN_USER"], password=os.environ["KN_PASSWORD"],
                            dsn=oracledb.makedsn(os.environ["KN_HOST"], int(os.environ["KN_PORT"]), service_name=os.environ["KN_SERVICE"]))


METADATA_SQL = '''SELECT at.id AS attribute_table_id, at.name AS table_name, ati.id AS integration_id,
 ats.name AS connection_name, to_jsonb(ati) AS integration
 FROM attribute_tables at JOIN attribute_table_integrations ati ON ati.attribute_table_id=at.id
 JOIN attribute_table_sql_connections ats ON ats.id=ati.attribute_table_sql_connection_id
 WHERE lower(ats.name)=lower(%s) ORDER BY at.name, ati.id'''

def field(obj: dict[str, Any], names: tuple[str, ...]) -> Any:
    return next((obj[x] for x in names if obj.get(x) not in (None, "")), None)

def discovery_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        raw = row.get("integration") or {}
        sql = field(raw, SQL_FIELDS)
        result.append({"attribute_table_id": row["attribute_table_id"], "table_name": row["table_name"],
          "integration_id": row["integration_id"], "connection_name": row["connection_name"],
          "highwater": field(raw, HIGHWATER_FIELDS), "sql_hash": hashlib.sha256(str(sql or "").encode()).hexdigest() if sql else None,
          "saved_sql": sql, "has_sql": bool(sql)})
    counts = Counter(x["table_name"] for x in result)
    for x in result: x["ambiguous"] = counts[x["table_name"]] != 1
    return result

def discover(conn) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=__import__('psycopg').rows.dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY; SET TIME ZONE 'Europe/Ljubljana'")
        cur.execute(METADATA_SQL, ("KN ORACLE",)); return discovery_rows(cur.fetchall())


def run_dir(base: Path, cutoff: datetime) -> Path:
    slug = cutoff.strftime("%Y%m%dT%H%M%SZ")
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base.mkdir(parents=True, exist_ok=True)
    d = base / f"kn-delta-audit_{now}_cutoff-{slug}"
    # A repeated invocation in the same second must not overwrite evidence.
    n = 1; candidate = d
    while candidate.exists(): n += 1; candidate = Path(str(d) + f"-{n}")
    candidate.mkdir(); return candidate

def write_jsonl(path: Path, records: Iterable[dict[str, Any]]):
    with path.open("w") as f:
        for r in records: f.write(json.dumps(r, default=jsonable, sort_keys=True) + "\n")

def cursor_rows(cur) -> Iterator[dict[str, Any]]:
    names = [x[0] for x in cur.description]
    while batch := cur.fetchmany(1000):
        for row in batch: yield dict(zip(names, row))

def forward_key_lookup(rows: Iterable[dict[str, Any]], names: list[str]):
    """Monotonic membership test over an ordered stream; avoids per-delta SQL probes."""
    it = iter(rows); current = next(it, None)
    def contains(key):
        nonlocal current
        token = ordering_key(key)
        while current is not None and ordering_key(key_of(current, names)) < token: current = next(it, None)
        return current is not None and ordering_key(key_of(current, names)) == token
    return contains

def integration_for(conn, integration_id: str, expected_table: str) -> dict[str, Any]:
    with conn.cursor(row_factory=__import__('psycopg').rows.dict_row) as cur:
        cur.execute("SET TRANSACTION READ ONLY; SET TIME ZONE 'Europe/Ljubljana'")
        cur.execute(METADATA_SQL, ("KN ORACLE",))
        found = [r for r in cur.fetchall() if str(r["integration_id"]) == str(integration_id)]
    if len(found) != 1: raise AuditError("selected integration is absent or no longer uses KN ORACLE")
    if found[0]["table_name"] != expected_table: raise AuditError("selection target table does not match resolved metadata table")
    sql = field(found[0].get("integration") or {}, SQL_FIELDS)
    if not sql: raise AuditError("saved integration SQL is unavailable in metadata")
    return {"sql": validated_select(sql), "sql_hash": hashlib.sha256(sql.encode()).hexdigest(), "connection": found[0]["connection_name"]}

def audit_selection(p: dict[str, str], s: Selection, cutoff: datetime, limit: int, export_dir=None, max_export_rows: int = 1000, allow_large_export: bool = False):
    """Run a single streaming, read-only comparison. Connections are closed on every path."""
    meta = pg_connect(p, metadata=True)
    try: integ = integration_for(meta, s.integration_id, s.target_table)
    finally: meta.close()
    oc = oracle_connect(); tc = pg_connect(p)
    try:
        with oc.cursor() as c:
            c.execute("ALTER SESSION SET TIME_ZONE = 'Europe/Ljubljana'")
            c.execute("SET TRANSACTION READ ONLY")
        with tc.cursor() as c: c.execute("SET TRANSACTION READ ONLY; SET TIME ZONE 'Europe/Ljubljana'")
        sk, tk = [x.source for x in s.keys], [x.target for x in s.keys]
        order_s, order_t = ", ".join("x." + qi(x) for x in sk), ", ".join(qi(x) for x in tk)
        source_cols = "x.*" if export_dir else ", ".join(f'x.{qi(x)} AS {qi(x)}' for x in [*sk, s.source_date])
        target_cols = "*" if export_dir else ", ".join(qi(x) for x in [*tk, s.target_date])
        # As-of audit validity is scoped to eligible rows; future/null-date records do not invalidate it.
        null_s = " OR ".join(f'x.{qi(x)} IS NULL' for x in sk)
        null_t = " OR ".join(f'{qi(x)} IS NULL' for x in tk)
        with oc.cursor() as c:
            c.execute(f'SELECT 1 FROM ({integ["sql"]}) x WHERE x.{qi(s.source_date)} IS NULL AND ROWNUM=1')
            if c.fetchone(): raise AuditError("null configured source date is a data-quality error")
            c.execute(f'SELECT 1 FROM ({integ["sql"]}) x WHERE x.{qi(s.source_date)} < :cutoff AND ({null_s}) AND ROWNUM=1', cutoff=cutoff.astimezone(LJ).replace(tzinfo=None))
            if c.fetchone(): raise AuditError("null composite key in eligible source integration output")
        with tc.cursor() as c:
            c.execute(f'SELECT 1 FROM {qi(s.target_schema)}.{qi(s.target_table)} WHERE {qi(s.target_date)} IS NULL LIMIT 1')
            if c.fetchone(): raise AuditError("null configured target date is a data-quality error")
            c.execute(f'SELECT 1 FROM {qi(s.target_schema)}.{qi(s.target_table)} WHERE {qi(s.target_date)} < %s AND ({null_t}) LIMIT 1', (cutoff,))
            if c.fetchone(): raise AuditError("null composite key in eligible target")
        source_sql = f'SELECT {source_cols} FROM ({integ["sql"]}) x WHERE x.{qi(s.source_date)} < :cutoff ORDER BY {order_s}'
        target_sql = f'SELECT {target_cols} FROM {qi(s.target_schema)}.{qi(s.target_table)} WHERE {qi(s.target_date)} < %s ORDER BY {order_t}'
        sc = oc.cursor(); sc.execute(source_sql, cutoff=cutoff.astimezone(LJ).replace(tzinfo=None))
        tcurs = tc.cursor(); tcurs.execute(target_sql, (cutoff,))
        # Merge opposite noneligible key streams once: no N+1 probe for missing eligible rows.
        snc = oc.cursor(); snc.execute(f'SELECT {", ".join(f"x.{qi(x)} AS {qi(x)}" for x in sk)} FROM ({integ["sql"]}) x WHERE x.{qi(s.source_date)} >= :cutoff ORDER BY {order_s}', cutoff=cutoff.astimezone(LJ).replace(tzinfo=None))
        tnc = tc.cursor(); tnc.execute(f'SELECT {", ".join(qi(x) for x in tk)} FROM {qi(s.target_schema)}.{qi(s.target_table)} WHERE {qi(s.target_date)} >= %s ORDER BY {order_t}', (cutoff,))
        s_after = forward_key_lookup(cursor_rows(snc), sk)
        t_after = forward_key_lookup(cursor_rows(tnc), tk)
        spool_files, handles, spool_rows, overflow = {}, {}, Counter(), set()
        if export_dir:
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", s.name).strip("._") or "table"
            for kind, sides in (("source_only", ("source",)), ("target_only", ("target",)), ("date_changed_mismatch", ("source", "target"))):
                spool_files[kind] = {}
                for side in sides:
                    path = export_dir / f".{safe}_{s.integration_id}_{kind}_{side}.spool.jsonl"
                    spool_files[kind][side], handles[(kind, side)] = path, path.open("w")
        def spool(kind, payload):
            for side, row in payload.items():
                handle = handles.get((kind, side))
                if not handle: continue
                # Normal export requests keep bounded evidence only; counting continues regardless.
                if not allow_large_export and spool_rows[kind] >= max_export_rows + 1:
                    overflow.add(kind); continue
                handle.write(json.dumps(row, default=jsonable, sort_keys=True) + "\n")
            spool_rows[kind] += 1
        try:
            counts, samples = compare_rows(cursor_rows(sc), cursor_rows(tcurs), sk, tk, s.source_date, s.target_date, cutoff, s_after, t_after, limit, spool)
        finally:
            for h in handles.values(): h.close()
        table = {"table":s.name, "integration_id":s.integration_id, "sql_hash":integ["sql_hash"], "keys":[asdict(x) for x in s.keys], "source_date":s.source_date, "target_date":s.target_date, "counts":counts}
        if export_dir:
            table["export"] = finalize_spools(spool_files, counts, export_dir, max_export_rows, allow_large_export, overflow)
        return table, samples
    finally:
        try: oc.close()
        finally: tc.close()

def finalize_spools(spools: dict, counts: dict[str, int], out: Path, cap: int, allow_large: bool, overflow: set) -> dict:
    """Publish first-pass payload spools only after exact counts are known."""
    result = {"skipped": False, "files": {}}
    for kind, sides in spools.items():
        if kind in overflow or (counts[kind] > cap and not allow_large):
            for path in sides.values(): path.unlink(missing_ok=True)
            result["files"][kind] = {"skipped": True, "reason": f"category exceeds {cap} rows", "complete": False}
            continue
        published, complete = {}, True
        for side, path in sides.items():
            actual = sum(1 for _ in path.open())
            if actual != counts[kind]: complete = False
            final = path.with_name(path.name.replace(".spool", "_full")); path.replace(final); published[side] = final.name
        result["files"][kind] = {"skipped": False, "complete": complete, "expected_rows": counts[kind], "paths": published, "override": bool(counts[kind] > cap and allow_large)}
    return result

def key_of(row: dict[str, Any], names: list[str]) -> tuple[Any, ...]: return tuple(row[x] for x in names)

def ordering_key(key: tuple[Any, ...]) -> tuple[tuple[str, Any], ...]:
    """Canonical key tokens. Text and UUID are deliberately distinct families."""
    out = []
    for v in key:
        if isinstance(v, bool): raise AuditError("boolean composite keys are unsupported")
        if isinstance(v, (int, float, Decimal)): out.append(("number", Decimal(str(v))))
        elif isinstance(v, str): out.append(("text", v))
        elif isinstance(v, uuid.UUID): out.append(("uuid", str(v)))
        else: raise AuditError(f"unsupported composite key type: {type(v).__name__}")
    return tuple(out)

def validated_stream(rows: Iterable[dict[str, Any]], keys: list[str], datecol: str) -> Iterator[dict[str, Any]]:
    """Validate a pre-ordered stream. Adjacent duplicate detection permits paging."""
    previous = None
    types = None
    for row in rows:
        if any(k not in row for k in keys) or datecol not in row: raise AuditError("source/target aliases missing from query output")
        key = key_of(row, keys)
        if any(v is None for v in key): raise AuditError("null composite key")
        families = tuple(x[0] for x in ordering_key(key))
        if types is None: types = families
        elif families != types: raise AuditError("incompatible composite key types; supported keys must be consistently text or numeric")
        token = ordering_key(key)
        if previous is not None and token <= previous:
            raise AuditError("duplicate or unordered composite key")
        previous = token; norm_date(row[datecol]); yield row

def compare_rows(source: Iterable[dict[str, Any]], target: Iterable[dict[str, Any]], skeys: list[str], tkeys: list[str], sdate: str, tdate: str, cutoff: datetime,
                 source_after=lambda k: False, target_after=lambda k: False, limit: int = 20, on_delta=None) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]]]:
    """Pure ordered merge. Callers provide after-cutoff existence probes."""
    si, ti = iter(validated_stream(source, skeys, sdate)), iter(validated_stream(target, tkeys, tdate))
    counts = Counter(); samples: dict[str, list[dict[str, Any]]] = {x: [] for x in ("source_only", "target_only", "date_changed_mismatch", "post_cutoff_volatile")}
    def add(kind, payload):
        counts[kind] += 1
        if on_delta is not None: on_delta(kind, payload)
        if len(samples[kind]) < limit: samples[kind].append(payload)
    s = next(si, None); t = next(ti, None)
    while s is not None or t is not None:
        if s is None: key = key_of(t, tkeys); add("post_cutoff_volatile" if source_after(key) else "target_only", {"target": t}); t = next(ti, None); continue
        if t is None: key = key_of(s, skeys); add("post_cutoff_volatile" if target_after(key) else "source_only", {"source": s}); s = next(si, None); continue
        raw_a, raw_b = key_of(s, skeys), key_of(t, tkeys)
        a,b = ordering_key(raw_a), ordering_key(raw_b)
        if tuple(x[0] for x in a) != tuple(x[0] for x in b):
            raise AuditError("incompatible source/target composite key type families")
        if a < b: add("post_cutoff_volatile" if target_after(raw_a) else "source_only", {"source": s}); s = next(si, None)
        elif b < a: add("post_cutoff_volatile" if source_after(raw_b) else "target_only", {"target": t}); t = next(ti, None)
        else:
            if norm_date(s[sdate]) != norm_date(t[tdate]): add("date_changed_mismatch", {"source":s, "target":t})
            s = next(si, None); t = next(ti, None)
    return {k: counts[k] for k in samples}, samples


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--environment", default="test"); ap.add_argument("--output-dir", default="artifacts")
    sub = ap.add_subparsers(dest="command", required=True)
    discover_p = sub.add_parser("discover")
    audit = sub.add_parser("audit"); audit.add_argument("--selection", required=True); audit.add_argument("--as-of", required=True); audit.add_argument("--limit", type=int, default=20); audit.add_argument("--export", action="store_true"); audit.add_argument("--allow-large-export", action="store_true"); audit.add_argument("--max-export-rows", type=int, default=1000)
    # Permit documented global options after the command too.
    for child in (discover_p, audit):
        child.add_argument("--environment", default=argparse.SUPPRESS)
        child.add_argument("--output-dir", default=argparse.SUPPRESS)
    load_dotenv()
    args = ap.parse_args(argv)
    try:
        p = profile(args.environment, require_kn=args.command == "audit"); base = Path(args.output_dir)
        if args.command == "discover":
            d = run_dir(base, datetime.now(timezone.utc)); c = pg_connect(p, metadata=True)
            try: rows = discover(c)
            finally: c.close()
            (d / "inventory.json").write_text(json.dumps(rows, indent=2, default=jsonable))
            lines = ["# KN ORACLE integrations", "", "|table|integration|highwater|SQL hash|ambiguous|", "|---|---:|---|---|---|"]
            lines += [f"|{r['table_name']}|{r['integration_id']}|{r['highwater'] or ''}|{r['sql_hash'] or ''}|{r['ambiguous']}|" for r in rows]
            (d / "inventory.md").write_text("\n".join(lines)+"\n"); print(d); return 0
        cutoff = parse_cutoff(args.as_of); selections = load_selection(Path(args.selection)); d = run_dir(base, cutoff)
        manifest = {"environment":p["name"], "started_at":datetime.now(timezone.utc).isoformat(), "as_of_utc":cutoff.isoformat(), "predicate":"date_changed < as_of", "timezone":"Europe/Ljubljana", "limit":args.limit, "export":args.export, "allow_large_export":args.allow_large_export, "snapshot_limitation":"Oracle and PostgreSQL transactions are separate snapshots; cutoff reduces but cannot eliminate concurrent-change races.", "tables":[], "errors":[]}
        if args.limit < 0: raise AuditError("--limit must be non-negative")
        for s in selections:
            try:
                table, samples = audit_selection(p, s, cutoff, args.limit, d if args.export else None, args.max_export_rows, args.allow_large_export)
                if args.export and any(not info.get("complete", False) and not info.get("skipped", False) for info in table.get("export", {}).get("files", {}).values()):
                    raise AuditError("full export replay drift detected; see replay_drift artifact")
                table["sample_files"] = {}
                for kind, records in samples.items():
                    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", s.name).strip("._") or "table"
                    path = d / f"{safe}_{s.integration_id}_{kind}_samples.jsonl"; write_jsonl(path, records[:args.limit])
                    table["sample_files"][kind] = path.name
                manifest["tables"].append(table)
            except Exception as e:
                manifest["errors"].append({"table":s.name, "error":str(e)})
        manifest["ended_at"] = datetime.now(timezone.utc).isoformat(); (d / "manifest.json").write_text(json.dumps(manifest, indent=2, default=jsonable))
        summary = ["# KN delta audit", "", "|table|status|source only|target only|mismatch|volatile|", "|---|---|---:|---:|---:|---:|"]
        summary += [f"|{x['table']}|ok|{x['counts']['source_only']}|{x['counts']['target_only']}|{x['counts']['date_changed_mismatch']}|{x['counts']['post_cutoff_volatile']}|" for x in manifest['tables']]
        summary += [f"|{x['table']}|error: {x['error']}|||||" for x in manifest['errors']]
        (d / "report.md").write_text("\n".join(summary) + "\n")
        print(d); return 2 if manifest["errors"] else 0
    except (AuditError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr); return 1

if __name__ == "__main__": raise SystemExit(main())
