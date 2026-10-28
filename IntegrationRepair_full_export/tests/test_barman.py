"""Small retained-WAL sequences; no database or real sleeping."""
from types import SimpleNamespace

import pytest

import barman

GiB = 1024**3


class Monitor:
    def __init__(self, slots):
        self.slots = iter(slots)
        self.commits = 0

    def execute(self, query):
        assert "slot_name='barman'" in query
        assert 'restart_lsn' in query
        return SimpleNamespace(fetchone=lambda: next(self.slots))

    def commit(self):
        self.commits += 1


@pytest.mark.parametrize('retained', [0, 3 * GiB, 5 * GiB])
def test_below_pause_threshold_does_not_wait(retained, monkeypatch):
    monkeypatch.setattr(barman.time, 'sleep', lambda seconds: pytest.fail('Unexpected wait'))
    db = Monitor([(True, retained)])
    barman.wait_for_barman(db)
    assert db.commits == 1


def test_pause_above_five_until_strictly_below_two(monkeypatch, capsys):
    db = Monitor([(True, 5 * GiB + 1), (True, 4 * GiB), (True, 2 * GiB), (True, 2 * GiB - 1)])
    sleeps = []
    def sleep(seconds):
        assert db.commits == len(sleeps) + 1  # No read transaction spans a wait.
        sleeps.append(seconds)
    monkeypatch.setattr(barman.time, 'sleep', sleep)
    barman.wait_for_barman(db)
    assert sleeps == [5, 5, 5] and db.commits == 4
    assert 'resuming' in capsys.readouterr().out


@pytest.mark.parametrize('slot', [None, (True, None), (False, GiB)])
def test_missing_or_inactive_slot_stops_apply(slot):
    db = Monitor([slot])
    with pytest.raises(RuntimeError, match='barman|Barman'):
        barman.wait_for_barman(db)
    assert db.commits == 1
