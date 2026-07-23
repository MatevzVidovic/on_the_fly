from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

from .model import LayerSpec


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
    if frame["_wfs_id"].duplicated().any():
        raise StorageError(f"{layer.output_name}: duplicate WFS feature ID in page")


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
        return self.destination.with_name(
            f".{self.destination.name}.{uuid.uuid4().hex}.tmp.gpkg"
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

    def publish(self, staging: Path) -> None:
        with sqlite3.connect(staging) as database:
            integrity = database.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise StorageError(f"staged GeoPackage integrity check failed: {integrity}")
        os.replace(staging, self.destination)


@contextmanager
def output_lock(destination: Path):
    lock_path = destination.resolve().with_suffix(destination.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise StorageError(f"another sync owns lock {lock_path}") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.close(descriptor)
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
