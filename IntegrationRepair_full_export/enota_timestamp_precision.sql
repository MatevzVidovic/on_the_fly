-- Run between comparisons/integrations. This does not recover lost fractions.
-- Widen precision only; retain timestamp WITHOUT time zone and UTC semantics.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE public.ev_parc_enota_h_2025_danes
    ALTER COLUMN date_change_utc TYPE timestamp without time zone;
COMMIT;
