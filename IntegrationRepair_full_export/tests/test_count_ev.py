"""Count real-shaped results without touching remote databases."""
from conftest import Cursor, Database, DATE
from count_ev import INTEGRATIONS, count_table


def test_count_table(definition):
    oracle_cursor = Cursor([(10, 8)])
    lift_cursor = Cursor([(11, 8)])
    result = count_table(definition, Database(oracle_cursor), Database(lift_cursor))
    assert result['oracle_total'] == 10
    assert result['lift_total'] == 11
    assert result['total_difference'] == 1
    assert result['eligible_difference'] == 0
    query, params = oracle_cursor.calls[-1]
    assert definition.query in query and 'CAST("CHANGED" AS TIMESTAMP)' in query
    assert params == {'cutoff': DATE}
    query, params = lift_cursor.calls[-1]
    assert 'WHERE "changed" <= %s::timestamp' in query.as_string()
    assert params == (DATE,)
    assert len(INTEGRATIONS) == 12


def test_parcel_units_report_both_exact_and_rounded_boundaries(definition):
    from dataclasses import replace
    from datetime import datetime
    definition = replace(definition, table='ev_parc_enota_h_2025_danes',
                         cutoff='2026-10-26 22:59:59.999000')
    oracle_cursor = Cursor([(100, 90)])
    class ResultsCursor(Cursor):
        def fetchone(self):
            return self.rows.pop(0)
    lift_cursor = ResultsCursor([(100, 80), (92,)])
    result = count_table(definition, Database(oracle_cursor), Database(lift_cursor))
    assert result['eligible_difference'] == -10
    assert result['rounded_cutoff_gap'] == -2
    assert result['lift_rounded_cutoff'] == '2026-10-26 23:00:00.000000'
    assert lift_cursor.calls[-1][1] == (datetime(2026, 10, 26, 23),)
