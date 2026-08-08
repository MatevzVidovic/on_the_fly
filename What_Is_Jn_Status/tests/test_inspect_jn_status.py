import unittest

import inspect_jn_status as inspector


class FakeClob:
    def read(self):
        return "long metadata"


class RecordingCursor:
    description = [("value",)]

    def __init__(self, statements):
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters):
        self.statements.append((statement, parameters))
        if ":owner" in statement or ":table" in statement:
            raise AssertionError("Oracle keyword used as a bind variable")

    def __iter__(self):
        return iter(())


class RecordingConnection:
    def __init__(self):
        self.statements = []

    def cursor(self):
        return RecordingCursor(self.statements)


class InspectJnStatusTests(unittest.TestCase):
    def test_identifier_is_normalised_and_injection_is_rejected(self):
        self.assertEqual(inspector.oracle_identifier("ev", "owner"), "EV")
        with self.assertRaises(ValueError):
            inspector.oracle_identifier("EV; DROP TABLE X", "owner")

    def test_environment_requires_all_connection_values(self):
        with self.assertRaisesRegex(RuntimeError, "KN_PASSWORD"):
            inspector.require_environment(
                {"KN_USER": "user", "KN_HOST": "host", "KN_PORT": "1521", "KN_SERVICE": "svc"}
            )

    def test_oracle_values_are_json_safe(self):
        self.assertEqual(inspector.json_value(FakeClob()), "long metadata")
        self.assertEqual(inspector.json_value(None), None)

    def test_trigger_filter_preserves_errors_and_matches_status(self):
        error = {"status": "error", "error": "not allowed"}
        self.assertEqual(inspector.matching_triggers(error), error)
        result = inspector.matching_triggers(
            {
                "status": "ok",
                "rows": [
                    {"trigger_name": "A", "trigger_body": "new.jn_status := 'A';"},
                    {"trigger_name": "B", "trigger_body": "new.other_column := 1;"},
                ],
            }
        )
        self.assertEqual([row["trigger_name"] for row in result["rows"]], ["A"])

    def test_report_uses_safe_bind_names_for_owner_and_table(self):
        connection = RecordingConnection()
        report = inspector.collect_report(connection, "EV", "JN_PARC_ENOTA")

        self.assertTrue(all(section["status"] == "ok" for section in report["sections"].values()))
        bound_statements = [item for item in connection.statements if item[1]]
        self.assertTrue(bound_statements)
        for statement, parameters in bound_statements:
            self.assertNotIn(":owner", statement)
            self.assertNotIn(":table", statement)
            self.assertNotIn("owner", parameters)
            self.assertNotIn("table", parameters)
            self.assertEqual(parameters, {"p_owner": "EV", "p_table": "JN_PARC_ENOTA"})


if __name__ == "__main__":
    unittest.main()
