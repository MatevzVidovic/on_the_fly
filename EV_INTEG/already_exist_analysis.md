# Existing EV historical-table analysis

This comparison uses the required EV source tables from `spec.md` and the PostgreSQL table inventory supplied on 2026-08-05. `ev_*_h` is treated as the expected historical destination naming convention; it is an inference from the existing database names, not a verified LIFT mapping.

| EV source table to integrate | Expected historical PostgreSQL name | Existing PostgreSQL table(s) | Assessment / required advance analysis |
| --- | --- | --- | --- |
| `DST_PRIPIS_PODATKI` | `ev_dst_pripis_podatki_h` | None found | Does **not** appear to exist. Confirm the intended target name and whether it is historical despite its name not beginning `JN_`. |
| `JN_DEL_STAVBE` | `ev_del_stavbe_h` | `ev_del_stavbe_h` | Already exists. Compare its column contract, key, revision timestamps, source filter, and row counts before reuse. |
| `JN_DEL_STAVB_ENOTA` | split historical tables | `ev_del_stavbe_enota_h_2020_2024`, `ev_del_stavbe_enota_h_2025_danes` | Already exists as the required split. Verify year boundaries, no gaps/overlap, omitted `PODATKI`, and that the 2025+ integration is active/correct. |
| `JN_PARC_DEL` | `ev_parc_del_h` | `ev_parc_del_h` | Already exists. Validate the historical key, revision joins, status filter, and count parity. |
| `JN_PARC_ENOTA` | split historical tables | `ev_parc_enota_h_2020`, `ev_parc_enota_h_2021`, `ev_parc_enota_h_2022`, `ev_parc_enota_h_2023`, `ev_parc_enota_h_2024`, `ev_parc_enota_h_2025_danes` | Already exists as the required split. Verify all annual boundary rules, no gaps/duplicates, omitted `PODATKI`, and the 2025+ delta integration. |
| `JN_PARCELA` | `ev_parcela_h` | `ev_parcela_h` | Already exists. Compare schema, primary/synthetic key, revision timestamps, status filter, and geometry handling. |
| `JN_PE_DST` | `ev_pe_dst_h` | `ev_pe_dst_h` | Already exists. This is one of the three POC tables; inspect before creating/running its LIFT integration or bootstrap loader. |
| `JN_PE_PARC` | `ev_pe_parc_h` | `ev_pe_parc_h`, `ev_h_pe_parc` | Already exists, but there are **two similarly named historical candidates**. Determine which is authoritative before loading anything; inspect columns, row counts, owners/creation dates, and downstream references. |
| `JN_POSEBNA_ENOTA` | `ev_posebna_enota_h` | `ev_posebna_enota_h`, `ev_posebna_enota_pod_h` | `ev_posebna_enota_h` is the likely direct historical match. `ev_posebna_enota_pod_h` may be a related child/detail table; inspect it rather than treating it as a duplicate. |
| `JN_PROSTOR` | `ev_prostor_h` | `ev_prostor_h` | Already exists. Validate its historical projection and counts before reuse. |
| `JN_STAVBA` | `ev_stavba_h` | `ev_stavba_h` | Already exists. Validate schema, revision timestamps, status filter, and geometry handling before reuse. |
| `PARC_PRIPIS_PODATKI` | `ev_parc_pripis_podatki_h` | None found | Does **not** appear to exist. Confirm target naming and whether its `JN_REV_NUM`-based history needs the same revision projection. |

## Summary

- Ten of the twelve required source-table integrations have an apparent historical destination already present.
- The two apparent gaps are `DST_PRIPIS_PODATKI` and `PARC_PRIPIS_PODATKI`.
- The three POC source tables already have likely historical destinations, so the immediate task is not necessarily table creation: first verify whether those tables already have the intended LIFT contract and data.

## Notable irregularities to investigate

1. `ev_pe_parc_h` and `ev_h_pe_parc` are potentially duplicate or differently-versioned representations of `JN_PE_PARC`. Do not select a bootstrap target from its name alone.
2. The `JN_DEL_STAVB_ENOTA` historical target is split into two ranges (`2020_2024` and `2025_danes`), while `JN_PARC_ENOTA` is split once per year through 2024 and then `2025_danes`. Confirm why the split strategies differ and verify the exact boundary predicate for every table.
3. Unsuffixed tables such as `ev_del_stavbe`, `ev_parcela`, `ev_posebna_enota`, and `ev_stavba` also exist alongside their `_h` equivalents. They are likely current-state tables, not suitable targets for the historical imports, but this must be confirmed from columns and consumers.
4. `ev_posebna_enota_pod_h` likely represents a subordinate/detail dataset, not a second copy of `JN_POSEBNA_ENOTA`; its key and provenance need checking.
5. The supplied inventory contains `ev_parc_del_enota` without an `_h` suffix, while the required source table is `JN_PARC_DEL`. Do not infer that it is its historical target without schema confirmation.
6. For every apparent existing target, inspect: column list and types; unique key; `valid_from`, `valid_to`, and `date_change`; source status handling; row count and min/max revision dates; and whether a LIFT integration already owns it. This is required before any loader writes to it.
