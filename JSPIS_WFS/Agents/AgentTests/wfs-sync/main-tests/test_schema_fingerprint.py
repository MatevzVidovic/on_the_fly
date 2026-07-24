from __future__ import annotations

from dataclasses import replace

from wfs_sync.model import LAYERS, LayerSpec, WfsConfig
from wfs_sync.wfs import FieldDefinition, WfsClient


FIELDS = [
    FieldDefinition("ID_UA", "xsd:decimal", False),
    FieldDefinition("ZAD_SPR", "xsd:dateTime", True),
]


class _SchemaClient(WfsClient):
    def __init__(
        self,
        schemas: dict[str, list[FieldDefinition]],
        *,
        crs: str = "EPSG:3794",
    ) -> None:
        self.config = WfsConfig(crs=crs)
        self.schemas = schemas
        self.requested: tuple[str, ...] | None = None

    def describe_feature_types(
        self, type_names: tuple[str, ...]
    ) -> dict[str, list[FieldDefinition]]:
        self.requested = type_names
        return self.schemas


def _schemas(fields: list[FieldDefinition]) -> dict[str, list[FieldDefinition]]:
    return {
        layer.type_name.rsplit(":", 1)[-1]: list(fields)
        for layer in LAYERS
    }


def test_schema_fingerprints_are_deterministic_and_keyed_by_output_layer() -> None:
    client = _SchemaClient(_schemas(FIELDS))

    first = client.schema_fingerprints(LAYERS)
    second = _SchemaClient(_schemas(list(reversed(FIELDS)))).schema_fingerprints(
        reversed(LAYERS)
    )

    assert first == second
    assert set(first) == {layer.output_name for layer in LAYERS}
    assert all(
        len(fingerprint) == 64
        and set(fingerprint) <= set("0123456789abcdef")
        for fingerprint in first.values()
    )
    assert client.requested == tuple(layer.type_name for layer in LAYERS)


def test_schema_field_drift_changes_fingerprint() -> None:
    baseline = _SchemaClient(_schemas(FIELDS)).schema_fingerprints(LAYERS)
    changed_fields = [
        FIELDS[0],
        FieldDefinition("ZAD_SPR", "xsd:string", True),
    ]
    changed = _SchemaClient(_schemas(changed_fields)).schema_fingerprints(LAYERS)

    assert changed.keys() == baseline.keys()
    assert all(changed[name] != baseline[name] for name in baseline)


def test_layer_type_and_crs_are_part_of_schema_contract() -> None:
    layer = LAYERS[0]
    baseline = _SchemaClient(_schemas(FIELDS)).schema_fingerprints((layer,))

    changed_crs = _SchemaClient(
        _schemas(FIELDS), crs="EPSG:4326"
    ).schema_fingerprints((layer,))

    renamed_type: LayerSpec = replace(
        layer, type_name="OTHER:UPRAVNI_AKTI"
    )
    renamed = _SchemaClient(_schemas(FIELDS)).schema_fingerprints((renamed_type,))

    assert changed_crs[layer.output_name] != baseline[layer.output_name]
    assert renamed[layer.output_name] != baseline[layer.output_name]
