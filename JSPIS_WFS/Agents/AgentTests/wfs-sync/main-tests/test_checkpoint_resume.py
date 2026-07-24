from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import geopandas as gpd
import pyogrio
import pytest
from shapely.geometry import Point

from conftest import source_frame
from wfs_sync.model import LAYERS, LayerSpec, WfsConfig
from wfs_sync.storage import GeoPackagePublisher, StorageError, output_lock
from wfs_sync.sync import sync_all
from wfs_sync.wfs import WfsError


def _page(keys: list[int]) -> gpd.GeoDataFrame:
    layer = LAYERS[0]
    frame = source_frame(
        layer,
        [f"point.{key}" for key in keys],
        [Point(450_000 + key, 100_000) for key in keys],
    )
    frame["ID_UA"] = keys
    return frame


class ResumableClient:
    config = WfsConfig(base_url="https://offline.invalid/wfs", page_size=2)

    def __init__(self, *, fail_after_first: bool = False) -> None:
        self.pages = [_page([1, 2]), _page([3, 4])]
        self.fail_after_first = fail_after_first
        self.resume_calls: list[dict[str, object]] = []

    def feature_count(self, type_name: str) -> int:
        return 4

    def iter_pages(
        self, layer: LayerSpec, expected_count: int
    ) -> Iterator[gpd.GeoDataFrame]:
        yield self.pages[0]
        if self.fail_after_first:
            raise WfsError("simulated network interruption")
        yield self.pages[1]

    def iter_pages_from(
        self,
        layer: LayerSpec,
        expected_count: int,
        *,
        after_id_ua: int | None,
        include_null: bool,
        already_emitted: int,
    ) -> Iterator[gpd.GeoDataFrame]:
        self.resume_calls.append(
            {
                "after_id_ua": after_id_ua,
                "include_null": include_null,
                "already_emitted": already_emitted,
            }
        )
        yield from [
            page for page in self.pages if int(page["ID_UA"].max()) > after_id_ua
        ]


def test_interrupted_download_resumes_without_replacing_previous_output(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "acts.gpkg"
    destination.write_bytes(b"previous-good")
    publisher = GeoPackagePublisher(destination)

    with pytest.raises(WfsError, match="network interruption"):
        sync_all(
            ResumableClient(fail_after_first=True),
            publisher,
            (LAYERS[0],),
        )

    assert destination.read_bytes() == b"previous-good"
    assert publisher.partial_path.exists()
    status = publisher.status()
    assert status.exists
    assert status.layers[LAYERS[0].output_name]["written_count"] == 2

    client = ResumableClient()
    results = sync_all(client, publisher, (LAYERS[0],))

    assert results[0].written_count == 4
    assert client.resume_calls == [
        {"after_id_ua": 2, "include_null": False, "already_emitted": 2}
    ]
    assert not publisher.partial_path.exists()
    assert not publisher.checkpoint_path.exists()
    assert publisher.manifest_path.exists()
    assert publisher.checksum_path.read_text().endswith("  acts.gpkg\n")
    assert pyogrio.read_info(destination, layer=LAYERS[0].output_name)["features"] == 4


def test_resume_reconciles_append_that_preceded_checkpoint_write(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "acts.gpkg"
    publisher = GeoPackagePublisher(destination)
    failing = ResumableClient(fail_after_first=True)
    with pytest.raises(WfsError):
        sync_all(failing, publisher, (LAYERS[0],))

    # Model a process death after the second append committed but before its
    # atomic checkpoint JSON replacement.
    publisher.write_page(
        publisher.partial_path,
        LAYERS[0],
        _page([3, 4]),
        first=False,
        crs="EPSG:3794",
    )

    client = ResumableClient()
    sync_all(client, publisher, (LAYERS[0],))

    assert client.resume_calls == []
    assert pyogrio.read_info(destination, layer=LAYERS[0].output_name)["features"] == 4


def test_status_reports_partial_truth_without_mutating_checkpoint(
    tmp_path: Path,
) -> None:
    publisher = GeoPackagePublisher(tmp_path / "acts.gpkg")
    with pytest.raises(WfsError):
        sync_all(
            ResumableClient(fail_after_first=True),
            publisher,
            (LAYERS[0],),
        )
    publisher.write_page(
        publisher.partial_path,
        LAYERS[0],
        _page([3, 4]),
        first=False,
        crs="EPSG:3794",
    )

    status = publisher.status((LAYERS[0],))

    state = status.layers[LAYERS[0].output_name]
    assert state["written_count"] == 4
    assert state["last_completed_id"] == 4
    assert state["complete"] is True
    assert status.complete is True
    persisted = publisher.load_checkpoint()
    assert persisted is not None
    assert persisted["layers"][LAYERS[0].output_name]["written_count"] == 2


def test_restart_discards_only_partial_state(tmp_path: Path) -> None:
    destination = tmp_path / "acts.gpkg"
    destination.write_bytes(b"published")
    publisher = GeoPackagePublisher(destination)
    publisher.partial_path.write_bytes(b"partial")
    publisher.save_checkpoint({"version": 1, "layers": {}, "complete": False})

    publisher.restart()

    assert destination.read_bytes() == b"published"
    assert not publisher.partial_path.exists()
    assert not publisher.checkpoint_path.exists()


def test_restart_waits_for_lock_before_discarding_checkpoint(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "acts.gpkg"
    publisher = GeoPackagePublisher(destination)
    publisher.partial_path.write_bytes(b"partial")
    publisher.save_checkpoint({"version": 1, "layers": {}, "complete": False})

    with output_lock(destination):
        with pytest.raises(StorageError, match="another sync owns lock"):
            sync_all(
                ResumableClient(),
                publisher,
                (LAYERS[0],),
                restart=True,
            )
        assert publisher.partial_path.read_bytes() == b"partial"
        assert publisher.checkpoint_path.exists()

    sync_all(ResumableClient(), publisher, (LAYERS[0],), restart=True)
    assert destination.exists()
    assert not publisher.checkpoint_path.exists()


def test_resume_rejects_changed_live_schema_fingerprint(tmp_path: Path) -> None:
    class SchemaClient(ResumableClient):
        def __init__(self, fingerprint: str, **kwargs: object) -> None:
            super().__init__(**kwargs)
            self.fingerprint = fingerprint

        def schema_fingerprints(
            self, layers: tuple[LayerSpec, ...]
        ) -> dict[str, str]:
            return {layer.type_name: self.fingerprint for layer in layers}

    publisher = GeoPackagePublisher(tmp_path / "acts.gpkg")
    with pytest.raises(WfsError):
        sync_all(
            SchemaClient("schema-a", fail_after_first=True),
            publisher,
            (LAYERS[0],),
        )

    with pytest.raises(StorageError, match="schema contract changed"):
        sync_all(SchemaClient("schema-b"), publisher, (LAYERS[0],))

    assert publisher.partial_path.exists()
    assert publisher.checkpoint_path.exists()


def test_recovery_finishes_metadata_after_publish_before_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "acts.gpkg"
    publisher = GeoPackagePublisher(destination)
    real_unlink = Path.unlink

    def interrupted_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == publisher.checkpoint_path:
            raise OSError("simulated termination after rename")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", interrupted_unlink)
    with pytest.raises(OSError, match="after rename"):
        sync_all(ResumableClient(), publisher, (LAYERS[0],))
    monkeypatch.setattr(Path, "unlink", real_unlink)

    assert destination.exists()
    assert publisher.checkpoint_path.exists()
    assert not publisher.partial_path.exists()

    results = sync_all(ResumableClient(), publisher, (LAYERS[0],))

    assert results[0].written_count == 4
    assert not publisher.checkpoint_path.exists()
    manifest = json.loads(publisher.manifest_path.read_text())
    assert manifest["layers"][LAYERS[0].output_name]["feature_count"] == 4
