"""Elapsed phase timings shared by normal runs and read-only benchmarks."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

LOG_PATH = Path(__file__).with_name('benchmarks') / 'timings.jsonl'


@contextmanager
def measure(stage, **details):
    record = dict(at=datetime.now(timezone.utc).isoformat(), stage=stage, **details)
    started = perf_counter()
    record['status'] = 'complete'
    try:
        yield record
    except BaseException:
        record['status'] = 'failed'
        raise
    finally:
        record['seconds'] = round(perf_counter() - started, 6)
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        print(f"Timing {stage}: {record['seconds']:.3f}s ({record['status']})", flush=True)
