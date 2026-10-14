"""Timing records include failed phases without swallowing their exception."""
import json
import pytest
import timings


def test_measure(tmp_path, monkeypatch):
    values = iter([10.0, 12.5])
    monkeypatch.setattr(timings, 'perf_counter', lambda: next(values))
    with timings.measure('example', run_id='run', rows=10):
        pass
    record = json.loads(timings.LOG_PATH.read_text())
    assert record['seconds'] == 2.5 and record['status'] == 'complete'
    assert record['run_id'] == 'run' and record['rows'] == 10


def test_measure_records_failure():
    with pytest.raises(RuntimeError, match='interrupted'):
        with timings.measure('example'):
            raise RuntimeError('interrupted')
    assert json.loads(timings.LOG_PATH.read_text())['status'] == 'failed'
