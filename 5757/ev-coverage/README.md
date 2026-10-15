# What model versions and dates actually occur in the EV valuation data

Observed on 2026-10-15 using small block samples plus indexed Oracle history lookups for one real unit per model. This is a verified example/coverage guide, **not a complete inventory or exact global min/max scan**. It covers building-part and parcel valuation data relevant to ticket 5757.

**Expanded analysis:** [Current versus history: dates, model distributions and estimated volumes](current-vs-history-statistics.md). This includes both Oracle current data and staging copies, with estimates clearly separated from verified examples.

**Exact imported-row validation:** [800 staging rows resolved by their composite Oracle journal keys](exact-key-sample/README.md). This is a staging-led sample, including recovered model IDs and dates.

## Connection and dates

The same Oracle connection in `5757/.env` exposes KN schemas (`NEP`, `NEP_OSTALO`, etc.) and the EV schema. KN contains the property-state inputs; the EV value history supplies the dated reference amounts. A KN record date does not establish which EV model generated a valuation.

EV history links `JN_REV_NUM` and `JN_REV_NUM_TO` to `EV.REVISION.REV_NUM`; `REVISION.CREATED` gives the observed start/end timestamps. The version ID on the valuation row links to `EV.MODELI_XML`, whose XML header gives the GV version imported into ISAM. Model market dates are separate from those history intervals.

## Actual example rows at two useful cutoffs

Each cell below is the actual EV version valid for the selected example unit at that date, followed by the XML/GV version. The example unit is the same across the two dates within each row. These findings do not guarantee every unit has coverage or the same generation.

| Type | Model | Example unit | At 2025-01-01 | At 2026-01-01 |
|---|---|---|---|---|
| Building part | GAR | 28888343 | 1155 / GV 74 | 1170 / GV 90 |
| Building part | HIS | 28686586 | 1149 / GV 161 | 1172 / GV 282 |
| Building part | IND | 29765975 | 1150 / GV 51 | 1173 / GV 66 |
| Building part | INP | 29884004 | 1151 / GV 36 | 1174 / GV 49 |
| Building part | KDS | 28602100 | 1165 / GV 26 | 1175 / GV 46 |
| Building part | PPL | 28737054 | 1152 / GV 151 | 1177 / GV 192 |
| Building part | PPP | 28592902 | 1153 / GV 185 | 1178 / GV 225 |
| Building part | SDP | 29890117 | 1154 / GV 18 | 1179 / GV 33 |
| Building part | STA | 28482262 | 1148 / GV 150 | 1180 / GV 223 |
| Building part | TUR | 100000058998 | 1156 / GV 27 | 1182 / GV 42 |
| Parcel unit | DRZ | 100000003802.DRZ | 1163 / GV 9 | 1169 / GV 16 |
| Parcel unit | GOZ | 100000003802.GOZ | 1162 / GV 73 | 1171 / GV 96 |
| Parcel unit | KME | 100000003802.KME | 1161 / GV 81 | 1176 / GV 100 |
| Parcel unit | STZ | 100000003802.STZ | 1164 / GV 13 | 1181 / GV 44 |

[Full source rows, unit IDs, revision numbers and exact intervals](verified-model-examples.json). Version identity does not by itself prove migrated formula equivalence. KDS 26 needs review because two EV definitions use that version marker; TUR’s EV 2020 definition is GV 27 while staging imported TUR 26; staging DRZ 16 has a model-date mismatch. See the [mapping export](../model-mapping/README.md).

## Observed time coverage

- The Oracle building history sample includes rows starting **2020-04-01 12:00:00**. Our earlier IND example has no covering row on 2020-01-01; do not backdate April records merely because the model date says January 2020.
- Indexed per-model histories show switches to the 2025 generation around **2025-05-13 23:59:59**, followed by revisions in late 2025 and 2026. Per-unit intervals, not a global date-to-model shortcut, decide which record applies.
- The Oracle parcel sample includes row starts as recent as **2026-10-12 23:59:59.999**. This is an observed sample date, not a proven database-wide maximum.
- The new staging parcel history sample contains **both old and new EV version IDs**. For example KME 1161 and 1176 coexist in `ev_parc_enota_h_2025_danes`. The same mixed-generation issue is visible in dated source building histories.
- ZPS rows with NULL version IDs and NAPAKA rows also occur. Preserve these as explicit special/error cases; do not invent a model mapping.

## What we currently have on staging

| Table/source | Observed finding |
|---|---|
| `ev_del_stavbe_enota` | Sample contains older EV IDs, including IND 1150. No validity dates in this table. |
| `ev_parc_enota` | Sample contains older parcel IDs (DRZ 1163, GOZ 1162, KME 1161, STZ 1164). No validity dates. |
| `ev_del_stavbe_enota_h_2020_2024` | All 1164 sampled rows have NULL start dates; version-ID column is absent. Oracle history retains the information for inspected source examples. |
| `ev_del_stavbe_enota_h_2025_danes` | Dated rows appear in 2025–2026, including starts before May 2025; version-ID column is absent. |
| `ev_parc_enota_h_2025_danes` | Dated rows with old and new version IDs; version ID can be checked directly. |

The current staging tables cannot be assumed to represent the current Oracle generation. Those are sample observations; no full freshness or completeness audit was performed. [Observed samples and date ranges](observed-coverage.json). A column absent from a staging schema is distinguished from an actual NULL ID in the Oracle source.

## How to choose the comparison

1. Choose a property cutoff supported by prepared KN inputs and EV history. **2026-01-01 is a useful candidate for the 2025 generation**, while **2025-01-01 is a useful candidate for older-generation comparisons**. Verify the selected rows per unit.
2. Select the EV history interval covering the cutoff: `start <= cutoff < end`, or open end; preserve ambiguous/missing cases.
3. Use that row’s actual EV version and the explicit XML identity map to choose/check the ISAM model version. Do not assume model date equals property cutoff.
4. For building histories missing local version IDs/dates, use bounded source lookups for pilots or correct the integration fields before scaling up.
5. Check required ISAM versions exist: some source versions are not imported or are only represented by working copies. No automatic aliasing to a similar version.

No whole-table counts/groupings were run. Sampling reads were capped at 3000 selected rows per table and all per-model verification used indexed unit keys, sequential read-only transactions, rollback and timeouts. Oracle block sampling returned zero current-building rows in this particular sample; this does not imply that table is empty. Global completeness, all distinct timestamps and rare model versions remain unmeasured.

[Compact example CSV](model-date-examples.csv) · [Index/constraint audit](../integration-index-audit/README.md)
