"""Disposable native DuckDB file: durable page imports, diffs and progress."""
import csv
import json
from pathlib import Path

from source import PAGE_SIZE
from timings import measure


def native_file(folder, source_rows, page, cutoff):
    import duckdb
    folder = Path(folder)
    filename = folder / 'native.duckdb'
    results = {}
    with duckdb.connect(str(filename)) as db:
        db.execute('CREATE TABLE source(key VARCHAR PRIMARY KEY,date VARCHAR)')
        db.execute('CREATE TABLE lift(target_id VARCHAR PRIMARY KEY,key VARCHAR,date VARCHAR)')
        db.execute('CREATE TABLE progress(stage VARCHAR PRIMARY KEY,last_key VARCHAR)')
        for name, rows, names in (
            ('source', [(row['key'], row['date']) for row in source_rows], ['key','date']),
            ('lift', [(uid,json.dumps(key),date) for uid,key,date in page], ['target_id','key','date'])):
            with measure('benchmark.duckdb_file.' + name + '_import', rows=len(rows)) as timing:
                for start in range(0, len(rows), PAGE_SIZE):
                    batch = rows[start:start+PAGE_SIZE]
                    path = folder / (name + '-page.csv')
                    with path.open('w', newline='') as stream:
                        writer = csv.writer(stream)
                        writer.writerow(names)
                        writer.writerows(batch)
                    columns = ','.join("'"+column+"':'VARCHAR'" for column in names)
                    db.execute('BEGIN')
                    db.execute(f'INSERT INTO {name} SELECT * FROM read_csv(?,header=true,columns={{{columns}}})', [str(path)])
                    db.execute('INSERT OR REPLACE INTO progress VALUES (?,?)', [name, batch[-1][0 if name=='source' else 1]])
                    db.execute('COMMIT')
            results[name + '_import'] = timing
        with measure('benchmark.duckdb_file.compare_and_store', rows=len(page)) as timing:
            db.execute('BEGIN')
            db.execute('''CREATE TABLE additions AS SELECT s.key,s.date,0 AS processed
                FROM source s LEFT JOIN lift p USING(key)
                WHERE s.date<=? AND (p.key IS NULL OR p.date<s.date)''', [cutoff])
            db.execute('''CREATE TABLE removals AS SELECT p.key,p.target_id,p.date,0 AS processed
                FROM lift p LEFT JOIN source s USING(key) WHERE s.key IS NULL''')
            db.execute('''CREATE TABLE warnings AS SELECT p.key,p.date,s.date AS source_date
                FROM lift p JOIN source s USING(key) WHERE p.date>s.date AND s.date<=?''', [cutoff])
            db.execute("INSERT OR REPLACE INTO progress VALUES ('prepared',NULL)")
            db.execute('COMMIT')
        results['compare_and_store'] = timing
        with measure('benchmark.duckdb_file.progress_update') as timing:
            db.execute('BEGIN')
            db.execute('UPDATE additions SET processed=1')
            db.execute('UPDATE removals SET processed=1')
            db.execute("INSERT OR REPLACE INTO progress VALUES ('applied',NULL)")
            db.execute('COMMIT')
        results['progress_update'] = timing
        signature = dict(
            additions=sorted(db.execute('SELECT key,date FROM additions').fetchall()),
            removals=sorted(db.execute('SELECT key,target_id,date FROM removals').fetchall()),
            warnings=sorted((json.loads(key),f'LIFT {date} is newer than Oracle {source_date}')
                            for key,date,source_date in db.execute('SELECT * FROM warnings').fetchall()))
    # Reopening verifies that commits survived closing the file.
    with duckdb.connect(str(filename), read_only=True) as db:
        results['reopened_source_rows'] = db.execute('SELECT count(*) FROM source').fetchone()[0]
        results['reopened_progress_rows'] = db.execute('SELECT count(*) FROM progress').fetchone()[0]
    results['file_bytes'] = filename.stat().st_size
    return results, signature
