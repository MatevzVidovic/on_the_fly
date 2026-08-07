from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from EV_INTEG._old.full_ev_backfill.ev_backfill import TableSpec, run_loader

SPEC = TableSpec(
    "jn_pe_parc",
    "JN_PE_PARC",
    "ID_PE_PARC",
    (
        "ID_PE_PARC",
        "ID_PE",
        "PC_MID",
        "JN_REV_NUM",
        "JN_REV_NUM_TO",
        "JN_REV_NUM_PREV",
        "JN_STATUS",
        "POVRSINA_PE",
        "VIR_POVRSINA_PE",
        "VREDNOST_DODATEK",
        "POV_PARC_BREZ_ZPS",
        "POV_PE_BREZ_ZPS",
        "DELITEV_MSG",
        "POVR_PARC_IZR",
    ),
)

if __name__ == "__main__":
    run_loader(SPEC, __file__)
