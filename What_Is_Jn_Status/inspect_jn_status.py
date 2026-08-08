#!/usr/bin/env python3
"""Create a read-only JSON report describing an Oracle JN_STATUS column."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    import oracledb
except ImportError:  # Keeps helper functions importable before dependencies are installed.
    oracledb = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


DEFAULT_OWNER = "EV"
DEFAULT_TABLE = "JN_PARC_ENOTA"
LOOKUP_OWNERS = ("EV", "SIF")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")


def oracle_identifier(value: str, label: str) -> str:
    """Return a safe, normalised unquoted Oracle identifier."""
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a simple Oracle identifier: {value!r}")
    return value.upper()


def require_environment(environ: Mapping[str, str]) -> dict[str, str]:
    required = ("KN_USER", "KN_PASSWORD", "KN_HOST", "KN_PORT", "KN_SERVICE")
    missing = [name for name in required if not environ.get(name)]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))

    try:
        int(environ["KN_PORT"])
    except ValueError as error:
        raise RuntimeError("KN_PORT must be an integer") from error

    return {name: environ[name] for name in required}


def json_value(value: Any) -> Any:
    """Convert Oracle values, including CLOBs, to JSON-compatible values."""
    if hasattr(value, "read"):
        return value.read()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def query_rows(connection: Any, statement: str, parameters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters or {})
        columns = [description[0].lower() for description in cursor.description]
        return [
            {column: json_value(value) for column, value in zip(columns, row)}
            for row in cursor
        ]


def collect_section(
    connection: Any,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Preserve partial results when a metadata view is not accessible."""
    try:
        return {"status": "ok", "rows": query_rows(connection, statement, parameters)}
    except Exception as error:  # Oracle permissions/version differences are report data.
        return {"status": "error", "error": str(error)}


def matching_triggers(section: dict[str, Any]) -> dict[str, Any]:
    """Retain only target-table triggers that mention JN_STATUS."""
    if section["status"] != "ok":
        return section
    return {
        "status": "ok",
        "rows": [
            row
            for row in section["rows"]
            if "JN_STATUS" in (row.get("trigger_body") or "").upper()
        ],
    }


def collect_report(connection: Any, owner: str, table: str) -> dict[str, Any]:
    target = {"owner": owner, "table": table, "column": "JN_STATUS"}
    quoted_target = f'"{owner}"."{table}"'
    # OWNER and TABLE are Oracle keywords, so do not use them as bind names.
    binds = {"p_owner": owner, "p_table": table}

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "read_only": True,
        "sections": {},
    }
    sections = report["sections"]

    sections["table_ddl"] = collect_section(
        connection,
        "SELECT DBMS_METADATA.GET_DDL('TABLE', :p_table, :p_owner) AS ddl FROM dual",
        binds,
    )
    sections["column_definition"] = collect_section(
        connection,
        """
        SELECT owner, table_name, column_name, data_type, data_length,
               data_precision, data_scale, nullable, data_default
        FROM all_tab_columns
        WHERE owner = :p_owner AND table_name = :p_table AND column_name = 'JN_STATUS'
        """,
        binds,
    )
    sections["column_comments"] = collect_section(
        connection,
        """
        SELECT owner, table_name, column_name, comments
        FROM all_col_comments
        WHERE owner = :p_owner AND table_name = :p_table AND column_name = 'JN_STATUS'
        """,
        binds,
    )
    sections["constraints"] = collect_section(
        connection,
        """
        SELECT c.owner, c.constraint_name, c.constraint_type, c.status,
               c.validated, c.search_condition_vc
        FROM all_constraints c
        JOIN all_cons_columns cc
          ON cc.owner = c.owner
         AND cc.constraint_name = c.constraint_name
         AND cc.table_name = c.table_name
        WHERE c.owner = :p_owner
          AND c.table_name = :p_table
          AND cc.column_name = 'JN_STATUS'
        ORDER BY c.constraint_name, cc.position
        """,
        binds,
    )
    sections["jn_status_columns_in_ev_and_sif"] = collect_section(
        connection,
        """
        SELECT owner, table_name, column_name, data_type, data_length, nullable
        FROM all_tab_columns
        WHERE column_name = 'JN_STATUS' AND owner IN ('EV', 'SIF')
        ORDER BY owner, table_name
        """,
    )
    triggers = collect_section(
        connection,
        """
        SELECT owner, trigger_name, table_name, triggering_event, trigger_type,
               status, trigger_body
        FROM all_triggers
        WHERE table_owner = :p_owner AND table_name = :p_table
        ORDER BY trigger_name
        """,
        binds,
    )
    sections["triggers_referencing_jn_status"] = matching_triggers(triggers)
    sections["source_referencing_jn_status"] = collect_section(
        connection,
        """
        SELECT owner, name, type, line, text
        FROM all_source
        WHERE owner IN ('EV', 'SIF')
          AND UPPER(text) LIKE '%JN_STATUS%'
        ORDER BY owner, name, type, line
        """,
    )
    sections["distinct_values"] = collect_section(
        connection,
        f"SELECT DISTINCT JN_STATUS FROM {quoted_target} ORDER BY JN_STATUS",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default=DEFAULT_OWNER, help=f"Table owner (default: {DEFAULT_OWNER})")
    parser.add_argument("--table", default=DEFAULT_TABLE, help=f"Table name (default: {DEFAULT_TABLE})")
    parser.add_argument("--output", type=Path, default=Path("jn_status_report.json"), help="JSON report path")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    owner = oracle_identifier(arguments.owner, "owner")
    table = oracle_identifier(arguments.table, "table")

    if load_dotenv is None or oracledb is None:
        raise RuntimeError("Install dependencies first: pip install -r requirements.txt")

    load_dotenv(Path(__file__).with_name(".env"))
    config = require_environment(os.environ)
    client_lib_dir = os.environ.get("KN_ORACLE_CLIENT_LIB_DIR")
    if client_lib_dir:
        oracledb.init_oracle_client(lib_dir=client_lib_dir)

    dsn = oracledb.makedsn(config["KN_HOST"], int(config["KN_PORT"]), service_name=config["KN_SERVICE"])
    with oracledb.connect(user=config["KN_USER"], password=config["KN_PASSWORD"], dsn=dsn) as connection:
        report = collect_report(connection, owner, table)

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote read-only metadata report to {arguments.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(2)
