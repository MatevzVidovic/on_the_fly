-- Run on STAGING before EACH experiment. Only the disposable copy is replaced.
CREATE SCHEMA IF NOT EXISTS simple_wal_lab;
DROP TABLE IF EXISTS simple_wal_lab.test_table;
CREATE TABLE simple_wal_lab.test_table
    (LIKE public.ev_posebna_enota_h INCLUDING INDEXES);
INSERT INTO simple_wal_lab.test_table SELECT * FROM public.ev_posebna_enota_h;
UPDATE simple_wal_lab.test_table SET date_change_utc = NULL
WHERE date_change_utc IS NOT NULL;
VACUUM ANALYZE simple_wal_lab.test_table;
