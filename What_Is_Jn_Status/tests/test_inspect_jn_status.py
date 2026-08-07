import unittest

import inspect_jn_status as inspector


class FakeClob:
    def read(self):
        return "long metadata"


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


if __name__ == "__main__":
    unittest.main()
