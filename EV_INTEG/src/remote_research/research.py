#!/usr/bin/env python3
"""Read-only Oracle evidence collection for one catalogued KN table."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from integrations.catalog import CatalogEntry, research_entry


def collect_evidence(connection: Any, entry: CatalogEntry) -> dict[str, Any]:
    """Collect dictionary evidence only; designed for an injected test connection."""
    spec, checks = entry.spec, entry.checks
    owner, table = (spec.oracle_owner or "EV").upper(), checks.source_table.upper()
    evidence: dict[str, Any] = {"owner": owner, "source_table": table}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name, nullable, data_default FROM all_tab_columns "
            "WHERE owner=:owner AND table_name=:table_name ORDER BY column_id",
            {"owner": owner, "table_name": table},
        )
        evidence["columns"] = tuple(tuple(row) for row in cursor.fetchall())
        cursor.execute(
            "SELECT c.constraint_name, c.constraint_type, c.status, cc.column_name, cc.position "
            "FROM all_constraints c LEFT JOIN all_cons_columns cc "
            "ON cc.owner=c.owner AND cc.constraint_name=c.constraint_name "
            "WHERE c.owner=:owner AND c.table_name=:table_name "
            "ORDER BY c.constraint_name, cc.position",
            {"owner": owner, "table_name": table},
        )
        evidence["constraints"] = tuple(tuple(row) for row in cursor.fetchall())
        cursor.execute(
            "SELECT i.index_name, i.uniqueness, i.status, i.visibility, i.index_type, c.column_name, c.column_position "
            "FROM all_indexes i JOIN all_ind_columns c ON c.index_owner=i.owner AND c.index_name=i.index_name "
            "WHERE i.owner=:owner AND i.table_name=:table_name ORDER BY i.index_name, c.column_position",
            {"owner": owner, "table_name": table},
        )
        evidence["indexes"] = tuple(tuple(row) for row in cursor.fetchall())
        # Dictionary statistics are deliberately used instead of COUNT(*):
        # research must not trigger a full remote-table scan.  They remain
        # candidate evidence because joins/filters can change query cardinality.
        cursor.execute(
            "SELECT num_rows, avg_row_len, last_analyzed FROM all_tables "
            "WHERE owner=:owner AND table_name=:table_name",
            {"owner": owner, "table_name": table},
        )
        row = cursor.fetchone()
        evidence["table_stats"] = None if row is None else tuple(row)
        cursor.execute(
            "SELECT SUM(bytes) FROM all_segments WHERE owner=:owner AND segment_name=:table_name "
            "AND segment_type IN ('TABLE', 'TABLE PARTITION', 'TABLE SUBPARTITION')",
            {"owner": owner, "table_name": table},
        )
        row = cursor.fetchone()
        evidence["segment_bytes"] = None if row is None else row[0]
        try:
            cursor.execute("SELECT dbms_metadata.get_ddl('TABLE', :table_name, :owner) FROM dual", {"owner": owner, "table_name": table})
            row = cursor.fetchone()
            ddl = None if row is None else row[0]
            evidence["ddl"] = ddl.read() if hasattr(ddl, "read") else ddl
        except Exception as error:
            evidence["ddl"] = f"(unavailable: {error})"
    return evidence


def render(entry: CatalogEntry, evidence: dict[str, Any] | None) -> str:
    spec = entry.spec
    lines = [
        f"table: {spec.target_relation}", f"KN SQL: {spec.source_sql}",
        f"membership key: {spec.membership_key}",
        f"native page tuple: {', '.join(spec.source_page_keys)}",
        f"date-change alias: {spec.date_change or '(none)'}",
        f"declared Oracle index: {spec.oracle_owner}.{spec.oracle_index}",
        f"declared leading columns: {', '.join(spec.oracle_index_columns or spec.source_page_keys)}",
    ]
    if evidence is None:
        return "\n".join([*lines, "mode: offline catalog contract (no Oracle evidence collected)"])
    columns = "; ".join(f"{name} nullable={nullable} default={default}" for name, nullable, default in evidence["columns"])
    constraints = "; ".join(f"{name} type={kind} status={status} column={column} position={position}" for name, kind, status, column, position in evidence["constraints"])
    grouped_indexes: dict[str, list[tuple[Any, ...]]] = {}
    for row in evidence["indexes"]:
        grouped_indexes.setdefault(str(row[0]), []).append(row)
    indexes = "; ".join(
        f"{name} unique={rows[0][1]} status={rows[0][2]} visibility={rows[0][3]} type={rows[0][4]} "
        f"columns={','.join(str(row[5]) for row in rows)}"
        for name, rows in grouped_indexes.items()
    )
    lines.extend((
        f"source-table statistics (approximate): num_rows={None if evidence['table_stats'] is None else evidence['table_stats'][0]} "
        f"avg_row_len={None if evidence['table_stats'] is None else evidence['table_stats'][1]} "
        f"last_analyzed={None if evidence['table_stats'] is None else evidence['table_stats'][2]}",
        f"source-table segment bytes (approximate): {evidence['segment_bytes']}",
        f"columns: {columns or '(none)'}",
        f"constraints: {constraints or '(none)'}",
        f"indexes: {indexes or '(none)'}",
        "DDL:", str(evidence["ddl"] or "(not returned; privilege may be missing)"),
    ))
    return "\n".join(lines)


def oracle_connection() -> Any:
    from dotenv import load_dotenv
    load_dotenv(SRC / "kn_to_stag_delta_with_delete" / ".env", override=False)
    import oracledb
    required = ("KN_USER", "KN_PASSWORD", "KN_HOST", "KN_PORT", "KN_SERVICE")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("missing KN Oracle environment variables: " + ", ".join(missing))
    return oracledb.connect(
        user=os.environ["KN_USER"], password=os.environ["KN_PASSWORD"],
        dsn=oracledb.makedsn(os.environ["KN_HOST"], int(os.environ["KN_PORT"]), service_name=os.environ["KN_SERVICE"]),
    )


def main(argv: list[str] | None = None, *, connect: Any = oracle_connection) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", help="catalogued staging table")
    parser.add_argument("--offline", action="store_true", help="print only checked-in catalog facts")
    args = parser.parse_args(argv)
    try:
        entry = research_entry(args.table)
    except KeyError as error:
        parser.error(str(error))
    if args.offline:
        print(render(entry, None)); return 0
    with connect() as connection:
        print(render(entry, collect_evidence(connection, entry)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
