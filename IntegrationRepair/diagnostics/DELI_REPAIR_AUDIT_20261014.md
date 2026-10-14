# Deli repair audit — 14 October 2026

Read-only checks found no payload or metadata error in the repaired rows. The count increase comes from the current Oracle population moving beyond a fixed cutoff, while LIFT retains its older versions. No target or source data was changed during this audit.

## Why 11 became 25

The cutoff stayed `2026-10-14 13:57:49` in source Ljubljana wall time. Preparation times below are converted from the saved UTC creation timestamps.

| Observation | Source-local time | Oracle count | LIFT count | Planned inserts | Signed estimate |
| --- | --- | ---: | ---: | ---: | ---: |
| First prepare | 14:09:03 | 2,739,514 | 2,739,348 | 177 | 11 |
| Second prepare | 14:23:22 | 2,739,500 | 2,739,525 | 0 | 25 |

LIFT increased by exactly 177, as planned. Oracle decreased by 14. Therefore the estimate increased by 14 without any unexpected LIFT inserts.

The sorted membership audit identified 14 existing Oracle keys with change timestamps between the prepares, all after the cutoff:

| Current Oracle change time | Keys |
| --- | ---: |
| 14:17:44 | 1 |
| 14:17:54 | 2 |
| 14:18:25 | 1 |
| 14:19:50 | 10 |

None of these keys belongs to the 7,664 repaired keys. Their older LIFT versions remain within the cutoff, while their current Oracle versions are outside it. These records still exist in Oracle; the metric does not establish that they should be deleted.

During the audit, three more Oracle records had moved beyond the cutoff at 14:25–14:28. The current scoped comparison therefore found 28 LIFT-only keys: 17 still present in unbounded Oracle with newer dates, plus 11 absent from the unbounded source query. Those same 11 absent-source keys were already present in the October 7 comparison. There were zero source-only keys.

An independent native Oracle `COUNT(*)` and the application's streamed count both returned **2,739,497** in a single read-only Oracle snapshot. This rules out a paging/counting discrepancy for that check.

The original full source inventories/SCNs were not saved. The 14-key timing reconstruction uses the current records and saved run totals, rather than replaying the two original snapshots.

## Transferred values

All **7,664** repaired records were fetched again from Oracle; all still had their prepared change date. The audit compared all **26 mapped fields** using exact source number text and PostgreSQL casts to the actual destination types, independently of `map_row`.

- **Zero mapped-field mismatches**, including timestamps and numeric values.
- Zero source-NULL/target-non-NULL differences in these repaired records.
- All **7,487 update UUIDs** match their pre-repair UUIDs in the October 7 target snapshot.
- All **177 insert UUIDs** are version 1, matching the agreed FMP insertion behavior.
- All repaired row timestamps equal the saved first apply time; all row-user fields equal the configured NIL identity.
- Two hundred rows from the latest normal integration cohort also matched their source payloads and timestamp representation.

The repaired writer identity differs from that latest normal integration cohort: repair uses NIL, while that integration used its initiating user's UUID. This is the tool's agreed system-user policy, not a type or conversion discrepancy. Both cohorts set creation/update timestamps together, in the same representation.

## Separate pre-existing payload discrepancy

A further random sample of 200 untouched normal-integration rows found one same-date payload mismatch, confirmed independently:

| Field | LIFT | Oracle |
| --- | --- | --- |
| Integration key | 746811 | 746811 |
| `datum_sys` | 2024-11-15 09:41:48 | 2024-11-15 09:41:48 |
| `postopek_id_do` | NULL | 101681619 |

This key was not repaired. Its LIFT creation timestamp is `2024-11-25 11:53:09.372273` and its update timestamp is NULL. This confirms a limitation of the agreed key/date-only criterion: unchanged dates can hide pre-existing payload differences. It is not evidence that the repair introduced a difference, and this audit did not change that policy.

## Evidence

- [Full payload, UUID, and membership audit](audit_deli_repair.json).
- [Independent SQL-versus-streamed count](check_deli_scoped_count.json).
- [Additional control sample](deli_payload_audit_20261014.json).
- [Saved repair progress](../kn-medium.sqlite), run `658cb459-9556-4f87-96cb-68b4d85c7f5f`.

`expected_needed_deletions` is a scoped count-gap metric, not a confirmed deletion count. A positive value can include ordinary Oracle records awaiting a later delta because their change times have passed the old cutoff.
