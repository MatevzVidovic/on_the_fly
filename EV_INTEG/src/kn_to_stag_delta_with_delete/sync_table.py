#!/usr/bin/env python3
"""Deprecated forwarding entrypoint; use ``ev_pe_parc.py`` directly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ev_pe_parc import main, parse_args


if __name__ == "__main__":
    raise SystemExit(main())
