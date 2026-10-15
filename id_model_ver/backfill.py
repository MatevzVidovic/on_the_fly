"""Backfill only id_model_ver on the two staging history tables; dry-run by default."""
import argparse
import hashlib
import sqlite3
from pathlib import Path
from time import perf_counter
from uuid import UUID

from dotenv import dotenv_values
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('ev_del_stavbe_enota_h_2020_2024', 'ev_del_stavbe_enota_h_2025_danes')


def lookup_models(cache, keys):
    """Batch local lookups; missing rows stay distinct from rows with a NULL model."""
    cache.execute('CREATE TEMP TABLE IF NOT EXISTS requested (sid INTEGER, revision INTEGER)')
    cache.execute('DELETE FROM requested')
    cache.executemany('INSERT INTO requested VALUES (?,?)', keys)
    return {(sid, revision): model for sid, revision, model in cache.execute(
        'SELECT m.sid,m.revision,m.model FROM requested r JOIN models m USING(sid,revision)')}


def transfer(target, cache, table, *, after=None, page_size=10000, pages=None, apply=False):
    table = sql.Identifier('public', table)
    page = processed = total = nulls = 0
    while pages is None or page < pages:
        started = perf_counter()
        with target.transaction():
            boundary = sql.SQL('WHERE id > %s') if after else sql.SQL('')
            params = (after, page_size) if after else (page_size,)
            current_value = sql.SQL('') if apply else sql.SQL(',id_model_ver')
            rows = target.execute(sql.SQL('''SELECT id,jn_del_st_enota_pk{} FROM {}
                {} ORDER BY id LIMIT %s''').format(current_value, table, boundary), params).fetchall()
            if not rows:
                break
            keys = [tuple(map(int, row[1].rsplit('-', 1))) for row in rows]
            models = lookup_models(cache, keys)
            missing = set(keys) - models.keys()
            if missing:
                raise ValueError(f'{len(missing)} source keys missing; page not committed. Examples: {list(missing)[:5]}')
            values = [models[key] for key in keys]
            if apply:
                count = target.execute(sql.SQL('''UPDATE {} AS t SET id_model_ver=v.model
                    FROM unnest(%s::uuid[], %s::bigint[]) AS v(id,model)
                    WHERE t.id=v.id''').format(table),
                    ([row[0] for row in rows], values)).rowcount
            else:
                count = sum(row[2] != value for row, value in zip(rows, values))
        # Report the boundary only after the target page commits successfully.
        after = rows[-1][0]
        page += 1
        processed += len(rows)
        total += count
        nulls += sum(value is None for value in values)
        print(f'Page {page}: {len(rows):,} checked, {count:,} '
              f'{"updated" if apply else "would change"}; {perf_counter()-started:.2f}s; '
              f'{"committed_after" if apply else "checked_after"}={after}', flush=True)
    print(f'{"APPLY" if apply else "DRY RUN"}: checked={processed:,}, {"updated" if apply else "differences"}={total:,}, '
          f'source_nulls={nulls:,}, last_id={after}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('table', choices=TABLES)
    parser.add_argument('--apply', action='store_true', help='commit updates; otherwise compare only')
    parser.add_argument('--after', type=UUID, help='last committed UUID when resuming')
    parser.add_argument('--page-size', type=int, default=10000)
    parser.add_argument('--cache', type=Path, help='completed SQLite source export')
    parser.add_argument('--pages', type=int, help='stop after this many pages')
    args = parser.parse_args()
    if args.page_size < 1 or (args.pages is not None and args.pages < 1):
        parser.error('--page-size and --pages must be positive')
    cfg = dotenv_values(ROOT / 'IntegrationRepair/.env')
    assert cfg['PG_HOST'] == dotenv_values(ROOT / 'KN_deltas_reason/reconciliation/.env')['STAG_HOST'], 'Expected staging host'
    source = dotenv_values(ROOT / 'IntegrationRepair_full_export/.env')
    pg = dict(host=cfg['PG_HOST'], port=cfg['PG_PORT'], user=cfg['PG_USER'], password=cfg['PG_PASSWORD'],
              dbname=cfg['PG_DATABASE_DATA'], connect_timeout=10, autocommit=True,
              options='-c statement_timeout=60000' + ('' if args.apply else ' -c default_transaction_read_only=on'))
    print(f'STAGING {args.table}: {"APPLY" if args.apply else "DRY RUN"}, page_size={args.page_size}', flush=True)
    path = args.cache or ROOT / 'id_model_ver/cache' / f'{args.table}.sqlite'
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as cache:
        info = cache.execute('SELECT target_table,source_id,created_at,row_count FROM export_info').fetchone()
        if info is None or info[0] != args.table or info[1] != hashlib.sha256(source['KN_ORACLE_DSN'].encode()).hexdigest():
            parser.error('Cache does not match this table/source; create the correct export first')
        print(f'Using source export from {info[2]} ({info[3]:,} rows): {path}', flush=True)
        with psycopg.connect(**pg) as target:
            transfer(target, cache, args.table, after=args.after, page_size=args.page_size, pages=args.pages, apply=args.apply)


if __name__ == '__main__':
    main()
