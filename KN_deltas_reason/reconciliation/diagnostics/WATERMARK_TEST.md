# FMP watermark regression reproduction

## Smallest developer-facing reproduction (offline)

`WatermarkTimezoneTest.php` is one short test with one assertion. It uses a fixture for the stored timezone-less watermark and the exact parsing/formatting expression from FMP's delta service, plus FMP's real format constant. It does not call the full service: it is an explanatory reproduction, so a later service fix must also be checked with the actual-service test below.

```bash
php /Users/matevzvidovic/fmp/vendor/bin/phpunit \
  --no-configuration --no-progress --do-not-cache-result \
  --bootstrap /Users/matevzvidovic/fmp/vendor/autoload.php \
  KN_deltas_reason/reconciliation/diagnostics/WatermarkTimezoneTest.php
```

Executed October 6: one assertion fails, showing source `14:00+02:00` becoming cutoff `14:00+00:00` (16:00 Ljubljana).

## Actual-service test (also offline)

The actual-service test now also prints a copyable Oracle query built by FMP's real `OracleSqlManagerService::wrapFilters()` / `wrapCount()`, substituting the captured cutoff for the bind parameter. Run only `--filter testNaivePostgresWatermarkMustPreserveTheSourceInstant` to print the failing case alone. Its expected assertion failure happens after SQL is printed.

`oracle-watermark-check.sql` contains that generated query formatted for copying, plus a display query for the October 6 watermark. Run it on KN Oracle: the synthetic row at 13:00 Ljubljana is excluded by the FMP cutoff and included by the correct cutoff. These queries use only DUAL. They verify Oracle's comparison semantics, not historical worker configuration or current missing-key counts.

Run from `/Users/matevzvidovic/on_the_fly`:

```bash
php /Users/matevzvidovic/fmp/vendor/bin/phpunit \
  --no-configuration --no-progress --do-not-cache-result \
  --bootstrap /Users/matevzvidovic/fmp/vendor/autoload.php \
  KN_deltas_reason/reconciliation/diagnostics/WatermarkRoundTripTest.php
```

**Do not substitute FMP's normal test bootstrap.** It reloads test databases. This command loads only Composer autoloading and does not boot Laravel or run integrations.

Neither test connects to a database or reads `.env`. The actual-service test now uses a fixture established by the earlier PostgreSQL read-only cast probe. Metadata UPDATE and ORM hydration are not exercised end-to-end.

The real `ProcessSqlDeltaIntegrationFacadeService::handle()` is executed with a UTC PHP default timezone. Metadata fetches, Temporal heartbeats and logging are mocked. The test captures its calculated `min_date` at the existing initialization log and deliberately stops before any Oracle query, target write or watermark update. No copied cutoff implementation is tested.

Re-run offline on October 6, 2026: **3 tests, 6 assertions, 1 failure**. Exit status 1 is intentional: the assertion demands preservation of the original instant.

| Input to real FMP delta service | Result |
| --- | --- |
| Stored-value fixture `2026-08-05 12:26:56` | FAIL: cutoff `12:26:56+00:00`, **+7200 seconds** |
| Offset retained: `2026-08-05 12:26:56+02:00` | PASS |
| Converted to UTC before storage: `2026-08-05 10:26:56` | PASS |

Local PHP 8.5 also reports dependency deprecations; these are separate from the assertion failure.

This proves the local FMP cutoff code shifts a timezone-less Ljubljana watermark when interpreted by a UTC worker. It does not establish historical deployment versions, historical runtime timezone, or every step of metadata persistence. The independently collected historical audit evidence is in `../AUDIT_FINDINGS.md`. No application fix has been applied; choosing a storage/timezone fix requires considering existing watermarks and other integrations.
