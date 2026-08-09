"""Offline compatibility baseline for command surfaces retained during migration."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KN = load_module("stage0_kn_to_stag", "src/kn_to_stag_delta_with_delete/sync_table.py")
COPY = load_module("stage0_stag_to_prod", "src/stag_to_prod/sync_table.py")
LIFT_INIT = load_module("stage5_lift_integ_init", "src/lift_integ_init/init.py")
CHECK = load_module("stage0_check_all", "src/check_all/check.py")


@pytest.mark.parametrize(
    ("relative_path", "required_options"),
    [
        ("src/kn_to_stag_delta_with_delete/sync_table.py", ("--resumable", "--only-new", "--fresh", "--auto-page-size")),
        ("src/stag_to_prod/sync_table.py", ("--page-key", "--page-size", "--truncate", "--apply", "--auto-page-size")),
        ("src/lift_integ_init/init.py", ("--last-sync-start-year", "--dry-run", "--apply")),
        ("src/check_all/check.py", ("--environment", "--max-page-size", "--constant-page-size", "--report")),
    ],
)
def test_active_cli_help_is_available_without_database_configuration(relative_path: str, required_options: tuple[str, ...]) -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / relative_path), "--help"],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )

    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout.lower()
    for option in required_options:
        assert option in completed.stdout


def test_kn_forwarder_uses_catalogued_core_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync", "ev_pe_parc_h", "--resumable", "--apply"])
    resumable = KN.parse_args()
    assert resumable.apply and resumable.resumable
    assert resumable.spec.source_page_keys == ("id_pe_parc", "jn_rev_num")


@pytest.mark.parametrize(
    "argv",
    [
        ["sync", "ev_pe_parc_h", "--only-new"],
        ["sync", "not_a_catalogued_table", "--resumable", "--apply"],
    ],
)
def test_kn_rejects_unsafe_resumable_mode_combinations(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        KN.parse_args()


def test_staging_to_production_copy_defaults_and_truncate_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync", "target"])
    dry_run = COPY.parse_args()
    assert not dry_run.apply
    assert (dry_run.page_key, dry_run.page_size) == ("id", 50_000)

    monkeypatch.setattr(sys, "argv", ["sync", "target", "--truncate"])
    with pytest.raises(SystemExit):
        COPY.parse_args()


def test_transfer_cli_adaptive_page_options_are_explicit_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync", "ev_pe_parc_h", "--resumable", "--apply", "--auto-page-size", "--initial-page-size", "100", "--max-page-size", "400"])
    kn = KN.parse_args()
    assert (kn.auto_page_size, kn.initial_page_size, kn.max_page_size) == (True, 100, 400)
    monkeypatch.setattr(sys, "argv", ["sync", "target", "--auto-page-size", "--max-page-size", "400"])
    copy = COPY.parse_args()
    assert copy.auto_page_size and copy.max_page_size == 400
    monkeypatch.setattr(sys, "argv", ["sync", "target", "--constant-page-size", "100", "--auto-page-size"])
    with pytest.raises(SystemExit):
        COPY.parse_args()


def test_metadata_adapter_defaults_to_dry_run_and_validates_year(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["init", "target"])
    assert not LIFT_INIT.parse_args().apply

    monkeypatch.setattr(sys, "argv", ["init", "target", "--last-sync-start-year", "0"])
    with pytest.raises(SystemExit):
        LIFT_INIT.parse_args()


def test_metadata_adapter_resolves_its_date_field_from_the_shared_catalog() -> None:
    spec = LIFT_INIT.resolve_table_spec("ev_dst_pripis_podatki_h")
    assert spec.target_table == "ev_dst_pripis_podatki_h"
    assert spec.date_change == "date_change"


def test_lift_init_apply_uses_the_preview_values_as_optimistic_guards() -> None:
    class Cursor:
        rowcount = 1
        statement = ""
        values = None
        def execute(self, statement, values): self.statement, self.values = statement, values
    cursor = Cursor()
    previous = object()
    previous_start = object()
    LIFT_INIT.apply_metadata_update(cursor, "integration", "maximum", previous, None, previous_start)
    assert "last_changed_datetime IS NOT DISTINCT FROM %s" in cursor.statement
    assert cursor.values == ["maximum", "integration", previous]

    cursor = Cursor()
    LIFT_INIT.apply_metadata_update(cursor, "integration", "maximum", previous, __import__("datetime").datetime(2025, 1, 1), previous_start)
    assert "last_sync_start IS NOT DISTINCT FROM %s" in cursor.statement
    assert cursor.values[-1] is previous_start


def test_lift_init_apply_refuses_concurrent_metadata_drift() -> None:
    class Cursor:
        rowcount = 0
        def execute(self, *_args): return None
    with pytest.raises(RuntimeError, match="changed after the dry-run preview"):
        LIFT_INIT.apply_metadata_update(Cursor(), "integration", "maximum", "before", None, None)


def test_lift_init_loads_only_its_canonical_env(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setitem(sys.modules, "dotenv", SimpleNamespace(load_dotenv=lambda path, override=False: calls.append((Path(path), override))))
    LIFT_INIT.load_environment()
    assert calls[0] == (LIFT_INIT.HERE / ".env", False)
    assert len(calls) == 1


def test_checker_parser_preserves_environment_report_and_page_size_contract() -> None:
    default = CHECK.parse_args([])
    assert (default.environment, default.max_page_size, default.initial_page_size, default.constant_page_size) == ("staging", 50_000, None, None)

    parsed = CHECK.parse_args(["--environment", "prod", "--report", "out.md", "--initial-page-size", "100", "--max-page-size", "400"])
    assert (parsed.environment, parsed.report, parsed.initial_page_size, parsed.max_page_size) == ("prod", Path("out.md"), 100, 400)

    with pytest.raises(SystemExit):
        CHECK.parse_args(["--constant-page-size", "100", "--max-page-size", "400"])


def test_core_first_and_second_sigint_preserve_the_safe_stop_contract() -> None:
    from integration_core import InterruptController
    controller = InterruptController()
    controller.handle()
    assert controller.stop_requested
    with pytest.raises(KeyboardInterrupt):
        controller.handle()
