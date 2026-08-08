#!/usr/bin/env python3
"""Resumable, set-based reconciliation from staging PostgreSQL to production."""
from __future__ import annotations

import argparse, hashlib, json, os, re, signal, sqlite3, sys, time, uuid, tempfile, shutil
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
HERE = Path(__file__).resolve().parent
STATE_ROOT = HERE / ".state"
STATE_VERSION = 3  # v2 did not freeze payload digests
STOP_REQUESTED = False

def valid_identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value): raise ValueError(f"{label} must be a plain PostgreSQL identifier")
    return value

def relation(schema: str, table: str) -> str: return f'"{schema}"."{table}"'
def quote(name: str) -> str: return f'"{name}"'
def streaming_cursor(conn: Any, label: str) -> Any:
    try:
        cursor=conn.cursor(name=f"stag_prod_{label}_{os.getpid()}_{id(conn)}")
    except TypeError:  # lightweight unit-test DB doubles
        cursor=conn.cursor()
    try: cursor.itersize=10_000
    except AttributeError: pass
    return cursor

def load_environment() -> None:
    try: from dotenv import load_dotenv
    except ImportError as e: raise RuntimeError("install requirements into .venv before running this script") from e
    load_dotenv(HERE / ".env", override=False)

def psycopg_module() -> Any:
    try: import psycopg; return psycopg
    except ImportError as e: raise RuntimeError("install requirements into .venv before running this script") from e

def settings(prefix: str) -> dict[str, Any]:
    required = [f"{prefix}_{x}" for x in ("USER", "PASSWORD", "HOST", "PORT")]
    missing = [x for x in required if not os.environ.get(x)]
    if missing: raise RuntimeError(f"missing PostgreSQL environment variables: {', '.join(missing)}")
    return {"user": os.environ[f"{prefix}_USER"], "password": os.environ[f"{prefix}_PASSWORD"], "host": os.environ[f"{prefix}_HOST"], "port": int(os.environ[f"{prefix}_PORT"]), "dbname": os.environ.get(f"{prefix}_DATABASE", "fmp_data_gurs")}

def columns(conn: Any, schema: str, table: str) -> list[str]:
    with conn.cursor() as c:
        c.execute("""SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s
          AND is_generated='NEVER' AND identity_generation IS DISTINCT FROM 'ALWAYS' ORDER BY ordinal_position""", (schema,table))
        return [r[0] for r in c.fetchall()]

# Kept as public compatibility helpers: the focused tests and small downstream
# scripts used these names before the resumable implementation was introduced.
table_columns = columns

def verify(stag: Any, prod: Any, schema: str, table: str, key: str, changed: str) -> list[str]:
    sc, pc = table_columns(stag,schema,table), table_columns(prod,schema,table)
    if not sc: raise RuntimeError(f"staging table {schema}.{table} was not found or has no insertable columns")
    if not pc: raise RuntimeError(f"production table {schema}.{table} was not found or has no insertable columns")
    if set(sc) != set(pc):
        raise RuntimeError(f"table columns differ for {schema}.{table}; only in staging: {sorted(set(sc)-set(pc)) or '-'}; only in production: {sorted(set(pc)-set(sc)) or '-'}")
    if key not in sc or changed not in sc: raise RuntimeError(f"both {schema}.{table} tables must have key field {key} and change field {changed}")
    return sc

verify_tables = verify

def unique_index(conn: Any, schema: str, table: str, key: str) -> bool:
    sql = """SELECT 1 FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_class idx ON idx.oid=i.indexrelid
      WHERE n.nspname=%s AND t.relname=%s AND i.indisunique AND i.indpred IS NULL
      AND i.indisvalid AND i.indisready AND idx.relam = (SELECT oid FROM pg_am WHERE amname='btree')
      AND (SELECT array_agg(a.attname ORDER BY x.ord) FROM unnest(i.indkey) WITH ORDINALITY x(attnum,ord) JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=x.attnum WHERE x.ord <= i.indnkeyatts) = ARRAY[%s] LIMIT 1"""
    with conn.cursor() as c: c.execute(sql,(schema,table,key)); return c.fetchone() is not None

def schema_signature(conn: Any, schema: str, table: str, copied: list[str]) -> list[tuple[str,str,str|None]]:
    with conn.cursor() as c:
        c.execute("""SELECT a.attname, format_type(a.atttypid,a.atttypmod), COALESCE(coll.collnamespace::regnamespace::text || '.' || coll.collname, '')
          FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace LEFT JOIN pg_collation coll ON coll.oid=a.attcollation
          WHERE n.nspname=%s AND t.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""",(schema,table))
        found={name:(typ,collation) for name,typ,collation in c.fetchall()}
    return [(name,*found[name]) for name in copied]

def db_identity(prefix: str) -> str:
    s=settings(prefix); return f"{s['host']}:{s['port']}/{s['dbname']}"
def state_path(schema:str,table:str,key:str,changed:str)->Path:
    raw=json.dumps([STATE_VERSION,db_identity("STAG"),db_identity("PROD"),schema,table,key,changed],sort_keys=True)
    return STATE_ROOT / hashlib.sha256(raw.encode()).hexdigest() / "state.sqlite"

def init_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path); db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA synchronous=FULL")
    db.executescript("""CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS source (id TEXT PRIMARY KEY, change_value TEXT, payload_digest TEXT NOT NULL, ordinal INTEGER NOT NULL, seen INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS actions (ordinal INTEGER PRIMARY KEY, id TEXT NOT NULL, change_value TEXT, action TEXT NOT NULL, prod_change TEXT);
      CREATE TABLE IF NOT EXISTS progress (phase TEXT PRIMARY KEY, last_ordinal INTEGER NOT NULL DEFAULT 0);
      CREATE INDEX IF NOT EXISTS actions_action_ordinal ON actions(action, ordinal);
      CREATE INDEX IF NOT EXISTS source_seen_ordinal ON source(seen, ordinal);""")
    return db

def sigint(_s: int, _f: Any) -> None:
    global STOP_REQUESTED
    if STOP_REQUESTED: raise KeyboardInterrupt
    STOP_REQUESTED=True; print("SIGINT received: finishing the current page, checkpointing it, then stopping. Press Ctrl-C again to abort immediately.", flush=True)

def encode_value(v: Any) -> str:
    """Lossless, explicit SQLite representation; never rely on str() ordering."""
    if v is None: return json.dumps(["null", None])
    if isinstance(v, uuid.UUID): return json.dumps(["uuid", str(v)])
    if isinstance(v, Decimal): return json.dumps(["decimal", str(v)])
    if isinstance(v, datetime): return json.dumps(["datetime", v.isoformat()])
    if isinstance(v, date): return json.dumps(["date", v.isoformat()])
    if isinstance(v, bool): return json.dumps(["bool", v])
    if isinstance(v, int): return json.dumps(["int", str(v)])
    if isinstance(v, float): return json.dumps(["float", repr(v)])
    if isinstance(v, str): return json.dumps(["str", v])
    raise RuntimeError(f"unsupported resumable state value type: {type(v).__name__}")

def decode_value(raw: str) -> Any:
    kind, value = json.loads(raw)
    if kind == "null": return None
    if kind == "uuid": return uuid.UUID(value)
    if kind == "decimal": return Decimal(value)
    if kind == "datetime": return datetime.fromisoformat(value)
    if kind == "date": return date.fromisoformat(value)
    if kind == "bool": return bool(value)
    if kind == "int": return int(value)
    if kind == "float": return float(value)
    if kind == "str": return value
    raise RuntimeError(f"unknown resumable state value tag: {kind}")

def change_cmp(a: Any,b: Any)->int|None:
    if a == b: return 0
    if a is None or b is None: return None
    return (a>b)-(a<b)

def payload_digest(row: tuple[Any, ...]) -> str:
    """Stable digest of every copied value, including NULL/type distinctions."""
    encoded=json.dumps([encode_value(value) for value in row], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

def advisory_key(schema:str,table:str,key:str)->int:
    return int.from_bytes(hashlib.sha256(f"stag-to-prod:{schema}.{table}:{key}".encode()).digest()[:8],"big",signed=True)
def lock(conn:Any,k:int)->None:
    with conn.cursor() as c: c.execute("SELECT pg_advisory_lock(%s)",(k,))

def stream_manifest(stag:Any, db:sqlite3.Connection, schema:str,table:str,columns:list[str],key:str,changed:str, progress:int)->int:
    if db.execute("SELECT 1 FROM meta WHERE key='manifest_done'").fetchone(): return int(db.execute("SELECT value FROM meta WHERE key='manifest_count'").fetchone()[0])
    db.execute("DELETE FROM source"); db.commit(); total=0
    print("preflight: freezing staging membership/change manifest...",flush=True)
    with streaming_cursor(stag,"manifest") as c:
        projection=', '.join(map(quote,columns)); c.execute(f"SELECT {projection} FROM {relation(schema,table)} ORDER BY {quote(key)}")
        while rows:=c.fetchmany(progress):
            out=[]
            for row in rows:
                ident=row[columns.index(key)]; ch=row[columns.index(changed)]
                if ident is None: raise RuntimeError(f"{schema}.{table} contains a NULL {key}")
                total+=1; out.append((encode_value(ident),encode_value(ch),payload_digest(row),total))
            try: db.executemany("INSERT INTO source(id,change_value,payload_digest,ordinal) VALUES (?,?,?,?)",out); db.commit()
            except sqlite3.IntegrityError as e: raise RuntimeError(f"{schema}.{table} contains a duplicate {key}") from e
            print(f"preflight manifest: {total} keys",flush=True)
            if STOP_REQUESTED: return total
    if STOP_REQUESTED: return total
    db.execute("INSERT OR REPLACE INTO meta VALUES ('manifest_done','1')"); db.execute("INSERT OR REPLACE INTO meta VALUES ('manifest_count',?)",(str(total),)); db.commit(); return total

def preflight(stag:Any,prod:Any,db:sqlite3.Connection,schema:str,table:str,key:str,changed:str,progress:int)->dict[str,int]:
    done=db.execute("SELECT 1 FROM meta WHERE key='preflight_done'").fetchone()
    if done:
        counts={k:int(v) for k,v in db.execute("SELECT key,value FROM meta WHERE key LIKE 'count_%'")}
        if counts.get("count_conflict",0): raise RuntimeError("persisted preflight contains production conflicts; restart after resolving them")
        return counts
    db.execute("DELETE FROM actions"); db.execute("UPDATE source SET seen=0"); db.commit(); counts={"count_insert":0,"count_update":0,"count_delete":0,"count_unchanged":0,"count_conflict":0}; ordinal=0
    print("preflight: comparing production membership/change values...",flush=True)
    with streaming_cursor(prod,"preflight") as c:
        c.execute(f"SELECT {quote(key)}, {quote(changed)} FROM {relation(schema,table)} ORDER BY {quote(key)}")
        while rows:=c.fetchmany(progress):
            for ident,ch in rows:
                if ident is None: raise RuntimeError(f"production {schema}.{table} contains a NULL {key}")
                stored=db.execute("SELECT change_value FROM source WHERE id=?",(encode_value(ident),)).fetchone()
                if stored is None:
                    ordinal+=1; db.execute("INSERT INTO actions VALUES (?,?,?,?,?)",(ordinal,encode_value(ident),None,"delete",encode_value(ch))); counts["count_delete"]+=1
                else:
                    cmp=change_cmp(decode_value(stored[0]),ch); action="unchanged" if cmp==0 else "update" if cmp==1 else "conflict"
                    ordinal+=1; encoded=encode_value(ident); db.execute("INSERT INTO actions VALUES (?,?,?,?,?)",(ordinal,encoded,stored[0],action,encode_value(ch))); db.execute("UPDATE source SET seen=1 WHERE id=?",(encoded,)); counts[f"count_{action}"]+=1
            db.commit(); print(f"preflight production: {ordinal} keys",flush=True)
            if STOP_REQUESTED: return counts
    if STOP_REQUESTED: return counts
    for source_id, source_change in db.execute("SELECT id,change_value FROM source WHERE seen=0 ORDER BY ordinal"):
        ordinal+=1; db.execute("INSERT INTO actions VALUES (?,?,?,?,NULL)",(ordinal,source_id,source_change,"insert")); counts["count_insert"]+=1
    for k,v in counts.items(): db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)",(k,str(v)))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('preflight_done','1')"); db.commit()
    if counts["count_conflict"]: raise RuntimeError("production has rows with a newer or incomparable change field; no changes were made")
    return counts

def preview(db:sqlite3.Connection, stag:Any,prod:Any,schema:str,table:str,columns:list[str],key:str,limit:int,counts:dict[str,int],apply:bool)->None:
    prod_ids=counts["count_delete"]+counts["count_unchanged"]+counts["count_update"]+counts["count_conflict"]
    print(json.dumps({"mode":"apply" if apply else "dry-run","schema":schema,"table":table,"id_field":key,"staging_ids":int(db.execute("SELECT count(*) FROM source").fetchone()[0]),"production_ids":prod_ids,"unchanged":counts["count_unchanged"],"delete_from_production":counts["count_delete"],"insert_into_production":counts["count_insert"],"update_in_production":counts["count_update"],"production_newer_conflicts":counts["count_conflict"]}))
    if not limit:return
    for action,conn in (("delete",prod),("insert",stag),("update",stag),("conflict",prod)):
        print(f"{action.upper()} rows (showing up to {limit}):")
        ids=[decode_value(r[0]) for r in db.execute("SELECT id FROM actions WHERE action=? ORDER BY ordinal LIMIT ?",(action,limit))]
        if not ids: print("(none)"); continue
        if action=="conflict":
            for r in db.execute("SELECT id,change_value,prod_change FROM actions WHERE action='conflict' ORDER BY ordinal LIMIT ?",(limit,)): print(json.dumps({"id":decode_value(r[0]),"staging_change":decode_value(r[1]),"production_change":decode_value(r[2])},default=str))
            continue
        with conn.cursor() as c:
            c.execute(f"SELECT {', '.join(map(quote,columns))} FROM {relation(schema,table)} WHERE {quote(key)}=ANY(%s) ORDER BY {quote(key)}",(ids,))
            for r in c.fetchall(): print(json.dumps(dict(zip(columns,r)),default=str,ensure_ascii=False))

def payload_rows(stag:Any,schema:str,table:str,cols:list[str],key:str,changed:str, expected:dict[Any,tuple[Any,str]],ids:list[Any])->list[tuple[Any,...]]:
    with streaming_cursor(stag,"verify") as c:
        c.execute(f"SELECT {', '.join(map(quote,cols))} FROM {relation(schema,table)} WHERE {quote(key)}=ANY(%s)",(ids,)); rows=c.fetchall()
    got={r[cols.index(key)] for r in rows}
    if got != set(ids): raise RuntimeError("staging changed after preflight; restart required")
    for row in rows:
        frozen_change, frozen_digest = expected[row[cols.index(key)]]
        if row[cols.index(changed)] != frozen_change or payload_digest(row) != frozen_digest:
            raise RuntimeError("staging payload changed after preflight; restart required")
    stag.commit()  # do not retain an implicit stale staging snapshot
    return rows

def equivalent(left: str, right: str, cols: list[str]) -> str:
    """NULL-safe exact row comparison used to make replay unambiguous."""
    return " AND ".join(f"{left}.{quote(col)} IS NOT DISTINCT FROM {right}.{quote(col)}" for col in cols)

def apply_page(prod:Any,rows:list[tuple[Any,...]],expected:dict[Any,Any],schema:str,table:str,cols:list[str],key:str,changed:str,action:str)->None:
    rel=relation(schema,table); temp='"_stag_prod_page"'; colsql=', '.join(map(quote,cols)); updates=[c for c in cols if c!=key]
    desired=equivalent("target","source",cols)
    with prod.transaction():
        with prod.cursor() as c:
            # AS SELECT preserves the destination's actual changed-column type
            # for the expected old version, including timestamptz and domains.
            c.execute(f"CREATE TEMP TABLE {temp} ON COMMIT DROP AS SELECT {colsql}, {quote(changed)} AS \"_expected_prod_change\" FROM {rel} WHERE false")
            with c.copy(f"COPY {temp} ({colsql}, \"_expected_prod_change\") FROM STDIN") as cp:
                for row in rows: cp.write_row((*row, expected[row[cols.index(key)]]))
            if action == "insert":
                c.execute(f"SELECT count(*) FROM {temp} source JOIN {rel} target ON target.{quote(key)}=source.{quote(key)} WHERE NOT ({desired})")
                if c.fetchone()[0]: raise RuntimeError("production changed since preflight; insert page is not safely replayable")
                c.execute(f"INSERT INTO {rel} ({colsql}) SELECT {colsql} FROM {temp} source WHERE NOT EXISTS (SELECT 1 FROM {rel} target WHERE target.{quote(key)}=source.{quote(key)})")
            else:
                expected_old=f"target.{quote(changed)} IS NOT DISTINCT FROM source.\"_expected_prod_change\""
                c.execute(f"SELECT count(*) FROM {temp} source LEFT JOIN {rel} target ON target.{quote(key)}=source.{quote(key)} WHERE target.{quote(key)} IS NULL OR (NOT ({desired}) AND NOT ({expected_old}))")
                if c.fetchone()[0]: raise RuntimeError("production changed since preflight; update page is not safely replayable")
                c.execute(f"UPDATE {rel} target SET {', '.join(f'{quote(x)}=source.{quote(x)}' for x in updates)} FROM {temp} source WHERE target.{quote(key)}=source.{quote(key)} AND NOT ({desired}) AND {expected_old}")

def delete_page(prod:Any, records:list[tuple[Any,Any]],schema:str,table:str,key:str,changed:str)->None:
    rel=relation(schema,table); temp='"_stag_prod_delete"'
    with prod.transaction():
        with prod.cursor() as c:
            c.execute(f"CREATE TEMP TABLE {temp} ON COMMIT DROP AS SELECT {quote(key)}, {quote(changed)} AS \"_expected_prod_change\" FROM {rel} WHERE false")
            with c.copy(f"COPY {temp} ({quote(key)}, \"_expected_prod_change\") FROM STDIN") as cp:
                for record in records: cp.write_row(record)
            guard=f"target.{quote(changed)} IS NOT DISTINCT FROM source.\"_expected_prod_change\""
            c.execute(f"SELECT count(*) FROM {temp} source JOIN {rel} target ON target.{quote(key)}=source.{quote(key)} WHERE NOT ({guard})")
            if c.fetchone()[0]: raise RuntimeError("production changed since preflight; delete page is not safely replayable")
            c.execute(f"DELETE FROM {rel} target USING {temp} source WHERE target.{quote(key)}=source.{quote(key)} AND {guard}")

def run_actions(stag:Any,prod:Any,db:sqlite3.Connection,schema:str,table:str,cols:list[str],key:str,changed:str,page:int,max_pages:int|None)->bool:
    total_pages = 0
    for action in ("insert","update"):
        last=db.execute("SELECT last_ordinal FROM progress WHERE phase=?",(action,)).fetchone(); last=last[0] if last else 0; done=0
        while True:
            if STOP_REQUESTED: return
            rows=db.execute("SELECT ordinal,id,change_value,prod_change FROM actions WHERE action=? AND ordinal>? ORDER BY ordinal LIMIT ?",(action,last,page)).fetchall()
            if not rows: break
            ids=[decode_value(r[1]) for r in rows]
            source_changes={}
            for _ordinal, encoded_id, _change, _prod_change in rows:
                frozen=db.execute("SELECT change_value,payload_digest FROM source WHERE id=?",(encoded_id,)).fetchone()
                source_changes[decode_value(encoded_id)]=(decode_value(frozen[0]),frozen[1])
            prod_expected={decode_value(r[1]): (decode_value(r[3]) if r[3] is not None else None) for r in rows}
            started=time.monotonic(); apply_page(prod,payload_rows(stag,schema,table,cols,key,changed,source_changes,ids),prod_expected,schema,table,cols,key,changed,action)
            last=rows[-1][0]; db.execute("INSERT OR REPLACE INTO progress VALUES (?,?)",(action,last)); db.commit(); done+=1
            print(f"{action} committed page {done} ({len(rows)} rows; {len(rows)/(time.monotonic()-started):,.0f} rows/s)",flush=True)
            total_pages += 1
            if STOP_REQUESTED or (max_pages and total_pages>=max_pages): return False
    # final source recheck: exact key/change frozen set must still match
    print("delete preflight: verifying frozen staging source...", flush=True)
    frozen=iter(db.execute("SELECT id,change_value FROM source ORDER BY ordinal"))
    expected_row=next(frozen,None)
    with streaming_cursor(stag,"final_verify") as c:
        c.execute(f"SELECT {quote(key)}, {quote(changed)} FROM {relation(schema,table)} ORDER BY {quote(key)}")
        while chunk:=c.fetchmany(10_000):
            for item in chunk:
                if expected_row != (encode_value(item[0]),encode_value(item[1])):
                    raise RuntimeError("staging changed since preflight; refusing deletes; restart required")
                expected_row=next(frozen,None)
                if STOP_REQUESTED: return False
    if expected_row is not None: raise RuntimeError("staging changed since preflight; refusing deletes; restart required")
    stag.commit()  # final verification is a fresh bounded read transaction
    last=db.execute("SELECT last_ordinal FROM progress WHERE phase='delete'").fetchone(); last=last[0] if last else 0; done=0
    while True:
        if STOP_REQUESTED: return False
        rows=db.execute("SELECT ordinal,id,prod_change FROM actions WHERE action='delete' AND ordinal>? ORDER BY ordinal LIMIT ?",(last,page)).fetchall()
        if not rows: break
        delete_page(prod,[(decode_value(r[1]),decode_value(r[2])) for r in rows],schema,table,key,changed)
        last=rows[-1][0]; db.execute("INSERT OR REPLACE INTO progress VALUES ('delete',?)",(last,)); db.commit(); done+=1; print(f"delete committed page {done} ({len(rows)} rows)",flush=True)
        total_pages += 1
        if STOP_REQUESTED or (max_pages and total_pages>=max_pages): return False
    return True

def args_parse()->argparse.Namespace:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("table"); p.add_argument("--schema"); m=p.add_mutually_exclusive_group(); m.add_argument("--dry-run",action="store_true");m.add_argument("--apply",action="store_true")
    p.add_argument("--id-field",default="id");p.add_argument("--change-field",default="date_change");p.add_argument("--preview-limit",type=int,default=5);p.add_argument("--page-size",type=int,default=10_000);p.add_argument("--batch-size",type=int,help="deprecated alias for --page-size");p.add_argument("--progress-every",type=int,default=10_000);p.add_argument("--restart",action="store_true");p.add_argument("--max-pages",type=int)
    a=p.parse_args();
    if a.batch_size: a.page_size=a.batch_size
    if a.page_size<=0 or a.progress_every<=0 or a.preview_limit<0 or (a.max_pages is not None and a.max_pages<=0): p.error("page/progress/max sizes must be positive and preview limit non-negative")
    if a.restart and not a.apply: p.error("--restart requires --apply")
    return a

def main()->int:
    a=args_parse(); signal.signal(signal.SIGINT,sigint)
    temporary_dir: Path | None = None
    try:
        load_environment()
        table=valid_identifier(a.table,"table"); schema=valid_identifier(a.schema or os.environ.get("SYNC_SCHEMA","public"),"schema"); key=valid_identifier(a.id_field,"id field").lower(); changed=valid_identifier(a.change_field,"change field").lower(); psy=psycopg_module()
        durable_path=state_path(schema,table,key,changed)
        path=durable_path
        if not a.apply:
            temporary_dir=Path(tempfile.mkdtemp(prefix="stag-to-prod-")); path=temporary_dir / "state.sqlite"
        with psy.connect(**settings("STAG")) as stag, psy.connect(**settings("PROD")) as prod:
            cols=verify(stag,prod,schema,table,key,changed)
            if not unique_index(stag,schema,table,key) or not unique_index(prod,schema,table,key): raise RuntimeError(f"both tables require a non-partial single-column unique index on {key}")
            k=advisory_key(schema,table,key)
            # Every invocation chooses the same global session order, avoiding
            # stag→prod / prod→stag deadlocks when endpoints are swapped.
            endpoints = {}
            for identity, role, connection in ((db_identity("STAG"),"stag",stag),(db_identity("PROD"),"prod",prod)):
                endpoints.setdefault(identity, (role, connection))
            ordered_connections=sorted(((identity,*value) for identity,value in endpoints.items()), key=lambda item:(item[0],item[1]))
            for _identity,_role,connection in ordered_connections: lock(connection,k)
            # Advisory locks are session scoped; close metadata transactions so
            # the snapshot transaction below can set its isolation level.
            stag.commit(); prod.commit()
            if a.restart and durable_path.exists(): shutil.rmtree(durable_path.parent)
            # A completed state is not an incremental cache: a new ordinary
            # apply is a new full reconciliation.
            if a.apply and durable_path.exists():
                old=sqlite3.connect(durable_path)
                try: completed=old.execute("SELECT 1 FROM meta WHERE key='completed'").fetchone()
                finally: old.close()
                if completed: shutil.rmtree(durable_path.parent)
            db=init_state(path)
            try:
                stag_sig=schema_signature(stag,schema,table,cols); prod_sig=schema_signature(prod,schema,table,cols)
                if stag_sig != prod_sig:
                    raise RuntimeError("staging and production copied column types/collations differ")
                signature=json.dumps({"stag":stag_sig,"prod":prod_sig},sort_keys=True)
                old_signature=db.execute("SELECT value FROM meta WHERE key='schema_signature'").fetchone()
                if old_signature and old_signature[0] != signature:
                    raise RuntimeError("table type/collation signature changed; use --restart")
                db.execute("INSERT OR REPLACE INTO meta VALUES ('schema_signature',?)",(signature,)); db.commit()
                if not db.execute("SELECT 1 FROM meta WHERE key='manifest_done'").fetchone():
                    # A single stable staging snapshot is the contract for the
                    # persisted manifest; SQLite checkpoints are independent.
                    with stag.transaction():
                        with stag.cursor() as c: c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                        stream_manifest(stag,db,schema,table,cols,key,changed,a.progress_every)
                if STOP_REQUESTED:
                    print("stopped during preflight; no production changes were made", flush=True)
                    return 0
                counts=preflight(stag,prod,db,schema,table,key,changed,a.progress_every); preview(db,stag,prod,schema,table,cols,key,a.preview_limit,counts,a.apply)
                if STOP_REQUESTED:
                    print("stopped during preflight; no production changes were made", flush=True)
                    return 0
                # Preflight/preview are reads; finish their implicit DB-API
                # transactions so each following page is a real transaction.
                stag.commit(); prod.commit()
                if a.apply:
                    completed=run_actions(stag,prod,db,schema,table,cols,key,changed,a.page_size,a.max_pages)
                    if completed: db.execute("INSERT OR REPLACE INTO meta VALUES ('completed','1')"); db.commit()
            finally: db.close()
        return 0
    except (RuntimeError,ValueError,KeyboardInterrupt) as e: print(f"error: {e}",file=sys.stderr); return 2
    finally:
        # Dry-run state is intentionally disposable even when connection,
        # preflight, or preview handling raises. Durable state is never here.
        if temporary_dir: shutil.rmtree(temporary_dir, ignore_errors=True)
if __name__=='__main__': raise SystemExit(main())
