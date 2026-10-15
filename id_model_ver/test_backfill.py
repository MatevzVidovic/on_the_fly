"""Small debugger-friendly examples; no database access."""
from contextlib import nullcontext
from unittest.mock import MagicMock, patch
from uuid import UUID
import pytest
from backfill import lookup_models, transfer
import sqlite3


def test_lookup_models_preserves_null_and_distinguishes_missing():
    with sqlite3.connect(':memory:') as cache:
        cache.execute('CREATE TABLE models (sid INTEGER,revision INTEGER,model INTEGER,PRIMARY KEY(sid,revision))')
        cache.executemany('INSERT INTO models VALUES (?,?,?)', [(123,10,1148),(456,20,None)])
        assert lookup_models(cache,[(123,10),(456,20),(789,30)]) == {(123,10):1148,(456,20):None}
        assert lookup_models(cache,[(456,20)]) == {(456,20):None}


def test_transfer_dry_run_does_not_update(capsys):
    target = MagicMock()
    target.transaction.side_effect = lambda: nullcontext()
    target.execute.return_value.fetchall.return_value = [(UUID(int=1), '123-10', None)]
    with patch('backfill.lookup_models', return_value={(123, 10): 1148}):
        transfer(target, object(), 'ev_del_stavbe_enota_h_2020_2024', pages=1)
    assert target.execute.call_count == 1
    assert 'would change' in capsys.readouterr().out


def test_transfer_apply_updates_by_uuid_including_source_null():
    target = MagicMock()
    target.transaction.side_effect = lambda: nullcontext()
    target.execute.return_value.fetchall.return_value = [
        (UUID(int=1), '123-10'), (UUID(int=2), '456-20')]
    target.execute.return_value.rowcount = 2
    with patch('backfill.lookup_models', return_value={(123, 10): 1165, (456, 20): None}):
        transfer(target, object(), 'ev_del_stavbe_enota_h_2025_danes', pages=1, apply=True)
    query, params = target.execute.call_args.args
    assert params == ([UUID(int=1), UUID(int=2)], [1165, None])
    assert 't.id=v.id' in query.as_string()
    assert 'IS DISTINCT FROM' not in query.as_string()
    assert 'id_model_ver' not in target.execute.call_args_list[0].args[0].as_string()


def test_transfer_missing_source_key_stops_before_update():
    target = MagicMock()
    target.transaction.side_effect = lambda: nullcontext()
    target.execute.return_value.fetchall.return_value = [(UUID(int=1), '123-10', None)]
    with patch('backfill.lookup_models', return_value={}):
        with pytest.raises(ValueError, match='source keys missing'):
            transfer(target, object(), 'ev_del_stavbe_enota_h_2020_2024', apply=True)
    assert target.execute.call_count == 1


def test_transfer_resumes_after_uuid_and_stops_on_empty_page():
    target = MagicMock()
    target.transaction.side_effect = lambda: nullcontext()
    target.execute.return_value.fetchall.return_value = []
    transfer(target, object(), 'ev_del_stavbe_enota_h_2020_2024', after=UUID(int=42))
    assert target.execute.call_args.args[1] == (UUID(int=42), 10000)
