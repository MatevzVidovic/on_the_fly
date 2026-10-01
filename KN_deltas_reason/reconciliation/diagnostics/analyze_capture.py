"""Readonly, repeatable symptom and cohort analysis of an existing capture."""
import argparse
import json
from pathlib import Path
import sqlite3

p = argparse.ArgumentParser()
p.add_argument('capture', type=Path)
p.add_argument('--assert-clean', action='store_true')
a = p.parse_args()
db = sqlite3.connect(a.capture.resolve().as_uri() + '?mode=ro', uri=True)
if db.execute('SELECT status FROM capture').fetchall() != [('COMPLETE',)]:
    raise ValueError('Expected exactly one COMPLETE capture')
db.executescript('''
CREATE TEMP TABLE comparison AS
SELECT s.business_key,s.native_changed_at source_date,t.native_changed_at target_date,
       t.uuid,t.created_at,t.updated_at,
       CASE WHEN t.uuid IS NULL THEN 'MISSING' WHEN s.changed_at=t.changed_at THEN 'EQUAL'
            WHEN s.changed_at>t.changed_at THEN 'STALE' ELSE 'AHEAD_OR_NULL' END category
FROM source_rows s LEFT JOIN target_rows t USING(business_key);
''')
queries = {
 'categories': 'SELECT category,count(*) n FROM comparison GROUP BY category',
 'source_duplicate_keys': 'SELECT count(*) n FROM (SELECT business_key FROM source_rows GROUP BY business_key HAVING count(*)>1)',
 'target_duplicate_keys': 'SELECT count(*) n FROM (SELECT business_key FROM target_rows GROUP BY business_key HAVING count(*)>1)',
 'target_only': 'SELECT count(*) n FROM target_rows t LEFT JOIN source_rows s USING(business_key) WHERE s.business_key IS NULL',
 'gap_days': "SELECT substr(source_date,1,10) day,count(*) n,sum(category='MISSING') missing,min(source_date) first,max(source_date) last FROM comparison WHERE category!='EQUAL' GROUP BY day",
 'gap_source_target_months': "SELECT substr(source_date,1,7) source_month,substr(target_date,1,7) target_month,count(*) n FROM comparison WHERE category!='EQUAL' GROUP BY 1,2 ORDER BY 1,2",
 'gap_audit': "SELECT updated_at,count(*) n FROM comparison WHERE category='STALE' GROUP BY updated_at ORDER BY n DESC",
 'audit_cohorts': "SELECT updated_at,count(*) n,sum(category='STALE') stale,min(source_date),max(source_date) FROM comparison WHERE uuid IS NOT NULL GROUP BY updated_at ORDER BY n DESC LIMIT 20",
 'tie_cohorts': "SELECT source_date,count(*) total,sum(category='EQUAL') equal,sum(category='MISSING') missing,sum(category='STALE') stale FROM comparison GROUP BY source_date HAVING sum(category!='EQUAL')>0 ORDER BY source_date",
 'boundary_days': "SELECT source_date,count(*) total,sum(category='EQUAL') equal,sum(category='MISSING') missing,sum(category='STALE') stale FROM comparison WHERE substr(source_date,1,10) IN ('2026-05-25','2026-08-05') GROUP BY source_date ORDER BY source_date",
 'gap_samples': "SELECT * FROM comparison WHERE category!='EQUAL' ORDER BY source_date,business_key LIMIT 12",
}
result = {'capture': str(a.capture)}
for name, sql in queries.items():
    if a.assert_clean and name not in ('categories', 'target_only', 'source_duplicate_keys', 'target_duplicate_keys'):
        continue
    cur = db.execute(sql)
    result[name] = [dict(zip([c[0] for c in cur.description], row)) for row in cur]
if a.assert_clean:
    print(json.dumps({name: result[name] for name in ('categories', 'target_only', 'source_duplicate_keys', 'target_duplicate_keys')}, indent=2))
else:
    print(json.dumps(result, indent=2))
if a.assert_clean and (any(r['category'] != 'EQUAL' and r['n'] for r in result['categories'])
                       or result['target_only'][0]['n']
                       or result['source_duplicate_keys'][0]['n']
                       or result['target_duplicate_keys'][0]['n']):
    raise SystemExit(1)
