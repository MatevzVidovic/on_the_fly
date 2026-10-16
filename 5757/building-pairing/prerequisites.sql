-- PREPARED ONLY. Review existing indexes first. Do not run CONCURRENTLY inside BEGIN.
-- The first index avoids repeatedly scanning the large calculation table.
CREATE INDEX CONCURRENTLY IF NOT EXISTS pripis_vmxpd_enota_lookup
    ON public.pripis_vmxpd_x_enote (id_rel_vm_pd, id_rel_prip_enota);
-- These support source selection and scoped replacement. Skip equivalent existing indexes.
CREATE INDEX CONCURRENTLY IF NOT EXISTS pripis_building_date_model
    ON public.pripis_enote_deli_stavb (id_rel_pr_datum, model);
CREATE INDEX CONCURRENTLY IF NOT EXISTS pripis_primerjava_ev_config
    ON public.pripis_primerjava_ev (id_rel_vm_pd);
-- EV dst_sid already had an index at the previous staging inspection; do not duplicate it.

-- Only if physical destination columns have less than two decimals (Lift display settings alone
-- do not prove PostgreSQL precision). This changes only the comparison output table.
ALTER TABLE public.pripis_primerjava_ev
    ALTER COLUMN isam_vrednost_izr TYPE numeric(20,2),
    ALTER COLUMN ev_vrednost TYPE numeric(20,2),
    ALTER COLUMN delta_izr TYPE numeric(20,2),
    ALTER COLUMN isam_vrednost_zaokrozena TYPE numeric(20,2),
    ALTER COLUMN ev_posplosena_vrednost TYPE numeric(20,2),
    ALTER COLUMN delta_posplosena TYPE numeric(20,2);
