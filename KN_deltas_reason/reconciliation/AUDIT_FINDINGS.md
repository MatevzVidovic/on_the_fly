# Narrow historical audit checks — 2026-10-01

Read-only investigation of production `lift_audit.public.events_2026`, scoped to integration `bfe62b52-9aaf-11ef-9c54-0242ac120008`. Staging audit partitions were empty. Production timestamps below are UTC unless explicitly identified as source/Ljubljana time. No integration was run or configuration changed.

Queries used the indexed `created_datetime` bounds (one to five minutes), an eight-second statement timeout, and integration/entity filters. The production partition is approximately 128 GB; do not search its JSON payload without timestamp bounds.

## Missing keys: strong evidence of shifted lower bounds

| Prior successful run | Audited outgoing watermark | Hypothetical next bound if timezone offset is lost and value parsed as UTC, expressed in Ljubljana | Missing source timestamp block | First subsequently audited source timestamp |
| --- | --- | --- | --- | --- |
| May 25 09:08:29–09:08:49 UTC | May 25 11:04:56 **+02:00** | May 25 **13:04:56** | 101 missing keys, 11:40:23–12:51:25 | May 30 run: May 25 **13:08:56** |
| August 5 10:36:25–10:37:10 UTC | August 5 12:26:56 **+02:00** | August 5 **14:26:56** | 16 missing keys, 12:38:01–14:25:13 | August 8 run: August 5 **14:42:17** |

These independently observed boundaries closely match the conditional timezone bug identified in code: an offset-bearing watermark is stored in a timezone-less field, then read as a naive `DateTime` using UTC. The audit also explicitly records UTC for run start/end DateTime objects. This is strong corroboration, not a captured historical Oracle bind parameter or proof of the exact deployed code.

The August 8 run finished `PROCESSED` at 02:50:21.006 UTC. The May 30 run repeatedly failed almost immediately with `SQLSTATE[42809]: cannot change materialized view "kn_nep_deli_stavb_a"`. Thus May 30 save events alone must not be treated as committed writes. The first attempted row nevertheless already follows the suspected excluded interval.

The June 6 run's first observed source timestamp was June 3 06:28:56; the remaining three missing keys have June 2 16:46:04. We have not established their prior watermark or proved the same mechanism for them.

## Stale dates: a record was fetched with correct dates

On June 20, key **463** has both `attribute_table_data.save` (02:50:15.134 UTC) and `.save.after` (02:50:15.142 UTC) audit events with:

- `datum_sys = 2026-06-15 14:31:41 +02:00`
- `datum_do = 2026-06-15 14:31:41 +02:00`
- `postopek_id_do = 103021619`

Successor key **2875323** follows at 02:50:15.148, with the same change/start date and open validity ending in 2100. The integration finished **PROCESSED** at 02:50:49.873 UTC.

Today's captured target key 463 instead has `datum_sys = 2022-06-01 13:25:59`, `datum_do = 2100-01-01`, and `updated_at = 2026-07-14 11:25:39.267436`.

Therefore, simple failure to fetch this key through pagination is ruled out for that run. The correct values reached the audited save path in a successful run. Audit payloads are not an independently read post-commit database snapshot: mapping/persistence behavior or a later overwrite must still be distinguished. The July 14 common update signature remains important; this does not identify its writer.

No matching integration events were found in the narrowly checked July 14 11:25–11:26 UTC window. This is not evidence that no operation occurred: audit suppression, a different writer, or different timestamp semantics remain possible.

## What this answers

Old OFFSET pagination remains a possible contributor, but it does not explain all evidence by itself. Two distinct leads now have stronger support:

1. A two-hour effective cutoff shift for 117 of the 120 missing keys.
2. Correct source dates reaching a successful audited save path but not surviving in today's target, demonstrated for key 463.

The missing May/August source timestamps occur **after** the preceding runs finished in Ljubljana time, rather than within their execution intervals. Source timestamps are not proof of physical insert/commit times, however. LIFT audit records target operations and cannot establish when Oracle committed or exposed a source row.

Next narrow checks: establish June 2's preceding watermark; identify July 14 writer and historical field mappings; recover actual historical SQL bind parameters if available. Do not reset watermarks or reimport as a substitute for establishing cause.
