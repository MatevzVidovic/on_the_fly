from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "unique_constraint_sql" / "generate.py"
SPEC = importlib.util.spec_from_file_location("unique_constraint_sql", MODULE_PATH)
assert SPEC and SPEC.loader
generate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate)


def test_render_contains_manual_preflight_and_btree_reuse_path() -> None:
    output = generate.render("ev_pe_parc_h")
    assert 'ALTER TABLE "public"."ev_pe_parc_h" ALTER COLUMN "jn_pe_parc_pk" SET NOT NULL;' in output
    assert "am.amname='btree'" in output
    assert "UNIQUE USING INDEX" in output


def test_main_writes_ignored_table_named_sql_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(generate, "OUTPUT_DIR", tmp_path)
    assert generate.main(["ev_pe_parc_h"]) == 0
    path = tmp_path / "ev_pe_parc_h.sql"
    assert path.exists()
    assert path.read_text(encoding="utf-8") == generate.render("ev_pe_parc_h")
