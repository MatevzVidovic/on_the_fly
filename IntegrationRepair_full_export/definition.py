"""Read the existing LIFT integration; no repair state lives here."""
from dataclasses import dataclass
from psycopg.rows import dict_row

REPAIR_USER_ID = '955ee6d4-d98e-11f0-bd04-de28270b37c5'


@dataclass
class IntegrationDefinition:
    id: str
    table: str
    query: str
    cutoff: object
    fields: list
    key: dict
    date: dict
    geometry: dict | None
    table_params: dict
    point_layer: bool

    @classmethod
    def load(cls, db, integration_id):
        with db.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT i.*, t.name AS table_name, t.type_params AS table_params,
                        c.name AS connection_name,
                        EXISTS (SELECT 1 FROM layers l WHERE l.attribute_table_id=t.id
                                AND l.geometry_type IN ('POINT', 'MULTIPOINT')) AS point_layer
                        FROM attribute_table_integrations i
                        JOIN attribute_tables t ON t.id=i.attribute_table_id
                        JOIN attribute_table_sql_connections c ON c.id=i.attribute_table_sql_connection_id
                        WHERE i.id=%s""", (integration_id,))
            row = cur.fetchone()
            if row is None:
                raise ValueError('Integration not found')
            if row['is_full_sync'] or row['integration_type'] != 'sql' or row['connection_name'] != 'KN ORACLE':
                raise ValueError('Only KN Oracle SQL delta integrations are supported')
            if row['last_changed_datetime'] is None:
                raise ValueError('Integration has no change-time watermark')
            cur.execute("""SELECT m.*, f.name AS target, f.type AS field_type,
                        f.type_params AS field_params FROM attribute_field_integrations m
                        JOIN attribute_fields f ON f.id=m.attribute_field_id
                        WHERE m.attribute_table_integration_id=%s AND NOT m.api_block_sync""", (integration_id,))
            fields = cur.fetchall()
        keys = [f for f in fields if f['api_id']]
        dates = [f for f in fields if f['api_last_sync_field']]
        if len(keys) != 1 or len(dates) != 1:
            raise ValueError('Require exactly one enabled key and change-time mapping')
        if keys[0]['field_type'] not in ('bigint', 'integer', 'plain-text-single-row'):
            raise ValueError(f"Unsupported key field type: {keys[0]['field_type']}")
        if any(f['target'] == 'id' for f in fields):
            raise ValueError('Mapped target UUID id is outside this repair tool')
        locations = [f for f in fields if f['api_location']]
        if len(locations) > 1 or any(f['api_location_transformation'] != 'wkt' for f in locations):
            raise ValueError('Only one WKT location mapping is supported')
        params, table_params = row['params'] or {}, row['table_params'] or {}
        if params.get('after_sync_events') or table_params.get('payload_decorators'):
            raise ValueError('Custom hooks/decorators are unsupported')
        for events in table_params.get('events', {}).values():
            if any(e['event_name'] != 'gms.attribute_table.materialized_view.sync' for e in events):
                raise ValueError('Custom table hooks are unsupported')
        return cls(str(row['id']), row['table_name'], row['url'].strip().rstrip(';'),
                   row['last_changed_datetime'], fields, keys[0], dates[0],
                   locations[0] if locations else None, table_params, row['point_layer'])

    def key_value(self, value):
        if value is None:
            raise ValueError('NULL integration key')
        return int(value) if self.key['field_type'] in ('bigint', 'integer') else str(value)
