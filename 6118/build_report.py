"""Classify the metadata snapshot; never connects to a database."""

import csv
from collections import Counter
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def classify(row):
    fields = row["sync_fields"]
    if not row["use_changed_datetime_for_delta"]:
        return "NO_DATE_WATERMARK", "", "Date-based delta is disabled.", ""
    if len(fields) != 1:
        return "NEEDS_REVIEW", "", f"Expected one sync field; found {len(fields)}.", ""
    field = fields[0]["api_name"]
    if row["manager"] != "oraclesql":
        return ("NEEDS_REVIEW", field,
                "PostgreSQL query selects created_at directly; source type and timezone semantics are unknown.", "")
    # The inspected Oracle queries put the complete sync projection on one line.
    # Require an unambiguous, whole-line alias match rather than searching for
    # timezone functions anywhere in the query (other date columns can differ).
    pattern = re.compile(r'^\s*(.+?)\s+(?:AS\s+)?"?' + re.escape(field) + r'"?\s*,?\s*$', re.I)
    matches = [m.group(1).strip() for line in row["query"].splitlines()
               if not line.lstrip().startswith("--") and (m := pattern.fullmatch(line))]
    if len(matches) != 1:
        return "NEEDS_REVIEW", "", "Could not isolate one complete sync-field expression.", ""
    expression = matches[0]
    if not re.search(r"\bFROM_TZ\s*\(", expression, re.I) or "'Europe/Ljubljana'" not in expression:
        return "NEEDS_REVIEW", expression, "Sync projection does not match the known Ljubljana pattern.", ""
    if re.search(r"\bSYS_EXTRACT_UTC\s*\(|\bAT\s+TIME\s+ZONE\s+'UTC'", expression, re.I):
        return "ALREADY_UTC", expression, "Configured watermark projection already converts to UTC.", ""
    alias = "DATUM_SYS_SYNC" if field.upper() == "DATUM_SYS" else "DATE_CHANGE_SYNC"
    proposed = f"{expression} AT TIME ZONE 'UTC' AS {alias}"
    return "AFFECTED", expression, "Configured watermark retains Europe/Ljubljana timezone without UTC conversion.", proposed


def main():
    rows = [json.loads(line) for line in (ROOT / "audit_snapshot.jsonl").read_text().splitlines()]
    assert len({row["integration_id"] for row in rows}) == len(rows), "Duplicate integrations"
    records = []
    for row in rows:
        assert row["is_full_sync"] is False and row["integration_type"] == "sql"
        classification, expression, reason, proposed = classify(row)
        fields = row["sync_fields"]
        records.append({
            "classification": classification,
            "integration_id": row["integration_id"], "integration_name": row["integration_name"],
            "table_name": row["table_name"], "table_id": row["table_id"],
            "company_id": row["company_id"], "manager": row["manager"],
            "connection_name": row["connection_name"],
            "sync_api_field": "; ".join(f["api_name"] for f in fields),
            "sync_target_field": "; ".join(f["target_name"] for f in fields),
            "sync_mapping_id": "; ".join(f["mapping_id"] for f in fields),
            "use_changed_datetime_for_delta": row["use_changed_datetime_for_delta"],
            "sync_expression": expression, "reason": reason,
            "proposed_additional_projection": proposed,
            "processing_status": row["processing_status"],
            "sync_schedule": row["sync_schedule"],
            "last_changed_datetime": row["last_changed_datetime"],
            "last_sync_end": row["last_sync_end"], "observed_at": row["observed_at"],
        })
    for filename, selected in (
        ("all_sql_delta_integrations.csv", records),
        ("affected_integrations.csv", [r for r in records if r["classification"] == "AFFECTED"]),
    ):
        with (ROOT / filename).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(selected)
    counts = Counter(r["classification"] for r in records)
    affected = [r for r in records if r["classification"] == "AFFECTED"]
    lines = [
        "6118 — Ljubljana timezone / delta-watermark configuration audit",
        f"Observed: {rows[0]['observed_at']}",
        "Database: test_njihov_access, PG_DATABASE_SYSTEM. Company ID: 33.",
        "Scope: is_full_sync = false AND integration_type = 'sql'.",
        "Date watermark mapping: attribute_field_integrations.api_last_sync_field = true.",
        "Source SQL: attribute_table_integrations.url.",
        "All database statements ran in read-only transactions ending with ROLLBACK.",
        "Only integration metadata was read. No source-data queries, changes, or syncs were run.",
        "", f"Total SQL delta integrations: {len(records)}",
        *[f"{key}: {value}" for key, value in sorted(counts.items())],
        "", "AFFECTED CONFIGURATIONS",
        "These match the mechanism described in jira.md. This audit does not establish actual missing rows.",
        "Status is reported as stored; FAILED/CONFIGURED integrations remain included if their configuration is affected.",
    ]
    for field in ("DATUM_SYS", "DATE_CHANGE"):
        group = [r for r in affected if r["sync_api_field"].upper() == field]
        lines += ["", f"{field}: {len(group)} integrations"]
        for r in group:
            lines += [f"  {r['table_name']} | integration: {r['integration_name']} | {r['processing_status']}",
                      f"    ID: {r['integration_id']}", f"    SQL: {r['sync_expression']}"]
    lines += ["", "OTHER SQL DELTA INTEGRATIONS"]
    for r in records:
        if r["classification"] != "AFFECTED":
            lines += [f"  {r['table_name']} | integration: {r['integration_name']} | {r['classification']}",
                      f"    {r['reason']}", f"    ID: {r['integration_id']}",
                      f"    SQL: {r['sync_expression']}"]
    lines += ["", "REMEDIATION REFERENCE (not applied)",
        "Add a separate UTC projection and designate it as the date watermark:",
        "  KN: FROM_TZ(CAST(DATUM_SYS AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS DATUM_SYS_SYNC",
        "  EV: FROM_TZ(CAST(COALESCE(RT.CREATED, RF.CREATED) AS TIMESTAMP), 'Europe/Ljubljana') AT TIME ZONE 'UTC' AS DATE_CHANGE_SYNC",
        "Prefer timezone-aware UTC: Lift compares against TO_TIMESTAMP_TZ bounds; bare SYS_EXTRACT_UTC depends on Oracle session timezone.",
        "  EV pripis tables use RF.CREATED alone: preserve that source expression (see CSV).",
        "An alias ending in _SYNC alone does not prove UTC conversion; inspect the selected expression and mapping.",
        "The already-UTC stanovanja integration uses AT TIME ZONE 'UTC' on its existing DATUM_SYS field.",
        "Confirm sync-field changes do not trigger full sync, as required by jira.md; this was not tested by this read-only audit.",
        "", "FILES / REPRODUCTION",
        "affected_integrations.csv: full affected list with IDs, mapping IDs, SQL evidence and suggested additional projection.",
        "all_sql_delta_integrations.csv: all 49 SQL delta integrations, including exceptions.",
        "audit_snapshot.jsonl: selected metadata and full integration SQL for independent review; no connection credentials.",
        "Refresh: python3 6118/read_db.py 6118/audit.sql > 6118/audit_snapshot.jsonl",
        "Rebuild: python3 6118/build_report.py",
    ]
    (ROOT / "findings.txt").write_text("\n".join(lines) + "\n")
    print(f"Audited {len(records)} integrations: {dict(counts)}")
    print("Affected watermark fields:", dict(Counter(r["sync_api_field"] for r in affected)))
    print("Affected statuses:", dict(Counter(r["processing_status"] for r in affected)))


if __name__ == "__main__":
    main()
