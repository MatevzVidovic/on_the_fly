"""UUID bisection: assumes filled eligible rows precede all unfinished rows."""
from uuid import UUID
from db import sql, TABLE


def find_start_id(db):
    first = db.execute(sql.SQL('SELECT id FROM {table} ORDER BY id LIMIT 1')
                       .format(table=TABLE)).fetchone()
    if first is None:
        return None
    last = db.execute(sql.SQL('SELECT id FROM {table} ORDER BY id DESC LIMIT 1')
                      .format(table=TABLE)).fetchone()
    if not isinstance(first[0], UUID):
        raise ValueError('Starting-point bisection requires a UUID id column')
    low, high = first[0].int, last[0].int
    candidate = None
    while low <= high:
        middle = (low + high) // 2
        row = db.execute(sql.SQL('''
            SELECT id, date_change_utc FROM {table}
            WHERE id >= %s AND date_change IS NOT NULL
            ORDER BY id LIMIT 1
        ''').format(table=TABLE), (UUID(int=middle),)).fetchone()
        if row is None:
            high = middle - 1
        elif row[1] is not None:
            low = row[0].int + 1
        else:
            candidate = row[0]
            high = middle - 1
    return candidate
