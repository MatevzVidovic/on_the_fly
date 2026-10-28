"""Copy restored rows into the existing _org2810 table, computing UTC on insert."""
import time
from datetime import datetime, timezone
from db import connect, sql, TABLE, DATE_COLUMN, SOURCE_DATE_COLUMN, ARGS, schema, table
from barman import wait_for_barman
from run_log import run_log


target_schema, target_name = schema, table + '_org2810'
if ARGS.copy_target:
    target_schema, target_name = (ARGS.copy_target.split('.', 1)
                                 if '.' in ARGS.copy_target else (schema, ARGS.copy_target))
TARGET = sql.Identifier(target_schema, target_name)
if TABLE.as_string() == TARGET.as_string():
    raise ValueError('Source and destination must be different tables')
if ARGS.batch_size <= 0 or ARGS.pause < 0:
    raise ValueError('Batch size must be positive and pause nonnegative')


def columns(db, relation):
    return db.execute('''
        SELECT attname, atttypid, attgenerated
        FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped
        ORDER BY attnum
    ''', (relation.as_string(),)).fetchall()


with run_log(__file__) as run:
    with connect() as db:
        run['phase'] = 'checking_copy'
        # Prevent two copies from this script writing the same destination together.
        locked = db.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0))',
                            (TARGET.as_string(),)).fetchone()[0]
        if not locked:
            raise RuntimeError('Another copy is already using this destination')
        source_columns = {name: kind for name, kind, generated in columns(db, TABLE)}
        target_columns = columns(db, TARGET)
        target_types = {name: kind for name, kind, generated in target_columns}
        if source_columns.get(ARGS.source_date_column) != 1114 or target_types.get(ARGS.date_column) != 1114:
            raise ValueError('Source date and destination UTC columns must be timestamp without time zone')
        for relation in (TABLE, TARGET):
            unique_id = db.execute('''
                SELECT EXISTS (
                    SELECT 1 FROM pg_index i JOIN pg_attribute a
                      ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0]
                    WHERE i.indrelid=%s::regclass AND a.attname='id' AND a.attnotnull
                      AND i.indisunique AND i.indisvalid AND i.indnkeyatts=1
                      AND i.indpred IS NULL AND i.indexprs IS NULL
                )
            ''', (relation.as_string(),)).fetchone()[0]
            if not unique_id:
                raise ValueError(f'{relation.as_string()} needs a unique, indexed, NOT NULL id')

        names, expressions = [], []
        for name, kind, generated in target_columns:
            if generated:
                if name == ARGS.date_column:
                    raise ValueError('Destination UTC column must be writable')
                continue  # PostgreSQL calculates generated columns.
            names.append(sql.Identifier(name))
            if name == ARGS.date_column:
                expressions.append(sql.SQL("({source_date} AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'")
                                   .format(source_date=SOURCE_DATE_COLUMN))
            else:
                if source_columns.get(name) != kind:
                    raise ValueError(f'Source is missing column {name}, or its type differs')
                expressions.append(sql.Identifier(name))
        missing = set(source_columns) - set(target_types)
        if missing:
            raise ValueError(f'Destination is missing source columns: {sorted(missing)}')

        last = db.execute(sql.SQL('SELECT id FROM {target} ORDER BY id DESC LIMIT 1')
                          .format(target=TARGET)).fetchone()
        last_id = last[0] if last else None
        print(f'Copy {TABLE.as_string()} -> {TARGET.as_string()} | resume after {last_id}', flush=True)
        run['phase'] = 'copy_backfill'
        while True:
            wait_for_barman(db)
            started = time.perf_counter()
            after = sql.SQL('') if last_id is None else sql.SQL('WHERE id > %s')
            result = db.execute(sql.SQL('''
                WITH batch AS MATERIALIZED (
                    SELECT * FROM {source} {after} ORDER BY id LIMIT {batch_size}
                ), inserted AS (
                    INSERT INTO {target} ({names}) OVERRIDING SYSTEM VALUE
                    SELECT {expressions} FROM batch ORDER BY id
                    RETURNING id
                )
                SELECT count(*), (SELECT id FROM inserted ORDER BY id DESC LIMIT 1)
                FROM inserted
            ''').format(source=TABLE, target=TARGET, after=after,
                        batch_size=sql.Literal(ARGS.batch_size),
                        names=sql.SQL(', ').join(names), expressions=sql.SQL(', ').join(expressions)),
                () if last_id is None else (last_id,)).fetchone()
            count, upper_id = result
            if count == 0:
                break
            last_id = upper_id  # The INSERT statement has committed before advancing.
            seconds = time.perf_counter() - started
            print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} | Copied {count} rows"
                  f' | copy+UTC {seconds:.2f}s | {count / seconds:.0f} rows/s | last_id {last_id}', flush=True)
            wait_for_barman(db)
            time.sleep(ARGS.pause)
    print('Copy finished. Tables have not been renamed or switched between logged/unlogged.', flush=True)
    run['phase'] = 'done'
