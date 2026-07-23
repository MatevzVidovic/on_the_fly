from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LayerSpec:
    type_name: str
    output_name: str
    geometry_family: Literal["point", "polygon"]
    sort_by: str
    integer_fields: tuple[str, ...]
    date_fields: tuple[str, ...]
    text_fields: tuple[str, ...]

    @property
    def attribute_fields(self) -> tuple[str, ...]:
        return self.integer_fields + self.date_fields + self.text_fields


@dataclass(frozen=True)
class WfsConfig:
    base_url: str = "https://storitve.eprostor.gov.si/ows-pub-wfs/wfs"
    page_size: int = 5_000
    timeout_seconds: float = 120.0
    retries: int = 4
    crs: str = "EPSG:3794"

    def __post_init__(self) -> None:
        if self.page_size < 1:
            raise ValueError("page_size must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.retries < 0:
            raise ValueError("retries cannot be negative")


@dataclass(frozen=True)
class LayerResult:
    type_name: str
    output_name: str
    expected_count: int
    written_count: int
    bounds: tuple[float, float, float, float] | None


LAYERS: tuple[LayerSpec, ...] = (
    LayerSpec(
        type_name="SI.MOP.GRAD:UPRAVNI_AKTI",
        output_name="upravni_akti_tocke",
        geometry_family="point",
        sort_by="ID_UA A",
        integer_fields=("ID_UA", "SIF_PU", "OB_ID", "VRS_AKT"),
        date_fields=(
            "DAT_IZD",
            "DAT_POP",
            "MAX_DAT_PRA",
            "DAT_RAZ",
            "ZAD_SPR",
            "DAT_ZAC_GRA",
        ),
        text_fields=(
            "NAZ_UPR_ORG",
            "STEV_ZAD",
            "SIF_VRS_UA_KRA_SIF",
            "VRS_AKT_2",
            "NAZ_UPR_POS",
            "OBJ",
        ),
    ),
    LayerSpec(
        type_name="SI.MOP.GRAD:UPRAVNI_AKTI_PARCELE",
        output_name="upravni_akti_parcele",
        geometry_family="polygon",
        sort_by="ID_UA A,SIFKO A,PARCELA A,OB_ID A,VRS_AKT A",
        integer_fields=("ID_UA", "OB_ID", "SIFKO", "VRS_AKT"),
        date_fields=("ZAD_SPR",),
        text_fields=("PARCELA", "BARVA_POLIGONA"),
    ),
)

