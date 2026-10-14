-- Run once against the STAGING DATA database before preparing the repair.
-- Copy one real row, changing its UUID, integration key, and change date.
BEGIN;

INSERT INTO ev_pe_parc_h
SELECT (jsonb_populate_record(NULL::ev_pe_parc_h,
    to_jsonb(template) || jsonb_build_object(
        'id', extra.id,
        'jn_pe_parc_pk', extra.key,
        'date_change', TIMESTAMP '2000-01-01 00:00:00'
    ))).*
FROM (SELECT * FROM ev_pe_parc_h LIMIT 1) AS template
CROSS JOIN (VALUES
    ('00000000-0000-4000-8000-000000000001', '__repair_test_extra_1'),
    ('00000000-0000-4000-8000-000000000002', '__repair_test_extra_2'),
    ('00000000-0000-4000-8000-000000000003', '__repair_test_extra_3')
) AS extra(id, key)
RETURNING id, jn_pe_parc_pk, date_change;

COMMIT;

-- Run this SELECT again after applying the repair: it should return no rows.
SELECT id, jn_pe_parc_pk, date_change
FROM ev_pe_parc_h
WHERE jn_pe_parc_pk IN (
    '__repair_test_extra_1', '__repair_test_extra_2', '__repair_test_extra_3'
);
