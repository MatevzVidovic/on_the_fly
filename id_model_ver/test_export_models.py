"""Local-only examples for completed and interrupted source exports."""
import sqlite3
from unittest.mock import MagicMock
import pytest
from export_models import export_models


def test_export_models_writes_exact_values_and_completion_metadata(tmp_path):
    oracle=MagicMock()
    cur=oracle.cursor.return_value.__enter__.return_value
    cur.fetchmany.side_effect=[[('123','10','1148'),('456','20',None)],[]]
    path=tmp_path/'models.sqlite'
    export_models(oracle,path,'ev_del_stavbe_enota_h_2020_2024','source')
    with sqlite3.connect(path) as cache:
        assert cache.execute('SELECT * FROM models ORDER BY sid').fetchall()==[(123,10,1148),(456,20,None)]
        info=cache.execute('SELECT target_table,source_id,row_count FROM export_info').fetchone()
        assert info==('ev_del_stavbe_enota_h_2020_2024','source',2)
    query=cur.execute.call_args.args[0]
    assert "2020-01-01" in query and "2025-01-01" in query
    assert 'JN_STATUS' not in query
    assert cur.execute.call_count==1
    assert not path.with_suffix('.partial').exists()


def test_failed_export_keeps_previous_completed_file(tmp_path):
    path=tmp_path/'models.sqlite'
    path.write_bytes(b'previous completed cache')
    oracle=MagicMock()
    oracle.cursor.return_value.__enter__.return_value.fetchmany.side_effect=RuntimeError('interrupted')
    with pytest.raises(RuntimeError,match='interrupted'):
        export_models(oracle,path,'ev_del_stavbe_enota_h_2025_danes','source')
    assert path.read_bytes()==b'previous completed cache'
    assert path.with_suffix('.partial').exists()
