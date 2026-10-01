"""Offline summaries of probe_staging.py output; no database credentials needed."""
import collections
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

artifact = json.loads(Path(sys.argv[1]).read_text())
here = Path(__file__).resolve().parent.parent
db = sqlite3.connect((here/'captures/staging/20261001T134900129421Z/capture.sqlite3').as_uri()+'?mode=ro',uri=True)
db.execute('ATTACH DATABASE ? AS prod',((here/'captures/20261001T133732435890Z/capture.sqlite3').as_uri()+'?mode=ro',))
summary = {}
for name,sql in {
 'shared_stale': 'SELECT count(*),sum(p.changed_at=t.changed_at) FROM source_rows s JOIN target_rows t USING(business_key) LEFT JOIN prod.target_rows p ON p.business_key=s.business_key WHERE s.changed_at>t.changed_at',
 'shared_missing': 'SELECT count(*),sum(p.business_key IS NULL) FROM source_rows s LEFT JOIN target_rows t USING(business_key) LEFT JOIN prod.target_rows p ON p.business_key=s.business_key WHERE t.business_key IS NULL',
 'source_dates_changed_between_captures': 'SELECT count(*) FROM source_rows s JOIN prod.source_rows p USING(business_key) WHERE s.changed_at<>p.changed_at',
 'staging_source_keys_absent_from_production_capture': 'SELECT count(*) FROM source_rows s LEFT JOIN prod.source_rows p USING(business_key) WHERE p.business_key IS NULL',
}.items():
    summary[name] = db.execute(sql).fetchone()
source = dict(db.execute('SELECT s.business_key,s.native_changed_at FROM source_rows s JOIN target_rows t USING(business_key) WHERE s.changed_at>t.changed_at'))
peers = collections.defaultdict(list)
for row in artifact['entity_peers']:
    peers[row[1]].append(row)
rows = artifact['stale_samples']
summary['stale_closure_patterns'] = {
 'rows': len(rows), 'open_2100': sum(r[4].startswith('2100') for r in rows),
 'closing_procedure_present': sum(r[6] is not None for r in rows),
 'sibling_opening_procedure_matches_closing_procedure': sum(r[6] is not None and any(s[0]!=r[0] and s[5]==r[6] for s in peers[r[1]]) for r in rows),
 'sibling_valid_from_equals_source_change': sum(any(s[0]!=r[0] and s[3]==source[str(r[0])].replace('T',' ').split('.')[0] for s in peers[r[1]]) for r in rows),
}
summary['other_tables'] = {}
for table, data in artifact['other_tables'].items():
    targets = collections.defaultdict(list)
    for key,date,uuid,audit in data['targets']:
        targets[key].append((date,uuid,audit))
    counts=collections.Counter(); days=collections.Counter(); audits=collections.Counter()
    for key,date in data['source'].items():
        source_date=datetime.fromisoformat(date.replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Ljubljana')).replace(tzinfo=None)
        target=targets[key]
        category=('MISSING' if not target else 'DUPLICATE' if len(target)>1 else 'NULL' if target[0][0] is None else
                  'EQUAL' if datetime.fromisoformat(target[0][0])==source_date else
                  'STALE' if datetime.fromisoformat(target[0][0])<source_date else 'AHEAD')
        counts[category]+=1
        if category!='EQUAL':
            days[(category,str(source_date.date()))]+=1
            if target:
                audits[(category,target[0][2])]+=1
    summary['other_tables'][table]={'observation':data['observation'],'counts':dict(counts),
        'gap_days':[{'category':c,'day':d,'n':n} for (c,d),n in sorted(days.items())],
        'gap_audit':[{'category':c,'audit':d,'n':n} for (c,d),n in audits.most_common(10)]}
print(json.dumps(summary,indent=2))
