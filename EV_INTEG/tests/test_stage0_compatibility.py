"""Offline compatibility baseline for command surfaces retained during migration."""

from __future__ import annotations

import importlib.util
import signal
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
COMPLEX_COPY = load_module("stage0_stag_to_prod_complex", "src/stag_to_prod_complex/sync_table.py")
ADAPT = load_module("stage0_adapt_last_changed", "src/adapt_last_changed_datetime/adapt.py")
CHECK = load_module("stage0_check_all", "src/check_all/check.py")


@pytest.mark.parametrize(
    ("relative_path", "required_options"),
    [
        ("src/kn_to_stag_delta_with_delete/sync_table.py", ("--integration-sql", "--id-field", "--resumable", "--only-new", "--source-page-key", "--restart")),
        ("src/stag_to_prod/sync_table.py", ("--page-key", "--page-size", "--restart", "--apply")),
        ("src/stag_to_prod_complex/sync_table.py", ("--id-field", "--change-field", "--restart", "--apply")),
        ("src/adapt_last_changed_datetime/adapt.py", ("--last-sync-start-year", "--dry-run", "--apply")),
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


def test_kn_default_dry_run_and_resumable_apply_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync", "target", "--integration-sql", "query.sql", "--id-field", "source_pk"])
    dry_run = KN.parse_args()
    assert not dry_run.apply and not dry_run.dry_run
    assert (dry_run.change_field, dry_run.preview_limit, dry_run.page_size, dry_run.page_size_cap) == ("date_change", 5, 50_000, 50_000)

    monkeypatch.setattr(sys, "argv", [
        "sync", "target", "--integration-sql", "query.sql", "--id-field", "source_pk",
        "--resumable", "--apply", "--source-page-key", "native_a,native_b",
    ])
    resumable = KN.parse_args()
    assert resumable.apply and resumable.resumable
    assert resumable.source_page_key == "native_a,native_b"


@pytest.mark.parametrize(
    "argv",
    [
        ["sync", "target", "--integration-sql", "query.sql", "--id-field", "source_pk", "--only-new", "--ignore-change-field", "--source-page-key", "native_pk"],
        ["sync", "target", "--integration-sql", "query.sql", "--id-field", "source_pk", "--restart"],
    ],
)
def test_kn_rejects_unsafe_resumable_mode_combinations(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        KN.parse_args()


def test_kn_resumable_without_apply_is_rejected_by_the_runtime_guard() -> None:
    args = SimpleNamespace(apply=False, ignore_change_field=False, ignore_not_null_constraint=False, ignore_unique_constraint=False)
    with pytest.raises(RuntimeError, match="--resumable is only available with --apply"):
        KN.run_resumable(args, "SELECT 1", "public", "target", "source_pk", "date_change", ("native_pk",), None, None)


def test_staging_to_production_copy_defaults_and_restart_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync", "target"])
    dry_run = COPY.parse_args()
    assert not dry_run.apply
    assert (dry_run.page_key, dry_run.page_size) == ("id", 50_000)

    monkeypatch.setattr(sys, "argv", ["sync", "target", "--restart"])
    with pytest.raises(SystemExit):
        COPY.parse_args()


def test_legacy_complex_copy_defaults_and_restart_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync", "target"])
    dry_run = COMPLEX_COPY.args_parse()
    assert not dry_run.apply
    assert (dry_run.id_field, dry_run.change_field, dry_run.page_size) == ("id", "date_change", 10_000)

    monkeypatch.setattr(sys, "argv", ["sync", "target", "--restart"])
    with pytest.raises(SystemExit):
        COMPLEX_COPY.args_parse()


def test_metadata_adapter_defaults_to_dry_run_and_validates_year(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["adapt", "target"])
    assert not ADAPT.parse_args().apply

    monkeypatch.setattr(sys, "argv", ["adapt", "target", "--last-sync-start-year", "0"])
    with pytest.raises(SystemExit):
        ADAPT.parse_args()


def test_checker_parser_preserves_environment_report_and_page_size_contract() -> None:
    default = CHECK.parse_args([])
    assert (default.environment, default.max_page_size, default.initial_page_size, default.constant_page_size) == ("staging", 50_000, None, None)

    parsed = CHECK.parse_args(["--environment", "prod", "--report", "out.md", "--initial-page-size", "100", "--max-page-size", "400"])
    assert (parsed.environment, parsed.report, parsed.initial_page_size, parsed.max_page_size) == ("prod", Path("out.md"), 100, 400)

    with pytest.raises(SystemExit):
        CHECK.parse_args(["--constant-page-size", "100", "--max-page-size", "400"])


def test_kn_first_and_second_sigint_preserve_the_documented_safe_stop_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    handlers: dict[int, object] = {}
    monkeypatch.setattr(KN.signal, "signal", lambda signum, handler: handlers.__setitem__(signum, handler))
    monkeypatch.setattr(KN.signal, "siginterrupt", lambda *_args: None)
    monkeypatch.setattr(KN, "_SIGINT_COUNT", 0)

    KN.install_sigint_handler()
    handler = handlers[signal.SIGINT]
    handler(signal.SIGINT, None)
    assert KN._SIGINT_COUNT == 1

    with pytest.raises(KeyboardInterrupt):
        handler(signal.SIGINT, None)
    assert KN._SIGINT_COUNT == 2
