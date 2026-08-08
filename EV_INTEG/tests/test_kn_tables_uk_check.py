import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "kn_tables_uk_check" / "report.py"
SPEC = importlib.util.spec_from_file_location("kn_tables_uk_check", MODULE_PATH)
assert SPEC and SPEC.loader
report = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = report
SPEC.loader.exec_module(report)


def unique(column: str, *, valid: bool = True, partial: bool = False) -> report.UniqueKey:
    return report.UniqueKey("example_uk", "example_uk", (column,), valid, partial)


def test_exact_valid_non_partial_single_column_index_passes() -> None:
    assert report.key_result("source_pk", [unique("source_pk")]) == (
        True, "`example_uk` (constraint `example_uk`)"
    )


def test_composite_partial_or_invalid_unique_indexes_do_not_cover_pk_field() -> None:
    keys = [
        report.UniqueKey("composite", None, ("source_pk", "revision"), True, False),
        unique("source_pk", partial=True),
        unique("source_pk", valid=False),
    ]
    assert report.key_result("source_pk", keys) == (False, "missing")


def test_report_marks_missing_pk_coverage_and_missing_table() -> None:
    integration = report.Integration("a_table", "KN ORACLE", "integration-id")
    text, failed = report.render_report("staging", [
        ("a_table", [integration], ["source_pk"], []),
        ("gone", [integration], None, []),
    ])
    assert failed
    assert "❌ `source_pk`: missing" in text
    assert "❌ table not found" in text


def test_report_treats_tables_without_pk_suffix_as_not_applicable() -> None:
    integration = report.Integration("a_table", "KN ORACLE", "integration-id")
    text, failed = report.render_report("staging", [("a_table", [integration], [], [])])
    assert not failed
    assert "not applicable" in text


def test_report_includes_coverage_summary() -> None:
    integration = report.Integration("a_table", "KN ORACLE", "integration-id")
    text, failed = report.render_report("staging", [("a_table", [integration], ["source_pk"], [unique("source_pk")])])
    assert not failed
    assert "1 `_pk` field(s) checked; 1 covered; 0 missing" in text
