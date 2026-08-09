#!/usr/bin/env python3
"""Retired reconciliation command; use ``src/stag_to_prod/sync_table.py``."""

from __future__ import annotations

import sys


def main(_argv: list[str] | None = None) -> int:
    print(
        "error: stag_to_prod_complex is retired; use src/stag_to_prod/sync_table.py "
        "for explicit UUID idempotent piping (it does not reconcile/delete business keys)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
