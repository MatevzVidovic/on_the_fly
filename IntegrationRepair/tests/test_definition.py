"""Read a small metadata definition, then convert its one integer key."""
from definition import IntegrationDefinition
from conftest import Cursor, Database, DATE


def test_load(definition):
    row = dict(id='integration', table_name='records', url=definition.query,
               last_changed_datetime=DATE, params={}, table_params={}, point_layer=False,
               connection_name='KN ORACLE', integration_type='sql', is_full_sync=False)
    cursor = Cursor([row])
    cursor.fetchall = lambda: definition.fields

    result = IntegrationDefinition.load(Database(cursor), 'integration')

    assert result.table == 'records'
    assert result.key['api_name'] == 'KEY'
    assert len(cursor.calls) == 2


def test_key_value(definition):
    result = definition.key_value('123')

    assert result == 123
