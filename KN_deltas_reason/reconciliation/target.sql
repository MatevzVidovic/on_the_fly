-- datum_sys must be timestamp WITHOUT time zone. Set its verified interpretation in config.json.
SELECT id::text AS uuid, del_stavbe_h_id::text AS business_key,
       to_char(datum_sys, 'YYYY-MM-DD"T"HH24:MI:SS.US') AS native_changed_at,
       created_at::text, updated_at::text
FROM public.kn_nep_deli_stavb_h
