-- Run on the LIFT data database (fmp_data_gurs), after checking the count.
-- It removes rows that the corrected KN/LIFT query will no longer return.
SELECT COUNT(*) AS rows_to_delete
FROM public.ev_del_stavbe_enota_h_2025_danes
WHERE jn_status = 'X';

DELETE FROM public.ev_del_stavbe_enota_h_2025_danes
WHERE jn_status = 'X';
