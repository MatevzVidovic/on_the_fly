from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from EV_INTEG._old.full_ev_backfill.ev_backfill import TableSpec, run_loader

SPEC = TableSpec(
    "jn_posebna_enota",
    "JN_POSEBNA_ENOTA",
    "ID_PE",
    (
        "ID_PE",
        "ID_PN",
        "NAZIV",
        "ID_MODEL",
        "VREDNOST",
        "JN_REV_NUM",
        "JN_REV_NUM_TO",
        "JN_REV_NUM_PREV",
        "JN_STATUS",
        "RAVEN",
        "CENX",
        "CENY",
        "NASLOV",
        "POSPLOSENA_VREDNOST",
        "OB_MID",
        "NASLOV_VROCANJA",
        "TIP",
        "FAKTOR_PO",
        "ID_DOKUMENT",
        "DELITEV_STATUS",
        "DELITEV_MSG",
        "DAT_PLOMBA",
        "PLOMBA_RAZLOG",
        "ID_MODEL_VER",
    ),
)

if __name__ == "__main__":
    run_loader(SPEC, __file__)
