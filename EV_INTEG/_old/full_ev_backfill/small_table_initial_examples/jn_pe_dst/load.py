from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from EV_INTEG._old.full_ev_backfill.ev_backfill import TableSpec, run_loader

SPEC = TableSpec(
    "jn_pe_dst",
    "JN_PE_DST",
    "ID_PE_DST",
    (
        "ID_PE_DST",
        "ID_PE",
        "DST_SID",
        "JN_REV_NUM",
        "JN_REV_NUM_TO",
        "JN_REV_NUM_PREV",
        "JN_STATUS",
        "VREDNOST_DODATEK",
        "DELITEV_MSG",
    ),
)

if __name__ == "__main__":
    run_loader(SPEC, __file__)
