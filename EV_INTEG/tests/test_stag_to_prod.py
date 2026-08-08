import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "stag_to_prod" / "sync_table.py"
SPEC = importlib.util.spec_from_file_location("stag_to_prod_sync", MODULE_PATH)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def test_verify_tables_accepts_identical_columns_in_different_orders(monkeypatch) -> None:
    monkeypatch.setattr(sync, "table_columns", lambda connection, *_args: (
        ["id", "source_key", "date_change"]
        if connection == "stag"
        else ["date_change", "id", "source_key"]
    ))

    assert sync.verify_tables("stag", "prod", "public", "target", "source_key", "date_change") == [
        "id", "source_key", "date_change"
    ]


def test_verify_tables_rejects_real_column_difference(monkeypatch) -> None:
    monkeypatch.setattr(sync, "table_columns", lambda connection, *_args: (
        ["id", "source_key", "date_change", "staging_only"]
        if connection == "stag"
        else ["id", "source_key", "date_change", "production_only"]
    ))

    with pytest.raises(RuntimeError, match=r"only in staging: \['staging_only'\].*only in production: \['production_only'\]"):
        sync.verify_tables("stag", "prod", "public", "target", "source_key", "date_change")
