from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "SRC"))
from ev_backfill.core import TableSpec, atomic_json_write, canonical_query, keyset_predicate, parse_relation, pg_connection, read_checkpoint, source_connection


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


def test_unqualified_target_uses_public_schema() -> None:
    assert parse_relation("ev_h_pe_parc") == ("public", "ev_h_pe_parc")


@pytest.mark.parametrize("relation", ["a.b.c", "a.bad-name", "a.;drop"])
def test_target_relation_must_be_safe_and_schema_qualified(relation: str) -> None:
    with pytest.raises(ValueError):
        parse_relation(relation)


def test_component_connection_settings_are_used_without_dsns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORACLE_USER", "oracle-user")
    monkeypatch.setenv("ORACLE_PASSWORD", "oracle-password")
    monkeypatch.setenv("ORACLE_HOST", "oracle.example")
    monkeypatch.setenv("ORACLE_PORT", "1521")
    monkeypatch.setenv("ORACLE_SERVICE", "EV")
    monkeypatch.setenv("PG_USER", "pg-user")
    monkeypatch.setenv("PG_PASSWORD", "pg-password")
    monkeypatch.setenv("PG_HOST", "postgres.example")
    monkeypatch.setenv("PG_PORT", "5432")
    monkeypatch.delenv("PG_DATABASE", raising=False)

    class Oracle:
        @staticmethod
        def makedsn(host: str, port: int, service_name: str) -> tuple[str, int, str]:
            return host, port, service_name

        @staticmethod
        def connect(**kwargs: object) -> dict[str, object]:
            return kwargs

    class Postgres:
        @staticmethod
        def connect(**kwargs: object) -> dict[str, object]:
            return kwargs

    assert source_connection(Oracle())["dsn"] == ("oracle.example", 1521, "EV")
    assert pg_connection(Postgres())["dbname"] == "fmp_data_gurs"
