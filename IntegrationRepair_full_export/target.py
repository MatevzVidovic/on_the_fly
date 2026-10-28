"""FMP payload mapping, then direct PostgreSQL reads/writes and completion."""
from uuid import uuid1
from psycopg import sql

from source import PAGE_SIZE, wall_time, utc_time

from definition import REPAIR_USER_ID
from store import classify


def map_row(payload, definition, max_date, user_id=REPAIR_USER_ID):
    """Return columns, SQL value expressions and binds. NULL mappings are omitted."""
    columns, expressions, values = [], [], []
    for field in definition.fields:
        value = payload.get(field['api_name'])
        if value is None:
            continue
        expression = sql.SQL('%s')
        if field['api_location']:
            settings = field['field_params']
            expression = sql.SQL('ST_Transform(ST_GeomFromText(%s, %s), %s)')
            if 'MULTI' in settings['geometry_type']:
                expression = sql.SQL('ST_Multi({})').format(expression)
            values.extend((value, field['api_location_transformation_srid'], settings['geometry_srid']))
        else:
            if field['field_type'] in ('datetime', 'date-time'):
                value = utc_time(value) if field['api_name'] == definition.date['api_name'] else wall_time(value)
            values.append(value)
        columns.append('geom' if field['api_location'] else field['target'])
        expressions.append(expression)
    columns.extend(('created_at', 'updated_at', 'created_by', 'updated_by'))
    expressions.extend([sql.SQL('%s')] * 4)
    values.extend((max_date, max_date, user_id, user_id))
    return columns, expressions, values


class LiftTarget:
    def __init__(self, db, metadata, definition, user_id=REPAIR_USER_ID):
        self.db, self.metadata, self.d = db, metadata, definition
        self.user_id = user_id
        self.allow_one_second_ahead = False
        self.allow_one_second_behind = False
        self.table = sql.Identifier(definition.table)
        self.key = sql.Identifier(definition.key['target'])
        self.date = sql.Identifier(definition.date['target'])

    def inventory(self, cutoff, after_key=None):
        with self.db.cursor(name='repair_inventory') as cur:
            cur.itersize = PAGE_SIZE
            query = sql.SQL('SELECT id, {}, {} FROM {}').format(self.key, self.date, self.table)
            if after_key is not None:
                query += sql.SQL(' WHERE {} >= %s').format(self.key)
                cur.execute(query + sql.SQL(' ORDER BY {}').format(self.key), (after_key,))
            else:
                cur.execute(query + sql.SQL(' ORDER BY {}').format(self.key))
            previous = None
            while rows := cur.fetchmany(PAGE_SIZE):
                page = []
                for target_id, key, date in rows:
                    key, date = self.d.key_value(key), utc_time(date)
                    if key == previous:
                        raise ValueError(f'Duplicate LIFT key: {key}')
                    previous = key
                    if key == after_key:
                        continue
                    if date <= cutoff:
                        page.append((str(target_id), key, date))
                yield page
        self.db.commit()

    def lookup_rows(self, keys):
        """Read the existing UUIDs and dates in one database round trip."""
        with self.db.cursor() as cur:
            cur.execute(sql.SQL('SELECT {}, id, {} FROM {} WHERE {}=ANY(%s)').format(
                self.key, self.date, self.table, self.key), (keys,))
            return {self.d.key_value(key): (target_id, utc_time(date)) for key, target_id, date in cur}

    def upsert_batch(self, writes, max_date):
        if not writes:
            return []
        existing = self.lookup_rows([self.d.key_value(payload[self.d.key['api_name']])
                                     for _, payload in writes])
        outcomes = []
        # Pipeline sends writes without waiting for a reply after every row.
        # Exiting the pipeline checks every reply before we commit this page.
        with self.db.pipeline(), self.db.cursor() as cur:
            for encoded_key, payload in writes:
                key = self.d.key_value(payload[self.d.key['api_name']])
                row = existing.get(key)
                source_date = utc_time(payload[self.d.date['api_name']])
                decision = classify(source_date, row[1] if row else None,
                                    self.allow_one_second_ahead, self.allow_one_second_behind)
                if decision == 'ahead':
                    warning = 'LIFT date is newer than Oracle date'
                    print(f'Warning key={key}: {warning}', flush=True)
                    outcomes.append((encoded_key, warning))
                    continue
                if row and decision == 'equal' and row[1] < source_date:
                    outcomes.append((encoded_key, None))
                    continue
                columns, expressions, values = map_row(payload, self.d, max_date, self.user_id)
                if row:
                    assignments = sql.SQL(',').join(sql.SQL('{}={}').format(sql.Identifier(c), e)
                                                   for c, e in zip(columns, expressions))
                    cur.execute(sql.SQL('UPDATE {} SET {} WHERE id=%s').format(self.table, assignments),
                                values + [row[0]])
                else:
                    cur.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
                        self.table, sql.SQL(',').join(map(sql.Identifier, ['id'] + columns)),
                        sql.SQL(',').join([sql.SQL('%s')] + expressions)), [uuid1()] + values)
                outcomes.append((encoded_key, None))
        self.db.commit()
        return outcomes

    def delete_batch(self, rows):
        with self.db.cursor() as cur:
            cur.executemany(sql.SQL('DELETE FROM {} WHERE id=%s').format(self.table),
                            [(row['target_id'],) for row in rows])
        self.db.commit()

    def complete(self):
        if self.d.point_layer:
            with self.db.cursor() as cur:
                cur.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s',
                            (self.d.table,))
                columns = {row[0] for row in cur}
                for column, kind in (('gid', 'SERIAL'), ('__mod', 'INTEGER')):
                    if column not in columns:
                        cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN {} {}').format(
                            self.table, sql.Identifier(column), sql.SQL(kind)))
                        cur.execute(sql.SQL('CREATE INDEX {} ON {} ({})').format(
                            sql.Identifier(f'{self.d.table}_{column}_idx'), self.table, sql.Identifier(column)))
                cur.execute(sql.SQL('UPDATE {} SET __mod=gid % 1000 WHERE __mod IS NULL').format(self.table))
            self.db.commit()
