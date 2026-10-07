"""Compare saved October 1/7 Oracle key/date snapshots. No remote connections."""
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'backdated_test_attempt/observations_ea4f75d1c93f.sqlite3'
NEW = ROOT / 'reconciliation/captures/staging_batch/20261007'
WINDOW = '2026-06-30T22:00:00.000000Z'  # July 1 midnight in Ljubljana.
original = json.loads((ROOT / 'backdated_test_attempt/exploration/artifacts/20260923T084030Z/integrations.json').read_text())
original = {row['target_table']: row for row in original}
results = []

with closing(sqlite3.connect(OLD.resolve().as_uri() + '?mode=ro', uri=True)) as old:
    definition = json.loads(old.execute('SELECT manifest FROM experiment').fetchone()[0])
    assert definition['config']['window_start'] == '2026-07-01 00:00:00'
    for path in sorted(NEW.glob('ev_*/capture.sqlite3')):
        table = path.parent.name
        observation = old.execute("""SELECT id,started_at,completed_at,row_count,max_changed_at
            FROM observations WHERE dataset=? AND status='COMPLETE'
            AND mode='INTEGRATION_LIKE' ORDER BY id DESC LIMIT 1""", (table,)).fetchone()
        if observation is None:
            print(json.dumps(dict(table=table, status='NO_OCTOBER_1_BASELINE')), flush=True)
            continue
        oid, started, completed, count, maximum = observation
        assert started.startswith('2026-10-01')
        # Both captures contain the same key/date expressions and membership predicates.
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            status, raw = db.execute('SELECT status,metadata_json FROM capture').fetchone()
            info = json.loads(raw)
            assert status == 'COMPLETE'
            normalize = lambda s: re.sub(r'\s+', '', s).replace('"', '').lower().rstrip(';')
            assert normalize(original[table]['integration_sql']) == normalize(info['before']['url'])
            # October 1 used nine fractional digits; October 7 used six.
            # Fail rather than hide genuinely higher precision in the old observation.
            assert old.execute("SELECT count(*) FROM records WHERE observation_id=? AND substr(changed_at,27,3)<>'000'", (oid,)).fetchone()[0] == 0
            boundary = maximum[:26] + 'Z' if maximum else None
            observed_before = started[:26] + 'Z'
            db.execute('ATTACH DATABASE ? AS previous', (OLD.resolve().as_uri() + '?mode=ro',))
            row = db.execute('''SELECT count(*),
                sum(b.matching_key IS NULL),
                sum(b.matching_key IS NULL AND n.changed_at < ?),
                sum(b.matching_key IS NULL AND n.changed_at = ?),
                sum(b.matching_key IS NULL AND n.changed_at < ?)
                FROM source_rows n LEFT JOIN previous.records b
                ON b.observation_id=? AND b.matching_key=n.business_key
                WHERE n.changed_at >= ?''', (boundary, boundary, observed_before, oid, WINDOW)).fetchone()
            changes = db.execute('''SELECT
                sum(n.changed_at < substr(b.changed_at,1,26)||'Z'),
                sum(n.changed_at > substr(b.changed_at,1,26)||'Z'),
                sum(n.changed_at = substr(b.changed_at,1,26)||'Z'),
                sum(n.business_key IS NULL),
                sum(n.changed_at < ?),
                sum(n.changed_at > substr(b.changed_at,1,26)||'Z' AND n.changed_at <= ?),
                sum(n.changed_at > substr(b.changed_at,1,26)||'Z' AND n.changed_at < ?)
                FROM previous.records b LEFT JOIN source_rows n
                ON n.business_key=b.matching_key WHERE b.observation_id=?''', (WINDOW, boundary, observed_before, oid)).fetchone()
            candidates = db.execute('''SELECT n.business_key,n.changed_at,b.changed_at
                FROM source_rows n LEFT JOIN previous.records b
                ON b.observation_id=? AND b.matching_key=n.business_key
                WHERE n.changed_at>=? AND
                ((b.matching_key IS NULL AND n.changed_at<=?) OR
                 n.changed_at < substr(b.changed_at,1,26)||'Z') LIMIT 10''', (oid, WINDOW, boundary)).fetchall()
            result = dict(table=table, status='COMPARED', old_observation=oid,
                old_started=started, old_completed=completed,
                new_started=info['intervals']['source_start'], new_completed=info['intervals']['source_end'],
                old_rows=count, new_window_rows=row[0], old_maximum_utc=boundary,
                new_keys=row[1] or 0, new_keys_before_old_max=row[2] or 0,
                new_keys_equal_old_max=row[3] or 0, new_keys_before_old_observation=row[4] or 0,
                backward_dates=changes[0] or 0, forward_dates=changes[1] or 0,
                unchanged_dates=changes[2] or 0, absent_from_full_source=changes[3] or 0,
                moved_below_window=changes[4] or 0,
                forward_dates_at_or_before_old_max=changes[5] or 0,
                forward_dates_before_old_observation=changes[6] or 0,
                candidate_examples=candidates)
            assert result['new_window_rows'] == result['old_rows'] + result['new_keys'] - result['absent_from_full_source'] - result['moved_below_window']
            assert sum(result[k] for k in ('backward_dates','forward_dates','unchanged_dates','absent_from_full_source')) == count
            results.append(result)
            print(json.dumps(result), flush=True)

output = ROOT / 'reconciliation/diagnostics/artifacts/ev_source_dates_20261001_20261007.json'
output.write_text(json.dumps(results, indent=2) + '\n')
print('Saved', output, flush=True)
