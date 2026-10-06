# Actual persistence round-trip test

`WatermarkPersistenceTest.php` uses an isolated local PostgreSQL database. It never reads `.env` or connects to staging/production. It reuses the existing actual-delta-service cutoff harness in `WatermarkRoundTripTest.php`.

Start the disposable database (the image is already installed on this computer):

```bash
docker run --detach --rm --name kn-watermark-test \
  -e POSTGRES_PASSWORD=local-test-only -e POSTGRES_USER=watermark_test \
  -e POSTGRES_DB=watermark_test -p 127.0.0.1:55439:5432 \
  dockerhub.flycom.si/postgres:15-3.4_1 postgres
docker exec kn-watermark-test pg_isready -U watermark_test -d watermark_test
```

Once ready, run from `/Users/matevzvidovic/on_the_fly`:

```bash
php /Users/matevzvidovic/fmp/vendor/bin/phpunit \
  --no-configuration --no-progress --do-not-cache-result \
  --bootstrap /Users/matevzvidovic/fmp/vendor/autoload.php \
  --filter testRealModelSaveReloadAndNextDeltaCutoff \
  KN_deltas_reason/reconciliation/diagnostics/WatermarkPersistenceTest.php
docker stop kn-watermark-test
```

The test runs FMP's actual maximum-date method, persistence manager, Eloquent model save/reload, delta `handle()` cutoff calculation, and Oracle filter builder. The temporary table has the same watermark type and is rolled back. User identity and unrelated delta services are mocked. It does not run the entire completion facade, event command/listeners, metadata repository joins or remote Oracle query. It uses the same outgoing format expression as delta `handle()`.

Measured October 6:

```text
Actual UPDATE binding: 2026-08-05 12:26:56.000000+02:00
Reloaded from PostgreSQL: 2026-08-05 12:26:56
Next FMP cutoff: 2026-08-05 12:26:56.000000+00:00
Actual Oracle filter: ... DATUM_SYS >= TO_TIMESTAMP_TZ(:last_sync_start, 'YYYY-MM-DD HH24:MI:SS.FF6TZH:TZM')
FAIL: shift=7200 seconds
```

One test, two assertions, one expected failure. PHP 8.5 also reports existing dependency deprecations. This establishes offset loss through FMP's actual persistence model and a shifted next cutoff with PHP configured as UTC. It does not establish the timezone of a historical deployed worker.

An additional read-only Oracle `DUAL` comparison was attempted, but the tunnel returned ORA-12541. You can independently verify the emitted bound in an Oracle console:

```sql
SELECT CASE WHEN
  TO_TIMESTAMP_TZ('2026-08-05 13:00:00.000000+02:00', 'YYYY-MM-DD HH24:MI:SS.FF6TZH:TZM') >=
  TO_TIMESTAMP_TZ('2026-08-05 12:26:56.000000+00:00', 'YYYY-MM-DD HH24:MI:SS.FF6TZH:TZM')
THEN 'INCLUDED' ELSE 'EXCLUDED' END AS result FROM dual;
```

Expected: EXCLUDED, despite 13:00 Ljubljana being later than the actual previous source watermark of 12:26:56 Ljubljana. Oracle compares the supplied instants; the incorrect instant has already appeared in FMP's cutoff parameter.
