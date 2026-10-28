#!/usr/bin/env python3
"""Show the twelve pinned EV UTC repair plans using local SQLite only."""
import argparse
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent
EV_RUNS = [
    ('prod-utc-ev-posebna-enota.sqlite', '6743f470-af71-43d7-bb2c-f90034b77ea4'),
    ('prod-utc-ev-pe-parc.sqlite', '76137212-9e54-4c21-9de0-627c7871da3e'),
    ('prod-utc-ev-pe-dst.sqlite', '4a85c0db-a183-40e3-b848-e351c6f7bd94'),
    ('prod-utc-ev-dst-pripis.sqlite', 'c5c635c7-cdf3-491d-ae46-33da9abb4958'),
    ('prod-utc-ev-stavba.sqlite', 'd38be079-97a7-45e3-a7b1-a7b3588421b4'),
    ('prod-utc-ev-prostor.sqlite', '0da71df5-3196-4d18-9b98-b30a7e71d52e'),
    ('prod-utc-ev-del-stavbe-enota.sqlite', 'cc60543d-3112-4f21-97e1-c104930805b2'),
    ('prod-utc-ev-parc-pripis.sqlite', 'a72a58ca-2e23-468e-abad-4c302f0092f7'),
    ('prod-utc-ev-del-stavbe.sqlite', '9eacdf4a-c15f-4bef-bb63-dd7052db5607'),
    ('prod-utc-ev-parc-del.sqlite', 'f65b2517-01db-4988-b271-144228ad8072'),
    ('prod-utc-ev-parcela.sqlite', '299d81c1-0176-4b56-8619-63740513e1e3'),
    ('prod-utc-ev-parc-enota.sqlite', 'a83190e2-dece-462b-aba7-0588bee1c7ee'),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-prepared', action='store_true', help='exit with an error if any comparison is unfinished')
    args = parser.parse_args(argv)
    totals = [0, 0, 0, 0]
    unfinished = 0
    print(f"{'Table':38} {'Inserts':>9} {'Updates':>9} {'Deletes':>9} {'Warnings':>9}  Status", flush=True)
    for filename, run_id in EV_RUNS:
        with sqlite3.connect((ROOT / filename).as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN')
            run = db.execute('SELECT * FROM integration_transfer WHERE id=?', (run_id,)).fetchone()
            if not run['prepared']:
                unfinished += 1
                print(f"{run['attribute_table_name']:38} {'—':>9} {'—':>9} {'—':>9} {run['warnings']:9,}  COMPARISON UNFINISHED", flush=True)
                continue
            inserts, updates = db.execute('''SELECT coalesce(sum(s.seen=0),0),coalesce(sum(s.seen=1),0)
                FROM addition_diff d JOIN remote_ids_and_date_changed s
                ON s.run_id=d.run_id AND s.key=d.key WHERE d.run_id=?''', (run_id,)).fetchone()
            values = [inserts, updates, run['delete_count'], run['warnings']]
            totals = [a+b for a, b in zip(totals, values)]
            state = 'APPLIED' if run['applied'] else 'PREPARED'
            print(f"{run['attribute_table_name']:38} {inserts:9,} {updates:9,} {run['delete_count']:9,} {run['warnings']:9,}  {state}", flush=True)
    print(f"{'TOTAL (completed plans only)':38} {totals[0]:9,} {totals[1]:9,} {totals[2]:9,} {totals[3]:9,}", flush=True)
    print(f'{len(EV_RUNS)-unfinished}/{len(EV_RUNS)} plans prepared. Counts are saved plans, not remaining work or a fresh database comparison.', flush=True)
    if args.require_prepared and unfinished:
        raise SystemExit('Finish run_ev_utc_compare.sh before applying the batch; nothing has been applied by this script.')


if __name__ == '__main__':
    main()
