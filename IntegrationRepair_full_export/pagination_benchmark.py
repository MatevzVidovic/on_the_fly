"""Read-only Oracle inventory paging probes using text or original numeric keys."""
import json
import oracledb
from timings import measure
from source import OracleSource


def pagination(definition, inventory, run, cfg, page_size, timeout, mode='all'):
    if not definition.oracle_key:
        raise ValueError('Pagination comparison requires an entry in oracle_keys.json')
    config = definition.oracle_key
    columns = ['"' + name.replace('"', '""') + '"' for name in config['columns']]
    if len(columns) != 2:
        raise ValueError('This pagination benchmark compares two-column numeric keys')
    count = inventory.execute('SELECT count(*) FROM remote_ids_and_date_changed WHERE run_id=?', (run['id'],)).fetchone()[0]
    anchors = [('start', None)]
    for name, fraction in [('middle_of_text_order', .5), ('late_in_text_order', .9)]:
        row = inventory.execute('''SELECT key FROM remote_ids_and_date_changed
            WHERE run_id=? ORDER BY key LIMIT 1 OFFSET ?''', (run['id'], int(count*fraction))).fetchone()
        if row:
            anchors.append((name, json.loads(row[0])))
    modes = ('text', 'numeric_pair', 'text_keyset', 'numeric_pair_keyset')
    if mode == 'numeric-keyset':
        modes = ('numeric_pair_keyset',)
    elif mode != 'all':
        modes = tuple(name for name in modes if name.endswith('_keyset') == (mode == 'keyset'))
    results = []
    for position, anchor in anchors:
        for mode in modes:
            db = oracledb.connect(user=cfg['KN_ORACLE_USER'], password=cfg['KN_ORACLE_PASSWORD'], dsn=cfg['KN_ORACLE_DSN'])
            db.call_timeout = timeout*1000
            result = dict(position=position, anchor=anchor, order=mode, pages=[])
            timing = {}
            try:
                source = OracleSource(db, definition)
                with db.cursor() as cur:
                    cur.execute('SET TRANSACTION READ ONLY')
                numeric = mode.startswith('numeric_pair')
                keyset = mode.endswith('_keyset')
                cursor_key = anchor
                with db.cursor() as cur:
                    cur.arraysize = page_size
                    previous = (tuple(map(int, str(anchor).split(config['separator'])))
                                if numeric else anchor) if anchor is not None else None
                    for page in range(3):
                        if page == 0 or keyset:
                            query = f'SELECT {source.key}, {source.date} FROM ({definition.query})'
                            binds = {}
                            if numeric:
                                order = ','.join(columns)
                                if cursor_key is not None:
                                    mid, revision = map(int, str(cursor_key).split(config['separator']))
                                    binds = dict(mid=mid, revision=revision)
                                    query += f' WHERE {columns[0]}>=:mid AND ({columns[0]}>:mid OR {columns[1]}>:revision)'
                            else:
                                order = source.key
                                if cursor_key is not None:
                                    binds = dict(anchor=cursor_key)
                                    query += f' WHERE {source.key}>:anchor'
                            query += f' ORDER BY {order}'
                            if keyset:
                                query += f' FETCH NEXT {page_size} ROWS ONLY'
                        with measure('benchmark.pagination.' + mode, position=position, page=page+1) as timing:
                            if page == 0 or keyset:
                                cur.execute(query, binds)
                            rows = cur.fetchmany(page_size)
                        timing['rows'] = len(rows)
                        result['pages'].append(timing)
                        for key, _ in rows:
                            ordered_key = tuple(map(int, key.split(config['separator']))) if numeric else key
                            if previous is not None and ordered_key <= previous:
                                raise ValueError('Pagination result is not strictly ordered')
                            previous = ordered_key
                        if not rows:
                            break
                        cursor_key = rows[-1][0]
                result['ordered'] = True
            except (oracledb.DatabaseError, oracledb.InterfaceError) as error:
                result['error'] = str(error).splitlines()[0]
                result['failed_phase'] = timing
            finally:
                if db.is_healthy():
                    db.close()
            results.append(result)
    return dict(results=results, note='Orders differ: anchors are chosen in text order; returned pages are not identical row sets. Stream mode reuses one cursor. Keyset mode runs a row-limited query per page. First page includes execute/sort.')
