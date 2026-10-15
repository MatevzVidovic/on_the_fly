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
