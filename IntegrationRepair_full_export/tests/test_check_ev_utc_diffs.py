"""Inspect saved plans read-only and block batch apply while one is unfinished."""
import pytest

import check_ev_utc_diffs as report
from conftest import DATE
from store import RepairStore


@pytest.mark.parametrize('group', [[], ['--kn']])
def test_main_counts_and_requires_every_pinned_plan(tmp_path, monkeypatch, capsys, group):
    store = RepairStore(tmp_path / 'ev.sqlite')
    first = store.create_run('integration', DATE, 'first')
    store.save_source(first, [(1, DATE), (2, DATE)])
    store.compare_target_page(first, [('one', 1, '2024-01-01 00:00:00.000000'), ('extra', 3, DATE)])
    store.finish_preparation(first)
    second = store.create_run('integration', DATE, 'second')
    monkeypatch.setattr(report, 'ROOT', tmp_path)
    monkeypatch.setattr(report, 'KN_RUNS' if group else 'EV_RUNS', [('ev.sqlite', first), ('ev.sqlite', second)])
    before = list(store.db.iterdump())
    report.main(group)
    out = capsys.readouterr().out
    assert '1/2 plans prepared' in out and 'COMPARISON UNFINISHED' in out
    total = next(line for line in out.splitlines() if line.startswith('TOTAL'))
    assert total.split()[-4:] == ['1', '1', '1', '0']
    with pytest.raises(SystemExit, match='Finish run_.*_utc_compare.sh'):
        report.main(group + ['--require-prepared'])
    assert list(store.db.iterdump()) == before
    store.finish_preparation(second)
    report.main(group + ['--require-prepared'])
    assert '2/2 plans prepared' in capsys.readouterr().out
    store.db.close()
