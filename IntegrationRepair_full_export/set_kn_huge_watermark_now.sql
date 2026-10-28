-- Run on the PRODUCTION SYSTEM metadata database (fmp), not the data database.
-- Normal integration and backfill/copy must be stopped before this cutover.
-- Keep the normal integration stopped until full repair/export/compare/apply finishes.
BEGIN;

-- Record the previous mark before changing it.
SELECT id, last_changed_datetime AS previous_utc_watermark
FROM attribute_table_integrations
WHERE id = 'e0c4ee44-f34c-11ef-9c8f-02420a0001ec';

UPDATE attribute_table_integrations
SET last_changed_datetime = CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
WHERE id = 'e0c4ee44-f34c-11ef-9c8f-02420a0001ec'
RETURNING id, last_changed_datetime AS new_utc_watermark;

COMMIT;
