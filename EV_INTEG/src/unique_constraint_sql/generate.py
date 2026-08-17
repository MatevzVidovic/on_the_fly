#!/usr/bin/env python3
"""Write manual PostgreSQL null/duplicate preflight and constraint SQL."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from integrations.catalog import research_entry


HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "generated"


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def render(table: str) -> str:
    """Return the manual SQL for one catalogued target table."""
    spec = research_entry(table).spec
    relation = f"{quote(spec.target_schema)}.{quote(spec.target_table)}"
    key = quote(spec.membership_key)
    constraint = quote(f"{spec.target_table}_{spec.membership_key}_key")
    lines = [
        "-- Read-only preflight; resolve any rows before running either ALTER.",
        f"SELECT {key}, COUNT(*) FROM {relation} GROUP BY {key} HAVING {key} IS NULL OR COUNT(*) > 1 ORDER BY {key} NULLS FIRST;",
        "",
        "-- Inspect valid ready non-partial one-column unique indexes first.",
        "SELECT idx.relname AS index_name, con.conname AS attached_constraint "
        "FROM pg_index i JOIN pg_class tab ON tab.oid=i.indrelid "
        "JOIN pg_namespace ns ON ns.oid=tab.relnamespace JOIN pg_class idx ON idx.oid=i.indexrelid "
        "LEFT JOIN pg_constraint con ON con.conindid=i.indexrelid "
        "JOIN LATERAL unnest(i.indkey) WITH ORDINALITY key(attnum, ord) ON key.ord <= i.indnkeyatts "
        "JOIN pg_attribute att ON att.attrelid=tab.oid AND att.attnum=key.attnum "
        "JOIN pg_am am ON am.oid=idx.relam "
        f"WHERE ns.nspname='{spec.target_schema}' AND tab.relname='{spec.target_table}' "
        f"AND i.indisunique AND i.indisvalid AND i.indisready AND i.indpred IS NULL AND am.amname='btree' "
        f"GROUP BY idx.relname, con.conname, i.indexrelid, i.indnkeyatts HAVING i.indnkeyatts=1 AND min(att.attname)='{spec.membership_key}';",
        "",
        "-- Run manually only after the preflight is empty.",
        f"ALTER TABLE {relation} ALTER COLUMN {key} SET NOT NULL;",
        "-- If inspection found an unattached suitable index, prefer this path:",
        f"ALTER TABLE {relation} ADD CONSTRAINT {constraint} UNIQUE USING INDEX \"existing_unique_index_name\";",
        "-- Otherwise create a new constraint/index:",
        f"ALTER TABLE {relation} ADD CONSTRAINT {constraint} UNIQUE ({key});",
    ]
    return "\n".join(lines) + "\n"


def output_path(table: str) -> Path:
    """Return the ignored output path after validating the catalog key."""
    return OUTPUT_DIR / f"{research_entry(table).spec.target_table}.sql"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="catalogued staging table")
    args = parser.parse_args(argv)
    try:
        path = output_path(args.table)
        content = render(args.table)
    except KeyError as error:
        parser.error(str(error))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
