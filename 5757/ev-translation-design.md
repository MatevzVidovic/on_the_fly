# EV → ISAM translation, explained simply

Imagine two cooks made the same cake. The cakes have different prices. We want to compare their ingredients to understand the difference.

But one cook writes **“0.8 kilograms of flour”**, and the other writes **“800 grams of flour.”** Comparing those numbers directly would tell us they differ—even though they mean the same thing.

**Our translator makes both ingredient lists speak the same language. It does not recalculate EV’s property value.**

## 1. Turn EV data into a common worksheet

For each ingredient, produce a little record:

| Question | Example answer |
|---|---|
| Which property and date? | Parcel 42, selected cutoff date |
| Which model and corresponding versions? | The versions we have confirmed belong together |
| Which part, if relevant? | A part identified by shared business attributes |
| Which ingredient? | Area, measured in square metres |
| Which group? | Variable (`SPREMENLJIVKA`) |
| What value? | 8,000 |
| Where did it come from? | EV field `example_area_ha`, original value 0.8 |
| What did we do to it? | Multiply hectares by 10,000 |

The field name and area example above are invented to explain the design, not an approved EV mapping.

**“Canonical ISAM structure” means this agreed worksheet: the same names, meanings and units that we use to compare with ISAM.** It does not mean copying EV into ISAM’s calculation tables.

## 2. Build a small dictionary of simple rules

A proposed Lift table, `pripis_primerjava_preslikave`, says:

> For this model/version, read this EV field, apply this conversion, and call the result this ISAM ingredient.

For example:

```text
EV: example_area_ha = 0.8
Rule: hectares × 10,000 → square metres
Common ingredient: area_m2 = 8,000
```

Simple renaming and unit conversions fit here. A missing value stays missing unless an agreed business rule says otherwise. **Missing is not automatically zero.**

## 3. Write SQL recipes for the complicated rules

Some translations need more than renaming:

- Two EV fields might need adding to form one ISAM ingredient.
- One EV record might contain enough information to produce several ISAM ingredients.
- Different parcel divisions might need regrouping into comparable business groups.

Put those recipes in versioned SQL files. The dictionary identifies which recipe applies. We must not invent a split when EV lacks the information needed to make it.

## 4. Compare the worksheets and save the evidence

```text
ISAM ingredients → put into the common worksheet ─┐
                                                ├→ compare → save detail rows
EV ingredients → dictionary / SQL recipes ───────┘
```

A proposed table, `pripis_primerjava_vmesni`, stores each ingredient comparison, linked to its final-value comparison:

```text
Ingredient: area_m2
ISAM:       8,000
EV:         8,000 after translation
Outcome:    equal
Evidence:   original EV field/value + rule used
```

This work runs only for eligible calculated-value differences: both sides have usable values and the absolute difference exceeds the configured tolerance.

## 5. Say “we cannot tell” when necessary

If parcel parts cannot be matched uniquely, show `NEENOLICNA_STRUKTURA`. Keep the parcel-total comparison and show aggregate evidence where meaningful; do not invent individual pairings.

If a field has no translation rule, show it as untranslated instead of hiding it.

There is also an ISAM prerequisite: its saved intermediate values are currently ordered lists. We need the correct corresponding key list to know what each value means. The small inspected sample could not resolve the referenced model record. **We must fix or recover that context before translating/comparing those records.**

## What we actually need to create

1. **A common worksheet format** for ingredients from both sides.
2. **A simple mapping table** plus **SQL recipes** for model/version-specific translations.
3. **Comparison code and saved detail rows**, including the original evidence and visible problems.

First prove this works for one model and one reliably matched property. Then extend it. Actual mappings, version correspondence and parcel-grouping rules still need confirmation.

Sources: [5757, sections 3–5](5757.md), [observed intermediate data](reference/db-translation-shapes.json), [ISAM saved-list sample](reference/db-isam-intermediate-samples.json), and [the existing ISAM writer](../symlinks/lift-temporal-python/src/packages/_gurs/modeling/zapis_md_trans.py). Table names above are proposals.
