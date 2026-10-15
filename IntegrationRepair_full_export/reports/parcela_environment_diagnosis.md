# EV parcela: the repeated diff is an environment switch

15 October 2026. All investigation was read-only. No apply, database mutation or environment-file edit was performed.

## Conclusion

The first successful EV parcela repair remains present on **staging**. The later count checks and fresh prepare point to the **production endpoint**. The same business difference appears because production has not received that parcela repair, not because the staging repair disappeared.

Endpoint classification was established by comparing host values with the existing `STAG_HOST` / `PROD_HOST` aliases in `KN_deltas_reason/reconciliation/.env`. No credentials or endpoint addresses are reproduced here. Both endpoints use the database name `fmp_data_gurs`, which alone does not distinguish them.

## Evidence

| Check | Staging endpoint | Current repair endpoint (production) |
| --- | ---: | ---: |
| Old repair keys examined | 28,621 | 28,621 |
| Keys present | 28,621 | 7,001 |
| Keys missing | 0 | 21,620 |
| Keys with repaired change date | 28,621 | 0 |
| Present keys with older change date | 0 | 7,001 |
| Keys with saved mvidovic actor in both metadata fields | 28,621 | 0 |

The new prepared run `007bbd84-c118-41b5-86f1-34e6a897abb1` and successful staging run `03ff3376-0110-4c42-a617-07662100d1bf` contain **identical key/date pairs** in their 28,621-entry upsert lists. There are no added keys, dropped keys or changed source dates between those lists.

The repair folder's `.env` modification time is `2026-10-15 09:50:37` Europe/Ljubljana. The original full post-apply audit was recorded at `09:17:22`, before that modification. Modification time alone does not prove which setting changed, but the endpoint comparison and live two-endpoint checks independently establish the current difference.

## Hypotheses resolved

- A restore/reload of staging: not supported; all previous repairs are still present there.
- A different endpoint: confirmed. The current repair `.env` host equals the configured production host; the older `IntegrationRepair/.env` host equals staging.
- A later normal integration undoing the repair: not needed to explain these observations; no such reversal was found on staging.
- Original apply failing to commit: contradicted by the independent successful audit and the current staging check.

No server-side commit-time history was available (`track_commit_timestamp=off`), so the investigation does not reconstruct every later operation. It establishes that the reported discrepancy was a comparison across environments.

## Why the local state was confusing

SQLite stores integration UUID, target table, cutoff, prepared/applied status and row progress. It currently does **not bind a run to a PostgreSQL endpoint**. The same integration UUID/table/database names occur on staging and production. Reusing a store after changing `.env` therefore retains the earlier environment's applied runs alongside new runs.

The old applied run should stay applied: it correctly records staging work. Running that old apply UUID again will return without writing. The fresh run `007bbd84-c118-41b5-86f1-34e6a897abb1` is the plan prepared against the current production endpoint. It has not been applied by this investigation.

For future runs, separate store files by environment (for example `staging-ev-parcela.sqlite` and `production-ev-parcela.sqlite`) and record the endpoint with run metadata if environment protection is added. This report does not rename files, alter `.env`, or change production repair behavior.

## Correction to earlier reporting

The earlier descriptions calling the later count checks “staging” were inaccurate. `ev_counts.json` and `ev_counts_rerun.json` used the current production `.env`. The 10/12 and 11/12 matching-count summaries apply to that endpoint.

The later stavba/prostor value audit also used that endpoint; its field comparisons remain valid, but the environment label should be production. The original parcela post-apply audit belongs to staging.

## Reproduction and raw artifacts

- `.venv/bin/python diagnostics/trace_parcela_repair.py --sample`: minimal read-only two-key probe of the **currently configured** target. It returns nonzero when a previous repair date/key is missing there; that alone is not a regression unless the endpoint is the same.
- `diagnostics/parcela_repair_trace.json`: all 28,621 current-endpoint keys and old/new diff comparison.
- `diagnostics/parcela_repair_trace_sample.json`: one missing key and one older existing key on the current endpoint.
- `diagnostics/parcela_environment_comparison.json`: all 28,621 staging keys still present, repaired dates and repair metadata verified; endpoint-alias comparison.
- `diagnostics/ev_parcela_value_audit.json`: the original successful staging payload audit.
