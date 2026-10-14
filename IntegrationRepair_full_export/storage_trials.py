#!/usr/bin/env python3
"""Local-only backend/commit trials on one cached, read-only sample."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import duckdb
from dotenv import dotenv_values
import psycopg
from psycopg import sql

from definition import IntegrationDefinition
from source import wall_time

BATCH = 10_000
SCHEMA = [
    'CREATE TABLE source(key TEXT PRIMARY KEY,date TEXT NOT NULL,seen INTEGER DEFAULT 0)',
    'CREATE TEMP TABLE page(target_id TEXT PRIMARY KEY,key TEXT UNIQUE,date TEXT NOT NULL)',
    'CREATE TABLE differences(kind TEXT,key TEXT,date TEXT,target_id TEXT)',
    'CREATE TABLE progress(stage TEXT PRIMARY KEY,last_key TEXT)',
]
PAGE_DIFF = '''INSERT INTO differences
    SELECT CASE WHEN s.key IS NULL THEN 'remove' WHEN s.date>p.date THEN 'update' ELSE 'ahead' END,
           p.key, coalesce(s.date,p.date), p.target_id
    FROM page p LEFT JOIN source s ON s.key=p.key
    WHERE s.key IS NULL OR (s.date<=? AND s.date<>p.date)'''

def sample(store_path, run_id, limit, output):
    """Cache a bounded actual source/LIFT interval once; never write remote data."""
    with sqlite3.connect(Path(store_path).resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory = sqlite3.Row
        run = dict(db.execute('SELECT * FROM integration_transfer WHERE id=?',(run_id,)).fetchone())
        source = [(json.loads(r['key']),r['date']) for r in db.execute(
            'SELECT key,date FROM remote_ids_and_date_changed WHERE run_id=? ORDER BY key LIMIT ?', (run_id,limit))]
    if not source or not all(isinstance(key,str) for key,_ in source):
        raise ValueError('This range experiment uses text integration keys')
    cfg = dotenv_values('.env')
    pg = dict(host=cfg['PG_HOST'],port=cfg['PG_PORT'],user=cfg['PG_USER'],password=cfg['PG_PASSWORD'],
              connect_timeout=5,options='-c default_transaction_read_only=on -c statement_timeout=10000')
    with psycopg.connect(**pg,dbname=cfg['PG_DATABASE_SYSTEM']) as db:
        definition = IntegrationDefinition.load(db,run['integration_id'])
    started = perf_counter()
    target = []
    with psycopg.connect(**pg,dbname=cfg['PG_DATABASE_DATA']) as db:
        for start in range(0,len(source),BATCH):
            keys = [key for key,_ in source[start:start+BATCH]]
            rows = db.execute(sql.SQL('SELECT id,{},{} FROM {} WHERE {}=ANY(%s) AND {}<=%s').format(
                sql.Identifier(definition.key['target']),sql.Identifier(definition.date['target']),
                sql.Identifier(definition.table),sql.Identifier(definition.key['target']),
                sql.Identifier(definition.date['target'])),(keys,run['cutoff'])).fetchall()
            target.extend((str(uid),key,wall_time(date)) for uid,key,date in rows)
    # Ordering is deliberately irrelevant: every backend receives these exact batches.
    report = dict(at=datetime.now(timezone.utc).isoformat(),run_id=run_id,cutoff=run['cutoff'],
                  source=source,target=target,remote_target_seconds=perf_counter()-started,
                  remote_read_only=True)
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(report))
    return report


def duck_insert(db, table, columns, batch, filename, ingestion):
    """Bounded bulk ingestion; include conversion/staging cost in every trial."""
    if ingestion=='arrays':
        db.execute(f'INSERT INTO {table}({",".join(columns)}) SELECT '+
                   ','.join('unnest(?::VARCHAR[])' for _ in columns), list(zip(*batch)))
    else:
        with open(filename,'w',newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
            writer.writerows(batch)
        types = ','.join("'"+name+"':'VARCHAR'" for name in columns)
        db.execute(f'INSERT INTO {table}({",".join(columns)}) SELECT * FROM read_csv(?,header=true,columns={{{types}}})',[str(filename)])


def trial(folder, source, target, cutoff, engine, algorithm, commit_rows, ingestion="csv"):
    """Same source and streamed target batches, with atomic data/checkpoint commits."""
    folder = Path(folder)
    filename = folder / ('trial.sqlite' if engine=='sqlite' else 'trial.duckdb')
    db = sqlite3.connect(filename,isolation_level=None) if engine=='sqlite' else duckdb.connect(
        ':memory:' if engine=='ram' else str(filename),config={'threads':2,'memory_limit':'512MiB'})
    if engine=='sqlite':
        db.execute('PRAGMA cache_size=-524288')  # Same 512 MiB cache budget, not SQLite's small default.
        db.execute('PRAGMA temp_store=MEMORY')
    for statement in SCHEMA:
        db.execute(statement)
    result = dict(engine=engine,algorithm=algorithm,commit_rows=commit_rows,
                  source_rows=len(source),target_rows=len(target),batch_rows=BATCH,ingestion=ingestion if engine!='sqlite' else 'executemany')
    started = perf_counter()
    db.execute('BEGIN')
    phase = perf_counter()
    for start in range(0,len(source),BATCH):
        batch = source[start:start+BATCH]
        if engine=='sqlite':
            db.executemany('INSERT INTO source(key,date) VALUES (?,?)',batch)
        else:
            duck_insert(db,'source',['key','date'],batch,folder/'source-page.csv',ingestion)
        db.execute("INSERT OR REPLACE INTO progress VALUES ('source',?)",(batch[-1][0],))
        # RAM commits preserve complete pages in memory; they do not persist a file.
        if commit_rows and (start+len(batch))%commit_rows==0:
            db.execute('COMMIT');db.execute('BEGIN')
    result['source_seconds'] = perf_counter()-phase
    phase = perf_counter()
    last = None
    for start in range(0,len(target),BATCH):
        batch = target[start:start+BATCH]
        if algorithm=='row_loop':
            for uid,key,date in batch:
                row = db.execute('SELECT date FROM source WHERE key=?',(key,)).fetchone()
                if row:
                    db.execute('UPDATE source SET seen=1 WHERE key=?',(key,))
                if row is None:
                    db.execute("INSERT INTO differences VALUES ('remove',?,?,?)",(key,date,uid))
                elif row[0]<=cutoff and row[0]!=date:
                    kind = 'update' if row[0]>date else 'ahead'
                    db.execute('INSERT INTO differences VALUES (?,?,?,?)',(kind,key,row[0],uid))
        else:
            db.execute('DELETE FROM page')
            if engine=='sqlite':
                db.executemany('INSERT INTO page VALUES (?,?,?)',batch)
            else:
                duck_insert(db,'page',['target_id','key','date'],batch,folder/'target-page.csv',ingestion)
            db.execute(PAGE_DIFF,(cutoff,))
            db.execute('UPDATE source SET seen=1 WHERE key IN (SELECT key FROM page)')
        last = batch[-1][1]
        db.execute("INSERT OR REPLACE INTO progress VALUES ('target',?)",(last,))
        if commit_rows and (start+len(batch))%commit_rows==0:
            db.execute('COMMIT');db.execute('BEGIN')
    db.execute("INSERT INTO differences SELECT 'insert',key,date,NULL FROM source WHERE seen=0 AND date<=?",(cutoff,))
    db.execute("INSERT OR REPLACE INTO progress VALUES ('prepared',NULL)")
    result['compare_seconds'] = perf_counter()-phase
    result['file_bytes_before_final_commit'] = filename.stat().st_size if filename.exists() else 0
    wal = Path(str(filename)+'.wal')
    result['wal_bytes_before_final_commit'] = wal.stat().st_size if wal.exists() else 0
    phase = perf_counter()
    db.execute('COMMIT')
    result['final_commit_seconds'] = perf_counter()-phase
    if engine!='sqlite':
        result['engine_memory_after_compare_bytes'] = db.execute('SELECT sum(memory_usage_bytes) FROM duckdb_memory()').fetchone()[0]
    if engine=='ram':
        phase = perf_counter()
        path = str(filename).replace("'","''")
        db.execute(f"ATTACH '{path}' AS saved")
        db.execute('COPY FROM DATABASE memory TO saved')
        db.execute('CHECKPOINT saved')
        result['snapshot_seconds'] = perf_counter()-phase
    else:
        result['snapshot_seconds'] = 0
    signature = sorted(db.execute('SELECT * FROM differences ORDER BY kind,key').fetchall())
    db.close()
    result['total_seconds'] = perf_counter()-started
    result['file_bytes'] = filename.stat().st_size
    reader = sqlite3.connect(filename) if engine=='sqlite' else duckdb.connect(str(filename),read_only=True)
    persisted = reader.execute('SELECT * FROM differences ORDER BY kind,key').fetchall()
    result['reopened_source_rows'] = reader.execute('SELECT count(*) FROM source').fetchone()[0]
    result['reopened_prepared'] = reader.execute("SELECT count(*) FROM progress WHERE stage='prepared'").fetchone()[0]==1
    reader.close()
    assert signature == persisted and result['reopened_source_rows']==len(source)
    result['signature_sha256'] = hashlib.sha256(json.dumps(signature).encode()).hexdigest()
    result['diff_counts'] = {kind:sum(row[0]==kind for row in signature) for kind in ('insert','update','remove','ahead')}
    return result


def failure_trials(folder):
    """A failed page is rolled back; only earlier completed RAM pages are exported."""
    results = []
    for mode in ('file_one_transaction','ram_page_transactions','ram_one_transaction'):
        path = Path(folder)/(mode+'.duckdb')
        db = duckdb.connect(':memory:' if mode.startswith('ram') else str(path))
        db.execute('CREATE TABLE completed(key INTEGER PRIMARY KEY)')
        db.execute('BEGIN');db.execute('INSERT INTO completed VALUES (1),(2)')
        if mode=='ram_page_transactions':
            db.execute('COMMIT');db.execute('BEGIN')
        try:
            db.execute('INSERT INTO completed VALUES (3)')
            db.execute('INSERT INTO completed VALUES (2)')  # Deliberate current-page SQL failure.
        except duckdb.ConstraintException:
            db.execute('ROLLBACK')
        # This commit cannot restore rows discarded by the rollback.
        if mode.startswith('ram'):
            db.execute(f"ATTACH '{str(path).replace(chr(39),chr(39)*2)}' AS saved")
            db.execute('COPY FROM DATABASE memory TO saved');db.execute('CHECKPOINT saved')
        db.close()
        with duckdb.connect(str(path),read_only=True) as reader:
            persisted = reader.execute('SELECT * FROM completed ORDER BY key').fetchall()
        results.append(dict(mode=mode,persisted_keys=[row[0] for row in persisted]))
    assert results[0]['persisted_keys']==[] and results[1]['persisted_keys']==[1,2]
    # Reload the saved complete RAM pages and continue in a fresh in-memory DB.
    resumed = Path(folder)/'resumed.duckdb'
    with duckdb.connect() as db:
        seed = str(Path(folder)/'ram_page_transactions.duckdb').replace("'","''")
        db.execute(f"ATTACH '{seed}' AS seed (READ_ONLY)")
        db.execute('COPY FROM DATABASE seed TO memory')
        db.execute('INSERT INTO completed VALUES (3)')
        db.execute(f"ATTACH '{str(resumed).replace(chr(39),chr(39)*2)}' AS saved")
        db.execute('COPY FROM DATABASE memory TO saved');db.execute('CHECKPOINT saved')
    with duckdb.connect(str(resumed),read_only=True) as reader:
        keys = [row[0] for row in reader.execute('SELECT * FROM completed ORDER BY key').fetchall()]
    assert keys==[1,2,3]
    results.append(dict(mode='reload_ram_snapshot_and_continue',persisted_keys=keys))
    # A failed remote fetch at a page boundary does not abort a healthy DB transaction.
    controlled = Path(folder)/'fetch-failed.duckdb'
    with duckdb.connect(str(controlled)) as db:
        db.execute('CREATE TABLE completed(key INTEGER PRIMARY KEY)')
        db.execute('BEGIN');db.execute('INSERT INTO completed VALUES (1),(2)')
        try:
            raise ConnectionError('Remote fetch stopped before the next page')
        except ConnectionError:
            db.execute('COMMIT')
    with duckdb.connect(str(controlled),read_only=True) as db:
        keys = [r[0] for r in db.execute('SELECT * FROM completed ORDER BY key').fetchall()]
    assert keys==[1,2]
    results.append(dict(mode='controlled_fetch_failure_commit_healthy_transaction',persisted_keys=keys))
    crash_file = Path(folder)/'never_saved.duckdb'
    child = subprocess.run([sys.executable,'-c',
        "import duckdb,os; db=duckdb.connect(); db.execute('CREATE TABLE data AS SELECT 1 AS id'); os._exit(23)"],
        capture_output=True)
    assert child.returncode==23 and not crash_file.exists()
    results.append(dict(mode='abrupt_process_exit',exit_code=child.returncode,snapshot_created=False))
    durable = Path(folder)/'crash-durable.duckdb'
    child = subprocess.run([sys.executable,'-c',
        "import duckdb,os,sys; db=duckdb.connect(sys.argv[1]); db.execute('CREATE TABLE completed(key INTEGER)'); db.execute('INSERT INTO completed VALUES (1),(2)'); db.execute('BEGIN'); db.execute('INSERT INTO completed VALUES (3)'); os._exit(23)", str(durable)],capture_output=True)
    with duckdb.connect(str(durable),read_only=True) as db:
        keys = [r[0] for r in db.execute('SELECT * FROM completed ORDER BY key').fetchall()]
    assert child.returncode==23 and keys==[1,2]
    results.append(dict(mode='abrupt_exit_with_previous_file_commit',persisted_keys=keys))
    return results


def main():
    global BATCH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',default='benchmarks/fixtures/storage-sample.json')
    parser.add_argument('--capture',action='store_true',help='capture one bounded read-only sample first')
    parser.add_argument('--store',default='full-ev-parcela.sqlite')
    parser.add_argument('--run',default='8190f417-bbd3-41f3-b727-b00b4d3065e4')
    parser.add_argument('--sizes',type=int,nargs='+',default=[10000,100000])
    parser.add_argument('--batch-size',type=int,default=10000)
    parser.add_argument('--ingestion',choices=('arrays','csv'),default='csv')
    parser.add_argument('--repeats',type=int,default=3)
    args = parser.parse_args()
    BATCH = args.batch_size
    if BATCH<1 or min(args.sizes)<1 or args.repeats<1:parser.error('sizes and repeats must be positive')
    data = sample(args.store,args.run,max(args.sizes),args.fixture) if args.capture else json.loads(Path(args.fixture).read_text())
    if max(args.sizes)>len(data['source']):parser.error('fixture is too small; capture a larger bounded sample')
    report = dict(at=datetime.now(timezone.utc).isoformat(),batch_rows=BATCH,memory_budget_mib=512,
                  fixture_sha256=hashlib.sha256(Path(args.fixture).read_bytes()).hexdigest(),
                  fixture_source_rows=len(data['source']),fixture_target_rows=len(data['target']),
                  implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  note='Same native-key Python batches; source load and streamed target staging included; no persisted full LIFT table; prepared-key sampling misses actual target-only keys, covered by unit fixtures.',trials=[])
    variants = [('sqlite','row_loop',BATCH),('sqlite','row_loop',0),
                ('sqlite','bulk',BATCH),('sqlite','bulk',0),
                ('duckdb','bulk',BATCH),('duckdb','bulk',0),('ram','bulk',BATCH),('ram','bulk',0)]
    with TemporaryDirectory(prefix='repair-storage-') as root:
        report['failure_tests'] = failure_trials(root)
        for size in args.sizes:
            source = data['source'][:size]
            target = [row for row in data['target'] if source[0][0]<=row[1]<=source[-1][0]]
            expected = None
            for repeat in range(args.repeats):
                # Rotate order so each backend does not always get the same warm-up position.
                rotated = variants[repeat:]+variants[:repeat]
                for engine,algorithm,commit_rows in rotated:
                    with TemporaryDirectory(dir=root) as folder:
                        result = trial(folder,source,target,data['cutoff'],engine,algorithm,commit_rows,args.ingestion)
                    if expected is None:expected=result['signature_sha256']
                    assert result['signature_sha256']==expected
                    result.update(repeat=repeat+1,results_equal=True)
                    report['trials'].append(result)
                    print(f"{size:,} {engine}/{algorithm} commit={commit_rows or 'end'}: {result['total_seconds']:.3f}s",flush=True)
    output = Path('benchmarks')/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'-storage.json')
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved {output}')


if __name__=='__main__':main()
