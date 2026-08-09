#!/usr/bin/env python3
"""Deprecated compatibility shim; use ``src/lift_integ_init/init.py``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lift_integ_init.init import main, parse_args, resolve_table_spec


if __name__ == "__main__":
    raise SystemExit(main())
