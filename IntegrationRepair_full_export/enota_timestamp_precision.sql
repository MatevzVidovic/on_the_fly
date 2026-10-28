-- Run between comparisons/integrations. This does not recover lost fractions.
-- Widen precision only; retain timestamp WITHOUT time zone and UTC semantics.
-- PostgreSQL 15.7: no heap rewrite for this precision widening; small catalog WAL.
-- FMP date-time already maps to timestamp; no FMP field-definition change needed.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE public.ev_parc_enota_h_2025_danes
    ALTER COLUMN date_change_utc TYPE timestamp without time zone;
COMMIT;
