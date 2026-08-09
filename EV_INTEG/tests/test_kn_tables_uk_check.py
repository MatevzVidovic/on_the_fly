"""Compatibility coverage for the retired dynamic unique-key report."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "kn_tables_uk_check" / "report.py"
SPEC = importlib.util.spec_from_file_location("kn_tables_uk_check", MODULE_PATH)
assert SPEC and SPEC.loader
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def test_retired_unique_key_report_fails_explicitly(capsys) -> None:
    assert report.main([]) == 2
    assert "unique_constraint_sql/generate.py" in capsys.readouterr().err
