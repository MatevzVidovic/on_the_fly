from pathlib import Path

from integration_core import TableSpec


SPEC = TableSpec(
    name="ev_pe_parc",
    source_sql=Path(__file__).resolve().parents[1] / "kn_to_stag_delta_with_delete" / "ev_pe_parc_h.sql",
    target_schema="public",
    target_table="ev_pe_parc_h",
    membership_key="jn_pe_parc_pk",
    # These are selected raw KN columns and in the source PK/index order.
    source_page_keys=("id_pe_parc", "jn_rev_num"),
    date_change="date_change",
    oracle_owner="EV",
    oracle_index="JN_PE_PARC_PK_JNF_IX",
)
