"""A disposable native DuckDB file keeps the same diff rules and durable data."""
import json
import pytest
from duckdb_benchmark import native_file
from conftest import DATE


def test_native_file(tmp_path):
    pytest.importorskip('duckdb')
    old, future = '2024-01-01 00:00:00.000000', '2099-01-01 00:00:00.000000'
    source = [dict(key=json.dumps(key), date=date) for key, date in [(1, DATE), (2, old), (3, future), (5, DATE)]]
    page = [('id-1', 1, old), ('id-2', 2, DATE), ('id-3', 3, old), ('id-4', 4, old)]
    result, signature = native_file(tmp_path, source, page, DATE)
    assert result['reopened_source_rows'] == 4 and result['reopened_progress_rows'] == 4
    assert signature['additions'] == [('1', DATE), ('5', DATE)]
    assert signature['removals'] == [('4', 'id-4', old)]
    assert signature['warnings'] == [(2, f'LIFT {DATE} is newer than Oracle {old}')]
