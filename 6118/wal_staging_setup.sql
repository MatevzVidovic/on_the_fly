-- Staging only, run with psql. Writes only to the new wal6118_bench schema.
-- Source: public.ev_posebna_enota_h. Integration configuration is not changed.
-- Confirm at least 2 GiB real free disk space and a healthy Barman receiver first.
-- Hard bounds: source <=50,000 rows and <=128 MiB including indexes.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '20s';

DO $$
BEGIN
    IF pg_is_in_recovery() OR current_setting('wal_level') = 'minimal' THEN
        RAISE EXCEPTION 'Run on a staging primary with replica/logical WAL';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'wal6118_bench') THEN
        RAISE EXCEPTION 'wal6118_bench already exists; preserve/review previous results first';
    END IF;
    IF pg_total_relation_size('public.ev_posebna_enota_h') > 128 * 1024 * 1024
       OR (SELECT count(*) FROM
           (SELECT 1 FROM public.ev_posebna_enota_h LIMIT 50001) limited) > 50000 THEN
        RAISE EXCEPTION 'Source exceeds small-table test limits';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='ev_posebna_enota_h'
          AND column_name='date_change' AND data_type='timestamp without time zone'
    ) THEN
        RAISE EXCEPTION 'Expected Ljubljana-local timestamp without time zone';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_attribute
        WHERE attrelid='public.ev_posebna_enota_h'::regclass
          AND attname='id' AND atttypid='uuid'::regtype AND NOT attisdropped)
       OR NOT EXISTS (SELECT 1 FROM pg_index i JOIN pg_attribute a
           ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0]
           WHERE i.indrelid='public.ev_posebna_enota_h'::regclass
             AND i.indisunique AND i.indisvalid AND i.indnkeyatts=1
             AND a.attname='id') THEN
        RAISE EXCEPTION 'Batched comparison requires a unique indexed UUID id';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='ev_posebna_enota_h'
          AND column_name='date_change_utc' AND data_type<>'timestamp without time zone') THEN
        RAISE EXCEPTION 'An existing UTC column must also be timestamp without time zone';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='public.ev_posebna_enota_h'::regclass AND NOT tgisinternal)
       OR EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.ev_posebna_enota_h'::regclass AND contype='f')
       OR EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public.ev_posebna_enota_h'::regclass
                  AND attnum>0 AND NOT attisdropped AND (attgenerated<>'' OR attidentity<>'')) THEN
        RAISE EXCEPTION 'Source has triggers/FKs/generated/identity columns: assess clone fidelity before testing';
    END IF;
END $$;

CREATE SCHEMA wal6118_bench;
CREATE TABLE wal6118_bench.baseline (LIKE public.ev_posebna_enota_h INCLUDING ALL);
ALTER TABLE wal6118_bench.baseline ADD COLUMN IF NOT EXISTS date_change_utc timestamp without time zone;

-- Exclude UTC from the initial insert, so already-filled source UTC values
-- cannot turn the comparison into a no-op or require a reset UPDATE.
DO $$
DECLARE cols text;
BEGIN
    SELECT string_agg(quote_ident(attname), ', ' ORDER BY attnum) INTO cols
    FROM pg_attribute WHERE attrelid='public.ev_posebna_enota_h'::regclass
      AND attnum>0 AND NOT attisdropped AND attname<>'date_change_utc';
    EXECUTE format('INSERT INTO wal6118_bench.baseline (%s) SELECT %s FROM public.ev_posebna_enota_h', cols, cols);
    IF NOT EXISTS (SELECT 1 FROM wal6118_bench.baseline WHERE date_change IS NOT NULL) THEN
        RAISE EXCEPTION 'No eligible rows: cannot benchmark a no-op';
    END IF;
    IF EXISTS (SELECT 1 FROM wal6118_bench.baseline WHERE date_change_utc IS NOT NULL) THEN
        RAISE EXCEPTION 'Expected null UTC values in the starting snapshot';
    END IF;
END $$;

CREATE TABLE wal6118_bench.batched (LIKE wal6118_bench.baseline INCLUDING ALL);
INSERT INTO wal6118_bench.batched SELECT * FROM wal6118_bench.baseline;
CREATE TABLE wal6118_bench.logging_toggle (LIKE wal6118_bench.baseline INCLUDING ALL);
INSERT INTO wal6118_bench.logging_toggle SELECT * FROM wal6118_bench.baseline;
ANALYZE wal6118_bench.baseline;
ANALYZE wal6118_bench.batched;
ANALYZE wal6118_bench.logging_toggle;
COMMIT;

SELECT current_database(), version(),
       (SELECT count(*) FROM wal6118_bench.baseline) AS copied_rows,
       pg_size_pretty(pg_total_relation_size('wal6118_bench.baseline')) AS clone_size;
