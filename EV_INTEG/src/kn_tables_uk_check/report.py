#!/usr/bin/env python3
"""Retired dynamic unique-key discovery command."""
from __future__ import annotations

import sys


def main(_argv: list[str] | None = None) -> int:
    print(
        "error: kn_tables_uk_check is retired; use "
        "src/unique_constraint_sql/generate.py TABLE for the catalogued manual preflight/DDL",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
