# 5757: first building-part pilot

## The whole task

We need to answer two questions:

1. Did ISAM and EV calculate the same value for the same property?
2. If their calculated values differ, which inputs or calculation components differ?

First compare final values. Then investigate the ingredients behind calculated-value differences. Compare calculated and generalized values separately.

Start with **deli stavb**, not whole buildings. Parcels come later because their parts must first be aggregated independently on each side.

The full requirements are in [5757.md](5757.md). The broader development sequence is in [development-roadmap.md](development-roadmap.md).

## First pilot: inspect one comparable building part

Build a small, read-only SQL query or Python script for:

- One presečni datum.
- One model.
- One del stavbe.
- Corresponding model versions on the two sides.

Its purpose is to prove that we can retrieve two records that actually belong together. We do not need permanent comparison tables, Lift screens or a complete EV translation layer yet.

### What it retrieves

| Information | ISAM | EV |
|---|---|---|
| Property identity | `del_stavbe_id` | `dst_sid` |
| Calculated value | `vrednost_izr` | `vrednost` |
| Generalized value | `vrednost_zaokrozena` | `posplosena_vrednost` |
| Context | Cutoff date, model and version | Evidence of corresponding date, model and version |
| Problems | Missing result or calculation error | Missing result or calculation error |
| Source evidence | IDs of the records used | IDs of the records used |

On the ISAM side, follow the prepared building part in `pripis_enote_deli_stavb` through the selected date/model configuration in `pripis_vm_x_pd` to its result in `pripis_vmxpd_x_enote`. Resolve the date through `pripis_presecni_datum` and the model/version through `md_verzije_modeli`.

On the EV side, start by inspecting `ev_del_stavbe_enota` for the same `dst_sid`. Establish which source or history records represent the required cutoff date; do not assume a current EV row represents a historical date.

### What we must establish

Matching the property ID alone is insufficient. We must establish:

- Both records refer to the same building part.
- Both represent the required cutoff date.
- Both use the same model and corresponding valuation-rule versions.
- Each side has an unambiguous result, or its missing/error/duplicate condition is reported.

EV and ISAM version identifiers must not be assumed equal or equivalent. Their correspondence still needs evidence. Earlier inspection also found that the inspected EV building-part history lacked `id_model_ver`, so historical version selection needs particular attention.

### Expected runnable output

```text
Del stavbe: …
Presečni datum: …
Model: …
ISAM source IDs: …
EV source IDs: …
ISAM version: …     EV version: …
Comparable: YES / NOT YET PROVEN
Reason: …

ISAM calculated: …   EV calculated: …
ISAM generalized: …  EV generalized: …
Source errors or missing data: …
```

If comparability is unproven, show the available source values and explain what evidence is missing. Do not label the pair equal or different as a valid comparison yet. Do not replace missing values with zero or silently choose between duplicate candidates.

**The pilot is successful when we can explain why this pair is comparable—or identify precisely what prevents us from proving it.** A comparable pair is required before proceeding to a real final-value comparison.

## Extend it in small runnable steps

### 1. Calculate the differences for the validated unit

Add two independent differences:

```text
delta_izr = ISAM.vrednost_izr − EV.vrednost
delta_posplosena = ISAM.vrednost_zaokrozena − EV.posplosena_vrednost
```

Keep calculated and generalized outcomes separate. Preserve missing values and source errors. Exercise equal, different, missing, failed and duplicate cases with controlled examples as needed.

This teaches us the comparison logic without introducing persistence or a UI.

### 2. Run the same logic for a small explicit list

Keep the date and model fixed and expand to a bounded list of building-part IDs. Preserve records found on only one side.

Inspect the resulting counts, missing results, errors, duplicates and real differences. Filter source queries early and inspect query plans before increasing volume.

This teaches us how the real data behaves beyond one successful example.

### 3. Explain one calculated-value difference

Choose a pair with valid calculated values on both sides and `abs(delta_izr) > tolerance`.

Decode ISAM's stored variables and factors using the correct model-version key lists. Inspect the corresponding EV intermediate data and translate a small number of fields whose meaning can be verified. Show the original EV field and conversion rule beside each translated value.

This teaches us what the translation layer actually needs to contain. A generalized-only difference does not trigger this intermediate comparison by default.

## What comes after the pilot

Once the source selection and small comparison work, save comparison results in new Lift tables, display them, and add the workflow/SFC launch action. Expand supported building-part models incrementally, then implement parcel aggregation and parcel-specific intermediate matching.

The decimal-storage change remains a prerequisite for trustworthy persisted calculated values. It is tracked separately in [decimal-migration-runbook.md](decimal-migration-runbook.md); changing the column type does not recover decimals already lost in old results.

## Starting point when returning to this plan

Build the **one-unit source inspector** first. Keep its date, model and building-part ID configurable. Use read-only database exploration and record the evidence for date and version selection before trusting a comparison.
