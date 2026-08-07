"""Read-only KN Oracle/FMP integration delta audit CLI."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from contextlib import ExitStack
from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from kn_audit_core import (AuditError, LJ, Selection, compare_eligible_rows, normalize_temporal,
                           parse_cutoff, qi)

SQL_START = re.compile(r"^\s*(?:with\b|select\b)", re.I | re.S)
SQL_FIELDS = ("url", "sql", "sql_query", "query", "select_sql", "source_sql", "integration_sql")
HIGHWATER_FIELDS = ("last_changed_datetime", "highwater", "high_water", "highwater_column", "date_changed_column")
METADATA_SQL = '''SELECT at.id AS attribute_table_id, at.name AS table_name, ati.id AS integration_id,
 ats.name AS connection_name, to_jsonb(ati) AS integration
 FROM attribute_tables at JOIN attribute_table_integrations ati ON ati.attribute_table_id=at.id
 JOIN attribute_table_sql_connections ats ON ats.id=ati.attribute_table_sql_connection_id
 WHERE lower(ats.name)=lower(%s) ORDER BY at.name, ati.id'''


def validated_select(sql: str) -> str:
    if not isinstance(sql, str): raise AuditError("integration SQL must start with SELECT or WITH")
    s = sql.strip()
    masked = re.sub(r"/\*.*?\*/|--[^\n]*|'(?:''|[^'])*'", lambda m: " " * len(m.group(0)), s, flags=re.S)
    if not SQL_START.match(masked): raise AuditError("integration SQL must start with SELECT or WITH")
    if masked.rstrip().endswith(";"):
        i = s.rfind(";"); s, masked = s[:i].rstrip(), masked[:i].rstrip()
    if ";" in masked or re.search(r"\b(?:insert|update|delete|merge|alter|drop|create|grant|execute|lock)\b|\bfor\s+update\b", masked, re.I):
        raise AuditError("integration SQL is not a single read-only statement")
    return s


def norm_date(value: Any) -> datetime:
    """Legacy public helper: Oracle native local timestamp conversion."""
    return normalize_temporal(value, "oracle_native_local", field="date")


def jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)): return v.isoformat()
    if isinstance(v, bytes): return v.hex()
    try:
        from decimal import Decimal
        if isinstance(v, Decimal): return str(v)
    except ImportError: pass
    return v


def load_selection(path: Path) -> list[Selection]:
    try:
        raw = json.loads(path.read_text())
        rows = raw["tables"] if isinstance(raw, dict) else raw
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise AuditError("selection must be a JSON array or an object with a tables array") from exc
    if not isinstance(rows, list): raise AuditError("selection tables must be an array")
    values = [Selection.from_dict(x) for x in rows]
    if not values: raise AuditError("selection has no tables")
    if len({x.integration_id for x in values}) != len(values): raise AuditError("selection repeats an integration id")
    return values


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.is_file(): return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k.strip()): os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def profile(env: str, require_kn: bool = False) -> dict[str, str]:
    p = env.upper()
    if p not in {"TEST", "STAG"}: raise AuditError("environment must be test or stag")
    need = ("USER", "PASSWORD", "HOST", "PORT") + (("DATABASE",) if require_kn else ())
    missing = [p + "_" + x for x in need if not os.getenv(p + "_" + x)]
    km = ["KN_" + x for x in ("USER", "PASSWORD", "HOST", "PORT", "SERVICE") if not os.getenv("KN_" + x)] if require_kn else []
    if missing or km: raise AuditError("missing environment variables: " + ", ".join(missing + km))
    return {"name":p.lower(), "user":os.environ[p+"_USER"], "password":os.environ[p+"_PASSWORD"], "host":os.environ[p+"_HOST"], "port":os.environ[p+"_PORT"], "database":os.getenv(p+"_DATABASE", ""), "metadata_database":os.getenv(p+"_METADATA_DATABASE", "fmp")}


def pg_connect(p: dict[str, str], metadata=False):
    import psycopg
    return psycopg.connect(host=p["host"], port=p["port"], user=p["user"], password=p["password"], dbname=p["metadata_database"] if metadata else p["database"], connect_timeout=int(os.getenv("KN_AUDIT_CONNECT_TIMEOUT_SECONDS", "15")), autocommit=False)


def oracle_connect():
    import oracledb
    lib = os.getenv("KN_ORACLE_CLIENT_LIB_DIR")
    if lib: oracledb.init_oracle_client(lib_dir=lib)
    return oracledb.connect(user=os.environ["KN_USER"], password=os.environ["KN_PASSWORD"], dsn=oracledb.makedsn(os.environ["KN_HOST"], int(os.environ["KN_PORT"]), service_name=os.environ["KN_SERVICE"]), tcp_connect_timeout=int(os.getenv("KN_AUDIT_CONNECT_TIMEOUT_SECONDS", "15")))


def field(obj: dict[str, Any], names: tuple[str, ...]) -> Any:
    return next((obj[x] for x in names if obj.get(x) not in (None, "")), None)


def discovery_rows(rows: Iterable[dict[str, Any]], include_sql: bool = False) -> list[dict[str, Any]]:
    result=[]
    for row in rows:
        raw=row.get("integration") or {}; sql=field(raw, SQL_FIELDS)
        result.append({"attribute_table_id":row["attribute_table_id"],"table_name":row["table_name"],"integration_id":row["integration_id"],"connection_name":row["connection_name"],"highwater":field(raw,HIGHWATER_FIELDS),"sql_hash":hashlib.sha256(str(sql or "").encode()).hexdigest() if sql else None,"has_sql":bool(sql), **({"saved_sql":sql} if include_sql else {})})
    counts=Counter(x["table_name"] for x in result)
    for x in result: x["ambiguous"]=counts[x["table_name"]]!=1
    return result


def configure_pg(conn, timeout_seconds: int, *, metadata: bool = False) -> None:
    with conn.cursor() as c:
        # Set transaction characteristics before every read; REPEATABLE READ gives
        # one stable target/metadata view for this connection.
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        c.execute("SELECT set_config('statement_timeout', %s, true)", (str(timeout_seconds * 1000),))
        c.execute("SET LOCAL TIME ZONE 'Europe/Ljubljana'")


def configure_oracle(conn, timeout_seconds: int) -> None:
    # Driver timeout bounds network/execute waits; DB role supplies the hard
    # read-only permission boundary.
    conn.call_timeout = timeout_seconds * 1000
    with conn.cursor() as c:
        c.execute("ALTER SESSION SET TIME_ZONE = 'Europe/Ljubljana'")
        c.execute("SET TRANSACTION READ ONLY")


def discover(conn, include_sql: bool = False) -> list[dict[str, Any]]:
    configure_pg(conn, 60, metadata=True)
    with conn.cursor(row_factory=__import__('psycopg').rows.dict_row) as cur:
        cur.execute(METADATA_SQL, ("KN ORACLE",)); return discovery_rows(cur.fetchall(), include_sql)


def resolve_integrations(conn, selections: list[Selection], timeout_seconds: int) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Resolve all selected IDs from one metadata connection/query."""
    configure_pg(conn, timeout_seconds, metadata=True)
    with conn.cursor(row_factory=__import__('psycopg').rows.dict_row) as c:
        c.execute(METADATA_SQL, ("KN ORACLE",)); rows=c.fetchall()
    wanted={s.integration_id:s for s in selections}; found={}; errors={}
    for row in rows:
        iid=str(row["integration_id"])
        if iid not in wanted: continue
        if iid in found: errors[iid] = f"{wanted[iid].name}: duplicate selected integration metadata"; found.pop(iid, None); continue
        s=wanted[iid]
        if row["table_name"] != s.target_table: errors[iid] = f"{s.name}: selection target table does not match metadata"; continue
        sql=field(row.get("integration") or {}, SQL_FIELDS)
        if not sql: errors[iid] = f"{s.name}: saved integration SQL unavailable"; continue
        try: safe=validated_select(sql)
        except AuditError as exc: errors[iid] = f"{s.name}: {exc}"; continue
        found[iid]={"sql":safe,"sql_hash":hashlib.sha256(safe.encode()).hexdigest(),"connection":row["connection_name"]}
    for iid in set(wanted)-set(found)-set(errors): errors[iid] = f"{wanted[iid].name}: selected integration is absent or no longer uses KN ORACLE"
    return found, errors


def run_dir(base: Path, cutoff: datetime) -> Path:
    base.mkdir(parents=True, exist_ok=True); stem=f"kn-delta-audit_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_cutoff-{cutoff:%Y%m%dT%H%M%SZ}"; d=base/stem; n=1
    while d.exists(): n+=1; d=base/f"{stem}-{n}"
    d.mkdir(mode=0o700); return d


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]):
    with path.open("w") as f:
        for r in records: f.write(json.dumps(r, default=jsonable, sort_keys=True)+"\n")
    path.chmod(0o600)


def cursor_rows(cur) -> Iterator[dict[str, Any]]:
    names=[x[0] for x in cur.description]
    while batch:=cur.fetchmany(1000):
        for row in batch: yield dict(zip(names,row))


EVIDENCE_CHUNK_KEYS = 100

def chunks(values, size=EVIDENCE_CHUNK_KEYS):
    for i in range(0, len(values), size): yield values[i:i + size]

def batch_predicate(cols: list[str], rows: list[dict[str, Any]], *, source: bool) -> tuple[str, Any]:
    """Bounded OR-of-ANDs. At most 100 keys, never a giant IN predicate."""
    pieces=[]
    if source:
        binds={}
        for n,row in enumerate(rows):
            pieces.append("(" + " AND ".join(f'x.{qi(c)} = :k{n}_{i}' for i,c in enumerate(cols)) + ")")
            binds.update({f"k{n}_{i}": row[c] for i,c in enumerate(cols)})
        return " OR ".join(pieces), binds
    params=[]
    for row in rows:
        pieces.append("(" + " AND ".join(f'{qi(c)} = %s' for c in cols) + ")")
        params.extend(row[c] for c in cols)
    return " OR ".join(pieces), tuple(params)

def fetch_evidence(oc, tc, export_dir: Path, s: Selection, integ: dict[str, Any], selected: dict[str, list[dict[str, dict[str, Any]]]]) -> dict[str, Any]:
    """Bounded, batched full-row reads after count/cap decision only."""
    output={}
    for kind,payloads in selected.items():
        files={}
        for side in ("source", "target"):
            key_rows=[p[side] for p in payloads if side in p]
            if not key_rows: continue
            cols=[x.source for x in s.keys] if side=="source" else [x.target for x in s.keys]
            full=[]
            for group in chunks(key_rows):
                pred,bind=batch_predicate(cols,group,source=side=="source")
                if side=="source":
                    sql=f"SELECT x.* FROM ({integ['sql']}) x WHERE {pred}"
                    with oc.cursor() as c: c.execute(sql,bind); full.extend(cursor_rows(c))
                else:
                    sql=f"SELECT * FROM {qi(s.target_schema)}.{qi(s.target_table)} WHERE {pred}"
                    with tc.cursor() as c: c.execute(sql,bind); full.extend(cursor_rows(c))
            # Exact returned row count is a bounded drift/duplicate guard. The
            # audit's numeric-key validation makes count equality sufficient.
            if len(full) != len(key_rows): raise AuditError(f"export re-read drift or duplicate rows for {kind}/{side}")
            safe=re.sub(r"[^A-Za-z0-9_.-]+","_",s.name).strip("._") or "table"; path=export_dir/f"{safe}_{s.integration_id}_{kind}_{side}_full.jsonl"; write_jsonl(path,full); files[side]=path.name
        output[kind]={"complete":True,"paths":files,"reread_at":datetime.now(timezone.utc).isoformat(),"chunks":(len(payloads)+EVIDENCE_CHUNK_KEYS-1)//EVIDENCE_CHUNK_KEYS,"note":"Full rows were re-read after count; no cross-database global snapshot exists."}
    return output


def audit_selection(p: dict[str,str], s: Selection, integ: dict[str,Any], cutoff: datetime, limit: int, export_dir: Path|None=None, max_export_rows: int=1000, allow_large_export: bool=False, timeout_seconds: int=1800):
    with ExitStack() as stack:
        oc=oracle_connect(); stack.callback(oc.close)
        tc=pg_connect(p); stack.callback(tc.close)
        configure_oracle(oc, timeout_seconds); configure_pg(tc, timeout_seconds)
        sk,tk=[x.source for x in s.keys],[x.target for x in s.keys]
        source_cutoff = cutoff.astimezone(LJ).replace(tzinfo=None) if s.source_temporal_mode == "oracle_native_local" else cutoff
        if s.source_temporal_mode == "oracle_native_local":
            source_pred = f'x.{qi(s.source_date)} < :cutoff'
        else:
            text_date=f"REPLACE(x.{qi(s.source_date)}, 'Z', '+00:00')"
            source_pred=(f"CASE WHEN INSTR({text_date}, '.') > 0 THEN "
                         f"TO_TIMESTAMP_TZ({text_date}, 'YYYY-MM-DD\"T\"HH24:MI:SS.FF TZH:TZM') "
                         f"ELSE TO_TIMESTAMP_TZ({text_date}, 'YYYY-MM-DD\"T\"HH24:MI:SS TZH:TZM') END < :cutoff")
        source_sql=f"SELECT {', '.join(f'x.{qi(c)} AS {qi(c)}' for c in [*sk,s.source_date])} FROM ({integ['sql']}) x WHERE {source_pred} ORDER BY {', '.join('x.'+qi(c) for c in sk)}"
        target_sql=f"SELECT {', '.join(qi(c) for c in [*tk,s.target_date])} FROM {qi(s.target_schema)}.{qi(s.target_table)} WHERE {qi(s.target_date)} < %s ORDER BY {', '.join(qi(c) for c in tk)}"
        sc=oc.cursor(); stack.callback(sc.close); tcurs=tc.cursor(name="kn_delta_target"); stack.callback(tcurs.close); tcurs.itersize=1000
        sc.execute(source_sql, {"cutoff": source_cutoff}); tcurs.execute(target_sql,(cutoff,))
        evidence={k:[] for k in ("source_only","target_only","date_changed_mismatch")}
        def retain(kind,payload):
            # The override intentionally accepts memory/query cost in exchange
            # for complete evidence.  Default retains only cap+1 key payloads.
            if export_dir and kind in evidence and (allow_large_export or len(evidence[kind]) <= max_export_rows):
                evidence[kind].append(payload)
        counts,samples=compare_eligible_rows(cursor_rows(sc),cursor_rows(tcurs),sk,tk,s.source_date,s.target_date,s.source_temporal_mode,s.target_temporal_mode,limit,retain)
        table={"table":s.name,"integration_id":s.integration_id,"sql_hash":integ["sql_hash"],"keys":[asdict(x) for x in s.keys],"source_date":s.source_date,"target_date":s.target_date,"source_temporal_mode":s.source_temporal_mode,"target_temporal_mode":s.target_temporal_mode,"counts":counts,"normal_scan_queries":{"oracle_saved_integration":1,"postgres_target":1}}
        if export_dir:
            skipped={}; selected={}
            for kind, count in counts.items():
                if count>max_export_rows and not allow_large_export: skipped[kind]={"skipped":True,"reason":f"category exceeds {max_export_rows} rows"}
                elif count>max_export_rows and allow_large_export: selected[kind]=evidence[kind]
                else: selected[kind]=evidence[kind]
            table["export"]={"files":{**skipped,**fetch_evidence(oc,tc,export_dir,s,integ,selected)},"cap":max_export_rows,"large_override":allow_large_export}
        return table,samples


def main(argv: list[str]|None=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument("--environment",default="test"); ap.add_argument("--output-dir",default="artifacts")
    sub=ap.add_subparsers(dest="command",required=True); dp=sub.add_parser("discover"); dp.add_argument("--include-sql",action="store_true")
    au=sub.add_parser("audit"); au.add_argument("--selection",required=True); au.add_argument("--as-of",required=True); au.add_argument("--limit",type=int,default=20); au.add_argument("--export",action="store_true"); au.add_argument("--allow-large-export",action="store_true"); au.add_argument("--max-export-rows",type=int,default=1000); au.add_argument("--query-timeout-seconds",type=int,default=1800)
    for child in (dp,au): child.add_argument("--environment",default=argparse.SUPPRESS); child.add_argument("--output-dir",default=argparse.SUPPRESS)
    load_dotenv(); args=ap.parse_args(argv)
    try:
        if args.command=="audit" and (args.limit<0 or args.max_export_rows<1 or args.query_timeout_seconds<1): raise AuditError("limit, export cap, and timeout must be positive (limit may be zero)")
        if args.command=="audit" and args.allow_large_export and not args.export: raise AuditError("--allow-large-export requires --export")
        p=profile(args.environment,require_kn=args.command=="audit"); d=run_dir(Path(args.output_dir), datetime.now(timezone.utc) if args.command=="discover" else parse_cutoff(args.as_of))
        if args.command=="discover":
            c=pg_connect(p,metadata=True)
            try: rows=discover(c,args.include_sql)
            finally: c.close()
            write_jsonl(d/"inventory.jsonl",rows); (d/"inventory.md").write_text("# KN ORACLE integrations\n\n"+"\n".join(f"- `{r['table_name']}` — `{r['integration_id']}` — highwater: `{r['highwater']}`" for r in rows)+"\n"); print(d); return 0
        cutoff=parse_cutoff(args.as_of); selections=load_selection(Path(args.selection)); mc=pg_connect(p,metadata=True)
        try: integrations, resolution_errors=resolve_integrations(mc,selections,args.query_timeout_seconds)
        finally: mc.close()
        manifest={"environment":p["name"],"started_at":datetime.now(timezone.utc).isoformat(),"as_of_utc":cutoff.isoformat(),"predicate":"date_changed < as_of (bound in both normal scan queries)","normal_scan_contract":"one cutoff-bounded Oracle integration key/date stream and one cutoff-bounded PostgreSQL target key/date stream per table","export_snapshot_limitation":"Evidence rows are re-read after exact counts; timestamps are recorded and there is no global cross-database snapshot.","tables":[],"errors":[]}
        for s in selections:
            try:
                if s.integration_id in resolution_errors: raise AuditError(resolution_errors[s.integration_id])
                table,samples=audit_selection(p,s,integrations[s.integration_id],cutoff,args.limit,d if args.export else None,args.max_export_rows,args.allow_large_export,args.query_timeout_seconds); table["sample_files"]={}
                for kind,records in samples.items():
                    path=d/f"{re.sub(r'[^A-Za-z0-9_.-]+','_',s.name)}_{s.integration_id}_{kind}_samples.jsonl"; write_jsonl(path,records); table["sample_files"][kind]=path.name
                manifest["tables"].append(table)
            except Exception as e: manifest["errors"].append({"table":s.name,"error":str(e)})
        manifest["ended_at"]=datetime.now(timezone.utc).isoformat(); (d/"manifest.json").write_text(json.dumps(manifest,indent=2,default=jsonable)); (d/"report.md").write_text("# KN delta audit\n\n"+json.dumps({x["table"]:x["counts"] for x in manifest["tables"]},indent=2)+"\n"); print(d); return 2 if manifest["errors"] else 0
    except (AuditError,OSError,json.JSONDecodeError) as e: print(f"error: {e}",file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
