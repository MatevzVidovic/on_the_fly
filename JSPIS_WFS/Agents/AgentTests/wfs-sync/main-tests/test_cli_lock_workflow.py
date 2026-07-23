from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from wfs_sync.storage import StorageError, output_lock


ROOT = Path(__file__).resolve().parents[4]


def test_bad_config_has_concise_nonzero_cli_result(tmp_path: Path) -> None:
    # Stage 1: invoke the public module entry point with an invalid local setting.
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "wfs_sync",
            "--page-size",
            "0",
            "sync",
            "--output",
            str(tmp_path / "unused.gpkg"),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    # Stage 2: operators get one actionable error, not a traceback or network call.
    assert result.returncode != 0
    assert "page_size must be positive" in result.stderr
    assert "Traceback" not in result.stderr
    assert "offline" not in result.stderr.lower()


def test_lock_is_advisory_and_released_after_owner_failure(tmp_path: Path) -> None:
    # The lock does not lock the GeoPackage itself, but it rejects a cooperating
    # second sync and is always cleaned when its owner exits.
    destination = tmp_path / "acts.gpkg"
    lock_path = destination.with_suffix(".gpkg.lock")
    with pytest.raises(RuntimeError, match="owner failed"):
        with output_lock(destination):
            assert lock_path.exists()
            destination.write_bytes(b"other readers can still access this file")
            with pytest.raises(StorageError, match="another sync owns lock"):
                with output_lock(destination):
                    pass
            raise RuntimeError("owner failed")
    assert not lock_path.exists()


def test_stale_lock_is_not_silently_stolen_or_deleted(tmp_path: Path) -> None:
    # A stale-looking PID is ambiguous across hosts/containers. The safe current
    # contract is to fail and leave it for an operator to inspect and remove.
    destination = tmp_path / "acts.gpkg"
    lock_path = destination.with_suffix(".gpkg.lock")
    lock_path.write_text("pid=999999999\n", encoding="utf-8")

    with pytest.raises(StorageError, match="another sync owns lock"):
        with output_lock(destination):
            pass

    assert lock_path.read_text(encoding="utf-8") == "pid=999999999\n"


def test_workflow_checksum_creation_is_cross_platform_python() -> None:
    # Keep checksum generation usable on Linux, macOS, and an on-prem Python runner.
    workflow = (ROOT / ".github/workflows/wfs-sync.yml").read_text(encoding="utf-8")

    assert "sha256sum " not in workflow
    assert "hashlib" in workflow
    assert "upravni_akti.gpkg.sha256" in workflow
