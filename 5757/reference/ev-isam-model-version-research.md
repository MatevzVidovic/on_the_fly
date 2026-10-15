# EV ↔ ISAM model versions and dates

Research date: 2026-10-15. Sources: direct read-only Oracle EV metadata and one building-part history; staging PostgreSQL metadata; local `~/isam` migration SQL. No calculations, imports, refreshes or database writes were performed.

## Findings that change the pilot

**ISAM IND 51 corresponds by source-version identity to EV `ID_MODEL_VER=1150`. ISAM IND 66 corresponds to EV `ID_MODEL_VER=1173`.** The EV XML explicitly starts with `<!-- verzija: 51 -->` and `<!-- verzija: 66 -->`, respectively. Both runtime and original XML prefixes agree. Local migrations preserve those GV version numbers in ISAM. This establishes version identity, not that every migrated formula/input produces identical results. [Oracle XML prefixes](model-research/04-ind-xml.json), [migration evidence](local-model-mapping-research.md).

The earlier pilot mapping `IND 66 → EV 1150` was wrong. Its numeric difference is not evidence of a defect: it compared different model generations. Do not reuse that mapping. [Original pilot output](../pilot/example-result.json).

**Do not equate model date with property cutoff date.** The correct normal comparison chooses an EV record valid at a chosen cutoff, reads its actual model-version identity, then calculates the same property state with the corresponding ISAM version. [Dated sample](model-research/12-unit-at-dates.json).

## How the identifiers connect

```text
EV.JN_DEL_STAVBE_ENOTA.ID_MODEL_VER
    → EV.MODELI_XML.ID_MODEL_VER
        → XML comment: verzija N + ID_MODEL
            → GV model/version N
                → ISAM md_verzije_modeli(model, verzija)
                    → ISAM UUID for that model version
```

EV's numeric version ID, GV's per-model version number, and ISAM's UUID are different identifiers. The model code and XML version marker form the evidence for the crosswalk. Do not compare those numbers directly. Migrations read `primoz_gv_verzije` and related factor/table/zone data and create `md_*` records. [IND migration](/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/verzije_2025/polnitev_gradnikov_isam2_ind.sql), [source metadata on staging](model-research/08-staging.json).

## The dates mean different things

| Field/source | What the evidence says |
|---|---|
| EV `MODELI_XML.DATUM_MODELA` | Date to which that version refers. IND 1150 says 1.1.2020; IND 1173 says 1.1.2025. |
| EV `MODELI_GRUPA.DATUM_TRGA` | Source comment: date of the real-estate market state to which valuation refers. |
| EV model/group `DATUM_OD`, `DATUM_DO` | Start/end of validity of the version or group; these are separate from market date. |
| EV `REVISION.CREATED` | Creation time of the revision number. Joining a value's opening/closing revisions gives its recorded validity interval. |
| ISAM `datum_modela` | Migration copies GV `datum_na` into it. |
| ISAM `pripis_presecni_datum.datum` | The selected property-state cutoff used by the pripis process; separate from model date. |

[Oracle column comments](model-research/09-date-comments.json), [IND metadata](model-research/03-ind-models.json), [local migration review](local-model-mapping-research.md).

The 2020 model group starts on **2020-04-01** and ends in May 2025. The 2025 group starts on **2025-05-13**, although its market date is January 2025. IND 1173's individual model validity starts on May 11. Thus neither model date nor model-row validity alone is a sufficient rule for selecting the actual valuation record. Read the dated value row and its version. Model 1150 also has a far-future individual end date despite its group being inactive. [Model/group metadata](model-research/03-ind-models.json).

## Concrete sample: building part 29974237

Oracle `EV.JN_DEL_STAVBE_ENOTA` contains:

| Recorded validity | EV version | XML/GV/ISAM version | Calculated / generalized |
|---|---:|---:|---:|
| 2020-04-01 → 2020-06-16 | 1150 | IND 51 | 7232.88 / 7230 |
| 2020-06-16 → 2022-12-27 | 1150 | IND 51 | 7232.88 / 7230 |
| 2022-12-27 → 2025-05-13 23:59:59 | 1150 | IND 51 | 7232.88 / 7230 |
| 2025-05-13 23:59:59 → 2025-11-02 23:59:59.999 | 1173 | IND 66 | 14824.32 / 14800 |
| 2025-11-02 23:59:59.999 → open | 1173 | IND 66 | 14824.32 / 14800 |

[Source rows and revision IDs](model-research/07-unit-history.json). Times here are source Oracle timestamps; the existing integration explicitly labels revision timestamps Europe/Ljubljana. Boundary/timezone policy needs to stay consistent with ISAM. The sample is away from transition boundaries.

An explicit lookup at three dates, using `start <= cutoff < end` (or open end), returned:

| Property cutoff | EV result for this unit | Corresponding ISAM model |
|---|---|---|
| 2020-01-01 | No covering source history row | Cannot perform a normal as-of comparison from this history at that date |
| 2025-01-01 | 7232.88, EV 1150 | IND 51 |
| 2026-01-01 | 14824.32, EV 1173 | IND 66 |

[Executed SQL](model-research/12-unit-at-dates.sql), [results](model-research/12-unit-at-dates.json). No history row on 2020-01-01 does not prove that no valuation ever existed elsewhere; it limits what this inspected history can support. Backdating the first April record would require a separate approved business rule.

**Recommended pilot: keep the property cutoff 2026-01-01, use IND 66, and select the dated EV history row with model 1173.** The existing staging configuration already uses IND 66 on that cutoff. Alternatively, a 2025-01-01 as-of pilot for this unit should use IND 51. Choosing IND 66 on January 2025 would be a retrospective/new-model exercise rather than comparison with the EV value actually recorded at that time. [Staging configuration](model-research/08-staging.json).

Staging currently stores ISAM 15310.00 / 15300 for this unit under IND 66 at 2026-01-01. Against the dated Oracle result, the arithmetic differences are **485.68 / 500**. These are candidates for investigation, not proof of a calculation bug: input-state alignment and completeness still need checking, and the schema change alone does not recover previously lost decimals. [ISAM sample](model-research/13-staging-pilot-result.json).

## Why the staging EV copies were misleading

For this unit, staging `ev_del_stavbe_enota` contains 7232.88 with model ID 1150, while Oracle history and staging's newer history contain 14824.32. The current staging table is therefore not a reliable current source for this example. This is a one-unit finding, not a full-table freshness audit. [Staging evidence](model-research/08-staging.json), [Oracle evidence](model-research/07-unit-history.json).

The staging old-history rows have NULL validity dates, but Oracle supplies those dates through `REVISION`. Oracle's building-part history also contains `ID_MODEL_VER`, which the inspected staging history schema lacks. The saved integration definition for newer building-part history omits `ID_MODEL_VER` from its SELECT. Restoring source dates and importing version IDs would allow precise local selection; until then, a bounded Oracle lookup can establish evidence for the pilot. This identifies differences, not the root cause of all missing dates. [Saved integration query](../../IntegrationRepair_full_export/diagnostics/current_key_queries.json), [schema inspection](model-research/02-columns.json), [staging sample](model-research/08-staging.json).

## Other models: identity crosswalk and exceptions

The following table was derived offline from bounded EV XML headers and the 34 relevant staging ISAM model rows. A header match establishes source-version identity; it is not full semantic validation. [EV headers](model-research/05-model-map.json), [crosswalk](model-research/11-crosswalk.json).

| ISAM model/version | Matching EV IDs |
|---|---|
| DRZ 16 | 1169 |
| GAR 90 | 1170 |
| GOZ 96 | 1171 |
| HIS 161 | 1149 |
| IND 51 | 1150 |
| IND 66 | 1173 |
| INP 36 | 1151 |
| INP 49 | 1174 |
| KDS 26 | 1157, 1165 |
| KDS 46 | 1175 |
| KME 81 | 1161 |
| KME 100 | 1176 |
| PPL 151 | 1152 |
| PPL 192 | 1177 |
| PPP 185 | 1153 |
| PPP 225 | 1178 |
| SDP 18 | 1154 |
| SDP 33 | 1179 |
| STA 150 | 1148 |
| STA 223 | 1180 |
| STZ 13 | 1164 |
| STZ 44 | 1181 |
| TUR 42 | 1182 |

Important exceptions:

- **KDS 26:** two EV versions, 1157 and 1165, have XML version 26, with differing model-date strings. A single version-number mapping is insufficient; retain actual EV IDs and review contents/validity.
- **DRZ 16:** the version marker matches EV 1169, but ISAM says model date 2024-01-01 while EV says 1.1.2025. Do not silently treat the date mismatch as validated.
- **TUR 26:** the inspected final 2020 EV XML is version 27 (EV 1156), while the historical migration imported 26. GV describes 27 as a copy of 26 with changes for reporting and the April 2020 pripis. Whether those changes preserve valuation behavior needs content comparison.
- **GOZ 36:** the imported historical model is from 2010; the inspected EV 2020 model is GV 73 (EV 1162). They cannot be mapped simply because both are GOZ.
- Several staging versions are later working copies (for example IND 67/68); no matching header appeared in the inspected EV set. Do not automatically map working copies to the original model.

[GV notes](model-research/08-staging.json), [migration profiles](/Users/matevzvidovic/isam/modeliranje/migracija/migracija_modelov/zgodovinske_verzije_2020/README.md). The EV scan was restricted to groups 2/3 and recent/open definitions; an absent match is not proof that no older definition exists anywhere.

## Small next implementation

1. Keep a simple explicit identity map: IND 51 → 1150; IND 66 → 1173, with source evidence.
2. For one unit/cutoff, select the history row first. Preserve missing/duplicate diagnoses; never choose the latest row irrespective of cutoff.
3. Validate the selected EV model against the configured ISAM model. A model mismatch is a diagnostic, not a normal valuation delta.
4. For the 2026 pilot, use the 14824.32 history record, then inspect the same unit's ISAM/EV intermediate inputs.
5. Before broadening, confirm that the property input snapshot is aligned with the selected valuation record. A dated value does not by itself prove every upstream input was refreshed on exactly that date.

The pilot has now been updated to use the exported identity map and dated Oracle history. See the [current pilot](../pilot/README.md) and [expanded export](../model-mapping/README.md). The original 66 → 1150 output is retained only as historical evidence and must not be used for a valid comparison.

## Database load controls and limits

Oracle queries were sequential, read-only transactions ending in rollback, with an eight-second per-call timeout and bounded fetches. Research used catalogs, small model metadata, short XML prefixes (two IND definitions at 3500 characters; other headers at 160), and one indexed property ID. Index metadata confirms the history has leading `DST_SID` indexes and revision lookups have a primary key. There were no full property counts, history-wide grouping, exports or parallel database queries. PostgreSQL checks used the existing read-only helper with statement/lock timeouts and rollback. [Query scripts and raw outputs](model-research/), [Oracle helper](../assets/research_oracle_models.py).

This was model/date research, not full model-equivalence validation, a complete history audit, or a database-wide integration repair.
