"""All KN→staging table facts, kept separate from adapters and check rules.

Entries whose SQL file is not yet in this repository are intentionally marked
as pending instead of inventing a query.  The thin command wrapper refuses a
pending entry before opening any database connection.

To activate a historical entry: (1) check in one reviewed KN SELECT with the
required aliases, (2) record the actual unique usable Oracle index and its
leading column order, (3) add/update its TableSpec + CheckSpec here, and (4)
run the offline tests plus a live research/preflight run.  Never promote a
name merely because an old loader or metadata row exists.

The seven historical exports promoted here were transcribed from
``already_exist_analysis/integs.md`` and their index order was checked against
``research/schema_info.csv``.  Those are evidence sources, not a replacement
for the live preflight that validates aliases/index state before apply.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from integration_core import CheckSpec, TableSpec


ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "kn_to_stag_delta_with_delete"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    spec: TableSpec
    checks: CheckSpec
    # Exact SQL that must be pasted into the corresponding LIFT integration.
    # TableSpec.source_sql remains the python-oracledb-safe KN→staging query.
    lift_sql: Path | None = None
    pending_sql: bool = False


def _entry(name: str, target: str, membership: str, page_keys: tuple[str, ...], source_table: str, index: str | None, kn_sql_name: str | None, lift_sql_name: str | None, index_columns: tuple[str, ...] | None = None, *, requires_jn_status: bool = True, from_2025: bool = False, forbid_columns: tuple[str, ...] = (), check_page_keys: tuple[str, ...] = ()) -> CatalogEntry:
    # A path is still a TableSpec fact when the integration SQL is pending;
    # live wrappers explicitly reject it rather than falling back to old code.
    source = SQL / (kn_sql_name or f"{name}_kn.sql")
    lift = SQL / (lift_sql_name or f"{name}_lift.sql")
    return CatalogEntry(
        TableSpec(name, source, "public", target, membership, page_keys, "date_change", "EV" if index else None, index, index_columns),
        CheckSpec(
            source_table=source_table,
            requires_jn_status=requires_jn_status,
            from_2025=from_2025,
            forbid_columns=forbid_columns,
            source_page_keys=check_page_keys,
        ),
        lift,
        not source.exists() or not lift.exists() or index is None,
    )


_DECLARED_ENTRIES = {
    "ev_dst_pripis_podatki_h": _entry("ev_dst_pripis_podatki", "ev_dst_pripis_podatki_h", "dst_pripis_podatki_pk", ("dst_pripis_podatki_pk",), "DST_PRIPIS_PODATKI", "SYS_C00102666", "ev_dst_pripis_podatki_h_kn.sql", "ev_dst_pripis_podatki_h_lift.sql", ("id",), requires_jn_status=False),
    "ev_del_stavbe_h": _entry("ev_del_stavbe", "ev_del_stavbe_h", "jn_del_stavbe_pk", ("dst_sid", "jn_rev_num"), "JN_DEL_STAVBE", "JN_DEL_STAVBE_PK_JNF_IX", "ev_del_stavbe_h_kn.sql", "ev_del_stavbe_h_lift.sql"),
    "ev_del_stavbe_enota_h_2025_danes": _entry("ev_del_stavbe_enota", "ev_del_stavbe_enota_h_2025_danes", "jn_del_st_enota_pk", ("dst_sid", "jn_rev_num"), "JN_DEL_STAVBE_ENOTA", "JN_DEL_STAVBE_ENOTA_PK_JNF_IX", "ev_del_stavbe_enota_h_2025_danes_kn.sql", "ev_del_stavbe_enota_h_2025_danes_lift.sql", from_2025=True, forbid_columns=("podatki",), check_page_keys=("jn_del_st_enota_pk",)),
    "ev_parc_del_h": _entry("ev_parc_del", "ev_parc_del_h", "jn_parcela_del_pk", ("id_parc_del", "jn_rev_num"), "JN_PARC_DEL", "JN_PARC_DEL_PK_JNF_IX", "ev_parc_del_h_kn.sql", "ev_parc_del_h_lift.sql"),
    "ev_parc_enota_h_2025_danes": _entry("ev_parc_enota", "ev_parc_enota_h_2025_danes", "jn_parcela_enota_pk", ("id_parc_enota", "jn_rev_num"), "JN_PARC_ENOTA", "JN_PARC_ENOTA_PK_JNF_IX", "ev_parc_enota_h_2025_danes_kn.sql", "ev_parc_enota_h_2025_danes_lift.sql", from_2025=True, forbid_columns=("podatki",)),
    "ev_parcela_h": _entry("ev_parcela", "ev_parcela_h", "jn_parcela_pk", ("pc_mid", "jn_rev_num"), "JN_PARCELA", "JN_PARCELA_PK_JNF_IX", "ev_parcela_h_kn.sql", "ev_parcela_h_lift.sql"),
    "ev_pe_dst_h": _entry("ev_pe_dst", "ev_pe_dst_h", "jn_pe_dst_pk", ("id_pe_dst", "jn_rev_num"), "JN_PE_DST", "JN_PE_DST_PK_JNF_IX", "ev_pe_dst_h_kn.sql", "ev_pe_dst_h_lift.sql"),
    "ev_pe_parc_h": _entry("ev_pe_parc", "ev_pe_parc_h", "jn_pe_parc_pk", ("id_pe_parc", "jn_rev_num"), "JN_PE_PARC", "JN_PE_PARC_PK_JNF_IX", "ev_pe_parc_h_kn.sql", "ev_pe_parc_h_lift.sql"),
    "ev_posebna_enota_h": _entry("ev_posebna_enota", "ev_posebna_enota_h", "jn_posebna_enota_pk", ("id_pe", "jn_rev_num"), "JN_POSEBNA_ENOTA", "JN_POSEBNA_ENOTA_PK_JNF_IX", "ev_posebna_enota_h_kn.sql", "ev_posebna_enota_h_lift.sql"),
    "ev_prostor_h": _entry("ev_prostor", "ev_prostor_h", "jn_prostor_pk", ("pro_id", "jn_rev_num"), "JN_PROSTOR", "JN_PROSTOR_PK_JNF_IX", "ev_prostor_h_kn.sql", "ev_prostor_h_lift.sql"),
    "ev_stavba_h": _entry("ev_stavba", "ev_stavba_h", "jn_sta_pk", ("sta_sid", "jn_rev_num"), "JN_STAVBA", "JN_STAVBA_PK_JNF_IX", "ev_stavba_h_kn.sql", "ev_stavba_h_lift.sql"),
    "ev_parc_pripis_podatki_h": _entry("ev_parc_pripis_podatki", "ev_parc_pripis_podatki_h", "parc_pripis_podatki_pk", ("parc_pripis_podatki_pk",), "PARC_PRIPIS_PODATKI", "SYS_C0034999", "ev_parc_pripis_podatki_h_kn.sql", "ev_parc_pripis_podatki_h_lift.sql", ("id",), requires_jn_status=False),
}

# Only these entries are executable and checked. Facts for the remaining
# historical names are deliberately kept out of the active catalog: they are
# unsupported until both their SQL and verified index declaration are checked
# in. There is no loader/checker fallback to the old monolith.
ENTRIES = {key: entry for key, entry in _DECLARED_ENTRIES.items() if not entry.pending_sql}
UNSUPPORTED_TABLES = frozenset(_DECLARED_ENTRIES) - frozenset(ENTRIES)
# Research backlog only. These names are neither runnable nor checked until
# the promotion checklist in this module's docstring is completed.
RESEARCH_BACKLOG = tuple(sorted(UNSUPPORTED_TABLES))


def catalog_entry(table: str) -> CatalogEntry:
    try:
        return ENTRIES[table.lower()]
    except KeyError as error:
        if table.lower() in UNSUPPORTED_TABLES:
            raise RuntimeError(f"{table} is formally unsupported until its checked-in SQL and verified Oracle index declaration are catalogued") from error
        raise KeyError(f"unknown KN staging integration: {table}") from error


def research_entry(table: str) -> CatalogEntry:
    """Return declared facts for read-only research, including backlog names."""
    try:
        return _DECLARED_ENTRIES[table.lower()]
    except KeyError as error:
        raise KeyError(f"unknown KN staging integration: {table}") from error


def table_spec(table: str) -> TableSpec:
    entry = catalog_entry(table)
    return entry.spec
