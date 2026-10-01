"""Manual, source-only KN/EV observations. Explicit SQL in sqls/; local SQLite comparisons."""

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


def experiment_definition(folder, username, dsn):
    config = json.loads((folder / "config.json").read_text())
    datetime.strptime(config["window_start"], "%Y-%m-%d %H:%M:%S")
    groups = json.loads((folder / "sqls/tables.json").read_text())
    extracts = []
    for dataset, group in sorted(groups.items()):
        if group not in ("KN", "EV"):
            raise ValueError(f"Unknown group for {dataset}: {group}")
        files = sorted((folder / "sqls" / dataset).glob("*.sql"))
        if not files:
            raise ValueError(f"No SQL for {dataset}")
        for path in files:
            if path.stem not in ("raw", "integration-like"):
                raise ValueError(f"Unknown mode: {path.name}")
            extracts.append({"dataset": dataset, "group": group,
                             "mode": path.stem.upper().replace("-", "_"),
                             "path": path.relative_to(folder).as_posix(),
                             "sql": path.read_text()})
    definition = {"format_version": 1, "config": config, "extracts": extracts,
                  "source": {"username": username, "dsn": dsn}}
    manifest = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(manifest.encode()).hexdigest()
    return definition, manifest, digest


def export_observations(database, definition, manifest, digest, extracts, connect):
    """A fresh read-only source connection and one atomic local observation per extract."""
    failures = 0
    with closing(sqlite3.connect(database)) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS experiment (digest TEXT NOT NULL, manifest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY, dataset TEXT NOT NULL, mode TEXT NOT NULL,
                started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL,
                row_count INTEGER, max_changed_at TEXT, error TEXT
            );
            CREATE TABLE IF NOT EXISTS records (
                observation_id INTEGER NOT NULL, matching_key TEXT NOT NULL,
                changed_at TEXT NOT NULL, source_created_at TEXT, source_datum_sys TEXT,
                PRIMARY KEY (observation_id, matching_key)
            ) WITHOUT ROWID;
        """)
        existing = db.execute("SELECT digest, manifest FROM experiment").fetchall()
        if existing and existing != [(digest, manifest)]:
            raise ValueError("Experiment definition mismatch: refusing to append")
        if not existing:
            db.execute("INSERT INTO experiment VALUES (?, ?)", (digest, manifest))
            db.commit()
        for extract in extracts:
            label = f"{extract['dataset']} {extract['mode']}"
            # Persist the attempt first. A killed process leaves RUNNING but no partial records.
            observation_id = db.execute(
                "INSERT INTO observations (dataset, mode, started_at, status) VALUES (?, ?, ?, 'RUNNING')",
                (extract["dataset"], extract["mode"], datetime.now(timezone.utc).isoformat()),
            ).lastrowid
            db.commit()
            count, maximum = 0, None
            print(f"Starting {label}; observation {observation_id}", file=sys.stderr)
            try:
                db.execute("BEGIN IMMEDIATE")
                with connect() as connection:
                    connection.call_timeout = 60000  # Per round trip, not total export duration.
                    with connection.cursor() as cursor:
                        cursor.execute("SET TRANSACTION READ ONLY")
                        cursor.arraysize = 5000
                        cursor.execute(extract["sql"].strip().removesuffix(";"),
                                       window_start=definition["config"]["window_start"])
                        columns = [item[0].lower() for item in cursor.description]
                        allowed = ["matching_key", "changed_at", "source_created_at", "source_datum_sys"]
                        if columns[:2] != allowed[:2] or len(set(columns)) != len(columns) or any(c not in allowed for c in columns):
                            raise ValueError(f"Unexpected diagnostic columns: {columns}")
                        created_index = columns.index("source_created_at") if "source_created_at" in columns else None
                        system_index = columns.index("source_datum_sys") if "source_datum_sys" in columns else None
                        while rows := cursor.fetchmany(5000):
                            # Oracle formats IDs and dates to text, avoiding driver rounding/TZ loss.
                            for row in rows:
                                if any(value is not None and not isinstance(value, str) for value in row):
                                    raise TypeError("Expected Oracle-formatted text diagnostics")
                                key, changed = row[:2]
                                db.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?)", (
                                    observation_id, key, changed,
                                    row[created_index] if created_index is not None else None,
                                    row[system_index] if system_index is not None else None,
                                ))
                                maximum = changed if maximum is None else max(maximum, changed)
                            count += len(rows)
                            print(f"{label}: {count:,} rows", file=sys.stderr)
                db.execute("""UPDATE observations SET status = 'COMPLETE', completed_at = ?,
                              row_count = ?, max_changed_at = ? WHERE id = ?""",
                           (datetime.now(timezone.utc).isoformat(), count, maximum, observation_id))
                db.commit()
                print(f"Saved {label}: {count:,} rows; maximum {maximum}", file=sys.stderr)
            except BaseException as error:
                db.rollback()
                db.execute("UPDATE observations SET status = 'FAILED', completed_at = ?, error = ? WHERE id = ?",
                           (datetime.now(timezone.utc).isoformat(), f"{type(error).__name__}: {error}", observation_id))
                db.commit()
                failures += 1
                print(f"FAILED {label}: {type(error).__name__}: {error}", file=sys.stderr)
                if not isinstance(error, Exception):
                    raise  # Ctrl-C records the failure, then stops; ordinary failures continue.
    print(f"Export finished: {len(extracts) - failures} complete; {failures} failed; {database}", file=sys.stderr)
    return failures


def compare_observations(database, output, group=None, table=None):
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        definition = json.loads(db.execute("SELECT manifest FROM experiment").fetchone()[0])
        extracts = [e for e in definition["extracts"]
                    if (group is None or e["group"] == group) and (table is None or e["dataset"] == table)]
        if not extracts:
            raise ValueError("No matching extracts in this experiment")
        writer = csv.writer(output)
        writer.writerow(["dataset", "group", "mode", "matching_key", "category", "field",
                         "old_value", "new_value", "older_than_baseline_max", "baseline_id", "latest_id"])
        for extract in extracts:
            dataset, mode = extract["dataset"], extract["mode"]
            observations = db.execute("""SELECT id, started_at, completed_at, status, row_count,
                                                max_changed_at, error FROM observations
                                         WHERE dataset = ? AND mode = ? ORDER BY id""", (dataset, mode)).fetchall()
            complete = [o for o in observations if o[3] == "COMPLETE"]
            label = f"{dataset} {mode}"
            # Surface every failed/interrupted attempt since the latest success.
            for attempt in observations:
                if attempt[3] != "COMPLETE" and (not complete or attempt[0] > complete[-1][0]):
                    print(f"{label}: recent attempt {attempt[0]} {attempt[3]} at {attempt[1]}: {attempt[6] or 'possibly interrupted/still running'}", file=sys.stderr)
            if complete:
                print(f"{label}: latest success #{complete[-1][0]} {complete[-1][1]} to {complete[-1][2]}, {complete[-1][4]:,} rows", file=sys.stderr)
            if len(complete) < 2:
                print(f"{label}: insufficient observations ({len(complete)} complete; need 2)", file=sys.stderr)
                continue
            first, latest = complete[0], complete[-1]
            counts = Counter()
            # Indexed joins, streamed locally: no whole-experiment Python dictionary.
            differences = db.execute("""
                SELECT n.matching_key, 'NEW_KEY', 'changed_at', NULL, n.changed_at,
                       CASE WHEN ? IS NULL THEN '' WHEN n.changed_at < ? THEN 'true' ELSE 'false' END
                FROM records n LEFT JOIN records b
                  ON b.observation_id = ? AND b.matching_key = n.matching_key
                WHERE n.observation_id = ? AND b.matching_key IS NULL
                UNION ALL
                SELECT b.matching_key, 'ABSENT_KEY', 'changed_at', b.changed_at, NULL, ''
                FROM records b LEFT JOIN records n
                  ON n.observation_id = ? AND n.matching_key = b.matching_key
                WHERE b.observation_id = ? AND n.matching_key IS NULL
            """, (first[5], first[5], first[0], latest[0], latest[0], first[0]))
            for key, category, field, old, new, late in differences:
                writer.writerow([dataset, extract["group"], mode, key, category, field, old, new, late, first[0], latest[0]])
                counts[category] += 1
                if late == "true":
                    counts["OLDER_THAN_BASELINE_MAX"] += 1
            for field in ("changed_at", "source_created_at", "source_datum_sys"):
                category = "CHANGED_TIMESTAMP" if field == "changed_at" else "CHANGED_AUDIT_TIMESTAMP"
                for key, old, new in db.execute(f"""
                    SELECT b.matching_key, b.{field}, n.{field}
                    FROM records b JOIN records n
                      ON n.observation_id = ? AND n.matching_key = b.matching_key
                    WHERE b.observation_id = ? AND b.{field} IS NOT n.{field}
                """, (latest[0], first[0])):
                    writer.writerow([dataset, extract["group"], mode, key, category, field, old, new, "", first[0], latest[0]])
                    counts[category] += 1
            print(f"{label}: baseline #{first[0]} {first[1]} to {first[2]}, {first[4]:,} rows; "
                  f"maximum {first[5]}; differences {dict(counts)}", file=sys.stderr)


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "compare"])
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--group", choices=["KN", "EV"])
    selection.add_argument("--table")
    parser.add_argument("--database", type=Path, help="Compare an existing experiment without .env; compare only")
    args = parser.parse_args()
    if args.command == "export" and args.database:
        parser.error("--database is compare-only; export chooses observations_<hash>.sqlite3")
    if args.command == "compare" and args.database:
        compare_observations(args.database, sys.stdout, args.group, args.table)
        sys.exit(0)

    import os
    from dotenv import load_dotenv

    load_dotenv(folder / ".env")
    definition, manifest, digest = experiment_definition(folder, os.environ["KN_ORACLE_USER"], os.environ["KN_ORACLE_DSN"])
    database = folder / f"observations_{digest[:12]}.sqlite3"
    if args.command == "compare":
        compare_observations(database, sys.stdout, args.group, args.table)
    else:
        import oracledb
        from functools import partial

        extracts = [e for e in definition["extracts"]
                    if (args.group is None or e["group"] == args.group) and (args.table is None or e["dataset"] == args.table)]
        if not extracts:
            parser.error("No matching extracts")
        if client := os.getenv("KN_ORACLE_CLIENT_LIB_DIR"):
            oracledb.init_oracle_client(lib_dir=client)
        connect = partial(oracledb.connect, user=os.environ["KN_ORACLE_USER"],
                          password=os.environ["KN_ORACLE_PASSWORD"], dsn=os.environ["KN_ORACLE_DSN"])
        sys.exit(bool(export_observations(database, definition, manifest, digest, extracts, connect)))
