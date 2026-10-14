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
        source.fetch_payloads(['123-45-67'])


def test_payload_lookup_rejects_unrequested_rows(definition):
    import pytest
    source = OracleSource(Database(Cursor([(2, DATE)])), definition)
    with pytest.raises(ValueError, match='unrequested key'):
        source.fetch_payloads([1])
