"""Step into Oracle reads with one supplied row and no Oracle server."""
from types import SimpleNamespace

import oracledb

from source import OracleSource, wall_time
from conftest import Cursor, Database, DATE


def test_wall_time():
    result = wall_time('2025-01-02 12:00:00 +02:00')

    assert result == DATE


def test_init(definition):
    cursor = Cursor()
    db = Database(cursor)

    source = OracleSource(db, definition)

    assert source.key == '"KEY"'
    assert len(cursor.calls) == 4
    assert db.outputtypehandler == source.timestamp_text


def test_timestamp_text():
    cursor = Cursor()
    metadata = SimpleNamespace(type_code=oracledb.DB_TYPE_TIMESTAMP)

    result = OracleSource.timestamp_text(cursor, metadata)

    assert result == (oracledb.DB_TYPE_VARCHAR, dict(size=80, arraysize=1))


def test_inventory(definition):
    source = OracleSource(Database(Cursor([(1, DATE)])), definition)

    pages = list(source.inventory(DATE))

    assert pages == [[(1, DATE)]]


def test_fetch_payloads(definition):
    source = OracleSource(Database(Cursor([(1, DATE)])), definition)

    payloads = source.fetch_payloads([1])

    assert payloads == {1: dict(KEY=1, CHANGED=DATE)}


def test_number_is_fetched_as_exact_text():
    result = OracleSource.timestamp_text(Cursor(), SimpleNamespace(type_code=oracledb.DB_TYPE_NUMBER))
    assert result == (oracledb.DB_TYPE_VARCHAR, dict(size=100, arraysize=1))


def test_unbounded_inventory_keeps_keys_past_cutoff(definition):
    future = '2099-01-01 00:00:00.000000'
    source = OracleSource(Database(Cursor([(1, future)])), definition)
    assert list(source.inventory(None)) == [[(1, future)]]


def test_configured_payload_lookup_uses_integer_components(definition):
    definition.key['field_type'] = 'plain-text-single-row'
    definition.oracle_key = dict(columns=['PC_MID', 'JN_REV_NUM'], separator='-')
    cursor = Cursor([('123-45', DATE)])
    source = OracleSource(Database(cursor), definition)
    assert source.fetch_payloads(['123-45'])['123-45']['KEY'] == '123-45'
    query, binds = cursor.calls[-1]
    assert '("PC_MID","JN_REV_NUM") IN ((:k0_0,:k0_1))' in query
    assert binds == {'k0_0': 123, 'k0_1': 45}
    source.fetch_payloads(['123-45'], use_key_columns=False)
    query, binds = cursor.calls[-1]
    assert '"KEY" IN (:k0)' in query
    assert binds == {'k0': '123-45'}


def test_configured_payload_lookup_rejects_wrong_key_shape(definition):
    import pytest
    definition.oracle_key = dict(columns=['PC_MID', 'JN_REV_NUM'], separator='-')
    source = OracleSource(Database(Cursor()), definition)
    with pytest.raises(ValueError, match='oracle_keys.json'):
        source.fetch_payloads(['123'])


def test_payload_lookup_rejects_unrequested_rows(definition):
    import pytest
    source = OracleSource(Database(Cursor([(2, DATE)])), definition)
    with pytest.raises(ValueError, match='unrequested key'):
        source.fetch_payloads([1])


def test_payload_extra_projection_keeps_saved_query_and_inventory_unchanged(definition):
    definition.key['field_type'] = 'plain-text-single-row'
    definition.query = 'SELECT KEY, CHANGED FROM EV.JN_PARC_ENOTA j'
    definition.oracle_key = dict(columns=['ID_PARC_ENOTA', '__REPAIR_REV'], separator='-',
                                 extra_select='j."JN_REV_NUM" AS "__REPAIR_REV"')
    cursor = Cursor([('123-45', DATE)])
    source = OracleSource(Database(cursor), definition)
    assert source.fetch_payloads(['123-45'])['123-45']['KEY'] == '123-45'
    query, binds = cursor.calls[-1]
    assert 'SELECT j."JN_REV_NUM" AS "__REPAIR_REV", KEY, CHANGED' in query
    assert '("ID_PARC_ENOTA","__REPAIR_REV") IN ((:k0_0,:k0_1))' in query
    assert binds == {'k0_0': 123, 'k0_1': 45}
    assert definition.query == 'SELECT KEY, CHANGED FROM EV.JN_PARC_ENOTA j'
    list(source.inventory(None))
    assert '__REPAIR_REV' not in cursor.calls[-1][0]


def test_text_component_preserves_letters_zeroes_and_separator(definition):
    definition.key['field_type'] = 'plain-text-single-row'
    definition.oracle_key = dict(columns=['ID_PARC_DEL', 'JN_REV_NUM'], separator='-',
                                 text_columns=['ID_PARC_DEL'])
    cursor = Cursor([('001-ABC-45', DATE)])
    source = OracleSource(Database(cursor), definition)
    assert source.fetch_payloads(['001-ABC-45'])['001-ABC-45']['KEY'] == '001-ABC-45'
    assert cursor.calls[-1][1] == {'k0_0': '001-ABC', 'k0_1': 45}


def test_min_date_inventory_binds_wall_time_and_resume_key(definition):
    cursor = Cursor([(2, DATE), (3, DATE)])
    source = OracleSource(Database(cursor), definition)
    assert list(source.inventory(None, after_key=2, min_date=DATE)) == [[(3, DATE)]]
    query, binds = cursor.calls[-1]
    assert 'CAST("CHANGED" AS TIMESTAMP) >= TO_TIMESTAMP(:min_date' in query
    assert 'AND "KEY" >= :after_key ORDER BY "KEY"' in query
    assert binds == {'min_date': DATE, 'after_key': 2}
