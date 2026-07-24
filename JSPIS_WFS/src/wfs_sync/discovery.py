from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .model import LAYERS, LayerSpec
from .wfs import FieldDefinition, WfsClient, WfsError


def _validate_schema(layer: LayerSpec, fields: list[FieldDefinition]) -> None:
    by_name = {field.name: field for field in fields}
    expected = set(layer.attribute_fields) | {"GEOMETRY"}
    if set(by_name) != expected:
        raise WfsError(
            f"{layer.type_name}: DescribeFeatureType schema mismatch; "
            f"missing={sorted(expected - set(by_name))}, "
            f"unexpected={sorted(set(by_name) - expected)}"
        )
    expected_types = {
        **{name: "xsd:decimal" for name in layer.integer_fields},
        **{name: "xsd:dateTime" for name in layer.date_fields},
        **{name: "xsd:string" for name in layer.text_fields},
        "GEOMETRY": "gml:GeometryPropertyType",
    }
    wrong_types = {
        name: (expected_types[name], field.xsd_type)
        for name, field in by_name.items()
        if field.xsd_type != expected_types[name]
    }
    if wrong_types:
        raise WfsError(f"{layer.type_name}: schema type mismatch: {wrong_types}")


def discover(client: WfsClient, layers: tuple[LayerSpec, ...] = LAYERS) -> dict:
    schemas = client.describe_feature_types(tuple(layer.type_name for layer in layers))
    discovered_layers = []
    for layer in layers:
        fields = schemas[layer.type_name.rsplit(":", 1)[-1]]
        _validate_schema(layer, fields)
        discovered_layers.append(
            {
                "type_name": layer.type_name,
                "output_name": layer.output_name,
                "count": client.feature_count(layer.type_name),
                "sort_by": layer.sort_by,
                "fields": [
                    {
                        "name": field.name,
                        "type": field.xsd_type,
                        "nullable": field.nullable,
                    }
                    for field in fields
                ],
            }
        )
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": client.config.base_url,
        "crs": client.config.crs,
        "disk_sync_mode": "checkpointed_full_snapshot",
        "database_sync_mode": "inventory_reconciled_delta",
        "sync_reason": (
            "PostGIS compares a complete geometry-free WFS ID/ZAD_SPR inventory "
            "with its mirror, upserts new or changed features, refreshes null "
            "timestamps, and deletes IDs absent from the source."
        ),
        "layers": discovered_layers,
    }


def write_report(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
