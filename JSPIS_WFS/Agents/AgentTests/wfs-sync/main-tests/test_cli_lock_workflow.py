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
    # second sync. Closing the descriptor releases it after owner failure.
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
    assert lock_path.exists()
    with output_lock(destination):
        assert f"pid={os.getpid()}" in lock_path.read_text(encoding="utf-8")


def test_stale_unlocked_lock_file_is_reused(tmp_path: Path) -> None:
    # File contents are informational only; ownership is the kernel flock held
    # by an open descriptor, so hard-killed processes cannot block later runs.
    destination = tmp_path / "acts.gpkg"
    lock_path = destination.with_suffix(".gpkg.lock")
    lock_path.write_text("pid=999999999\n", encoding="utf-8")

    with output_lock(destination):
        assert f"pid={os.getpid()}" in lock_path.read_text(encoding="utf-8")

    assert lock_path.exists()


def test_inactive_github_workflow_is_not_shipped() -> None:
    # Production scheduling belongs to persistent on-prem cron, not an unpushed
    # GitHub-hosted workflow whose partial disk cannot survive between runs.
    assert not (ROOT / ".github/workflows/wfs-sync.yml").exists()
