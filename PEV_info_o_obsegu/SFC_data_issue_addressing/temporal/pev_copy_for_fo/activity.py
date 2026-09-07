"""Copy only the two verified PEV tables; let their existing triggers update FO."""
from uuid import UUID, uuid5, uuid4

from temporalio import activity
from temporalio.exceptions import ApplicationError
from sdk.db_loader import get_db_manager_for_caller
from core.temporal.shared_context import get_user_id_context

# Fixed namespace + source ID means one copy per source, even after a lost reply.
COPY_NAMESPACE = UUID("ba5d5e53-dae8-4367-956a-d25fb8ab81b6")
# Business columns verified against the test DB on 2026-09-07.
# IDs, audit metadata and sequence-backed columns are regenerated.
PEV_STAVBE_COLUMNS = "geom, id_rel_fo, stavba_id, ko_id, st_stavbe, upostevan, id_dnp, id_stavbe, id_nep, model"
PEV_PARCELE_COLUMNS = "geom, id_rel_fo, parcela_id, ko_id, st_parcele, povrsina, delez_vpr, delez_rez, delez_rez_vir, soglasje, nosilec, upostevan, delez_bzps, delez, delez_vir, id_dnp, del, id_nep, model, id_zemljisca, id_rel_pe"
PEV_DELI_STAVB_COLUMNS = "del_stavbe_id, ko_id, st_stavbe, st_dela_stavbe, dst_upost, hisna_stevilka_id, povrsina, delez_vpr, delez_rez, delez_rez_vir, delez, delez_vir, soglasje, nosilec, upostevan, vrsta_dejanske_rabe_del_st_id, id_dnp, del, id_nep, model, id_dela_stavbe, ins, id_stavbe, id_rel_fo, id_rel_pe"


@activity.defn
def copy_pev_for_fo(request: dict) -> dict:
    table = request.get("table")
    if table not in ("pev_stavbe", "pev_parcele"):
        raise ApplicationError("Unsupported PEV table", non_retryable=True)
    try:
        source_id = str(UUID(request["record_id"]))
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        raise ApplicationError("record_id must be a UUID", non_retryable=True) from error
    user_id = get_user_id_context()
    if user_id == "00000000-0000-0000-0000-000000000000":
        raise ApplicationError("Authenticated user context is required", non_retryable=True)
    copy_id = str(uuid5(COPY_NAMESPACE, f"{table}:{source_id}"))
    columns = PEV_STAVBE_COLUMNS if table == "pev_stavbe" else PEV_PARCELE_COLUMNS
    db = get_db_manager_for_caller()

    with db.session() as cur:
        cur.execute("SET LOCAL lock_timeout = '10s'")
        cur.execute("SET LOCAL statement_timeout = '120s'")
        # Serialize clicks on this source; all changes commit together.
        cur.execute(f"SELECT id_rel_fo, fo_geom_upost, prikazan_na_sloju FROM public.{table} WHERE id = %s FOR UPDATE", (source_id,))
        source = cur.fetchone()
        if not source:
            raise ApplicationError("Source record does not exist", non_retryable=True)
        cur.execute(f"SELECT id FROM public.{table} WHERE id = %s", (copy_id,))
        if cur.fetchone():
            return {"copy_id": copy_id, "already_copied": True}
        if source["prikazan_na_sloju"] is False:
            raise ApplicationError("Cannot copy a hidden FO copy", non_retryable=True)
        if source["fo_geom_upost"] is not True or not source["id_rel_fo"]:
            raise ApplicationError("Source must be enabled for an FO", non_retryable=True)

        # Different components of the same FO must not overwrite each other's totals.
        cur.execute("SELECT id FROM public.pev_fo WHERE id = %s FOR UPDATE", (source["id_rel_fo"],))
        if not cur.fetchone():
            raise ApplicationError("Related FO does not exist", non_retryable=True)
        if table == "pev_stavbe":
            cur.execute("SELECT id FROM public.pev_deli_stavb WHERE id_rel_sta = %s ORDER BY id FOR UPDATE", (source_id,))
            parts = cur.fetchall()

        cur.execute(
            f"UPDATE public.{table} SET fo_geom_upost = false, updated_by = %s, updated_at = now() WHERE id = %s",
            (user_id, source_id),
        )
        # Insert disabled: the parcel BEFORE INSERT trigger otherwise rewrites delez_bzps.
        cur.execute(
            f"""INSERT INTO public.{table}
                (id, created_by, created_at, prikazan_na_sloju, fo_geom_upost, {columns})
                SELECT %s, %s, now(), false, false, {columns}
                FROM public.{table} WHERE id = %s""",
            (copy_id, user_id, source_id),
        )
        if table == "pev_stavbe":
            # Parts keep their business attributes and direct FO relationship.
            for part in parts:
                cur.execute(
                    f"""INSERT INTO public.pev_deli_stavb
                        (id, created_by, created_at, id_rel_sta, {PEV_DELI_STAVB_COLUMNS})
                        SELECT %s, %s, now(), %s, {PEV_DELI_STAVB_COLUMNS}
                        FROM public.pev_deli_stavb WHERE id = %s""",
                    (str(uuid4()), user_id, copy_id, part["id"]),
                )
        # The existing UPDATE trigger now recalculates from the complete copy.
        cur.execute(f"UPDATE public.{table} SET fo_geom_upost = true WHERE id = %s", (copy_id,))
    return {"copy_id": copy_id, "already_copied": False}
