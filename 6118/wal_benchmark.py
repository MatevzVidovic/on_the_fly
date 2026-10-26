"""Bounded WAL comparison on isolated copies, never on an integration table.

Local mechanics test:
    python3 6118/wal_benchmark.py --local
Manual staging test, with libpq PG* environment variables already configured:
    python3 6118/wal_benchmark.py --staging --expected-database STAGING_DB \
        --confirmed-free-gib 2

Remote tests require a fresh wal6118_bench schema (created by the setup script),
real free-space confirmation and <=50k source rows. No credentials are printed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import uuid


ROOT = Path(__file__).resolve().parent
OLD = ROOT / "ev_pe_parc_utc_backfill.sql"
LSN_SQL = "pg_wal_lsn_diff(pg_current_wal_insert_lsn(), '0/0')::bigint"


class Database:
    def __init__(self, env, psql="psql", command_prefix=None, container=None):
        self.env = dict(env)
        self.env["PGCONNECT_TIMEOUT"] = "5"
        self.env["PGAPPNAME"] = "wal6118_isolated_benchmark"
        self.psql = psql
        self.command_prefix = command_prefix or []
        self.container = container
        self.wal_directory_permission = None

    def run(self, sql=None, file=None, variables=None, readonly=False):
        args = self.command_prefix + [self.psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1"]
        for name, value in (variables or {}).items():
            args += ["-v", f"{name}={value}"]
        if file:
            if self.container:
                sql = Path(file).read_text()
            else:
                args += ["-f", str(file)]
        env = self.env.copy()
        env["PGOPTIONS"] = "-c default_transaction_read_only=" + ("on" if readonly else "off")
        if readonly:
            sql = "BEGIN READ ONLY; SET LOCAL statement_timeout='5s';\n" + sql + "\nROLLBACK;"
        result = subprocess.run(args, input=sql, text=True, capture_output=True,
                                env=env, timeout=120)
        if result.returncode:
            message = result.stderr
            for key in ("PGPASSWORD", "PGUSER", "PGHOST"):
                if env.get(key):
                    message = message.replace(env[key], "<REDACTED>")
            raise RuntimeError(message.strip())
        return [json.loads(line) for line in result.stdout.splitlines()
                if line.startswith("{") or line.startswith("[")]

    def snapshot(self):
        if self.wal_directory_permission is None:
            self.wal_directory_permission = self.run("SELECT jsonb_build_object('allowed', "
                "has_function_privilege('pg_catalog.pg_ls_waldir()', 'EXECUTE'));",
                readonly=True)[0]["allowed"]
        wal_size = "(SELECT sum(size) FROM pg_ls_waldir())" if self.wal_directory_permission else "NULL"
        snapshot = self.run(f"""SELECT jsonb_build_object(
            'time', clock_timestamp(), 'lsn_bytes', {LSN_SQL},
            'wal_directory_bytes', {wal_size},
            'slots', (SELECT jsonb_agg(jsonb_build_object(
                'name', slot_name, 'type', slot_type, 'active', active,
                'restart_lsn', restart_lsn,
                'retained_bytes', pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)))
                FROM pg_replication_slots),
            'relation_bytes', (SELECT jsonb_object_agg(relname, pg_total_relation_size(oid))
                FROM pg_class WHERE relnamespace='wal6118_bench'::regnamespace AND relkind='r')
        );""", readonly=True)[0]
        if self.container:
            disk = subprocess.run(["docker", "exec", self.container, "df", "-Pk", "/var/lib/postgresql/data"],
                                  check=True, text=True, capture_output=True)
            snapshot["filesystem_free_bytes"] = int(disk.stdout.splitlines()[-1].split()[3])*1024
        else:
            snapshot["filesystem_free_bytes"] = None  # DBA must monitor the remote host.
        return snapshot


def local_database():
    if not shutil.which("docker"):
        raise RuntimeError("The disposable local test requires Docker")
    container = "wal6118-"+uuid.uuid4().hex[:10]
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    subprocess.run(["docker", "run", "--rm", "-d", "--name", container,
                    "--network", "none", "--memory", "1g", "--cpus", "2",
                    "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:15", "postgres",
                    "-c", "wal_level=replica", "-c", "max_wal_size=1GB",
                    "-c", "checkpoint_timeout=30min", "-c", "full_page_writes=on",
                    "-c", "synchronous_commit=on", "-c", "wal_compression=off"],
                   check=True, capture_output=True, text=True)
    db = Database(env, command_prefix=["docker", "exec", "-i", "-e", "PGOPTIONS",
                  "-e", "PGAPPNAME", "-u", "postgres", container], container=container)
    deadline = time.monotonic()+45
    while time.monotonic() < deadline:
        main_process = subprocess.run(["docker", "exec", container, "cat", "/proc/1/comm"],
                                      text=True, capture_output=True)
        ready = subprocess.run(["docker", "exec", "-u", "postgres", container,
                                "pg_isready", "-q"], capture_output=True)
        # The image briefly runs a temporary initialization server. Wait for
        # PostgreSQL itself to become PID1, not that temporary server.
        if ready.returncode == 0 and main_process.stdout.strip() == "postgres":
            return db, container
        time.sleep(0.2)
    subprocess.run(["docker", "rm", "-f", "-v", container], capture_output=True)
    raise RuntimeError("Disposable PostgreSQL container did not become ready")


def lsn_delta(before, after):
    return after["lsn_bytes"] - before["lsn_bytes"]


def max_retained(snapshot):
    values = [slot["retained_bytes"] for slot in snapshot["slots"] or []
              if slot["retained_bytes"] is not None]
    return max(values, default=0)


def check_staging_endpoint(env, expected_database):
    # DB names can be identical in staging and production. Also require the
    # exact endpoint already identified by the user as their staging access.
    settings = {}
    path = ROOT.parent / "symlinks/test_njihov_access/.env"
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        settings[key.strip()] = value.strip().strip("\"'")
    matches = (
        env.get("PGHOST") == settings["PG_HOST"]
        and env.get("PGPORT", "5432") == settings.get("PG_PORT", "5432")
        and expected_database == settings["PG_DATABASE_DATA"]
        and env.get("PGDATABASE") == expected_database
    )
    if not matches:
        raise RuntimeError("Endpoint/database must match test_njihov_access; no connection or write attempted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true")
    mode.add_argument("--staging", action="store_true")
    parser.add_argument("--expected-database")
    parser.add_argument("--confirmed-free-gib", type=float)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--pause-seconds", type=float, default=0.5)
    parser.add_argument("--max-wal-mib-per-second", type=float, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 1000 or args.pause_seconds < 0.1:
        parser.error("Use 1..1000 rows and at least 0.1s pause per batch")
    if not 0 < args.max_wal_mib_per_second <= 16:
        parser.error("Use a positive WAL pacing budget of at most 16 MiB/s")
    if args.staging and (not args.expected_database or (args.confirmed_free_gib or 0) < 2):
        parser.error("Staging requires its expected database and >=2 GiB confirmed actual free space")

    original_hash = hashlib.sha256(OLD.read_bytes()).hexdigest()
    control = None
    monitor_stop, monitor_thread = threading.Event(), None
    current_phase = ["setup"]
    result = {"kind": "disposable_local_mechanics" if args.local else "manual_staging",
              "success_scope": "SQL correctness and script completion; not production storage/Barman acceptance",
              "original_sha256": original_hash, "batch_size": args.batch_size,
              "pause_seconds": args.pause_seconds,
              "max_wal_mib_per_second": args.max_wal_mib_per_second,
              "limits": "50k source rows;128MiB source;64MiB extra retained WAL or 16MiB per batch stops batching",
              "measurements": []}
    output = args.output or ROOT / ("wal_local_results.json" if args.local else "wal_staging_results.json")
    try:
        if args.local:
            if shutil.disk_usage("/private/tmp").free < 2 * 1024**3:
                raise RuntimeError("Local test needs at least 2 GiB available disk")
            db, control = local_database()
            db.run("""CREATE TABLE public.ev_posebna_enota_h (
                id uuid PRIMARY KEY, integration_key text UNIQUE,
                date_change timestamp without time zone NOT NULL, payload text NOT NULL);
                INSERT INTO public.ev_posebna_enota_h
                SELECT md5(g::text)::uuid, g::text,
                  (CASE WHEN g%2=0 THEN timestamp '2026-01-15 12:00:00'
                        ELSE timestamp '2026-07-15 12:00:00' END)
                    + (g%60)*interval '1 second', repeat(md5(g::text), 28)
                FROM generate_series(1,35768) g;""")
        else:
            check_staging_endpoint(os.environ, args.expected_database)
            db = Database(os.environ)

        info = db.run("""SELECT jsonb_build_object('database', current_database(),
            'version', version(), 'wal_level', current_setting('wal_level'),
            'archive_mode', current_setting('archive_mode'),
            'full_page_writes', current_setting('full_page_writes'),
            'checkpoint_timeout', current_setting('checkpoint_timeout'),
            'max_wal_size', current_setting('max_wal_size'),
            'can_create_schema', has_database_privilege(current_database(),'CREATE'));""", readonly=True)[0]
        result["environment"] = info
        if args.staging and info["database"] != args.expected_database:
            raise RuntimeError("Database mismatch: no benchmark writes attempted")
        if not info["can_create_schema"]:
            raise RuntimeError("No CREATE-schema permission: no benchmark writes attempted")
        db.run(file=ROOT / "wal_staging_setup.sql")
        # BEGIN/COMMIT in setup has completed. Do not include fixture creation WAL
        # in backfill totals; it must still be budgeted operationally in staging.
        result["after_setup"] = db.snapshot()
        result["physical_receiver_present"] = any(
            slot["type"] == "physical" and slot["active"]
            for slot in result["after_setup"]["slots"] or [])

        def monitor():
            while not monitor_stop.wait(1):
                try:
                    sample = db.snapshot()
                    sample["phase"] = current_phase[0]
                    result.setdefault("timeline", []).append(sample)
                except Exception as exc:
                    result.setdefault("monitor_errors", []).append(str(exc))

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        if args.staging:
            deadline = time.monotonic()+300
            while max_retained(db.snapshot()) > 16*1024**2:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Setup backlog did not drain within 5min; preserve results and inspect Barman")
                time.sleep(2)

        def phase(label, sql=None, file=None):
            current_phase[0] = label
            if args.local:
                db.run("CHECKPOINT;")  # Equal initial full-page-image conditions.
            before = db.snapshot()
            start = time.monotonic()
            db.run(sql=sql, file=file)
            after = db.snapshot()
            record = {"phase": label, "seconds": time.monotonic()-start,
                      "wal_bytes": lsn_delta(before, after), "before": before, "after": after}
            result["measurements"].append(record)
            print(f"{label}: {record['wal_bytes']:,} WAL bytes", flush=True)
            return record

        # Baseline FIRST. It is the old UPDATE against an isolated clone.
        phase("original_logged_update", file=ROOT / "wal_baseline.sql")
        if args.staging:
            deadline = time.monotonic()+300
            while max_retained(db.snapshot()) > 16*1024**2:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Baseline backlog did not drain within 5min; stop and inspect Barman")
                time.sleep(2)

        # Expose the exact trap the user asked about. This clone has no dependents.
        phase("set_unlogged", sql="SET lock_timeout='2s'; SET statement_timeout='20s'; ALTER TABLE wal6118_bench.logging_toggle SET UNLOGGED;")
        phase("unlogged_update", sql="""SET statement_timeout='20s';
            UPDATE wal6118_bench.logging_toggle SET date_change_utc=
            (date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC'
            WHERE date_change_utc IS NULL AND date_change IS NOT NULL;""")
        phase("restore_logged", sql="SET lock_timeout='2s'; SET statement_timeout='20s'; ALTER TABLE wal6118_bench.logging_toggle SET LOGGED;")
        if args.staging:
            deadline = time.monotonic()+300
            while max_retained(db.snapshot()) > 16*1024**2:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Logging-toggle backlog did not drain within 5min; stop")
                time.sleep(2)

        if args.local:
            db.run("CHECKPOINT;")
        current_phase[0] = "paced_logged_batches"
        start_snapshot = db.snapshot()
        starting_retained = max_retained(start_snapshot)
        last_id, total_rows, batches = "", 0, []
        started = time.monotonic()
        while True:
            before = db.snapshot()
            if max_retained(before) > starting_retained+64*1024**2:
                raise RuntimeError("Retained WAL exceeded the extra 64MiB budget; preceding batches remain committed")
            if before["filesystem_free_bytes"] is not None and before["filesystem_free_bytes"] < 2*1024**3:
                raise RuntimeError("Free local disk below 2GiB; preceding batches remain committed")
            batch_start = time.monotonic()
            update = db.run(file=ROOT / "utc_backfill_batched.sql", variables={
                "target_schema": "wal6118_bench", "target_table": "batched",
                "last_id": last_id, "batch_size": args.batch_size})[0]
            after = db.snapshot()
            if not update["rows"]:
                break
            batch = {"rows": update["rows"], "wal_bytes": lsn_delta(before, after),
                     "seconds": time.monotonic()-batch_start,
                     "retained_bytes_after": max_retained(after) if after["slots"] else None}
            batches.append(batch)
            result["batches"] = batches
            last_id, total_rows = update["last_id"], total_rows+update["rows"]
            if batch["wal_bytes"] > 16*1024**2:
                raise RuntimeError("One batch exceeded 16MiB WAL budget; preceding batches remain committed")
            # No database connection/transaction is held during the pause.
            delay = max(args.pause_seconds,
                        batch["wal_bytes"]/(args.max_wal_mib_per_second*1024**2)-batch["seconds"])
            batch["pause_seconds"] = delay
            time.sleep(delay)
        finish = db.snapshot()
        result["measurements"].append({"phase": "paced_logged_batches",
            "seconds": time.monotonic()-started, "rows": total_rows,
            "batch_count": len(batches), "largest_batch_wal_bytes": max(b["wal_bytes"] for b in batches),
            "wal_bytes": lsn_delta(start_snapshot, finish), "before": start_snapshot, "after": finish})
        print(f"paced_logged_batches: {total_rows:,} rows, {len(batches)} committed batches", flush=True)

        result["validation"] = {}
        for table in ("baseline", "batched", "logging_toggle"):
            record = db.run(f"""SELECT jsonb_build_object('rows', count(*),
                'mismatches', count(*) FILTER (WHERE date_change_utc IS DISTINCT FROM
                  ((date_change AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC')),
                'missing_utc', count(*) FILTER (WHERE date_change IS NOT NULL AND date_change_utc IS NULL),
                'logged', (SELECT relpersistence='p' FROM pg_class WHERE oid='wal6118_bench.{table}'::regclass),
                'original_fields_changed', EXISTS (
                    SELECT to_jsonb(t)-'date_change_utc' FROM wal6118_bench.{table} t
                    EXCEPT SELECT to_jsonb(s)-'date_change_utc' FROM public.ev_posebna_enota_h s
                )) FROM wal6118_bench.{table};""", readonly=True)[0]
            result["validation"][table] = record
            if record["mismatches"] or record["missing_utc"] or not record["logged"] or record["original_fields_changed"]:
                raise RuntimeError(f"Validation failed for {table}")
        if len({r['rows'] for r in result['validation'].values()}) != 1:
            raise RuntimeError("Comparison row counts differ")
        result["success"] = True
    except Exception as exc:
        result["success"] = False
        result["error"] = str(exc)
        raise
    finally:
        monitor_stop.set()
        if monitor_thread:
            monitor_thread.join(timeout=10)
        if control:
            subprocess.run(["docker", "rm", "-f", "-v", control], capture_output=True, timeout=30)
        result["original_unchanged"] = hashlib.sha256(OLD.read_bytes()).hexdigest() == original_hash
        output.write_text(json.dumps(result, indent=2)+"\n")
        print(f"Results: {output}", flush=True)


if __name__ == "__main__":
    main()
