"""Small shared start/stop log for runnable scripts."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


@contextmanager
def run_log(script):
    path = Path(__file__).with_name('full.sqlite')
    log = sqlite3.connect(path, timeout=10)
    log.execute('''CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY, script TEXT, started_at TEXT, stopped_at TEXT,
        status TEXT, last_phase TEXT, logging_restored INTEGER, error TEXT
    )''')
    now = lambda: datetime.now(timezone.utc).isoformat()
    run_id = log.execute('INSERT INTO runs(script,started_at,status) VALUES (?,?,?)',
                         (Path(script).name, now(), 'running')).lastrowid
    log.commit()
    state = {'phase': 'starting', 'logging_restored': None}
    status, error = 'completed', None
    try:
        yield state
    except KeyboardInterrupt:
        status = 'interrupted'
        print('\nInterrupted; cancelling current statement. Earlier committed changes remain.', flush=True)
        if 'unlogged' in Path(script).name:
            print('Table may still be UNLOGGED. Logging is not automatically restored.', flush=True)
        raise SystemExit(130) from None
    except BaseException as exc:
        status, error = 'failed', str(exc)
        raise
    finally:
        log.execute('''UPDATE runs SET stopped_at=?,status=?,last_phase=?,
                       logging_restored=?,error=? WHERE id=?''',
                    (now(), status, state['phase'], state['logging_restored'], error, run_id))
        log.commit()
        log.close()
