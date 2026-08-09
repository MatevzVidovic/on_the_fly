"""Compatibility tests for the retired KN staging entrypoint.

The old file used to test a second, monolithic loader.  The supported behavior
now lives in ``integration_core.kn_staging`` and is covered by
``test_kn_staging_core.py``.  These tests intentionally cover only the public
forwarding contract, so the retired engine cannot return by accident.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "kn_to_stag_delta_with_delete" / "sync_table.py"
SPEC = importlib.util.spec_from_file_location("kn_to_stag_sync", MODULE_PATH)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def test_legacy_entrypoint_forwards_to_the_supported_core_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync_table.py", "ev_pe_parc_h", "--resumable", "--apply"])
    args = sync.parse_args()
    assert args.spec.target_table == "ev_pe_parc_h"
    assert args.resumable and args.apply


def test_legacy_entrypoint_rejects_formally_unsupported_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sync_table.py", "not_a_catalogued_table"])
    with pytest.raises(SystemExit):
        sync.parse_args()


def test_legacy_entrypoint_exposes_the_canonical_main() -> None:
    assert sync.main.__module__ == "ev_pe_parc"
