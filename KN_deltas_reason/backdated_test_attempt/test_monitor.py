"""Deterministic local fixtures. No Oracle, credentials, or production writes."""

from contextlib import closing, redirect_stderr
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from monitor import compare_observations, experiment_definition, export_observations


class FakeOracle:
    def __init__(self, batches, columns=("MATCHING_KEY", "CHANGED_AT")):
        self.batches = iter(batches)
        self.description = [(c,) for c in columns]
        self.queries = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, **binds):
        self.queries.append((query, binds))

    def fetchmany(self, size):
        item = next(self.batches, [])
        if isinstance(item, BaseException):
            raise item
        return item


class MonitorTest(unittest.TestCase):
    early = "2026-08-01T00:00:00.123456789Z"
    boundary = "2026-09-20T00:00:00.000000000Z"
    later = "2026-09-23T00:00:00.000000000Z"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        (self.folder / "sqls/a").mkdir(parents=True)
        (self.folder / "sqls/b").mkdir()
        (self.folder / "sqls/a/raw.sql").write_text("SELECT diagnostic_fields FROM source_a")
        (self.folder / "sqls/b/integration-like.sql").write_text("SELECT diagnostic_fields FROM source_b")
        (self.folder / "sqls/tables.json").write_text('{"a":"KN","b":"EV"}')
        (self.folder / "config.json").write_text('{"window_start":"2026-07-01 00:00:00"}')
        self.definition, self.manifest, self.digest = experiment_definition(self.folder, "observer", "test/service")
        self.db = self.folder / f"observations_{self.digest[:12]}.sqlite3"
        self.stderr = io.StringIO()
        self.logs = redirect_stderr(self.stderr)
        self.logs.__enter__()
        self.addCleanup(self.logs.__exit__, None, None, None)

    def export(self, rows, columns=("MATCHING_KEY", "CHANGED_AT")):
        return export_observations(self.db, self.definition, self.manifest, self.digest,
                                   self.definition["extracts"][:1], lambda: FakeOracle([rows], columns))

    def differences(self):
        output = io.StringIO()
        compare_observations(self.db, output, table="a")
        return list(csv.DictReader(io.StringIO(output.getvalue())))

    def test_all_difference_categories_and_fixed_baseline(self):
        columns = ("MATCHING_KEY", "CHANGED_AT", "SOURCE_CREATED_AT", "SOURCE_DATUM_SYS")
        self.export([("gone", self.early, None, None),
                     ("backward", self.boundary, None, "native-old"),
                     ("forward", self.early, "native-old", None),
                     ("same", self.boundary, None, None)], columns)
        large = "12345678901234567890123456789012345678"
        latest = [("backward", self.early, "native-new", None),
                  ("forward", self.later, None, "native-new"),
                  ("same", self.boundary, None, None),
                  (large, self.early, None, None),
                  ("equal", self.boundary, None, None),
                  ("newer", self.later, None, None)]
        self.export(latest, columns)
        rows = self.differences()
        self.assertEqual(len(rows), 10)  # 3 new, 1 absent, 2 changed, 4 audit changes
        new = {r["matching_key"]: r for r in rows if r["category"] == "NEW_KEY"}
        self.assertEqual(new[large]["older_than_baseline_max"], "true")
        self.assertEqual(new["equal"]["older_than_baseline_max"], "false")
        self.assertEqual(new["newer"]["older_than_baseline_max"], "false")
        self.assertFalse(any(r["matching_key"] == "same" for r in rows))
        audits = [r for r in rows if r["category"] == "CHANGED_AUDIT_TIMESTAMP"]
        self.assertTrue(any(r["old_value"] == "" and r["new_value"] for r in audits))
        self.assertTrue(any(r["new_value"] == "" and r["old_value"] for r in audits))
        self.export(latest, columns)
        self.assertEqual(len(self.differences()), 10)
        self.assertEqual({r["baseline_id"] for r in self.differences()}, {"1"})
        self.assertEqual({r["latest_id"] for r in self.differences()}, {"3"})

    def test_unchanged_and_empty_baseline(self):
        self.export([])
        self.assertEqual(self.differences(), [])
        self.assertIn("insufficient observations", self.stderr.getvalue())
        self.export([("new", self.early)])
        self.assertEqual(self.differences()[0]["older_than_baseline_max"], "")
        self.export([("new", self.early)])
        self.assertEqual(self.differences()[0]["baseline_id"], "1")

    def test_unchanged_nonempty(self):
        self.export([("key", self.early)])
        self.export([("key", self.early)])
        self.assertEqual(self.differences(), [])

    def test_failures_rollback_and_continue(self):
        self.export([("old", self.boundary)])
        failures = [RuntimeError("lost connection"),
                    [("duplicate", self.early), ("duplicate", self.early)],
                    [(None, self.early)], [("null-date", None)]]
        for failure in failures:
            connections = iter([FakeOracle([[("partial", self.early)], failure]),
                                FakeOracle([[("other", self.early)]])])
            result = export_observations(self.db, self.definition, self.manifest, self.digest,
                                         self.definition["extracts"], lambda: next(connections))
            self.assertEqual(result, 1)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM records").fetchone()[0], 5)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations WHERE status='FAILED'").fetchone()[0], 4)
        self.differences()
        self.assertIn("recent attempt", self.stderr.getvalue())
        self.assertIn("latest success #1", self.stderr.getvalue())

    def test_interrupt_and_connection_failure_recorded(self):
        with self.assertRaises(KeyboardInterrupt):
            export_observations(self.db, self.definition, self.manifest, self.digest,
                                self.definition["extracts"],
                                lambda: FakeOracle([[("partial", self.early)], KeyboardInterrupt()]))
        def broken_connect():
            raise RuntimeError("cannot connect")
        self.assertEqual(export_observations(self.db, self.definition, self.manifest, self.digest,
                                            self.definition["extracts"], broken_connect), 2)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations WHERE status='FAILED'").fetchone()[0], 3)

    def test_atomic_status_counts_and_readonly_source(self):
        oracle = FakeOracle([[("key", self.early)]])
        self.assertEqual(export_observations(self.db, self.definition, self.manifest, self.digest,
                                            self.definition["extracts"][:1], lambda: oracle), 0)
        self.assertEqual(oracle.queries[0], ("SET TRANSACTION READ ONLY", {}))
        self.assertEqual(oracle.queries[1][1], {"window_start": "2026-07-01 00:00:00"})
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT status,row_count,max_changed_at FROM observations").fetchone(),
                             ("COMPLETE", 1, self.early))

    def test_experiment_hash_and_manifest_guard(self):
        (self.folder / "sqls/tables.json").write_text('{"b":"EV","a":"KN"}')
        self.assertEqual(experiment_definition(self.folder, "observer", "test/service")[2], self.digest)
        for username, dsn in [("other", "test/service"), ("observer", "other/service")]:
            self.assertNotEqual(experiment_definition(self.folder, username, dsn)[2], self.digest)
        self.export([])
        with self.assertRaisesRegex(ValueError, "mismatch"):
            export_observations(self.db, self.definition, "changed manifest", self.digest,
                                self.definition["extracts"], lambda: FakeOracle([]))
        # Filters select extracts only AFTER hashing the entire cohort.
        self.assertEqual(experiment_definition(self.folder, "observer", "test/service")[2], self.digest)
        (self.folder / "sqls/b/integration-like.sql").write_text("SELECT additional_audit_field FROM source_b")
        self.assertNotEqual(experiment_definition(self.folder, "observer", "test/service")[2], self.digest)
        (self.folder / "sqls/b/integration-like.sql").write_text("SELECT diagnostic_fields FROM source_b")
        self.assertEqual(experiment_definition(self.folder, "observer", "test/service")[2], self.digest)
        (self.folder / "config.json").write_text('{"window_start":"2026-06-01 00:00:00"}')
        self.assertNotEqual(experiment_definition(self.folder, "observer", "test/service")[2], self.digest)

    def test_compare_uses_stored_definition_not_current_config(self):
        self.export([("key", self.early)])
        self.export([("key", self.boundary)])
        (self.folder / "config.json").unlink()
        self.assertEqual(self.differences()[0]["category"], "CHANGED_TIMESTAMP")
        with self.assertRaisesRegex(ValueError, "No matching"):
            compare_observations(self.db, io.StringIO(), table="missing")

    def test_wrong_output_shape_and_types_fail(self):
        self.assertEqual(self.export([("key", self.early)], ("UNKNOWN", "CHANGED_AT")), 1)
        self.assertEqual(self.export([(123, self.early)]), 1)

    def test_checked_in_cohort_and_special_predicates(self):
        folder = Path(__file__).resolve().parent
        definition, _, _ = experiment_definition(folder, "fixture", "fixture")
        extracts = definition["extracts"]
        self.assertEqual(len(extracts), 42)
        self.assertEqual(sum(e["mode"] == "RAW" for e in extracts), 20)
        self.assertEqual(sum(e["group"] == "EV" for e in extracts), 21)
        sql = {e["dataset"]: e["sql"] for e in extracts}
        self.assertIn("DEL_STAVBE_H_ID", sql["kn_nep_deli_stavb_h"])
        self.assertIn("TEREN_GEOM is not null", sql["kn_nep_stavbe_zps_h"])
        self.assertIn("ID = '77920'", sql["ev_g_zeleznice_l_h"])
        self.assertIn("2025-01-01", sql["ev_del_stavbe_enota_h_2025_danes"])
        self.assertIn("2025-01-01", sql["ev_parc_enota_h_2025_danes"])
        for name in ("ev_parcela_h", "ev_parc_enota_h_2025_danes"):
            self.assertIn("j.JN_STATUS <> 'X'", sql[name])
            self.assertIn("LEFT JOIN EV.REVISION rt", sql[name])
            self.assertIn("COALESCE(rt.CREATED, rf.CREATED)", sql[name])
        self.assertEqual(sum("AS source_created_at" in s for s in sql.values()), 2)
        self.assertEqual(sum("AS source_datum_sys" in s for s in sql.values()), 3)
        for extract in extracts:
            self.assertIn(":window_start", extract["sql"])
            self.assertNotIn("SDO_UTIL", extract["sql"])
            if extract["group"] == "EV":
                self.assertEqual(extract["mode"], "INTEGRATION_LIKE")


if __name__ == "__main__":
    unittest.main()
