#!/usr/bin/env python3
"""Show pinned EV or KN UTC repair plans using local SQLite only."""
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

KN_RUNS = [
    ('prod-utc-kn-obcine.sqlite', '0dcf61cd-b73e-4c88-b342-9cf950e203d0'),
    ('prod-utc-kn-katastrske-obcine.sqlite', '57fe9933-5bdf-43df-8934-bd1a8d92a12f'),
    ('prod-utc-kn-naselja.sqlite', '46e3f071-cb5d-4e12-945c-c4753179289d'),
    ('prod-utc-kn-ulice.sqlite', '314dbfba-b333-429b-b222-2d857389fd4a'),
    ('prod-utc-kn-gozdno-gosp-obm.sqlite', '0e4cafde-a889-4fc4-aa49-4fbaf9b9bc1b'),
    ('prod-utc-kn-stanovanja.sqlite', '94d1e47f-844d-4f74-97f7-a0f26fdbb8b1'),
    ('prod-utc-kn-hisne-stevilke.sqlite', 'bd207318-217b-4306-9403-de5e7ca7f003'),
    ('prod-utc-kn-stavbe-parcele.sqlite', '4b7db52b-c534-406a-abd1-54c00499fd10'),
    ('prod-utc-kn-stavbe-zps.sqlite', '5a56bf89-7eeb-4247-8fc4-780c51cee26f'),
    ('prod-utc-kn-etaze.sqlite', '1ef39986-ed80-49d9-858b-ccaefc06d921'),
    ('prod-utc-kn-deli.sqlite', '60ffe59d-3ac0-47ff-b9df-8b0767568019'),
    ('prod-utc-kn-stavbe-centroidi.sqlite', '6a88167e-9ca7-4662-bd57-8ba62de2f359'),
    ('prod-utc-kn-stavbe-obrisi.sqlite', 'b6ce2873-827e-418d-9faf-a889de85929c'),
    ('prod-utc-kn-etaze-deli.sqlite', '0b5e6c05-263f-46bd-85ab-266e692cc70a'),
    ('prod-utc-kn-prostori.sqlite', 'f616494f-f419-4adb-9de4-4e65f18ba839'),
    ('prod-utc-kn-parcele-gozdno.sqlite', '6621799c-c6f7-4093-804b-0ee65f26b40b'),
    ('prod-utc-kn-parcele.sqlite', '27b899c3-535f-4e83-a13b-afadefde4350'),
    ('prod-utc-kn-parcele-dejanske-rabe.sqlite', '094c3784-278d-4e31-b478-ae8e0a213638'),
    ('prod-utc-kn-parcele-namenske-rabe.sqlite', '04168203-09e6-43d0-b216-4d523d43bb6b'),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-prepared', action='store_true', help='exit with an error if any comparison is unfinished')
    parser.add_argument('--kn', action='store_true', help='show the nineteen KN plans instead of EV')
    args = parser.parse_args(argv)
    runs = KN_RUNS if args.kn else EV_RUNS
    totals = [0, 0, 0, 0]
    unfinished = 0
    print(f"{'Table':38} {'Inserts':>9} {'Updates':>9} {'Deletes':>9} {'Warnings':>9}  Status", flush=True)
    for filename, run_id in runs:
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
    print(f'{len(runs)-unfinished}/{len(runs)} plans prepared. Counts are saved plans, not remaining work or a fresh database comparison.', flush=True)
    if args.require_prepared and unfinished:
        script = 'run_kn_utc_compare.sh' if args.kn else 'run_ev_utc_compare.sh'
        raise SystemExit(f'Finish {script} before applying the batch; nothing has been applied by this script.')


if __name__ == '__main__':
    main()
