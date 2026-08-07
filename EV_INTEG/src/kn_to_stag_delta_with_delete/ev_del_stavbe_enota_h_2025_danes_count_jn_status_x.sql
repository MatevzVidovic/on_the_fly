-- Run on the LIFT data database (fmp_data_gurs).  The target is already the
-- 2025+ split, so no additional date filter is needed.
SELECT COUNT(*) AS jn_status_x_rows
FROM public.ev_del_stavbe_enota_h_2025_danes
WHERE jn_status = 'X';
