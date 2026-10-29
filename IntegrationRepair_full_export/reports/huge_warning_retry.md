# Huge KN warning retry — read-only findings and proposed repairs

Run: `eb6eef3a-e08f-4e0f-b105-94625718e188`. Preview fetched all 18 warning keys afresh from Oracle and checked candidates with PostGIS; no production rows were written.

## Verification finished

The timing file records successful verification completion: 29,745,477 eligible LIFT rows scanned in 405.897792 seconds. The current verifier prints final difference counts only to its terminal, not a result file. Therefore its timing record does not establish its final insert/update/removal counts. See `kn_huge_verify_completion.json`.

## Warning analysis

There are 17 geometry parse warnings and one source-change-time warning. Of these 18 keys, 17 are currently absent in LIFT and one geometry key already has a target row. They therefore do not independently explain the entire 72-row total-count gap. If no other data changes, inserting the 17 currently absent warning keys would reduce that total gap to 55; the remaining keys require separate investigation/catch-up.

The geometry rows contain concatenated polygon WKT rather than one valid WKT object. Merely wrapping the polygons as a MULTIPOLYGON makes them parseable, but the result has overlapping components and is topologically invalid. Each component in the examined cases is individually valid.

## Proposed transformation

For these concatenated-POLYGON cases only: package the original rings into a MULTIPOLYGON, apply `ST_UnaryUnion`, then `ST_Multi`. No snapping, coordinate-grid rounding, buffering or broad `ST_MakeValid` fallback is used. Serialization uses `ST_AsText(...,17)` before the existing target mapper imports the geometry. Union dissolves overlaps/internal boundaries and may introduce intersection vertices/reorder rings. It preserves the geometric union of the valid components, not their summed area or exact vertex sequence. It is a proposed interpretation of the source defect, not proof of intended cadastral boundaries or holes. [PostGIS documentation](https://www.postgis.net/docs/ST_UnaryUnion.html).

All 17 proposed unions passed PostGIS validity; the one source-change row has valid freshly fetched geometry without transformation. The table below compares summed component area (overlaps counted twice) with union area (overlaps counted once), in EPSG:3794 square metres. These are geometric diagnostics; no business area attributes are automatically recalculated.

| Key | Already in LIFT? | Transformation | Component area sum | Proposed union area |
|---|:---:|---|---:|---:|
| 10017683842 | yes | polygon union | 251.7947259025376 | 228.18041545270444 |
| 10027313954 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10027332664 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10027338141 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10027381297 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10027528068 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10027576330 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10027603371 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10027769816 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10029866017 | no | none; fresh source row | — | — |
| 10029886756 | no | polygon union | 170.06997489543298 | 103.10997119252313 |
| 10030073862 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10030090521 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10030133068 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10030363740 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10030496929 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10030616174 | no | polygon union | 170.0699748954329 | 103.10997119252319 |
| 10030765118 | no | polygon union | 170.0699748954329 | 103.10997119252319 |

## Script

`retry_huge_warnings.py` is standalone and does not modify the completed run or its original warnings. It fetches the warned keys afresh each time, uses the existing payload mapper/actor, checks geometry validity and observes the Barman pause guard. The fresh fetch deliberately does not require the original prepared change timestamp, since one warning was caused by that changing. Existing newer target dates are still protected by the normal upsert rules.

Preview (remote read-only):

```bash
.venv/bin/python retry_huge_warnings.py
```

Write these specific rows after reviewing the proposal:

```bash
.venv/bin/python retry_huge_warnings.py --apply
```

Each valid row is committed independently; failures can leave earlier rows committed, and the script can be rerun. Other write errors stop execution. The script does not run materialized-view refreshes or change the normal integration watermark. Preview and apply have separate JSON reports with per-key status and original/proposed WKT, source/prepared/target dates and area diagnostics. The original SQLite warning history remains unchanged.

Recount afterward:

```bash
bash run_utc_counts.sh --group kn --include-huge \
  --table kn_nep_ostalo_dejanske_rabe_parcel_h \
  --output reports/kn_huge_after_warning_retry_counts.json
```

Evidence: `huge_warning_retry_preview.json`, `kn_huge_after_apply_counts.json`. The original single-row geometry investigation also compared legacy LOB fetching and optimized fetching byte-for-byte; its malformed WKT was identical.
