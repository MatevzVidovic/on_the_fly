# FMP watermark regression reproduction

Run from `/Users/matevzvidovic/on_the_fly`:

```bash
php /Users/matevzvidovic/fmp/vendor/bin/phpunit \
  --no-configuration --no-progress --do-not-cache-result \
  --bootstrap /Users/matevzvidovic/fmp/vendor/autoload.php \
  KN_deltas_reason/reconciliation/diagnostics/WatermarkRoundTripTest.php
```

**Do not substitute FMP's normal test bootstrap.** It reloads test databases. This command loads only Composer autoloading and does not boot Laravel or run integrations.

The test reads `reconciliation/.env` for `STAG_*` credentials. Its sole database operation is a parameterized `SELECT CAST(? AS timestamp without time zone)::text` in a read-only transaction, rolled back afterward. It creates no tables and writes no data. The cast models the known metadata column type; it does not exercise FMP's metadata UPDATE or ORM hydration end-to-end.

The real `ProcessSqlDeltaIntegrationFacadeService::handle()` is executed with a UTC PHP default timezone. Metadata fetches, Temporal heartbeats and logging are mocked. The test captures its calculated `min_date` at the existing initialization log and deliberately stops before any Oracle query, target write or watermark update. No copied cutoff implementation is tested.

Observed on October 1, 2026: **3 tests, 7 assertions, 1 failure**. Exit status 1 is intentional: the assertion demands preservation of the original instant.

| Input to real FMP delta service | Result |
| --- | --- |
| PostgreSQL cast of `2026-08-05 12:26:56+02:00` → `2026-08-05 12:26:56` | FAIL: cutoff `12:26:56+00:00`, **+7200 seconds** |
| Offset retained: `2026-08-05 12:26:56+02:00` | PASS |
| Converted to UTC before storage: `2026-08-05 10:26:56` | PASS |

Local PHP 8.5 also reports dependency deprecations; these are separate from the assertion failure.

This proves the local FMP cutoff code shifts a timezone-less Ljubljana watermark when interpreted by a UTC worker. It does not establish historical deployment versions, historical runtime timezone, or every step of metadata persistence. The independently collected historical audit evidence is in `../AUDIT_FINDINGS.md`. No application fix has been applied; choosing a storage/timezone fix requires considering existing watermarks and other integrations.
