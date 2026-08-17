from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("remote_research", ROOT / "src" / "remote_research" / "research.py")
assert SPEC and SPEC.loader
research = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research)

CONSTRAINT_SPEC = importlib.util.spec_from_file_location("unique_constraint_sql", ROOT / "src" / "unique_constraint_sql" / "generate.py")
assert CONSTRAINT_SPEC and CONSTRAINT_SPEC.loader
constraints = importlib.util.module_from_spec(CONSTRAINT_SPEC)
CONSTRAINT_SPEC.loader.exec_module(constraints)


def test_research_collects_and_renders_injected_oracle_evidence_for_pending_entry() -> None:
    class Lob:
        def __init__(self, value: str) -> None: self.value = value
        def read(self) -> str: return self.value

    responses = [
        [("ID", "N", "'x'")],
        [("PK_EXAMPLE", "P", "ENABLED", "ID", 1)],
        [("PK_EXAMPLE", "UNIQUE", "VALID", "VISIBLE", "NORMAL", "ID", 1)],
        [(42, 128, "2026-08-09")],
        [(8192,)],
        [(Lob("CREATE TABLE EV.JN_STAVBA (...)"),)],
    ]

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_: object): return None
        def execute(self, _sql, _binds=None): return None
        def fetchall(self): return responses.pop(0)
        def fetchone(self): return responses.pop(0)[0]

    class Connection:
        def cursor(self): return Cursor()

    class Connected:
        def __enter__(self): return Connection()
        def __exit__(self, *_: object): return None

    assert research.main(["ev_stavba_h"], connect=lambda: Connected()) == 0
    # ``ev_stavba_h`` is backlog/pending, yet research accepts it; runnable
    # commands still reject it through catalog_entry.


def test_render_shows_actual_index_and_column_evidence() -> None:
    from integrations.catalog import research_entry
    text = research.render(research_entry("ev_stavba_h"), {
        "table_stats": (1, 128, "2026-08-09"),
        "segment_bytes": 8192,
        "columns": (("ID", "N", None),),
        "constraints": (("PK", "P", "ENABLED", "ID", 1),),
        "indexes": (("PK", "UNIQUE", "VALID", "VISIBLE", "NORMAL", "ID", 1),),
        "ddl": "DDL",
    })
    assert "unique=UNIQUE" in text and "nullable=N" in text and "num_rows=1" in text and "DDL" in text


def test_constraint_sql_accepts_catalogue_entry_and_writes_btree_reuse_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(constraints, "OUTPUT_DIR", tmp_path)
    assert constraints.main(["ev_stavba_h"]) == 0
    output = (tmp_path / "ev_stavba_h.sql").read_text(encoding="utf-8")
    assert "am.amname='btree'" in output
    assert "UNIQUE USING INDEX" in output
