from __future__ import annotations

import hashlib
import inspect
import json
import logging
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd

from .model import LAYERS, LayerResult, LayerSpec
from .storage import GeoPackagePublisher, StorageError, empty_frame, output_lock
from .wfs import WfsClient, WfsError

LOGGER = logging.getLogger(__name__)


def _contract(client: WfsClient, layers: tuple[LayerSpec, ...]) -> dict[str, object]:
    layer_contract = [
        {
            "type_name": layer.type_name,
            "output_name": layer.output_name,
            "geometry_family": layer.geometry_family,
            "sort_by": layer.sort_by,
            "integer_fields": list(layer.integer_fields),
            "date_fields": list(layer.date_fields),
            "text_fields": list(layer.text_fields),
        }
        for layer in layers
    ]
    encoded = json.dumps(layer_contract, sort_keys=True).encode()
    schema_fingerprints = getattr(client, "schema_fingerprints", None)
    schema_fingerprint: object = (
        schema_fingerprints(layers)
        if schema_fingerprints is not None
        else hashlib.sha256(encoded).hexdigest()
    )
    return {
        "endpoint": client.config.base_url,
        "crs": client.config.crs,
        "schema_fingerprint": schema_fingerprint,
    }


def _new_checkpoint(
    contract: dict[str, object],
    layers: tuple[LayerSpec, ...],
    expected: dict[str, int],
) -> dict[str, object]:
    return {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contract": contract,
        "complete": False,
        "layers": {
            layer.output_name: {
                "type_name": layer.type_name,
                "expected_count": expected[layer.output_name],
                "written_count": 0,
                "null_complete": False,
                "last_completed_id": None,
                "complete": False,
            }
            for layer in layers
        },
    }


def _resume_pages(
    client: WfsClient,
    layer: LayerSpec,
    expected: int,
    progress: dict[str, object],
) -> Iterator[gpd.GeoDataFrame]:
    written = int(progress["written_count"])
    if not written:
        yield from client.iter_pages(layer, expected)
        return
    resume = getattr(client, "iter_pages_from", None)
    if resume is not None:
        yield from resume(
            layer,
            expected,
            after_id_ua=progress["last_completed_id"],
            include_null=not bool(progress["null_complete"]),
            already_emitted=written,
        )
        return
    parameters = inspect.signature(client.iter_pages).parameters
    if "after_id_ua" not in parameters or "include_null" not in parameters:
        raise WfsError(
            f"{layer.type_name}: checkpoint exists but WFS client has no "
            "resume-aware paging support"
        )
    yield from client.iter_pages(
        layer,
        expected,
        after_id_ua=progress["last_completed_id"],
        include_null=not bool(progress["null_complete"]),
    )


def _reconcile_checkpoint(
    publisher: GeoPackagePublisher,
    checkpoint: dict[str, object],
    layers: tuple[LayerSpec, ...],
) -> None:
    layer_states = checkpoint["layers"]
    assert isinstance(layer_states, dict)
    changed = False
    for layer in layers:
        state = layer_states[layer.output_name]
        assert isinstance(state, dict)
        truth = publisher.inspect_layer_progress(publisher.partial_path, layer)
        saved_count = int(state["written_count"])
        actual_count = int(truth["written_count"])
        if actual_count < saved_count:
            raise StorageError(
                f"{layer.output_name}: partial has {actual_count} rows, "
                f"checkpoint records {saved_count}"
            )
        if actual_count > int(state["expected_count"]):
            raise StorageError(
                f"{layer.output_name}: partial exceeds expected source count"
            )
        if actual_count != saved_count:
            state.update(truth)
            changed = True
        if actual_count == int(state["expected_count"]) and not state["complete"]:
            state["complete"] = True
            changed = True
    if changed:
        checkpoint["complete"] = all(
            bool(layer_states[layer.output_name]["complete"]) for layer in layers
        )
        publisher.save_checkpoint(checkpoint)


def sync_layer(
    client: WfsClient,
    publisher: GeoPackagePublisher,
    staging: Path,
    layer: LayerSpec,
    *,
    checkpoint: dict[str, object] | None = None,
) -> tuple[int, int]:
    if checkpoint is None:
        expected = client.feature_count(layer.type_name)
        progress: dict[str, object] = {
            "expected_count": expected,
            "written_count": 0,
            "null_complete": False,
            "last_completed_id": None,
            "complete": False,
        }
    else:
        layer_states = checkpoint["layers"]
        assert isinstance(layer_states, dict)
        progress = layer_states[layer.output_name]
        assert isinstance(progress, dict)
        expected = int(progress["expected_count"])
    LOGGER.info("layer=%s expected=%d", layer.output_name, expected)
    written = int(progress["written_count"])
    seen_ids: set[str] = set()
    first = written == 0
    if progress["complete"]:
        return expected, written
    if expected == 0:
        if first:
            publisher.write_page(
                staging,
                layer,
                empty_frame(layer, client.config.crs),
                first=True,
                crs=client.config.crs,
            )
        progress["null_complete"] = True
        progress["complete"] = True
        if checkpoint is not None:
            publisher.save_checkpoint(checkpoint)
    else:
        for page_number, frame in enumerate(
            _resume_pages(client, layer, expected, progress), start=1
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
            keys = frame["ID_UA"]
            if keys.isna().all():
                progress["null_complete"] = True
            elif keys.isna().any():
                raise WfsError(f"{layer.type_name}: page mixes null and numeric ID_UA")
            else:
                boundary = int(keys.max())
                previous = progress["last_completed_id"]
                if previous is not None and boundary <= int(previous):
                    raise WfsError(
                        f"{layer.type_name}: resumed cursor did not advance"
                    )
                progress["last_completed_id"] = boundary
                # Reaching numeric data proves the iterator completed its
                # nullable-key phase, including the zero-null case.
                progress["null_complete"] = True
            progress["written_count"] = written
            if checkpoint is not None:
                truth = publisher.inspect_layer_progress(staging, layer)
                if int(truth["written_count"]) != written:
                    raise StorageError(
                        f"{layer.output_name}: stored {truth['written_count']}, "
                        f"wrote {written}"
                    )
                progress.update(truth)
                publisher.save_checkpoint(checkpoint)
            LOGGER.info(
                "layer=%s page=%d downloaded=%d/%d cursor=%s",
                layer.output_name,
                page_number,
                written,
                expected,
                progress["last_completed_id"],
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
    progress["complete"] = True
    if checkpoint is not None:
        publisher.save_checkpoint(checkpoint)
    return expected, written


def sync_all(
    client: WfsClient,
    publisher: GeoPackagePublisher,
    layers: tuple[LayerSpec, ...] = LAYERS,
    *,
    restart: bool = False,
) -> list[LayerResult]:
    started = time.monotonic()
    with output_lock(publisher.destination):
        if restart:
            publisher.restart()
        checkpoint = publisher.load_checkpoint()
        contract = _contract(client, layers)

        # Recovery for interruption after atomic rename but before checkpoint
        # cleanup. At this point the completed destination is authoritative.
        if checkpoint is not None and not publisher.partial_path.exists():
            if checkpoint.get("complete") and publisher.destination.exists():
                if checkpoint.get("contract") != contract:
                    raise StorageError(
                        "completed checkpoint is incompatible with current source"
                    )
                layer_states = checkpoint["layers"]
                assert isinstance(layer_states, dict)
                stored = publisher.inspect(publisher.destination, layers)
                if any(
                    stored[layer.output_name][0]
                    != int(layer_states[layer.output_name]["expected_count"])
                    for layer in layers
                ):
                    raise StorageError(
                        "published GeoPackage does not match completed checkpoint"
                    )
                results = _results_from_storage(
                    layers, layer_states, stored
                )
                publisher.finalize_publication(
                    _manifest(contract, layers, layer_states)
                )
                publisher.checkpoint_path.unlink(missing_ok=True)
                return results
            layer_states = checkpoint.get("layers")
            if isinstance(layer_states, dict) and all(
                int(state["written_count"]) == 0
                for state in layer_states.values()
                if isinstance(state, dict)
            ):
                # A request may fail after initial checkpoint creation but
                # before the first GeoPackage layer is created.
                pass
            else:
                raise StorageError(
                    f"checkpoint exists but partial file is missing: "
                    f"{publisher.partial_path}"
                )

        if checkpoint is None:
            if publisher.partial_path.exists():
                raise StorageError(
                    f"partial file exists without checkpoint: {publisher.partial_path}"
                )
            expected = {
                layer.output_name: client.feature_count(layer.type_name)
                for layer in layers
            }
            checkpoint = _new_checkpoint(contract, layers, expected)
            publisher.save_checkpoint(checkpoint)
        else:
            if checkpoint.get("contract") != contract:
                raise StorageError(
                    "checkpoint source endpoint, CRS, layers, or schema contract "
                    "changed; restart is required"
                )
            layer_states = checkpoint["layers"]
            assert isinstance(layer_states, dict)
            for layer in layers:
                current = client.feature_count(layer.type_name)
                saved = int(layer_states[layer.output_name]["expected_count"])
                if current != saved:
                    raise WfsError(
                        f"{layer.type_name}: source count changed since checkpoint "
                        f"({saved} -> {current}); restart is required"
                    )
            _reconcile_checkpoint(publisher, checkpoint, layers)

        staging = publisher.create_staging_path()
        counts = {
            layer.output_name: sync_layer(
                client,
                publisher,
                staging,
                layer,
                checkpoint=checkpoint,
            )
            for layer in layers
        }
        stored = publisher.inspect(staging, layers)
        layer_states = checkpoint["layers"]
        assert isinstance(layer_states, dict)
        results = _results_from_storage(layers, layer_states, stored)

        # A long parcel transfer can overlap later point-layer changes.
        for layer in layers:
            expected = counts[layer.output_name][0]
            final_count = client.feature_count(layer.type_name)
            if final_count != expected:
                raise WfsError(
                    f"{layer.type_name}: source count changed before publication "
                    f"({expected} -> {final_count})"
                )

        checkpoint["complete"] = True
        publisher.save_checkpoint(checkpoint)
        publisher.publish(
            staging,
            manifest=_manifest(contract, layers, layer_states),
        )
        publisher.checkpoint_path.unlink(missing_ok=True)
        LOGGER.info(
            "published=%s elapsed_seconds=%.1f",
            publisher.destination,
            time.monotonic() - started,
        )
        return results


def _results_from_storage(
    layers: tuple[LayerSpec, ...],
    layer_states: dict[str, object],
    stored: dict[str, tuple[int, tuple[float, float, float, float] | None]],
) -> list[LayerResult]:
    results = []
    for layer in layers:
        state = layer_states[layer.output_name]
        assert isinstance(state, dict)
        expected = int(state["expected_count"])
        written = int(state["written_count"])
        stored_count, bounds = stored[layer.output_name]
        if stored_count != written or written != expected:
            raise WfsError(
                f"{layer.output_name}: stored={stored_count}, wrote={written}, "
                f"expected={expected}"
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
    return results


def _manifest(
    contract: dict[str, object],
    layers: tuple[LayerSpec, ...],
    layer_states: dict[str, object],
) -> dict[str, object]:
    return {
        "version": 1,
        **contract,
        "layers": {
            layer.output_name: {
                "type_name": layer.type_name,
                "feature_count": int(
                    layer_states[layer.output_name]["expected_count"]  # type: ignore[index]
                ),
            }
            for layer in layers
        },
    }
