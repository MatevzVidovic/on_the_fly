from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "SRC"))
from ev_backfill.core import TableSpec, atomic_json_write, canonical_query, keyset_predicate, parse_relation, read_checkpoint


SPEC = TableSpec("jn_pe_dst", "JN_PE_DST", "ID_PE_DST", (
    "ID_PE_DST", "ID_PE", "DST_SID", "JN_REV_NUM", "JN_REV_NUM_TO", "JN_REV_NUM_PREV",
    "JN_STATUS", "VREDNOST_DODATEK", "PODATKI", "DELITEV_MSG",
))


def test_keyset_predicate_uses_the_full_native_primary_key() -> None:
    predicate = keyset_predicate("ID_PE_DST", True)
    assert 'j."ID_PE_DST" > :last_key' in predicate
    assert 'j."JN_REV_NUM" > :last_rev' in predicate
    assert keyset_predicate("ID_PE_DST", False) == ""


def test_canonical_query_keeps_history_contract_and_podatki() -> None:
    query = canonical_query(SPEC, True)
    assert "j.\"PODATKI\" AS podatki" in query
    assert "JOIN EV.REVISION rf" in query
    assert "LEFT JOIN EV.REVISION rt" in query
    assert "WHERE j.\"JN_STATUS\" <> 'X'" in query
    assert "rf.CREATED < :fence" in query
    assert "ORDER BY j.\"ID_PE_DST\", j.\"JN_REV_NUM\"" in query


def test_checkpoint_is_replaced_atomically_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / ".state" / "checkpoint.json"
    atomic_json_write(path, {"pages": 1, "last_key": "a"})
    atomic_json_write(path, {"pages": 2, "last_key": "b"})
    assert read_checkpoint(path) == {"pages": 2, "last_key": "b"}
    assert not list(path.parent.glob(".checkpoint.json.*"))


@pytest.mark.parametrize("relation", ["table", "a.b.c", "a.bad-name", "a.;drop"])
def test_target_relation_must_be_safe_and_schema_qualified(relation: str) -> None:
    with pytest.raises(ValueError):
        parse_relation(relation)
