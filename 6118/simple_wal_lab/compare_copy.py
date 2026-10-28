"""Read-only, full-content comparison of restored source and copied destination."""
import json
import time
from db import connect, sql, TABLE, SOURCE_DATE_COLUMN, ARGS, schema, table
from run_log import run_log

target_schema, target_name = schema, table + '_org2810'
if ARGS.copy_target:
    target_schema, target_name = (ARGS.copy_target.split('.', 1)
                                 if '.' in ARGS.copy_target else (schema, ARGS.copy_target))
TARGET = sql.Identifier(target_schema, target_name)
if TABLE.as_string() == TARGET.as_string():
    raise ValueError('Source and destination must differ')


def columns(db, relation):
    return {name: (kind, typename, formatted) for name, kind, typename, formatted in db.execute('''
        SELECT a.attname,a.atttypid,t.typname,format_type(a.atttypid,a.atttypmod)
        FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid
        WHERE a.attrelid=%s::regclass AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY a.attnum
    ''', (relation.as_string(),)).fetchall()}


with run_log(__file__) as run:
    run["phase"] = "comparing"
    started = time.perf_counter()
    with connect() as db:
        # Counts and comparisons all see one consistent snapshot. No PostgreSQL writes.
        db.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        try:
            db.execute("SET LOCAL statement_timeout='120s'")
            db.execute("SET LOCAL lock_timeout='5s'")
            source = columns(db, TABLE)
            target = columns(db, TARGET)
            if 'id' not in source or 'id' not in target or source['id'][0] != target['id'][0]:
                raise ValueError('Both tables need matching id columns')
            if source.get(ARGS.source_date_column, (None,))[0] != 1114 or target.get(ARGS.date_column, (None,))[0] != 1114:
                raise ValueError('Source date and target UTC must be timestamp without time zone')
            if (set(source) - {ARGS.date_column}) != (set(target) - {ARGS.date_column}):
                raise ValueError('Source and destination column sets differ beyond the UTC column')
            counts = {}
            for label, relation in [('source', TABLE), ('target', TARGET)]:
                total, unique, nonnull = db.execute(sql.SQL('SELECT count(*),count(DISTINCT id),count(id) FROM {table}')
                                                   .format(table=relation)).fetchone()
                counts[label + '_rows'] = total
                if total != unique or total != nonnull:
                    raise ValueError(f'{label}: duplicate or NULL IDs; cannot compare rows reliably')

            differences = []
            for name in target:
                left, right = sql.Identifier('s', name), sql.Identifier('t', name)
                if name == ARGS.date_column:
                    # Apply the target's actual timestamp precision, including timestamp(0).
                    left = sql.SQL("((s.{source_date} AT TIME ZONE 'Europe/Ljubljana') AT TIME ZONE 'UTC')::{kind}")
                    left = left.format(source_date=SOURCE_DATE_COLUMN, kind=sql.SQL(target[name][2]))
                else:
                    if source[name][0] != target[name][0]:
                        raise ValueError(f'Type mismatch for {name}')
                if target[name][1] == 'geometry':
                    # Exact EWKB includes coordinate values and SRID; no GeoJSON rounding.
                    left, right = (sql.SQL('ST_AsEWKB({})').format(value) for value in (left, right))
                else:
                    # Stable text comparison also supports json/xml without equality operators.
                    left, right = (sql.SQL('({})::text').format(value) for value in (left, right))
                differences.append((name, sql.SQL('{} IS DISTINCT FROM {}').format(left, right)))
            joined = sql.SQL('FROM {source} s FULL JOIN {target} t ON s.id=t.id').format(source=TABLE, target=TARGET)
            any_difference = sql.SQL(' OR ').join(test for name, test in differences)
            per_column = sql.SQL(', ').join(sql.SQL('{} AS {}').format(
                sql.SQL('count(*) FILTER (WHERE s.id IS NOT NULL AND t.id IS NOT NULL AND ({}))').format(test),
                sql.Identifier(name)) for name, test in differences)
            result = db.execute(sql.SQL('''
                SELECT count(*) FILTER (WHERE t.id IS NULL) AS missing_in_target,
                       count(*) FILTER (WHERE s.id IS NULL) AS extra_in_target,
                       count(*) FILTER (WHERE s.id IS NOT NULL AND t.id IS NOT NULL AND ({different})) AS mismatched_rows,
                       {per_column} {joined}
            ''').format(different=any_difference, per_column=per_column, joined=joined)).fetchone()
            missing, extra, mismatched = result[:3]
            column_mismatches = {name: count for (name, test), count in zip(differences, result[3:]) if count}
            passed = counts['source_rows'] == counts['target_rows'] and not (missing or extra or mismatched)
            report = dict(source=TABLE.as_string(), target=TARGET.as_string(), **counts,
                          compared_columns=len(differences), utc_expected_type=target[ARGS.date_column][2],
                          missing_in_target=missing, extra_in_target=extra,
                          mismatched_rows=mismatched, mismatches_by_column=column_mismatches, passed=passed)
            if not passed:
                changed_columns = sql.SQL(', ').join(sql.SQL('CASE WHEN ({}) THEN {} END').format(test, sql.Literal(name))
                                                     for name, test in differences)
                examples = db.execute(sql.SQL('''
                    SELECT COALESCE(s.id,t.id)::text,
                           CASE WHEN s.id IS NULL THEN 'extra_in_target'
                                WHEN t.id IS NULL THEN 'missing_in_target' ELSE 'different_values' END,
                           array_remove(ARRAY[{columns}],NULL)
                    {joined}
                    WHERE s.id IS NULL OR t.id IS NULL OR ({different}) LIMIT 10
                ''').format(columns=changed_columns, joined=joined, different=any_difference)).fetchall()
                report['examples'] = [dict(id=i, issue=issue, columns=cols) for i, issue, cols in examples]
            report['seconds'] = round(time.perf_counter() - started, 2)
            print(json.dumps(report, indent=2))
        finally:
            db.execute('ROLLBACK')
    run["phase"] = "passed" if passed else "mismatches"
raise SystemExit(0 if passed else 1)
