# Decimal migration state — checked 2026-10-15

Read-only checks against the staging data and system databases confirmed:

| Item | State |
|---|---|
| PostgreSQL `pripis_vmxpd_x_enote.vrednost_izr` | Unrestricted `numeric`; precision/scale are NULL, not `(20,2)` |
| Lift definition for that field | `decimal`, `type_params.scale = 2` |
| Statistics materialized view | Exists and populated; sampled `refreshed_at` is 2026-10-15 09:17:42.967717 UTC |
| MV query, owner, effective grants and indexes | Match exported backup |
| MV sum/min/max calculated-value columns | PostgreSQL `numeric`, as expected after the source type change |
| Lift definitions for those three MV columns | Still bigint/integer; need metadata alignment |

The stale MV fields are `vsota_vrednost_izr` (Lift bigint), `min_vrednost_izr` (Lift integer), and `max_vrednost_izr` (Lift integer). Their physical MV columns are already numeric. Update/synchronize their Lift definitions to Decimal Number rather than attempting to alter the MV columns.

## Why setting two decimal places did not change the SQL type

The UI writes `type_params.scale`. In the inspected local backend, `CreateOrUpdatePhysicalAttributeFieldsFacadeService::castFieldValues` skips a physical migration when the requested native type matches the actual native type and the expression has not changed. It does not compare numeric precision/scale there. Thus changing scale on an already numeric field can update Lift metadata without changing PostgreSQL's typmod. This is consistent with the observed database state; the deployed backend revision has not been independently verified.

The application also has a decimal-rounding path using this metadata during its data-save handling. Therefore scale is not necessarily only visual formatting. Direct SQL/Python writes are still governed by PostgreSQL's unrestricted numeric type; it does not enforce two decimal places. The inspected ISAM result writer explicitly rounds calculated values to two decimals, but a live write/read round trip was not performed during these read-only checks.

The task requires numeric and suggests numeric(20,2). Unrestricted numeric satisfies decimal storage but does not enforce the suggested precision/scale. If strict numeric(20,2) is chosen, it needs another coordinated dependency-aware migration; do not repeat dropping/recreating the MV merely to make the type label look different.

No writes, migrations, refreshes or metadata updates were performed by the assistant. Previously lost decimals have not been recovered or assessed by this check.

Evidence: [data DB snapshot](mv-backup/staging-after-refresh.json), [Lift metadata](mv-backup/lift-decimal-metadata-check.json).

Local code: [physical field update](../symlinks/fmp/app/_AttributeTables/Services/Facade/AttributeField/CreateOrUpdatePhysicalAttributeFieldsFacadeService.php), [scale control](../symlinks/fmp/resources/assets/vue/templates/mapview/components/Panels/AttributeTablePanel/AttributeField/type-params/NumberTypeParam.vue), [application save rounding](../symlinks/fmp/app/_AttributeTables/Services/Facade/AttributeTableData/SaveAttributeTableDataFacadeService.php).
