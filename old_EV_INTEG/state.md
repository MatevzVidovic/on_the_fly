# EV integration state

## Prompt

Look at `already_exist_analysis/already_exist_analysis.md`.

Do the existing tables have correct SQL in their integrations? Where are the errors? Which integrations use KN as the SQL connection—the minority connection ID?

## SQL integration review

| Integration | Assessment | Finding |
| --- | --- | --- |
| `ev_pe_parc_h` | Incorrect | Selects `PODATKI`, but `research/schema_info.csv` shows `EV.JN_PE_PARC` has no `PODATKI` column. This should raise Oracle `ORA-00904` unless the source schema changed. |
| `ev_parc_enota_h_2025_danes` | Incorrect / incomplete | Filters only `rf.created >= 2025-01-01`; it is missing the required `jn_status <> 'X'` filter. |
| `ev_del_stavbe_h` | Correct pattern | Historical revision joins, timestamps, synthetic key, and status filter match the required pattern. |
| `ev_parc_del_h` | Correct pattern | Historical revision joins, timestamps, synthetic key, and status filter match the required pattern. |
| `ev_parcela_h` | Correct pattern | Historical revision joins, timestamps, synthetic key, and status filter match the required pattern. |
| `ev_pe_dst_h` | Correct pattern | Historical revision joins, timestamps, synthetic key, and status filter match the required pattern. |
| `ev_posebna_enota_h` | Correct pattern | Historical revision joins, timestamps, synthetic key, and status filter match the required pattern. |
| `ev_prostor_h` | Correct pattern | Historical revision joins, timestamps, synthetic key, and status filter match the required pattern. |
| `ev_stavba_h` | Correct pattern | Historical revision joins, timestamps, synthetic key, and status filter match the required pattern. |
| `ev_posebna_enota_pod_h` | Unverified | Looks internally consistent, but its source table is outside this repository's research export, so its source-column contract cannot be verified here. |

## SQL connection assignment

The minority connection ID is identified as the KN SQL connection: `54f1cc9c-3983-11f1-8947-06be7399cd5a`.

| SQL connection | Integrations |
| --- | --- |
| KN — `54f1cc9c-3983-11f1-8947-06be7399cd5a` | `ev_del_stavbe_h`, `ev_parc_enota_h_2025_danes`, `ev_stavba_h` |
| Other / EV — `d5f1b77c-7403-11ef-b604-02420a0001cd` | `ev_parc_del_h`, `ev_parcela_h`, `ev_pe_dst_h`, `ev_pe_parc_h`, `ev_posebna_enota_h`, `ev_posebna_enota_pod_h`, `ev_prostor_h` |

## Existing destination tables without a returned integration

| Destination tables | Interpretation |
| --- | --- |
| `ev_del_stavbe_enota_h_2020_2024` | No integration was returned; may be legacy or manually loaded. |
| `ev_parc_enota_h_2020` through `ev_parc_enota_h_2024` | No integrations were returned; may be legacy or manually loaded. |

## Evidence

Reviewed integration export: `../already_exist_analysis/integs.md`.
