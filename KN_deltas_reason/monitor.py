"""Manual snapshots of one KN source query; compare the latest to the first."""

import argparse
import csv
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys


def export_snapshot(connection, database, source_sql, window_start):
    # Format dates and keys in Oracle, avoiding driver numeric rounding and TZ loss.
    query = f"""
        SELECT CAST(q.DEL_STAVBE_H_ID AS VARCHAR2(4000)) AS matching_key,
               TO_CHAR(SYS_EXTRACT_UTC(q.DATUM_SYS),
                       'YYYY-MM-DD"T"HH24:MI:SS.FF9"Z"') AS changed_at
        FROM ({source_sql}) q
        WHERE q.DATUM_SYS >= TO_TIMESTAMP_TZ(
            :window_start || ' Europe/Ljubljana',
            'YYYY-MM-DD HH24:MI:SS TZR')
    """
    started_at = datetime.now(timezone.utc).isoformat()
    source_identity = f"{connection.username}@{connection.dsn}"
    with closing(sqlite3.connect(database)) as db, db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                source_sql TEXT NOT NULL,
                source_identity TEXT NOT NULL,
                window_start TEXT NOT NULL,
                row_count INTEGER,
                max_changed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS records (
                snapshot_id INTEGER NOT NULL,
                matching_key TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                PRIMARY KEY (snapshot_id, matching_key)
            ) WITHOUT ROWID;
        """)
        # One transaction: an exception, Ctrl-C or process death leaves no partial snapshot.
        db.execute("BEGIN IMMEDIATE")
        baseline = db.execute(
            "SELECT source_sql, window_start, source_identity FROM snapshots ORDER BY id LIMIT 1"
        ).fetchone()
        if baseline is not None and baseline != (source_sql, window_start, source_identity):
            raise ValueError("SQL, window_start or Oracle identity changed. Use a new --database for a new baseline.")
        snapshot_id = db.execute(
            "INSERT INTO snapshots (started_at, source_sql, window_start, source_identity) VALUES (?, ?, ?, ?)",
            (started_at, source_sql, window_start, source_identity),
        ).lastrowid
        count = 0
        with connection.cursor() as cursor:
            cursor.arraysize = 5000
            cursor.execute(query, window_start=window_start)
            while rows := cursor.fetchmany(5000):
                db.executemany(
                    "INSERT INTO records VALUES (?, ?, ?)",
                    ((snapshot_id, key, changed) for key, changed in rows),
                )
                count += len(rows)
                print(f"Snapshot {snapshot_id}: {count:,} rows", file=sys.stderr)
        maximum = db.execute(
            "SELECT MAX(changed_at) FROM records WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()[0]
        db.execute(
            "UPDATE snapshots SET completed_at = ?, row_count = ?, max_changed_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), count, maximum, snapshot_id),
        )
    print(f"Saved snapshot {snapshot_id}: {count:,} rows; maximum {maximum}", file=sys.stderr)
    return snapshot_id


def compare_snapshots(database, source_sql, window_start, output):
    # A read-only connection avoids creating an empty file for a mistyped path.
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        snapshots = db.execute(
            "SELECT id, source_sql, window_start, max_changed_at FROM snapshots ORDER BY id"
        ).fetchall()
        if len(snapshots) < 2:
            raise ValueError("Need at least two complete snapshots. Run export again on a later day.")
        if any((sql, start) != (source_sql, window_start) for _, sql, start, _ in snapshots):
            raise ValueError("SQL or window_start changed. Restore them or use a new --database.")
        baseline_id, _, _, boundary = snapshots[0]
        latest_id = snapshots[-1][0]
        if boundary is None:
            raise ValueError("First snapshot is empty: no baseline boundary. Start a new --database.")
        writer = csv.writer(output)
        writer.writerow(["matching_key", "changed_at_utc"])
        count = 0
        for row in db.execute("""
            SELECT current.matching_key, current.changed_at
            FROM records current
            WHERE current.snapshot_id = ? AND current.changed_at < ?
              AND NOT EXISTS (
                  SELECT 1 FROM records baseline
                  WHERE baseline.snapshot_id = ?
                    AND baseline.matching_key = current.matching_key
              )
            ORDER BY current.matching_key
        """, (latest_id, boundary, baseline_id)):
            writer.writerow(row)
            count += 1
    print(
        f"Baseline {baseline_id}; latest {latest_id}; fixed boundary {boundary}; "
        f"{count:,} late-visibility candidates", file=sys.stderr,
    )
    return count


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "compare"])
    parser.add_argument("--database", type=Path, default=folder / "snapshots.sqlite3")
    args = parser.parse_args()
    window_start = json.loads((folder / "config.json").read_text())["window_start"]
    datetime.strptime(window_start, "%Y-%m-%d %H:%M:%S")
    source_sql = (folder / "source.sql").read_text().strip().removesuffix(";")
    if args.command == "compare":
        compare_snapshots(args.database, source_sql, window_start, sys.stdout)
    else:
        import os
        import oracledb
        from dotenv import load_dotenv

        load_dotenv(folder / ".env")
        if client := os.getenv("KN_ORACLE_CLIENT_LIB_DIR"):
            oracledb.init_oracle_client(lib_dir=client)
        with oracledb.connect(
            user=os.environ["KN_ORACLE_USER"],
            password=os.environ["KN_ORACLE_PASSWORD"],
            dsn=os.environ["KN_ORACLE_DSN"],
        ) as connection:
            export_snapshot(connection, args.database, source_sql, window_start)
