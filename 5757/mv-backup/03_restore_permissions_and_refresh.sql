-- Run AFTER the simplified CREATE-only statement succeeds and is committed.
-- Restores saved owner/effective permissions, then populates the MV.
-- No DROP or CREATE commands. Prepared only, not executed.

BEGIN;

SET LOCAL search_path = pg_catalog, public;

ALTER MATERIALIZED VIEW "public"."pripis_standardne_statistike_napak" OWNER TO "gurs_readwrite";


GRANT INSERT ON TABLE "public"."pripis_standardne_statistike_napak" TO "flycom_rw";

GRANT SELECT ON TABLE "public"."pripis_standardne_statistike_napak" TO "flycom_rw";

GRANT UPDATE ON TABLE "public"."pripis_standardne_statistike_napak" TO "flycom_rw";

GRANT DELETE ON TABLE "public"."pripis_standardne_statistike_napak" TO "flycom_rw";

GRANT TRUNCATE ON TABLE "public"."pripis_standardne_statistike_napak" TO "flycom_rw";

GRANT REFERENCES ON TABLE "public"."pripis_standardne_statistike_napak" TO "flycom_rw";

GRANT TRIGGER ON TABLE "public"."pripis_standardne_statistike_napak" TO "flycom_rw";

GRANT SELECT ON TABLE "public"."pripis_standardne_statistike_napak" TO "gurs_read";

GRANT SELECT ON TABLE "public"."pripis_standardne_statistike_napak" TO "flycom_ro";

-- Original view was populated.

-- Refresh may be expensive; schedule it appropriately.

REFRESH MATERIALIZED VIEW "public"."pripis_standardne_statistike_napak";

COMMIT;
