from __future__ import annotations

import logging
import time
from pathlib import Path

from .model import LAYERS, LayerResult, LayerSpec
from .storage import GeoPackagePublisher, empty_frame, output_lock
from .wfs import WfsClient, WfsError

LOGGER = logging.getLogger(__name__)


def sync_layer(
    client: WfsClient,
    publisher: GeoPackagePublisher,
    staging: Path,
    layer: LayerSpec,
) -> tuple[int, int]:
    expected = client.feature_count(layer.type_name)
    LOGGER.info("layer=%s expected=%d", layer.output_name, expected)
    written = 0
    seen_ids: set[str] = set()
    first = True
    if expected == 0:
        publisher.write_page(
            staging,
            layer,
            empty_frame(layer, client.config.crs),
            first=True,
            crs=client.config.crs,
        )
    else:
        for page_number, frame in enumerate(
            client.iter_pages(layer, expected), start=1
        ):
            page_ids = set(frame["_wfs_id"].astype(str))
            duplicate_ids = seen_ids.intersection(page_ids)
            if duplicate_ids:
                example = min(duplicate_ids)
                raise WfsError(
                    f"{layer.type_name}: duplicate WFS ID across pages: {example}"
                )
            seen_ids.update(page_ids)
            written += publisher.write_page(
                staging,
                layer,
                frame,
                first=first,
                crs=client.config.crs,
            )
            first = False
            LOGGER.info(
                "layer=%s page=%d downloaded=%d/%d",
                layer.output_name,
                page_number,
                written,
                expected,
            )
    if written != expected:
        raise WfsError(
            f"{layer.type_name}: downloaded {written}, expected {expected}"
        )
    final_count = client.feature_count(layer.type_name)
    if final_count != expected:
        raise WfsError(
            f"{layer.type_name}: source count changed during sync "
            f"({expected} -> {final_count})"
        )
    return expected, written


def sync_all(
    client: WfsClient,
    publisher: GeoPackagePublisher,
    layers: tuple[LayerSpec, ...] = LAYERS,
) -> list[LayerResult]:
    started = time.monotonic()
    staging: Path | None = None
    with output_lock(publisher.destination):
        try:
            staging = publisher.create_staging_path()
            counts = {
                layer.output_name: sync_layer(client, publisher, staging, layer)
                for layer in layers
            }
            stored = publisher.inspect(staging, layers)
            results = []
            for layer in layers:
                expected, written = counts[layer.output_name]
                stored_count, bounds = stored[layer.output_name]
                if stored_count != written:
                    raise WfsError(
                        f"{layer.output_name}: stored {stored_count}, wrote {written}"
                    )
                results.append(
                    LayerResult(
                        type_name=layer.type_name,
                        output_name=layer.output_name,
                        expected_count=expected,
                        written_count=written,
                        bounds=bounds,
                    )
                )
            # A long parcel transfer can overlap later point-layer changes.
            # Recheck every source immediately before the atomic replacement.
            for layer in layers:
                expected = counts[layer.output_name][0]
                final_count = client.feature_count(layer.type_name)
                if final_count != expected:
                    raise WfsError(
                        f"{layer.type_name}: source count changed before publication "
                        f"({expected} -> {final_count})"
                    )
            publisher.publish(staging)
            staging = None
            LOGGER.info(
                "published=%s elapsed_seconds=%.1f",
                publisher.destination,
                time.monotonic() - started,
            )
            return results
        finally:
            if staging is not None:
                staging.unlink(missing_ok=True)
