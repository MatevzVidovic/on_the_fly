"""Exercise count reporting and read-only connections without remote servers."""
import json

import pytest

import check_counts
from conftest import Cursor, Database


@pytest.mark.parametrize('options,lift_count', [(['--group', 'kn'], 11), (['--include-huge'], 10)])
def test_main_reports_real_count_gaps_and_preserves_read_only(definition, tmp_path, monkeypatch, capsys, options, lift_count):
    cfg = dict(PG_HOST='example', PG_PORT='5432', PG_USER='reader', PG_PASSWORD='secret',
               PG_DATABASE_SYSTEM='metadata', PG_DATABASE_DATA='data',
               KN_ORACLE_USER='reader', KN_ORACLE_PASSWORD='secret', KN_ORACLE_DSN='example')
    monkeypatch.setattr(check_counts, 'dotenv_values', lambda path: cfg)
    monkeypatch.setattr(check_counts.IntegrationDefinition, 'load', lambda db, id: definition)
    rollbacks = []
    class Connection(Database):
        def rollback(self):
            rollbacks.append(self)
    metadata = Connection(Cursor([('integration', 'records')]))
    lift = Connection(Cursor([(lift_count, 8)]))
    oracle = Connection(Cursor([(10, 8)]))
    def connect(**settings):
        assert 'default_transaction_read_only=on' in settings['options']
        return metadata if settings['dbname'] == 'metadata' else lift
    monkeypatch.setattr(check_counts.psycopg, 'connect', connect)
    monkeypatch.setattr(check_counts.oracledb, 'connect', lambda **settings: oracle)
    path = tmp_path / 'counts.json'
    check_counts.main([*options, '--output', str(path)])
    report = json.loads(path.read_text())
    result = report['tables'][0]
    assert result['total_gap'] == 10-lift_count and result['cutoff_gap'] == 0
    assert result['counts_match'] == (lift_count == 10)
    assert report['finished_at'] and report['difference'] == 'Oracle minus LIFT'
    assert 'kn_nep_ostalo_namenske_rabe' in report['excluded_tables']
    assert (check_counts.HUGE_TABLE in report['excluded_tables']) == ('--include-huge' not in options)
    assert len(rollbacks) == 2
    assert oracle.example_cursor.calls[0][0] == 'SET TRANSACTION READ ONLY'
    assert 'REPEATABLE READ, READ ONLY' in lift.example_cursor.calls[0][0]
    assert definition.query in oracle.example_cursor.calls[1][0]
    assert ('MATCH' if lift_count == 10 else 'DIFF') in capsys.readouterr().out
