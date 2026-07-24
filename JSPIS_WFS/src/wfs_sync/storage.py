from __future__ import annotations

import hashlib
import fcntl
import json
import os
import sqlite3
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

from .model import LAYERS, CheckpointStatus, LayerSpec


class StorageError(RuntimeError):
    pass


def validate_frame(frame: gpd.GeoDataFrame, layer: LayerSpec, crs: str) -> None:
    if frame.crs is None or frame.crs.to_string().upper() != crs.upper():
        raise StorageError(
            f"{layer.output_name}: expected CRS {crs}, got {frame.crs}"
        )
    if frame.empty:
        return
    present_geometry = frame.geometry[frame.geometry.notna()]
    if present_geometry.is_empty.any():
        raise StorageError(f"{layer.output_name}: empty geometry")
    allowed = (
        {"Point"}
        if layer.geometry_family == "point"
        else {"Polygon", "MultiPolygon"}
    )
    actual = set(present_geometry.geom_type)
    if not actual <= allowed:
        raise StorageError(
            f"{layer.output_name}: geometry types {sorted(actual)} not in {sorted(allowed)}"
        )
    bounds = present_geometry.bounds.to_numpy(dtype=float)
    if bounds.size and not np.isfinite(bounds).all():
        raise StorageError(f"{layer.output_name}: non-finite geometry coordinates")
    if frame["_wfs_id"].isna().any() or (frame["_wfs_id"].astype(str) == "").any():
        raise StorageError(f"{layer.output_name}: missing WFS feature ID")
    # The live point layer contains at least one byte-for-byte identical source
    # duplicate with the same WFS ID. A GeoPackage snapshot preserves source
    # rows; the database mirror canonicalizes identical IDs separately.


def empty_frame(layer: LayerSpec, crs: str) -> gpd.GeoDataFrame:
    data: dict[str, pd.Series] = {}
    for field in layer.integer_fields:
        data[field] = pd.Series(dtype="Int64")
    for field in layer.date_fields:
        data[field] = pd.Series(dtype="datetime64[ns, UTC]")
    for field in layer.text_fields:
        data[field] = pd.Series(dtype="string")
    data["_wfs_id"] = pd.Series(dtype="string")
    return gpd.GeoDataFrame(data, geometry=gpd.GeoSeries([], crs=crs), crs=crs)


class GeoPackagePublisher:
    def __init__(self, destination: Path) -> None:
        self.destination = destination.resolve()

    def create_staging_path(self) -> Path:
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        return self.partial_path

    @property
    def partial_path(self) -> Path:
        return self.destination.with_name(
            f".{self.destination.stem}.partial{self.destination.suffix}"
        )

    @property
    def checkpoint_path(self) -> Path:
        return self.destination.with_name(f".{self.destination.name}.checkpoint.json")

    @property
    def manifest_path(self) -> Path:
        return self.destination.with_name(f"{self.destination.name}.manifest.json")

    @property
    def checksum_path(self) -> Path:
        return self.destination.with_name(f"{self.destination.name}.sha256")

    def load_checkpoint(self) -> dict[str, Any] | None:
        if not self.checkpoint_path.exists():
            return None
        try:
            value = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(
                f"cannot read checkpoint {self.checkpoint_path}: {exc}"
            ) from exc
        if not isinstance(value, dict) or value.get("version") != 1:
            raise StorageError(f"unsupported checkpoint {self.checkpoint_path}")
        return value

    def save_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        self._atomic_text(
            self.checkpoint_path,
            json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        )

    def restart(self) -> None:
        """Discard resumable state. The last complete publication is preserved."""
        self.partial_path.unlink(missing_ok=True)
        self.checkpoint_path.unlink(missing_ok=True)

    def status(
        self, layers: tuple[LayerSpec, ...] = LAYERS
    ) -> CheckpointStatus:
        checkpoint = self.load_checkpoint()
        displayed_layers = (
            deepcopy(checkpoint.get("layers", {})) if checkpoint else {}
        )
        if checkpoint and self.partial_path.exists():
            for layer in layers:
                state = displayed_layers.get(layer.output_name)
                if not isinstance(state, dict):
                    continue
                truth = self.inspect_layer_progress(self.partial_path, layer)
                state.update(truth)
                state["complete"] = (
                    int(truth["written_count"]) == int(state["expected_count"])
                )
        return CheckpointStatus(
            destination=self.destination,
            partial=self.partial_path,
            checkpoint=self.checkpoint_path,
            exists=checkpoint is not None,
            complete=bool(displayed_layers)
            and all(bool(state.get("complete")) for state in displayed_layers.values()),
            layers=displayed_layers,
        )

    def write_page(
        self,
        staging: Path,
        layer: LayerSpec,
        frame: gpd.GeoDataFrame,
        *,
        first: bool,
        crs: str,
    ) -> int:
        validate_frame(frame, layer, crs)
        pyogrio.write_dataframe(
            frame,
            staging,
            layer=layer.output_name,
            driver="GPKG",
            append=not first,
            geometry_type="Point" if layer.geometry_family == "point" else "MultiPolygon",
            promote_to_multi=layer.geometry_family == "polygon",
        )
        return len(frame)

    def inspect(
        self, staging: Path, layers: tuple[LayerSpec, ...]
    ) -> dict[str, tuple[int, tuple[float, float, float, float] | None]]:
        actual_layers = set(pyogrio.list_layers(staging)[:, 0])
        expected_layers = {layer.output_name for layer in layers}
        if actual_layers != expected_layers:
            raise StorageError(
                f"staged layers mismatch: expected={sorted(expected_layers)}, "
                f"actual={sorted(actual_layers)}"
            )
        result = {}
        for layer in layers:
            info = pyogrio.read_info(staging, layer=layer.output_name)
            count = int(info["features"])
            raw_bounds = info.get("total_bounds")
            bounds = (
                tuple(float(value) for value in raw_bounds)
                if count and raw_bounds is not None
                else None
            )
            result[layer.output_name] = (count, bounds)
        return result

    def inspect_layer_progress(self, path: Path, layer: LayerSpec) -> dict[str, Any]:
        if not path.exists():
            return {
                "written_count": 0,
                "null_complete": False,
                "last_completed_id": None,
            }
        actual_layers = set(pyogrio.list_layers(path)[:, 0])
        if layer.output_name not in actual_layers:
            return {
                "written_count": 0,
                "null_complete": False,
                "last_completed_id": None,
            }
        quoted_layer = layer.output_name.replace('"', '""')
        with sqlite3.connect(path) as database:
            count, null_count, maximum = database.execute(
                f'SELECT COUNT(*), '
                f'SUM(CASE WHEN "ID_UA" IS NULL THEN 1 ELSE 0 END), '
                f'MAX("ID_UA") FROM "{quoted_layer}"'
            ).fetchone()
        return {
            "written_count": int(count),
            # A present nullable group is written atomically. Numeric rows also
            # prove that the iterator already passed the nullable-key phase.
            "null_complete": bool(null_count or maximum is not None),
            "last_completed_id": int(maximum) if maximum is not None else None,
        }

    def publish(
        self,
        staging: Path,
        *,
        manifest: dict[str, Any] | None = None,
    ) -> None:
        with sqlite3.connect(staging) as database:
            integrity = database.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise StorageError(f"staged GeoPackage integrity check failed: {integrity}")
        os.replace(staging, self.destination)
        self.finalize_publication(manifest or {})

    def finalize_publication(self, manifest: dict[str, Any]) -> None:
        if not self.destination.exists():
            raise StorageError(f"publication is missing: {self.destination}")
        digest = hashlib.sha256()
        with self.destination.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        payload = {
            **manifest,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "sha256": digest.hexdigest(),
        }
        self._atomic_text(
            self.manifest_path, json.dumps(payload, indent=2, sort_keys=True) + "\n"
        )
        self._atomic_text(
            self.checksum_path,
            f"{digest.hexdigest()}  {self.destination.name}\n",
        )

    @staticmethod
    def _atomic_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as output:
                output.write(text)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


@contextmanager
def output_lock(destination: Path):
    lock_path = destination.resolve().with_suffix(destination.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StorageError(f"another sync owns lock {lock_path}") from exc
        os.ftruncate(descriptor, 0)
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.fsync(descriptor)
        yield
    finally:
        # Closing releases flock even after exceptions. The harmless file is
        # deliberately retained so process death cannot create a stale lock.
        os.close(descriptor)
