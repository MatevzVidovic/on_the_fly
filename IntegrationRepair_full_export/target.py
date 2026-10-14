"""FMP payload mapping, then direct PostgreSQL reads/writes and completion."""
from uuid import uuid1
from psycopg import sql

from source import PAGE_SIZE, wall_time

NIL_USER = '00000000-0000-0000-0000-000000000000'


def map_row(payload, definition, max_date):
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
                value = wall_time(value)
            values.append(value)
        columns.append('geom' if field['api_location'] else field['target'])
        expressions.append(expression)
    columns.extend(('created_at', 'updated_at', 'created_by', 'updated_by'))
    expressions.extend([sql.SQL('%s')] * 4)
    values.extend((max_date, max_date, NIL_USER, NIL_USER))
    return columns, expressions, values


class LiftTarget:
    def __init__(self, db, metadata, definition):
        self.db, self.metadata, self.d = db, metadata, definition
        self.table = sql.Identifier(definition.table)
        self.key = sql.Identifier(definition.key['target'])
        self.date = sql.Identifier(definition.date['target'])

    def inventory(self, cutoff):
        with self.db.cursor(name='repair_inventory') as cur:
            cur.itersize = PAGE_SIZE
            cur.execute(sql.SQL('SELECT id, {}, {} FROM {} ORDER BY {}').format(
                self.key, self.date, self.table, self.key))
            previous = None
            while rows := cur.fetchmany(PAGE_SIZE):
                page = []
                for target_id, key, date in rows:
                    key, date = self.d.key_value(key), wall_time(date)
                    if key == previous:
                        raise ValueError(f'Duplicate LIFT key: {key}')
                    previous = key
                    if date <= cutoff:
                        page.append((str(target_id), key, date))
                yield page
        self.db.commit()

    def upsert(self, payload, max_date):
        key = self.d.key_value(payload[self.d.key['api_name']])
        source_date = wall_time(payload[self.d.date['api_name']])
        with self.db.cursor() as cur:
            cur.execute(sql.SQL('SELECT id, {} FROM {} WHERE {}=%s').format(self.date, self.table, self.key), (key,))
            existing = cur.fetchone()
            if existing and wall_time(existing[1]) > source_date:
                return 'LIFT date is newer than Oracle date'
            columns, expressions, values = map_row(payload, self.d, max_date)
            if existing:
                assignments = sql.SQL(',').join(sql.SQL('{}={}').format(sql.Identifier(c), e)
                                               for c, e in zip(columns, expressions))
                cur.execute(sql.SQL('UPDATE {} SET {} WHERE id=%s').format(self.table, assignments),
                            values + [existing[0]])
            else:
                cur.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(
                    self.table, sql.SQL(',').join(map(sql.Identifier, ['id'] + columns)),
                    sql.SQL(',').join([sql.SQL('%s')] + expressions)), [uuid1()] + values)
        return None

    def upsert_batch(self, writes, max_date):
        outcomes = []
        for key, payload in writes:
            warning = self.upsert(payload, max_date)
            if warning:
                print(f'Warning key={key}: {warning}', flush=True)
            outcomes.append((key, warning))
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
        if not self.d.table_params.get('prevent_materialized_view_refresh'):
            views = self.metadata.execute("""SELECT DISTINCT v.source_destination
                FROM attribute_table_sources r JOIN attribute_table_sources v
                  ON v.attribute_table_id=r.attribute_table_id
                WHERE r.source_type='sql_related_table' AND r.source_destination=%s
                  AND NOT r.is_archived AND v.source_type='sql_view' AND NOT v.is_archived
                  AND v.source_destination IS NOT NULL""", (self.d.table,)).fetchall()
            for (view,) in views:
                self.db.execute(sql.SQL('REFRESH MATERIALIZED VIEW CONCURRENTLY {}').format(sql.Identifier(view)))
                self.db.commit()
