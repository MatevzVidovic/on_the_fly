"""Oracle SQL and driver values. Both reads wrap the same saved query."""
from datetime import datetime
import re
import oracledb

PAGE_SIZE = 10_000


def wall_time(value):
    """Canonical wall-clock text; timezone offsets never shift the clock."""
    if value is None:
        raise ValueError('NULL change time')
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S.%f')
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.(\d+))?(?:\s*[+-]\d{2}:\d{2})?', value)
    if not match:
        raise ValueError(f'Unexpected Oracle timestamp: {value!r}')
    # PostgreSQL timestamp stores six fractional digits. Oracle KN values use six.
    fraction = (match[3] or '').ljust(6, '0')
    if len(fraction) > 6 and fraction[6:].strip('0'):
        raise ValueError('Source timestamp exceeds PostgreSQL microsecond precision')
    return f'{match[1]} {match[2]}.{fraction[:6]}'


class OracleSource:
    def __init__(self, db, definition):
        self.db, self.d = db, definition
        self.key = '"' + definition.key['api_name'].replace('"', '""') + '"'
        self.date = '"' + definition.date['api_name'].replace('"', '""') + '"'
        # Fetch timestamps as FMP PDO text: preserve wall fields, not session timezone.
        with db.cursor() as cur:
            cur.execute("ALTER SESSION SET NLS_DATE_FORMAT='YYYY-MM-DD HH24:MI:SS'")
            cur.execute("ALTER SESSION SET NLS_TIMESTAMP_FORMAT='YYYY-MM-DD HH24:MI:SS.FF9'")
            cur.execute("ALTER SESSION SET NLS_TIMESTAMP_TZ_FORMAT='YYYY-MM-DD HH24:MI:SS.FF9 TZH:TZM'")
            cur.execute("ALTER SESSION SET NLS_NUMERIC_CHARACTERS='.,'")
        db.outputtypehandler = self.timestamp_text

    @staticmethod
    def timestamp_text(cursor, metadata):
        # Preserve Oracle NUMBER precision instead of converting decimals to float.
        if metadata.type_code == oracledb.DB_TYPE_NUMBER:
            return cursor.var(oracledb.DB_TYPE_VARCHAR, size=100, arraysize=cursor.arraysize)
        if metadata.type_code in (oracledb.DB_TYPE_DATE, oracledb.DB_TYPE_TIMESTAMP,
                                  oracledb.DB_TYPE_TIMESTAMP_TZ, oracledb.DB_TYPE_TIMESTAMP_LTZ):
            return cursor.var(oracledb.DB_TYPE_VARCHAR, size=80, arraysize=cursor.arraysize)

    def inventory(self, cutoff, after_key=None, min_date=None):
        # Keep pairs beyond the upper cutoff; optionally restrict the source date below.
        with self.db.cursor() as cur:
            cur.arraysize = PAGE_SIZE
            query = f'SELECT {self.key}, {self.date} FROM ({self.d.query})'
            predicates, binds = [], {}
            if min_date is not None:
                predicates.append(f"CAST({self.date} AS TIMESTAMP) >= TO_TIMESTAMP(:min_date, 'YYYY-MM-DD HH24:MI:SS.FF6')")
                binds['min_date'] = min_date
            if after_key is not None:
                # Include the boundary to detect duplicate keys across a restart.
                predicates.append(f'{self.key} >= :after_key')
                binds['after_key'] = after_key
            if predicates:
                query += ' WHERE ' + ' AND '.join(predicates)
            cur.execute(query + f' ORDER BY {self.key}', binds)
            previous = None
            while rows := cur.fetchmany(PAGE_SIZE):
                page = []
                for key, date in rows:
                    key, date = self.d.key_value(key), wall_time(date)
                    if key == previous:
                        raise ValueError(f'Duplicate Oracle key: {key}')
                    previous = key
                    if key == after_key:
                        continue
                    if cutoff is None or date <= cutoff:
                        page.append((key, date))
                yield page

    def fetch_payloads(self, keys, use_key_columns=True):
        payloads = {}
        # Oracle 19c limits IN to 1000 expressions.
        for start in range(0, len(keys), 1000):
            subset = keys[start:start + 1000]
            requested = set(subset)
            config = self.d.oracle_key if use_key_columns else None
            query = self.d.query
            if config:
                # Two EV queries omit the revision column; expose it for filtering only.
                if config.get('extra_select'):
                    query = re.sub(r'^SELECT\b', lambda m: m[0] + ' ' + config['extra_select'] + ',',
                                   query, count=1, flags=re.IGNORECASE)
                columns = ['"' + column.replace('"', '""') + '"' for column in config['columns']]
                predicate = '(' + ','.join(columns) + ')'
                binds, tuples = {}, []
                for i, key in enumerate(subset):
                    parts = str(key).rsplit(config['separator'], len(columns) - 1)
                    if len(parts) != len(columns):
                        raise ValueError(f'Key does not match oracle_keys.json: {key}')
                    names = [f'k{i}_{j}' for j in range(len(columns))]
                    binds.update((name, part if column in config.get('text_columns', []) else int(part))
                                 for name, part, column in zip(names, parts, config['columns']))
                    tuples.append('(' + ','.join(':' + name for name in names) + ')')
                placeholders = ','.join(tuples)
            else:
                predicate = self.key
                binds = {f'k{i}': key for i, key in enumerate(subset)}
                placeholders = ','.join(':' + name for name in binds)
            with self.db.cursor() as cur:
                cur.arraysize = len(subset)
                cur.execute(f'SELECT * FROM ({query}) WHERE {predicate} IN ({placeholders})', binds)
                names = [c[0] for c in cur.description]
                for values in cur:
                    row = dict(zip(names, (v.read() if isinstance(v, oracledb.LOB) else v for v in values)))
                    key = self.d.key_value(row[self.d.key['api_name']])
                    if key not in requested:
                        raise ValueError(f'Oracle key configuration returned an unrequested key: {key}')
                    if key in payloads:
                        raise ValueError(f'Duplicate Oracle key: {key}')
                    if row.get('__OPERATION', 'UPSERT') != 'UPSERT':
                        raise ValueError('Operation feeds are unsupported; repair requires current rows')
                    payloads[key] = row
        return payloads
