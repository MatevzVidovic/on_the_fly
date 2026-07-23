from __future__ import annotations

from collections.abc import Iterable, Iterator

import geopandas as gpd
import pandas as pd

from wfs_sync.model import LayerSpec, WfsConfig


def source_frame(
    layer: LayerSpec,
    feature_ids: Iterable[str],
    geometries: Iterable[object],
    *,
    nullable_values: bool = False,
) -> gpd.GeoDataFrame:
    """Return a page with the exact production attribute schema."""
    ids = list(feature_ids)
    geometry = list(geometries)
    assert len(ids) == len(geometry)
    size = len(ids)
    data: dict[str, object] = {}
    for name in layer.integer_fields:
        values = [None if nullable_values and index == size - 1 else index + 1 for index in range(size)]
        data[name] = pd.Series(values, dtype="Int64")
    for name in layer.date_fields:
        values = [
            None if nullable_values and index == size - 1 else "2024-01-02T03:04:05Z"
            for index in range(size)
        ]
        data[name] = pd.to_datetime(values, utc=True)
    for name in layer.text_fields:
        data[name] = pd.Series(
            [None if nullable_values and index == size - 1 else f"Črna {index}" for index in range(size)],
            dtype="string",
        )
    data["_wfs_id"] = pd.Series(ids, dtype="string")
    return gpd.GeoDataFrame(data, geometry=geometry, crs="EPSG:3794")


class PagedClient:
    """Offline WFS substitute that preserves page boundaries and final hit checks."""

    def __init__(
        self,
        pages: dict[str, list[gpd.GeoDataFrame]],
        *,
        final_counts: dict[str, int] | None = None,
    ) -> None:
        self.config = WfsConfig(page_size=2)
        self.pages = pages
        self.initial_counts = {
            type_name: sum(len(page) for page in layer_pages)
            for type_name, layer_pages in pages.items()
        }
        self.final_counts = final_counts or self.initial_counts
        self.count_calls: dict[str, int] = {}

    def feature_count(self, type_name: str) -> int:
        call = self.count_calls.get(type_name, 0)
        self.count_calls[type_name] = call + 1
        return (
            self.initial_counts[type_name]
            if call == 0
            else self.final_counts[type_name]
        )

    def iter_pages(
        self, layer: LayerSpec, expected_count: int
    ) -> Iterator[gpd.GeoDataFrame]:
        assert expected_count == self.initial_counts[layer.type_name]
        yield from self.pages[layer.type_name]
