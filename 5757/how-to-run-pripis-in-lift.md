# Run a pripis calculation in Lift, including IND 51

Verified 2026-10-15 using the SFC comparator dumps, current staging FMP assignments, and local workflow code. No actions were launched and no database data was changed.

## Exact location

Open the results table for **`pripis_presecni_datum`**, then open the **row action menu** for the desired cutoff-date record.

| Action | SFC title | Position key | Menu order |
|---|---|---|---:|
| Prepare units | Generiranje enot vrednotenja | RESULTS_TABLE_ROW_MENU | 25 |
| Calculate values | Izračun vrednosti enot vrednotenja | RESULTS_TABLE_ROW_MENU | 24 |

The calculation button text in the saved SFC code is **Izračun vrednosti enot**. Its SFC UUID is `06635e34-6407-11f1-a726-0ecfb36ed36d`. The stored `order` is 24; this is not the 24th visible item. Subsequent source inspection found no explicit ordering by this field in the row-menu rendering path, so changing it is not verified to reorder this menu. These actions are attached to the date table, not to the model-version table or the KP transaction table.

[Current staging assignments](pilot/pripis-sfc-wiring.json). The comparator's latest dump (`20261005_130202`) confirms the table/position assignment. Its inline code fields are empty; the earlier `20260928_120912` dump contains the action code. Live staging metadata also has empty inline code, so the exact current externally stored JavaScript was not independently downloaded.

The saved code calls:

```text
Generiranje enot vrednotenja
→ /xhr/workflows/PripravaPrepisaWorkflow
→ workflow_payload: { "id-pr-datum": RECORD_DATA.id }

Izračun vrednosti enot
→ /xhr/workflows/CalculateValuesWorkflow
→ workflow_payload: { id_rel_pr_datum: RECORD_DATA.id }
```

The local calculation workflow receives that date-row ID and uses `pripis_vm_x_pd` to select configured model versions. It is separate from the KP/NP action, which uses `CalculatePodposliWorkflow`.

## Run historical IND 51

Historical model date and property-state cutoff are separate choices. IND 51 has model date **2020-01-01**, but it can be selected to calculate property state at another supported cutoff. For our sample unit, the EV value recorded at **2025-01-01** uses IND 51 / EV 1150; its source valuation history has no covering row at 2020-01-01. See [model/date research](reference/ev-isam-model-version-research.md).

For a dated comparison with the known EV record, use **2025-01-01**:

1. Open the existing `2025-01-01` row in `pripis_presecni_datum`.
2. In **`pripis_vm_x_pd`**, create the model/date connection below. If a suitable relation editor is exposed in your Lift layout, that editor can create the same connection. Its exact UI label has not been verified.
3. From the date row menu, run **Generiranje enot vrednotenja** if that date's units have not been prepared. Wait for it to finish before calculating.
4. From the same date row menu, run **Izračun vrednosti enot**. This uses the configured model versions; there is no model selector in the saved SFC.
5. Inspect `pripis_vmxpd_x_enote`, filtering `id_rel_vm_pd` to the configuration row created in step 2. For building parts, its `id_rel_prip_enota` points to `pripis_enote_deli_stavb.id`. Final values and intermediate lists are saved together.

Connection fields for **IND 51 at 2025-01-01 on staging**:

| Field in pripis_vm_x_pd | Value |
|---|---|
| id_rel_pr_datum | `7273d0e6-6b09-11f1-86b6-424abd3ca6bd` |
| id_rel_verzije_modeli | `99956834-d772-4f90-b01a-0078f15f6062` |

IND 51 is already marked `pripisna = true`. At the time of inspection, no IND 51 connection existed; the only IND connection was IND 66 at 2026-01-01. Do not repoint that existing connection just to run the historical pilot. [Verified staging state](pilot/pripis-ind-run-state.json).

If you specifically need **2020-01-01 property state**, create/select that cutoff and connect IND 51 to it instead. That date does not currently exist on staging. Before running a large preparation, establish that the required historical property inputs exist: the preparation code filters dated source rows; it cannot reconstruct missing historical data merely because an old model exists. A matching EV as-of reference also needs to be available.

## Scope and reruns

The existing calculation button runs **all configured models with prepared units for that cutoff**, across prepared building and parcel units. It is not a one-unit pilot action. To calculate only IND through this action, the selected date must have only the intended IND model configuration; first inspect its other configurations. Keep one intended version per model/date.

Generation rebuilds the selected date's prepared units and rooms. Calculation replaces existing results for the processed date/model configurations. Reuse existing prepared units when only recalculating model values; generation is not a required step on every calculation rerun.

The IND 66 coefficient investigation is [deferred](deferred-investigations.md). No migration/model correction was applied as part of finding this trigger.

## How the stored SFC order is assigned

Local Lift source inspection found `order: this.getSavedAttributes.length` in `SfcBindToElement.vue`. The binding save assigns the number automatically from the number of matching saved bindings, rather than `max(order)+1`. Its update action sends that same calculation, so updating a binding can also change its order. Deletion or concurrent edits can produce equal numbers. The count filtering is not always strictly table-scoped: for ordinary table bindings the attribute-table filter is only added when `attributeFieldId` is set. Therefore this number must not be interpreted as a clean per-table position.

Both the SFC store Link tab and binding form were inspected. Neither exposes a numeric order field or a binding reorder control. Backend update requests accept `order`, but no ordinary UI setter was found.

Equal values do not replace or hide either binding. The inspected `SfcStoreRenderer` iterates the filtered binding list directly; the store getter filters without sorting. No explicit `order` tie-breaker was found on the row-menu path. Its effective sequence follows the loaded list; a durable order for ties is not established. This corrects the earlier assumption that stored order necessarily controls this menu.

Source references:

- [Automatic assignment and update](/Users/matevzvidovic/on_the_fly/symlinks/fmp/resources/assets/vue/basicComponents/sfc-editor/SfcBindToElement.vue:330).
- [Binding-count filters](/Users/matevzvidovic/on_the_fly/symlinks/fmp/resources/assets/vue/basicComponents/sfc-editor/SfcBindToElement.vue:188).
- [Link UI](/Users/matevzvidovic/on_the_fly/symlinks/fmp/resources/assets/vue/tools/admin/sfc-store/tabs/Link.vue:1).
- [Renderer iteration](/Users/matevzvidovic/on_the_fly/symlinks/fmp/resources/assets/vue/basicComponents/sfc-editor/SfcStoreRenderer.vue:3).

These findings describe the inspected local source; no live UI changes were made.
