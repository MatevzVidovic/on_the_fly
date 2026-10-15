"""Verify counts while preserving the original prepared/applied state."""
from types import SimpleNamespace

from conftest import DATE
from verify_lift import verify


def test_verify(store, run_id, definition):
    earlier = '2025-01-01 12:00:00.000000'
    later = '2025-01-03 12:00:00.000000'
    store.save_source(run_id, [(1, DATE), (2, DATE), (3, earlier), (4, DATE), (5, later)])
    store.finish_source(run_id)
    store.finish_preparation(run_id)
    store.finish_application(run_id)
    before = list(store.db.iterdump())
    target = SimpleNamespace(d=definition, inventory=lambda cutoff: iter([
        [('a', 1, DATE), ('b', 2, earlier), ('c', 3, DATE),
         ('e', 5, DATE), ('extra', 6, DATE)]]))
    counts = verify(run_id, target, store.db)
    assert counts == dict(source_eligible=4, lift_eligible=5, equal=1, updates=1,
                          removals=1, warnings=1, inserts=1, upserts=2)
    assert list(store.db.iterdump()) == before


def test_verify_refuses_incomplete_source(store, run_id, definition):
    import pytest
    target = SimpleNamespace(d=definition)
    with pytest.raises(ValueError, match='completed Oracle export'):
        verify(run_id, target, store.db)
