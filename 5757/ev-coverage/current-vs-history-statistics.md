# Current tables versus history: EV models, dates and volumes

Checked 2026-10-15. This report combines **verified point lookups**, **bounded block samples**, **planner estimates**, and one exact aggregation over the small revision dictionary. These evidence levels must not be mixed. Large valuation tables were not counted or grouped in full.

## Two different meanings of current

**Oracle source current tables** (`EV.DEL_STAVBE_ENOTA`, `EV.PARC_ENOTA`) represent current stored valuations. Indexed checks found newer-generation rows matching open source history rows. **Staging current copies** (`ev_del_stavbe_enota`, `ev_parc_enota`) contain older versions in samples and planner statistics. Do not treat those copies as a verified current Oracle snapshot or assume they share one known cutoff date.

For a source current row, its revision date is when that record was written, not a common valuation cutoff for the whole table. Model market date is a third concept.

## Which source suits which comparison?

| Option | What it answers | Date handling | Main limitation |
|---|---|---|---|
| Oracle current valuation tables | How do the currently stored EV amounts compare? | Capture a consistent source snapshot and align property inputs; retain each row’s actual model ID | Different rows have different last-change dates; it is not automatically a January snapshot |
| Staging current copies | How do these imported amounts compare? | First establish the import snapshot and date semantics | Observed model generation differs from current Oracle; no validity intervals on these tables |
| Dated history (`_h` / Oracle `JN_*`) | What was recorded as valid at a chosen cutoff? | `valid_from <= cutoff < valid_to`, or an open end | Must handle missing intervals, duplicates, model IDs and source coverage; staging building history lacks required fields |

For the ticket’s **same presečni datum** requirement, dated history is the direct fit. Current data is still a valid alternative for an explicitly defined current-snapshot comparison. Choose the mode deliberately; do not select an active row merely because its model market date matches the desired cutoff.

## Verified current-versus-open-history examples

These are exact indexed point lookups for individual units, not global counts. [Full rows](active-vs-history-examples.json).

| Type | Model | Example unit | Oracle active EV version | Open-history EV version |
|---|---|---|---|---|
| building | GAR | 28888343 | 1170 | 1170 |
| building | HIS | 28686586 | 1172 | 1172 |
| building | IND | 29765975 | 1173 | 1173 |
| building | INP | 29884004 | 1174 | 1174 |
| building | KDS | 28602100 | 1175 | 1175 |
| building | PPL | 28737054 | No row for this example | No row for this example |
| building | PPP | 28592902 | 1178 | 1178 |
| building | SDP | 29890117 | 1179 | 1179 |
| building | STA | 28482262 | 1180 | 1180 |
| building | TUR | 100000058998 | 1182 | 1182 |
| parcel | DRZ | 100000003802.DRZ | 1169 | 1169 |
| parcel | GOZ | 100000003802.GOZ | 1171 | 1171 |
| parcel | KME | 100000003802.KME | 1176 | 1176 |
| parcel | STZ | 100000003802.STZ | 1181 | 1181 |

The selected PPL example has neither an active row nor an open history row. That does not mean PPL is absent globally: this is a closed historical example. Rows inspected for other models agree on active/open version identity.

## How much data is on staging?

**Approximate row counts from planner metadata, analyzed 2026-10-04. Not counts of distinct properties.** Separate history tables can hold multiple revisions for one unit; summing them does not establish distinct-unit coverage.

| Staging table | Estimated rows |
|---|---:|
| `ev_del_stavbe_enota` | 1,914,127 |
| `ev_del_stavbe_enota_h_2020_2024` | 6,902,079 |
| `ev_del_stavbe_enota_h_2025_danes` | 4,877,667 |
| `ev_parc_enota` | 8,313,618 |
| `ev_parc_enota_h_2020` | 17,228,166 |
| `ev_parc_enota_h_2021` | 8,397,585 |
| `ev_parc_enota_h_2022` | 12,332,600 |
| `ev_parc_enota_h_2023` | 12,572,742 |
| `ev_parc_enota_h_2024` | 14,671,040 |
| `ev_parc_enota_h_2025_danes` | 25,544,474 |

## Models in the staging current copies

Percentages and row counts below are **estimates** from `pg_stats`, not exact live group counts. The observed version IDs map to source model definitions; they do not establish a common property cutoff.

| Table | EV version | Model / XML version | EV model date | Estimated share | Estimated rows |
|---|---:|---|---|---:|---:|
| `ev_del_stavbe_enota` | 1165 | KDS / 26 | 1.1.2019 | 35.03% | 670,455 |
| `ev_del_stavbe_enota` | 1149 | HIS / 161 | 1.1.2020 | 29.04% | 555,926 |
| `ev_del_stavbe_enota` | 1148 | STA / 150 | 1.1.2020 | 18.24% | 349,201 |
| `ev_del_stavbe_enota` | 1155 | GAR / 74 | 1.1.2020 | 10.07% | 192,753 |
| `ev_del_stavbe_enota` | 1153 | PPP / 185 | 1.1.2020 | 2.55% | 48,746 |
| `ev_del_stavbe_enota` | 1152 | PPL / 151 | 1.1.2020 | 1.88% | 35,986 |
| `ev_del_stavbe_enota` | 1150 | IND / 51 | 1.1.2020 | 1.72% | 32,859 |
| `ev_del_stavbe_enota` | 1154 | SDP / 18 | 1.1.2020 | 0.97% | 18,503 |
| `ev_del_stavbe_enota` | 1156 | TUR / 27 | 1.1.2020 | 0.18% | 3,445 |
| `ev_del_stavbe_enota` | 1151 | INP / 36 | 1.1.2020 | 0.17% | 3,190 |
| `ev_del_stavbe_enota` | NULL | Unspecified version (includes special/error cases) | — | 0.16% | 3,063 |
| `ev_parc_enota` | 1161 | KME / 81 | 1.1.2020 | 34.85% | 2,897,296 |
| `ev_parc_enota` | 1164 | STZ / 13 | 1.1.2020 | 23.57% | 1,959,520 |
| `ev_parc_enota` | 1162 | GOZ / 73 | 1.1.2020 | 20.17% | 1,676,580 |
| `ev_parc_enota` | 1163 | DRZ / 9 | 1.1.2020 | 10.32% | 857,965 |
| `ev_parc_enota` | NULL | Unspecified version (includes special/error cases) | — | 11.09% | 922,257 |

## Old and new model generations inside newer parcel history

Both generations occur in `ev_parc_enota_h_2025_danes`. Estimated shares refer to **history rows**, not distinct parcels or rows valid at any one date.

| EV version | Model / XML version | EV model date | Estimated share | Estimated rows |
|---:|---|---|---:|---:|
| 1176 | KME / 100 | 1.1.2025 | 29.66% | 7,576,491 |
| 1181 | STZ / 44 | 1.1.2025 | 23.15% | 5,912,694 |
| 1171 | GOZ / 96 | 1.1.2025 | 17.65% | 4,508,600 |
| 1169 | DRZ / 16 | 1.1.2025 | 9.47% | 2,419,062 |
| 1161 | KME / 81 | 1.1.2020 | 3.20% | 817,423 |
| 1164 | STZ / 13 | 1.1.2020 | 2.00% | 511,741 |
| 1162 | GOZ / 73 | 1.1.2020 | 1.96% | 501,523 |
| 1163 | DRZ / 9 | 1.1.2020 | 0.77% | 197,544 |
| NULL | Unspecified version (includes special/error cases) | — | 12.13% | 3,099,396 |

Building history does not have a local `id_model_ver` column, so an equivalent version-count breakdown cannot be read from that schema. Do not infer a version from the year in its table name.

## What dates actually appear?

**Exact revision-dictionary counts:** this is a small source table. A revision can affect many units or none of the valuation rows of interest, so these are not valuation counts. [Query and results](oracle-revision-calendar.json).

| Year | Revision records | First revision | Last revision |
|---|---:|---|---|
| 2020 | 234 | 2020-04-01 12:00:00 | 2020-12-31 04:00:01.303052 |
| 2021 | 333 | 2021-01-01 04:00:01.657344 | 2021-12-31 04:00:01.135782 |
| 2022 | 155 | 2022-01-01 14:00:01.859233 | 2022-12-27 00:00:00 |
| 2023 | 191 | 2023-04-13 13:21:29 | 2023-12-29 00:30:01 |
| 2024 | 268 | 2024-01-01 00:30:01 | 2024-12-31 00:30:01 |
| 2025 | 426 | 2025-01-01 00:30:00 | 2025-12-31 23:59:59.999000 |
| 2026 | 216 | 2026-01-01 23:59:59.999000 | 2026-10-14 23:59:59.999000 |

This source revision dictionary begins on **2020-04-01**, not 2020-01-01. Model date 2020-01-01 does not supply a January history interval. Exact indexed examples show older versions covering 2025-01-01 and newer versions covering 2026-01-01. The transition in the inspected examples is May 2025, not January. [Per-model examples at both cutoffs](README.md).

**Observed valuation-row dates, not global minima/maxima:**

- Oracle history samples include starts at 2020-04-01; parcel current samples include revision dates through 2026-10-12.
- Staging newer building history samples include starts from 2025-03-21 through 2026-02-15, and end dates through 2026-05-12. Those are bounds of this sample only.
- All 1164 rows in the older staging building-history sample have NULL start dates; the table also lacks model-version IDs. Oracle supplies those fields for inspected examples.
- Small samples from every staging parcel-year table 2020–2024 have dated rows and old version IDs. Unlike the older building copy, those sampled parcel rows retain start dates.
Validate individual interval uniqueness and ordering before an as-of run; no global interval-quality audit was performed.

[Initial observed samples](observed-coverage.json) · [Older parcel-year samples](staging-yearly-parcel-samples.json). Samples and planner statistics do not establish every rare model/date or exact population coverage.

## What to use for the next pilot

Keep both options explicit:

1. **Historical mode:** choose 2026-01-01, read dated history, then check actual version per row. For IND, the verified pair is ISAM 66 / EV 1173. For 2025-01-01, verified IND examples instead use ISAM 51 / EV 1150.
2. **Current mode:** read Oracle current values, align a current property snapshot and verify each actual model version. Do not substitute staging’s old current copies without establishing their snapshot.
3. Before full historical runs, repair/augment the staging building-history date/version fields or use source lookups for bounded pilots. Verify coverage and interval uniqueness at the chosen cutoff; selecting all rows in a year table is not an as-of selection.

## Reusable statistics and limits

- [Staging estimates by model and version, CSV](staging-estimated-counts.csv). Unlisted non-MCV values are not proven absent.
- [Oracle model count estimates, CSV](oracle-estimated-counts.csv). Histogram counts are estimated from saved statistics and can be stale; analysis dates are included.
- [Staging raw planner metadata](staging-catalogue-statistics.json).
- [Oracle raw frequency histograms](oracle-model-histograms.json).
- Exact global valuation counts by model/version/cutoff were **not** run. There is no version-leading index in the inspected source valuation indexes; an exhaustive grouping can scan millions of current rows or tens of millions of history rows. It belongs in an explicitly planned bounded/off-peak aggregation or in the comparison run itself, not an unbounded exploratory query.
- All live queries here were sequential read-only transactions ending in rollback, with timeouts. Large tables were accessed through metadata, bounded block samples or indexed unit lookups.
