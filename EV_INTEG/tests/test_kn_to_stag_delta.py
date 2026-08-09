"""Public-contract tests for the canonical KN staging CLI."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "kn_to_stag_delta_with_delete" / "sync_table.py"
SPEC = importlib.util.spec_from_file_location("kn_to_stag_sync", MODULE_PATH)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def test_canonical_entrypoint_uses_the_supported_core_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync_table.py", "ev_pe_parc_h", "--resumable", "--apply"])
    args = sync.parse_args()
    assert args.spec.target_table == "ev_pe_parc_h"
    assert args.resumable and args.apply


def test_canonical_entrypoint_rejects_formally_unsupported_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync_table.py", "not_a_catalogued_table"])
    with pytest.raises(SystemExit):
        sync.parse_args()


def test_canonical_entrypoint_owns_the_main() -> None:
    assert sync.main.__module__ == "kn_to_stag_sync"


def test_every_table_entrypoint_is_a_thin_runnable_selector() -> None:
    directory = MODULE_PATH.parent
    wrappers = sorted(path for path in directory.glob("ev_*.py"))
    assert len(wrappers) == 12
    for wrapper in wrappers:
        source = wrapper.read_text(encoding="utf-8")
        assert "from sync_table import cli" in source
        assert "SystemExit(cli(" in source
        assert len(source.splitlines()) <= 8
        completed = subprocess.run(
            [sys.executable, str(wrapper), "--help"], capture_output=True,
            text=True, check=False,
        )
        assert completed.returncode == 0, f"{wrapper.name}: {completed.stderr}"
